import logging
import secrets
from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_DEFAULT_TZ = 'Asia/Ho_Chi_Minh'
_DEFAULT_VIDEO_BASE = 'https://meet.jit.si'
# purpose -> ir.config_parameter holding the ZNS template id. Empty default =>
# that send is silently NOT created (family-link A1 no-phantom rule), so
# vietuat installs clean.
_TEMPLATE_PARAM = {
    'telehealth_join': 'health_telehealth.zns_template_join',
}


def _safe_phone(phone):
    """normalize_vn_phone raises on invalid; we want falsy-on-invalid
    (conventions ledger §5.15)."""
    from odoo.addons.health_base.models.phone_utils import normalize_vn_phone
    try:
        return normalize_vn_phone(phone) or ''
    except ValidationError:
        return ''


class HealthTelehealthSession(models.Model):
    """One video session per online FSO.

    Created at booking confirm (state pending), opened at service start
    (state open — the only state that reveals the room URL), closed at
    completion, cancelled with the visit. Search-first get-or-create keeps
    it idempotent (one session per FSO). No expiry cron — expiry is a
    render-time check (family-link precedent).
    """
    _name = 'health.telehealth.session'
    _description = 'Telehealth Video Session'
    _order = 'create_date desc'
    _rec_name = 'room_slug'

    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Visit', required=True,
        index=True, ondelete='cascade')
    room_slug = fields.Char(
        required=True, copy=False, readonly=True,
        help='Unguessable room path segment (the v1 access control). '
             'Generated once at session creation.')
    patient_token = fields.Char(
        required=True, index=True, copy=False, readonly=True,
        default=lambda self: secrets.token_urlsafe(24),
        help='Capability token for the waiting-room page URL. Never logged '
             'at info level.')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='pending', required=True, index=True)
    opened_at = fields.Datetime(readonly=True, copy=False)
    closed_at = fields.Datetime(readonly=True, copy=False)
    expires_at = fields.Datetime(
        help='scheduled end + 24h; checked at render time (no cron).')
    room_url = fields.Char(
        compute='_compute_room_url',
        help='Capability URL = <video_base_url>/<room_slug>. Not stored; '
             'never logged at info level.')
    outbound_message_id = fields.Many2one(
        'health.outbound.message', string='Join Message',
        readonly=True, copy=False, ondelete='set null')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True,
        index=True, help='Catchment area used for access control.')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    def init(self):
        # Conventions ledger §5.1 — _sql_constraints are not materialized in
        # Odoo 19; back the token + one-session-per-FSO contracts with real
        # unique indexes.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_telehealth_session_token_uidx
            ON health_telehealth_session (patient_token)
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_telehealth_session_fso_uidx
            ON health_telehealth_session (fso_id)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('room_slug')
    def _compute_room_url(self):
        base = self._video_base_url()
        for session in self:
            session.room_url = (
                '%s/%s' % (base, session.room_slug) if session.room_slug else '')

    @api.depends('fso_id.patient_id')
    def _compute_catchment_province_id(self):
        for session in self:
            patient = session.fso_id.patient_id
            session.catchment_province_id = (
                patient._get_health_catchment_province() if patient else False)

    # ------------------------------------------------------------------
    # Config / URL / timezone helpers
    # ------------------------------------------------------------------
    @api.model
    def _video_base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'health_telehealth.video_base_url', _DEFAULT_VIDEO_BASE).rstrip('/')

    def _base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', 'http://localhost:8069').rstrip('/')

    def _page_url(self):
        """The WAITING-ROOM page URL (never the room URL) — this is what the
        patient receives."""
        self.ensure_one()
        return '%s/tele/visit/%s' % (self._base_url(), self.patient_token)

    def _fso_tz(self):
        self.ensure_one()
        try:
            return pytz.timezone(self.fso_id.booking_timezone or _DEFAULT_TZ)
        except pytz.UnknownTimeZoneError:
            return pytz.timezone(_DEFAULT_TZ)

    def _wall(self, dt):
        """Naive-UTC datetime -> wall-clock in the FSO booking timezone
        (the +7h class of bug is the most-hit mistake in this codebase)."""
        if not dt:
            return None
        return pytz.utc.localize(dt).astimezone(self._fso_tz())

    def _staff_given_name(self):
        """Doctor first, else lead staff; given name only (Vietnamese given
        name is the last token — mirrors the family page's split(' ')[-1])."""
        self.ensure_one()
        fso = self.fso_id
        staff = fso.primary_doctor_id or fso.lead_staff_id
        if not staff or not staff.name:
            return ''
        return staff.name.split(' ')[-1]

    # ------------------------------------------------------------------
    # Expiry + get-or-create (idempotent)
    # ------------------------------------------------------------------
    @api.model
    def _session_expiry(self, fso):
        """scheduled end + 24h (family-link _link_expiry math)."""
        if not fso.scheduled_datetime:
            return False
        minutes = fso.scheduled_duration or 120
        return (fso.scheduled_datetime + timedelta(minutes=minutes)
                + timedelta(hours=24))

    def _is_expired(self):
        self.ensure_one()
        return bool(self.expires_at and self.expires_at < fields.Datetime.now())

    @api.model
    def _get_or_create(self, fso):
        """Search-first get-or-create. On create, also stamps the FSO's
        existing online_meeting_url + online_platform so every backend view
        shows the link — that is the ONLY FSO write this model makes."""
        fso.ensure_one()
        session = self.sudo().search([('fso_id', '=', fso.id)], limit=1)
        if session:
            return session
        session = self.sudo().create({
            'fso_id': fso.id,
            'room_slug': 'vu-%s-%s' % (fso.id, secrets.token_urlsafe(12)),
            'expires_at': self._session_expiry(fso),
        })
        # The capability URL lands on the shipped FSO fields (platform custom).
        fso.sudo().write({
            'online_meeting_url': session.room_url,
            'online_platform': 'custom',
        })
        return session

    # ------------------------------------------------------------------
    # Lifecycle transitions (called from the FSO hooks, all sudo-safe)
    # ------------------------------------------------------------------
    def open_session(self):
        for session in self:
            if session.state in ('closed', 'cancelled'):
                continue
            vals = {'state': 'open'}
            if not session.opened_at:
                vals['opened_at'] = fields.Datetime.now()
            session.sudo().write(vals)

    def close_session(self):
        for session in self:
            if session.state == 'cancelled':
                continue
            session.sudo().write({
                'state': 'closed',
                'closed_at': fields.Datetime.now(),
            })

    def cancel_session(self):
        for session in self:
            if session.state == 'closed':
                continue
            session.sudo().write({
                'state': 'cancelled',
                'closed_at': fields.Datetime.now(),
            })

    # ------------------------------------------------------------------
    # Waiting-room render data — driven by session + FSO state
    # ------------------------------------------------------------------
    def _page_context(self):
        """Server-side render data. modes: pending / open / closed / neutral.

        The room URL appears ONLY in the 'open' mode (the URL-gating is the
        page's whole security story). Cancelled / expired render neutral
        upstream in the controller.
        """
        self.ensure_one()
        fso = self.fso_id
        base = {
            'patient_name': fso.patient_id.name or '',
            'staff_name': self._staff_given_name(),
            'facility_phone': fso.facility_id.phone or '',
        }
        state = self.state
        if state == 'open':
            base.update({
                'mode': 'open',
                'room_url': self.room_url,
            })
            return base
        if state == 'closed':
            base.update({'mode': 'closed'})
            return base
        if state == 'pending':
            start = self._wall(fso.scheduled_datetime)
            end = self._wall(fso.estimated_end_datetime)
            base.update({
                'mode': 'pending',
                'visit_date': start.strftime('%d/%m/%Y') if start else '',
                'time_window': ('%s - %s' % (
                    start.strftime('%H:%M'), end.strftime('%H:%M'))
                    if start and end else (
                        start.strftime('%H:%M') if start else '')),
            })
            return base
        return {'mode': 'neutral'}

    # ------------------------------------------------------------------
    # Sending (ZNS through the shipped messaging safety rails)
    # ------------------------------------------------------------------
    def _zns_params(self):
        """{patient_name, visit_date (wall-clock), staff_name, link}. link =
        the WAITING-ROOM page URL, never the room URL."""
        self.ensure_one()
        start = self._wall(self.fso_id.scheduled_datetime)
        return {
            'patient_name': self.fso_id.patient_id.name or '',
            'visit_date': start.strftime('%d/%m/%Y') if start else '',
            'staff_name': self._staff_given_name(),
            'link': self._page_url(),
        }

    def _send_join_zns(self):
        """Log + send one telehealth-join ZNS honoring health_messaging's
        rails (family-link ``_send_zns`` verbatim-adapted).

        Respects health_messaging.enabled / dry_run exactly (dry_run ->
        simulated, no real send). No template configured => the row is
        silently NOT created. Search-first on the dedup key makes double
        confirm a no-op.
        """
        self.ensure_one()
        purpose = 'telehealth_join'
        ICP = self.env['ir.config_parameter'].sudo()
        template_id = ICP.get_param(_TEMPLATE_PARAM[purpose], '')
        if not template_id:
            return self.env['health.outbound.message']
        dedup_key = 'telejoin-%s' % self.id
        Message = self.env['health.outbound.message'].sudo()
        existing = Message.search([('dedup_key', '=', dedup_key)], limit=1)
        if existing:
            self._store_message(existing)
            return existing

        enabled = ICP.get_param('health_messaging.enabled', 'False') in (
            'True', 'true', '1')
        dry_run = ICP.get_param('health_messaging.dry_run', 'True') in (
            'True', 'true', '1')
        patient = self.fso_id.patient_id
        phone = _safe_phone(patient.mobile or patient.phone)
        params = self._zns_params()
        msg = Message.create({
            'purpose': purpose,
            'channel': 'zns',
            'partner_id': patient.id,
            'fso_id': self.fso_id.id,
            'phone': phone,
            'dedup_key': dedup_key,
            'payload_json': params,
            'state': 'queued',
        })
        self._store_message(msg)

        if not phone:
            msg.write({'state': 'skipped',
                       'error_text': _('No usable phone for the patient.')})
            return msg
        if not enabled:
            msg.state = 'skipped'
            return msg
        if dry_run:
            msg.write({'state': 'simulated', 'sent_at': fields.Datetime.now()})
            return msg

        try:
            from odoo.addons.health_zalo.services.zalo_api import get_api_client
            config = self.env['zalo.config'].search([('active', '=', True)], limit=1)
            result = get_api_client(self.env).send_zns_notification(
                config, phone, template_id, params)
            if isinstance(result, dict) and result.get('error') \
                    and result.get('error') != 0:
                msg.write({'state': 'failed',
                           'error_text': 'ZNS error: %s' % (
                               result.get('message') or result.get('error'))})
            else:
                msg.write({'state': 'sent', 'sent_at': fields.Datetime.now()})
        except Exception as exc:  # noqa: BLE001 — a send must never break the flow
            msg.write({'state': 'failed', 'error_text': 'ZNS: %s' % exc})
        return msg

    def _store_message(self, msg):
        self.ensure_one()
        if self.outbound_message_id.id != msg.id:
            self.sudo().write({'outbound_message_id': msg.id})
