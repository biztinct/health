# -*- coding: utf-8 -*-
"""Patient "My Care" portal — per-patient standing access token.

Distinct from the per-VISIT tokens (health_family_link/self_booking/telehealth):
this is one standing token per patient granting access to THEIR OWN care record
via /my/care/<token>. The token (delivered to the patient's phone) is the
authentication. Security model in docs/strategy/handovers/patient-portal-phase.md
§0.1 — 256-bit token (unique index in init(), §5.1), revoke/rotate, render-time
expiry, dual rate-limit at the controller, append-only access log, every read
sudo but scoped to this one patient_id.
"""
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Vietnam is UTC+7 with no DST — naive-UTC datetimes shift by a fixed offset for
# wall-clock display (matches the family-link page convention).
_VN_OFFSET = timedelta(hours=7)

_UPCOMING_STATES = ('confirmed', 'assigned', 'in_progress')
_HISTORY_STATES = ('completed', 'completed_pending_invoice', 'closed')


class HealthPortalAccess(models.Model):
    _name = 'health.portal.access'
    _inherit = ['mail.thread']
    _description = 'Patient My Care Portal Access'
    _rec_name = 'patient_id'
    _order = 'id desc'

    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, index=True,
        ondelete='cascade', domain=[('is_patient', '=', True)], tracking=True)
    token = fields.Char(
        required=True, index=True, copy=False,
        default=lambda self: secrets.token_urlsafe(32),
        groups='health_base.group_healthcare_operations_manager',
        help='Capability token — the /my/care URL is a capability URL. '
             'Never logged; visible to ops only.')
    state = fields.Selection([
        ('active', 'Active'),
        ('revoked', 'Revoked'),
    ], default='active', required=True, index=True, tracking=True)
    expires_at = fields.Datetime(
        string='Expires At',
        help='Optional. Empty = standing link. Checked at render time.')
    last_access_datetime = fields.Datetime(string='Last Access', readonly=True)
    access_count = fields.Integer(string='Access Count', readonly=True, default=0)
    portal_url = fields.Char(string='My Care URL', compute='_compute_portal_url')

    def init(self):
        # §5.1 — materialize the uniqueness contracts (Odoo 19 does not).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_portal_access_token_uidx
            ON health_portal_access (token)
        """)
        # One standing access per patient (rotate replaces the token in place).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_portal_access_patient_uidx
            ON health_portal_access (patient_id)
        """)

    def _compute_portal_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url') or ''
        for access in self:
            access.portal_url = (
                '%s/my/care/%s' % (base, access.token) if access.token else '')

    # -- lifecycle -----------------------------------------------------------
    @api.model
    def get_or_create_for(self, patient):
        """One standing access per patient; reactivate a revoked one."""
        access = self.sudo().search(
            [('patient_id', '=', patient.id)], limit=1)
        if not access:
            access = self.sudo().create({'patient_id': patient.id})
        elif access.state == 'revoked':
            access.state = 'active'
        return access

    def action_rotate_token(self):
        for access in self:
            access.token = secrets.token_urlsafe(32)
            access.message_post(body=_('My Care token rotated — the previous '
                                       'link no longer works.'))
        return True

    def action_revoke(self):
        self.write({'state': 'revoked'})
        return True

    def action_reactivate(self):
        self.write({'state': 'active'})
        return True

    def _is_expired(self):
        self.ensure_one()
        return bool(self.expires_at and fields.Datetime.now() > self.expires_at)

    # -- access recording ----------------------------------------------------
    def _record_access(self, section, ip):
        """Append an audit row + bump counters. Sudo (public controller)."""
        self.ensure_one()
        self.env['health.portal.access.log'].sudo().create({
            'access_id': self.id,
            'patient_id': self.patient_id.id,
            'section': section,
            'ip': (ip or '')[:64],
        })
        self.sudo().write({
            'last_access_datetime': fields.Datetime.now(),
            'access_count': self.access_count + 1,
        })

    # -- render context (sudo, scoped to THIS patient) -----------------------
    def _hub_context(self):
        self.ensure_one()
        patient = self.patient_id
        return {
            'patient_name': patient.name or '',
            'patient_code': patient.patient_code or '',
            'token': self.token,
            'upcoming': self._visits(upcoming=True),
            'history': self._visits(upcoming=False),
        }

    def _visits(self, upcoming):
        self.ensure_one()
        Order = self.env['health.fieldservice.order'].sudo()
        if upcoming:
            floor = fields.Datetime.now() - timedelta(hours=12)
            domain = [
                ('patient_id', '=', self.patient_id.id),
                ('state', 'in', _UPCOMING_STATES),
                ('scheduled_datetime', '>=', fields.Datetime.to_string(floor)),
            ]
            order = 'scheduled_datetime asc'
        else:
            domain = [
                ('patient_id', '=', self.patient_id.id),
                ('state', 'in', _HISTORY_STATES),
            ]
            order = 'scheduled_datetime desc'
        return [self._visit_row(o)
                for o in Order.search(domain, order=order, limit=50)]

    def _visit_row(self, order):
        # Given-name-only for staff privacy (VN given name = last token); NO
        # clinical PHI on the visits list (that's the records section, 4B).
        staff = order.lead_staff_id
        given = (staff.name or '').split()[-1] if staff and staff.name else ''
        when = order.scheduled_datetime
        return {
            'ref': order.name or '',
            'service': dict(order._fields['service_type']._description_selection(
                self.env)).get(order.service_type, order.service_type or ''),
            'when': (when + _VN_OFFSET).strftime('%d/%m/%Y %H:%M') if when else '',
            'staff': given,
            'facility_phone': (order.facility_id.phone or '') if order.facility_id else '',
            'state': order.state,
            'state_label': dict(order._fields['state']._description_selection(
                self.env)).get(order.state, order.state or ''),
        }


class HealthPortalAccessLog(models.Model):
    _name = 'health.portal.access.log'
    _description = 'My Care Portal Access Log'
    _order = 'id desc'
    _log_access = False

    access_id = fields.Many2one(
        'health.portal.access', string='Access', index=True, ondelete='cascade')
    patient_id = fields.Many2one('res.partner', string='Patient', index=True)
    section = fields.Char(string='Section')
    ip = fields.Char(string='IP Address')
    ts = fields.Datetime(string='Timestamp', default=fields.Datetime.now,
                         index=True)

    def write(self, vals):
        raise UserError(_('Portal access log entries are append-only.'))

    def unlink(self):
        raise UserError(_('Portal access log entries cannot be deleted.'))
