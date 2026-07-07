# -*- coding: utf-8 -*-
"""Unified outbound message log + queue and the channel-cascade engine.

Cascade per send: ZNS → email → staff call-activity, each step only when
the previous is unavailable/failed. Safety: `health_messaging.dry_run`
defaults True — the full pipeline runs but the real ZNS/email calls are
skipped and the row is marked `simulated`."""

import logging
from datetime import timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import str2bool

from odoo.addons.health_base.models.phone_utils import normalize_vn_phone

_logger = logging.getLogger(__name__)

# purpose → ir.config_parameter holding the ZNS template id
ZNS_TEMPLATE_PARAM = {
    'booking_confirmation': 'health_messaging.zns_template_confirmation',
    'reminder_24h': 'health_messaging.zns_template_reminder24',
    'reminder_2h': 'health_messaging.zns_template_reminder2',
    'cancellation_notice': 'health_messaging.zns_template_cancellation',
}
CONFIRMABLE_STATES = ('confirmed', 'assigned')


class HealthOutboundMessage(models.Model):
    _name = 'health.outbound.message'
    _description = 'Outbound Message'
    _order = 'create_date desc'

    name = fields.Char(required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    purpose = fields.Selection([
        ('booking_confirmation', 'Booking Confirmation'),
        ('reminder_24h', 'Reminder (24h)'),
        ('reminder_2h', 'Reminder (2h)'),
        ('cancellation_notice', 'Cancellation Notice'),
    ], required=True, index=True)
    channel = fields.Selection([
        ('zns', 'Zalo ZNS'),
        ('email', 'Email'),
        ('staff_activity', 'Staff Call Activity'),
    ], help='Which cascade step actually ran.')
    partner_id = fields.Many2one(
        'res.partner', string='Recipient', required=True,
        ondelete='restrict', index=True)
    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Visit', index=True,
        ondelete='set null')
    phone = fields.Char(help='Normalized phone, as sent.')
    state = fields.Selection([
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('simulated', 'Simulated'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
        ('escalated', 'Escalated'),
    ], default='queued', required=True, index=True)
    error_text = fields.Text()
    payload_json = fields.Json(string='Template Params')
    sent_at = fields.Datetime()
    dedup_key = fields.Char(index=True, copy=False)
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True,
        index=True, help='Catchment area used for filtering and access control')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    def init(self):
        # Odoo 19 does not materialize _sql_constraints — partial unique
        # index backs the dedup-key contract (race backstop; the queueing
        # helper search-firsts, so a duplicate is normally a no-op).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_outbound_message_dedup_uidx
            ON health_outbound_message (dedup_key)
            WHERE dedup_key IS NOT NULL AND dedup_key != ''
        """)

    @api.depends('partner_id')
    def _compute_catchment_province_id(self):
        for message in self:
            message.catchment_province_id = (
                message.partner_id._get_health_catchment_province()
                if message.partner_id else False)

    @api.model_create_multi
    def create(self, vals_list):
        seen = set()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'health.outbound.message') or _('New')
            key = vals.get('dedup_key')
            # Pre-check dedup_key BEFORE super() so a race raises a
            # ValidationError, not the index's IntegrityError (conventions
            # §5.3). Normal callers search-first, so this only fires on a
            # true concurrent race (swallowed by the caller's try/except).
            if key:
                if key in seen or self.search_count([('dedup_key', '=', key)]):
                    raise ValidationError(_(
                        'An outbound message with dedup key "%s" already '
                        'exists.') % key)
                seen.add(key)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------
    def _param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(
            'health_messaging.%s' % key, default)

    def _enabled(self):
        return str2bool(self._param('enabled', 'False'))

    def _dry_run(self):
        # SAFETY: defaults True when the param was never set.
        return str2bool(self._param('dry_run', 'True'))

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    @api.model
    def process_purpose(self, fso, purpose):
        """Queue + run the cascade for one (fso, purpose). Idempotent:
        search-first on the dedup key and no-op if a row already exists.
        Master-disable is a true no-op (installing changes nothing)."""
        if not self._enabled():
            return self.browse()
        dedup_key = 'fso-%s-%s' % (fso.id, purpose)
        existing = self.search([('dedup_key', '=', dedup_key)], limit=1)
        if existing:
            return existing
        message = self.create({
            'purpose': purpose,
            'partner_id': fso.patient_id.id,
            'fso_id': fso.id,
            'dedup_key': dedup_key,
            'state': 'queued',
        })
        message._run_cascade()
        return message

    def action_retry(self):
        """Manual re-run of the cascade for a failed/escalated row."""
        for message in self:
            if message.state in ('sent', 'simulated'):
                continue
            message.write({'state': 'queued', 'error_text': False,
                           'channel': False})
            message._run_cascade()
        return True

    # ------------------------------------------------------------------
    # Cascade engine
    # ------------------------------------------------------------------
    def _run_cascade(self):
        self.ensure_one()
        fso = self.fso_id
        purpose = self.purpose
        partner = self.partner_id
        # Guards → skipped (never raise).
        if purpose != 'cancellation_notice' and (
                not fso or fso.state not in CONFIRMABLE_STATES):
            return self._skip('Visit is not in a confirmable state.')
        if not partner.active:
            return self._skip('Recipient is archived.')
        # Quiet hours → stay queued for a later cron tick.
        if self._in_quiet_hours(fso):
            if self.state != 'queued':
                self.state = 'queued'
            return self
        params = self._build_params(fso)
        self.payload_json = params
        if self._step_zns(fso, params):
            return self
        if self._step_email(fso, params):
            return self
        self._step_escalate(fso)
        return self

    def _skip(self, reason):
        self.write({'state': 'skipped', 'error_text': reason})
        return self

    def _in_quiet_hours(self, fso):
        tz = self._fso_tz(fso)
        now_local = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
        hour = now_local.hour + now_local.minute / 60.0
        start = float(self._param('quiet_start', '21.0') or 21.0)
        end = float(self._param('quiet_end', '7.0') or 7.0)
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end  # window wraps midnight

    @staticmethod
    def _fso_tz(fso):
        try:
            return pytz.timezone(
                (fso.booking_timezone if fso else None) or 'Asia/Ho_Chi_Minh')
        except pytz.UnknownTimeZoneError:
            return pytz.timezone('Asia/Ho_Chi_Minh')

    def _build_params(self, fso):
        """Shared template param dict. visit_date/visit_time are wall-clock
        in the FSO booking timezone (the +7h class of bug is the most-hit
        timezone mistake in this codebase — localize explicitly)."""
        tz = self._fso_tz(fso)
        local = None
        if fso.scheduled_datetime:
            local = pytz.utc.localize(fso.scheduled_datetime).astimezone(tz)
        lang = fso.patient_id.lang or 'vi_VN'
        service_field = fso._fields['service_type']
        labels = dict(service_field._description_selection(
            fso.with_context(lang=lang).env))
        return {
            'patient_name': fso.patient_id.name or '',
            'visit_date': local.strftime('%d/%m/%Y') if local else '',
            'visit_time': local.strftime('%H:%M') if local else '',
            'facility_name': fso.facility_id.name or '',
            'service_type': labels.get(fso.service_type) or (
                fso.service_type or ''),
        }

    # -- step 1: ZNS ---------------------------------------------------
    def _step_zns(self, fso, params):
        config = self.env['zalo.config'].search(
            [('active', '=', True)], limit=1)
        template_id = self._param(
            ZNS_TEMPLATE_PARAM[self.purpose].split('.', 1)[1])
        phone = self._safe_phone(fso.patient_phone)
        if not (config and template_id and phone):
            return False  # unavailable — fall through
        self.phone = phone
        if self._dry_run():
            self.write({'state': 'simulated', 'channel': 'zns',
                        'sent_at': fields.Datetime.now()})
            return True
        try:
            from odoo.addons.health_zalo.services.zalo_api import get_api_client
            result = get_api_client(self.env).send_zns_notification(
                config, phone, template_id, params)
        except Exception as exc:  # noqa: BLE001 — cascade must fall through
            self.error_text = 'ZNS: %s' % exc
            return False
        # health_zalo can also signal failure via an error-shaped dict.
        if isinstance(result, dict) and result.get('error') \
                and result.get('error') != 0:
            self.error_text = 'ZNS error: %s' % (
                result.get('message') or result.get('error'))
            return False
        self.write({'state': 'sent', 'channel': 'zns',
                    'sent_at': fields.Datetime.now()})
        return True

    @staticmethod
    def _safe_phone(phone):
        # normalize_vn_phone raises ValidationError on invalid input; the
        # cascade wants a falsy result instead (handover §1 contract).
        try:
            return normalize_vn_phone(phone) or ''
        except ValidationError:
            return ''

    # -- step 2: email -------------------------------------------------
    def _step_email(self, fso, params):
        if not fso.patient_email:
            return False
        template = self.env.ref(
            'health_messaging.mail_template_%s' % self.purpose,
            raise_if_not_found=False)
        if not template:
            return False
        # The templates are self-contained on object.* (tz-correct via
        # format_datetime) — no injected context needed.
        if self._dry_run():
            self.write({'state': 'simulated', 'channel': 'email',
                        'sent_at': fields.Datetime.now()})
            return True
        try:
            template.send_mail(fso.id, force_send=False,
                               email_values={'email_to': fso.patient_email})
        except Exception as exc:  # noqa: BLE001 — fall through to escalation
            self.error_text = (self.error_text or '') + ' | Email: %s' % exc
            return False
        self.write({'state': 'sent', 'channel': 'email',
                    'sent_at': fields.Datetime.now()})
        return True

    # -- step 3: escalation -------------------------------------------
    def _step_escalate(self, fso):
        user = (fso.lead_staff_id.user_id
                if fso.lead_staff_id and fso.lead_staff_id.user_id
                else self._facility_manager_user(fso))
        self.write({'state': 'escalated', 'channel': 'staff_activity'})
        if not user:
            self.error_text = (self.error_text or '') + \
                ' | Escalation: no staff/manager user to notify.'
            return
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return
        try:
            fso.activity_schedule(
                activity_type_id=activity_type.id,
                summary=_('Call patient to confirm visit'),
                date_deadline=(fso.scheduled_date or fields.Date.today()),
                user_id=user.id)
        except Exception:  # noqa: BLE001 — alerting must never break capture
            _logger.exception(
                'Messaging escalation activity failed for FSO %s', fso.id)

    @staticmethod
    def _facility_manager_user(fso):
        """Facility-manager fallback (mirrors health_incident
        _get_facility_manager_user)."""
        facility = fso.facility_id or (
            fso.patient_id.primary_facility_id if fso.patient_id else False)
        manager = facility.facility_manager_id if facility else False
        return manager.user_id if manager and manager.user_id else False

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def cron_process_visit_messages(self):
        if not self._enabled():
            return True
        now = fields.Datetime.now()
        FSO = self.env['health.fieldservice.order']
        # Slightly overlapping windows so a delayed tick never skips a visit.
        self._queue_window(FSO, 'reminder_24h',
                           now + timedelta(hours=23),
                           now + timedelta(hours=24, minutes=15))
        self._queue_window(FSO, 'reminder_2h',
                           now + timedelta(hours=1, minutes=45),
                           now + timedelta(hours=2, minutes=15))
        # Re-process quiet-hour deferrals.
        for message in self.search([('state', '=', 'queued')]):
            try:
                message._run_cascade()
            except Exception:  # noqa: BLE001 — one bad row never aborts
                _logger.exception(
                    'Messaging re-process failed for %s', message.name)
        return True

    @api.model
    def _queue_window(self, FSO, purpose, start, end):
        orders = FSO.search([
            ('state', 'in', CONFIRMABLE_STATES),
            ('scheduled_datetime', '>=', start),
            ('scheduled_datetime', '<=', end),
        ])
        for fso in orders:
            try:
                self.process_purpose(fso, purpose)
            except Exception:  # noqa: BLE001 — per-record isolation
                _logger.exception(
                    'Messaging queue failed for FSO %s (%s)', fso.id, purpose)

    def action_view_fso(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'res_id': self.fso_id.id,
            'view_mode': 'form',
        }
