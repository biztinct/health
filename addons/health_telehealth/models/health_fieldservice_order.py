import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# FSO states in which an assigned staff member may fetch the room URL from the
# PWA/backend (a session only exists from confirm onward; draft has none).
_JOINABLE_STATES = ('confirmed', 'assigned', 'in_progress')


class HealthFieldserviceOrder(models.Model):
    """Telehealth lifecycle wiring on the FSO.

    Every hook is post-super + try/except wrapped: a telehealth failure must
    NEVER block booking confirm / start / complete / cancel (family-link
    precedent). Online visits only — home/clinic visits get nothing.
    """
    _inherit = 'health.fieldservice.order'

    telehealth_session_id = fields.Many2one(
        'health.telehealth.session', string='Telehealth Session',
        compute='_compute_telehealth_session_id')
    telehealth_session_state = fields.Selection(
        related='telehealth_session_id.state', string='Video Session State')

    def _compute_telehealth_session_id(self):
        Session = self.env['health.telehealth.session'].sudo()
        for order in self:
            order.telehealth_session_id = (
                Session.search([('fso_id', '=', order.id)], limit=1)
                if order.id else False)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def _telehealth_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'health_telehealth.enabled', 'True') in ('True', 'true', '1')

    # ------------------------------------------------------------------
    # Lifecycle hooks (post-super, try/except — never block the workflow)
    # ------------------------------------------------------------------
    def action_confirm_booking(self):
        result = super().action_confirm_booking()
        try:
            self._telehealth_on_confirm()
        except Exception as exc:  # noqa: BLE001 — never block confirmation
            _logger.error(
                'Telehealth confirm hook failed (non-blocking): %s', exc)
        return result

    def action_start_service(self):
        result = super().action_start_service()
        try:
            self._telehealth_sync_state('open')
        except Exception as exc:  # noqa: BLE001
            _logger.error(
                'Telehealth start hook failed (non-blocking): %s', exc)
        return result

    def action_complete_service(self):
        result = super().action_complete_service()
        try:
            self._telehealth_sync_state('closed')
        except Exception as exc:  # noqa: BLE001
            _logger.error(
                'Telehealth complete hook failed (non-blocking): %s', exc)
        return result

    def write(self, vals):
        result = super().write(vals)
        # Cancellation seam (report point c): cancel_with_reason and any
        # stage-driven cancel both land as state='cancelled' on the FSO write
        # (write() syncs stage.state -> vals['state']), so this one hook
        # catches every cancellation path with no coupling to the wizard.
        if vals.get('state') == 'cancelled':
            try:
                self._telehealth_sync_state('cancelled')
            except Exception as exc:  # noqa: BLE001
                _logger.error(
                    'Telehealth cancel hook failed (non-blocking): %s', exc)
        return result

    def _telehealth_on_confirm(self):
        Session = self.env['health.telehealth.session']
        for order in self:
            if order.service_location != 'online':
                continue
            if not order._telehealth_enabled():
                continue
            session = Session._get_or_create(order)
            # Consent is log-only (never blocks confirmation) — 'service'
            # covers the consult itself; no recording in v1.
            self.env['health.consent'].check_consent(order.patient_id, 'service')
            session._send_join_zns()

    def _telehealth_sync_state(self, target):
        Session = self.env['health.telehealth.session'].sudo()
        for order in self:
            session = Session.search([('fso_id', '=', order.id)], limit=1)
            if not session:
                continue
            if target == 'open':
                session.open_session()
            elif target == 'closed':
                session.close_session()
            elif target == 'cancelled':
                session.cancel_session()

    # ------------------------------------------------------------------
    # Join URL — the single access-checked accessor (PWA + backend share it)
    # ------------------------------------------------------------------
    def _tele_join_url(self):
        """Room URL for an assigned staff member on a joinable online visit,
        else ''. Access: the caller must be an assigned staff member OR a
        manager/owner; the session must exist and the FSO be in a joinable
        state. Managers/owners use the backend button; nurses the PWA.

        FSO/session data is read via sudo() while the access DECISION is made
        against the REAL user (captured before sudo). This deliberately
        bypasses the FSO catchment record rule (ledger §5 #4: the nurse rule
        keys on user.catchment_province_id, so an assigned nurse without a
        catchment cannot even read their own FSO) — identity here is the staff
        ASSIGNMENT, not read access, and nothing is leaked because the URL is
        returned only to the actually-assigned staff or a manager/owner."""
        self.ensure_one()
        user = self.env.user
        fso = self.sudo()
        session = fso.telehealth_session_id
        if not session or fso.state not in _JOINABLE_STATES:
            return ''
        employee = user.employee_id
        assigned = bool(
            employee and employee.id in fso.assignment_ids.mapped('staff_id').ids)
        privileged = (user.has_group('health_base.group_healthcare_manager')
                      or user.has_group('health_base.group_healthcare_owner'))
        if not (assigned or privileged):
            return ''
        return session.room_url

    def action_tele_join(self):
        """Backend "Join Video" button — opens the room in a new tab."""
        self.ensure_one()
        url = self._tele_join_url()
        if not url:
            raise UserError(_(
                'The video room is not available yet. It opens when the visit '
                'is confirmed and you are assigned to it.'))
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}
