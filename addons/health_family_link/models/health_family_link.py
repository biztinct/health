import logging
import secrets
from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# purpose -> ir.config_parameter holding the ZNS template id. Empty default =>
# that send is silently NOT created (A1), so vietuat installs clean.
_TEMPLATE_PARAM = {
    'family_visit_link': 'health_family_link.zns_template_family_link',
    'family_snapshot': 'health_family_link.zns_template_family_snapshot',
}
# FSO states that expose which page section.
_UPCOMING_STATES = ('confirmed', 'assigned')
_COMPLETED_STATES = ('completed', 'completed_pending_invoice', 'closed')
_DEFAULT_TZ = 'Asia/Ho_Chi_Minh'
_SUMMARY_MAX = 200


def _safe_phone(phone):
    """normalize_vn_phone raises on invalid; we want falsy-on-invalid
    (conventions ledger §5.15)."""
    from odoo.addons.health_base.models.phone_utils import normalize_vn_phone
    try:
        return normalize_vn_phone(phone) or ''
    except ValidationError:
        return ''


class HealthFamilyLink(models.Model):
    """A4 — a tokenized, no-login page per (visit, family relation).

    One link covers the whole visit lifecycle; the completion ZNS points at
    the same URL. Search-first on create keeps it idempotent (one link per
    (fso, relation)). No expiry cron — expiry is checked at render time; and
    consent withdrawal is enforced at render time too (A6).
    """
    _name = 'health.family.link'
    _description = 'Family Visit Link'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)
    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Visit', required=True,
        index=True, ondelete='cascade')
    relation_id = fields.Many2one(
        'health.client.relation', string='Family Relation', required=True,
        ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Recipient', ondelete='set null',
        help='Snapshot of relation.representative_id at link creation.')
    token = fields.Char(
        required=True, index=True, copy=False,
        default=lambda self: secrets.token_urlsafe(24),
        help='Capability token — the page URL is a capability URL. '
             'Never logged at info level.')
    state = fields.Selection([
        ('sent', 'Sent'),
        ('revoked', 'Revoked'),
    ], default='sent', required=True, index=True)
    expires_at = fields.Datetime(
        help='scheduled end + 24h; re-extended to actual end + 24h at '
             'completion. Checked at render time (no cron).')
    # A4 linkage (report point d): two explicit Many2one's — one per purpose —
    # extending the offer precedent's single outbound_message_id to the two
    # family purposes. Cleaner than an o2m (no reverse field needed on the
    # shipped health.outbound.message).
    visit_link_message_id = fields.Many2one(
        'health.outbound.message', string='Visit-Link Message',
        readonly=True, copy=False, ondelete='set null')
    snapshot_message_id = fields.Many2one(
        'health.outbound.message', string='Snapshot Message',
        readonly=True, copy=False, ondelete='set null')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True,
        index=True, help='Catchment area used for access control.')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    def init(self):
        # Conventions ledger §5.1 — _sql_constraints are not materialized in
        # Odoo 19; back the token uniqueness contract with a real index.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_family_link_token_uidx
            ON health_family_link (token)
        """)

    @api.depends('fso_id', 'partner_id')
    def _compute_display_name(self):
        for link in self:
            patient = link.fso_id.patient_id.name or ''
            rep = link.partner_id.name or ''
            link.display_name = _('Family link: %(patient)s -> %(rep)s') % {
                'patient': patient, 'rep': rep} if (patient or rep) else _('Family link')

    @api.depends('partner_id', 'fso_id.patient_id')
    def _compute_catchment_province_id(self):
        for link in self:
            patient = link.fso_id.patient_id
            link.catchment_province_id = (
                patient._get_health_catchment_province() if patient else False)

    # ------------------------------------------------------------------
    # Eligibility (A2) — three ANDed conditions per recipient
    # ------------------------------------------------------------------
    @api.model
    def _eligible_relations(self, fso, require_medical=False):
        """Opted-in relations for this FSO's patient.

        cond 1 (receives_visit_updates) always; cond 2
        (can_receive_medical_info) only when ``require_medical`` (the
        snapshot); cond 3 (data_sharing consent) is patient-level — checked
        once, and a False short-circuits to an empty set so zero eligible
        recipients means zero sends AND zero rows (§D.8.6 no-phantom rule).
        """
        patient = fso.patient_id
        if not patient:
            return self.env['health.client.relation']
        # cond 3 — never raises; logs evidence to the append-only check log.
        if not self.env['health.consent'].check_consent(patient, 'data_sharing'):
            return self.env['health.client.relation']
        domain = [
            ('client_id', '=', patient.id),
            ('receives_visit_updates', '=', True),
            ('active', '=', True),
        ]
        if require_medical:
            domain.append(('can_receive_medical_info', '=', True))
        return self.env['health.client.relation'].sudo().search(domain)

    # ------------------------------------------------------------------
    # Link get-or-create (idempotent) + expiry
    # ------------------------------------------------------------------
    @api.model
    def _link_expiry(self, fso):
        """scheduled end + 24h (A4). Falls back to scheduled + 2h when the
        duration is unset."""
        if not fso.scheduled_datetime:
            return False
        minutes = fso.scheduled_duration or 120
        return fso.scheduled_datetime + timedelta(minutes=minutes) + timedelta(hours=24)

    @api.model
    def _completion_expiry(self, fso):
        """actual end + 24h (A4); falls back to the scheduled expiry."""
        if fso.actual_end_datetime:
            return fso.actual_end_datetime + timedelta(hours=24)
        return self._link_expiry(fso)

    @api.model
    def _get_or_create_link(self, fso, relation):
        link = self.sudo().search(
            [('fso_id', '=', fso.id), ('relation_id', '=', relation.id)], limit=1)
        if link:
            return link
        return self.sudo().create({
            'fso_id': fso.id,
            'relation_id': relation.id,
            'partner_id': relation.representative_id.id,
            'expires_at': self._link_expiry(fso),
        })

    def _is_expired(self):
        self.ensure_one()
        return bool(self.expires_at and self.expires_at < fields.Datetime.now())

    # ------------------------------------------------------------------
    # URL / timezone helpers
    # ------------------------------------------------------------------
    def _base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', 'http://localhost:8069').rstrip('/')

    def _page_url(self):
        self.ensure_one()
        return '%s/family/visit/%s' % (self._base_url(), self.token)

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
        """Lead staff, given name only (Vietnamese given name is the last
        token — mirrors the offer page's split(' ')[-1])."""
        self.ensure_one()
        staff = self.fso_id.lead_staff_id
        if not staff or not staff.name:
            return ''
        return staff.name.split(' ')[-1]

    # ------------------------------------------------------------------
    # Snapshot content sanitization (A3)
    # ------------------------------------------------------------------
    def _snapshot_summary(self):
        """First 200 chars of patient_condition_after -> treatment_performed
        -> clinical_notes (Html, stripped), in that precedence. NEVER touches
        diagnosis, condition codes, or medications (A3). Sourced from the
        visit's latest health.clinical.note (NOT the Legacy FSO fields)."""
        self.ensure_one()
        note = self.fso_id.clinical_note_ids.sorted('create_date', reverse=True)[:1]
        if not note:
            return ''
        text = note.patient_condition_after or note.treatment_performed or ''
        if not text and note.clinical_notes:
            text = html2plaintext(note.clinical_notes)
        return (text or '').strip()[:_SUMMARY_MAX]

    # ------------------------------------------------------------------
    # Render-data assembly (A5 / A6) — factored out for direct testing
    # ------------------------------------------------------------------
    def _page_context(self):
        """Server-side render data driven by the FSO state.

        modes: upcoming / arrived / completed / neutral. Cancelled, draft, and
        (A6) a completed visit whose data_sharing consent is now withdrawn all
        render the neutral page — no existence oracle, no stale PHI.
        """
        self.ensure_one()
        fso = self.fso_id
        base = {
            'patient_name': fso.patient_id.name or '',
            'staff_name': self._staff_given_name(),
            'staff_role': _('y tá'),
            'facility_phone': fso.facility_id.phone or '',
        }
        state = fso.state
        if state in _UPCOMING_STATES:
            start = self._wall(fso.scheduled_datetime)
            end = self._wall(fso.estimated_end_datetime)
            base.update({
                'mode': 'upcoming',
                'visit_date': start.strftime('%d/%m/%Y') if start else '',
                'time_window': ('%s - %s' % (
                    start.strftime('%H:%M'), end.strftime('%H:%M'))
                    if start and end else (
                        start.strftime('%H:%M') if start else '')),
            })
            return base
        if state == 'in_progress':
            arrived = self._wall(fso.actual_start_datetime)
            base.update({
                'mode': 'arrived',
                'arrived_time': arrived.strftime('%H:%M') if arrived else '',
            })
            return base
        if state in _COMPLETED_STATES:
            # A6 — re-check data_sharing on every view; consent gone => neutral.
            if not self.env['health.consent'].check_consent(
                    fso.patient_id, 'data_sharing'):
                return {'mode': 'neutral'}
            visit_dt = self._wall(fso.actual_end_datetime or fso.scheduled_datetime)
            base.update({
                'mode': 'completed',
                'visit_date': visit_dt.strftime('%d/%m/%Y') if visit_dt else '',
                'summary': self._snapshot_summary(),
            })
            return base
        # cancelled / draft / anything else -> neutral.
        return {'mode': 'neutral'}

    # ------------------------------------------------------------------
    # Sending (ZNS through the shipped messaging safety rails — A1)
    # ------------------------------------------------------------------
    def _zns_params(self):
        """A3 — {patient_name, visit_date (wall-clock), staff_name, link}.
        The full summary lives on the PAGE, never in ZNS params."""
        self.ensure_one()
        start = self._wall(self.fso_id.scheduled_datetime)
        return {
            'patient_name': self.fso_id.patient_id.name or '',
            'visit_date': start.strftime('%d/%m/%Y') if start else '',
            'staff_name': self._staff_given_name(),
            'link': self._page_url(),
        }

    def _send_zns(self, purpose):
        """Log + send one family ZNS honoring health_messaging's rails.

        Respects health_messaging.enabled / dry_run exactly (dry_run ->
        simulated, no real send). No template configured => the row is
        silently NOT created (A1). Search-first on the dedup key makes double
        confirm/complete a no-op.
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        template_id = ICP.get_param(_TEMPLATE_PARAM[purpose], '')
        if not template_id:
            return self.env['health.outbound.message']
        dedup_key = '%s-%s-%s' % (
            'famlink' if purpose == 'family_visit_link' else 'famsnap',
            self.fso_id.id, self.relation_id.id)
        Message = self.env['health.outbound.message'].sudo()
        existing = Message.search([('dedup_key', '=', dedup_key)], limit=1)
        if existing:
            self._store_message(purpose, existing)
            return existing

        enabled = ICP.get_param('health_messaging.enabled', 'False') in (
            'True', 'true', '1')
        dry_run = ICP.get_param('health_messaging.dry_run', 'True') in (
            'True', 'true', '1')
        phone = _safe_phone(self.partner_id.mobile or self.partner_id.phone)
        params = self._zns_params()
        msg = Message.create({
            'purpose': purpose,
            'channel': 'zns',
            'partner_id': self.partner_id.id,
            'fso_id': self.fso_id.id,
            'phone': phone,
            'dedup_key': dedup_key,
            'payload_json': params,
            'state': 'queued',
        })
        self._store_message(purpose, msg)

        if not phone:
            msg.write({'state': 'skipped',
                       'error_text': _('No usable phone for the recipient.')})
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

    def _store_message(self, purpose, msg):
        self.ensure_one()
        field = ('visit_link_message_id' if purpose == 'family_visit_link'
                 else 'snapshot_message_id')
        if self[field].id != msg.id:
            self.sudo().write({field: msg.id})
