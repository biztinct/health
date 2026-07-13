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
import logging
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

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

    @staticmethod
    def _given_name(name):
        # VN given name = last whitespace token; safe on blank/whitespace names.
        parts = (name or '').split()
        return parts[-1] if parts else ''

    def _visit_row(self, order):
        # Given-name-only for staff privacy; NO clinical PHI on the visits list
        # (that's the records section, 4B).
        given = self._given_name(order.lead_staff_id.name
                                 if order.lead_staff_id else '')
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

    # -- My Records (4B): the patient's OWN finalized medical records ---------
    # A patient accessing their own record is their right — NOT gated by
    # data_sharing consent (that governs EXTERNAL sharing). Only emr_state=final
    # notes are shown (drafts are work-in-progress, never the legal record).
    def _records(self):
        self.ensure_one()
        Note = self.env['health.clinical.note'].sudo()
        if 'emr_state' not in Note._fields:
            return Note.browse()  # health_emr not installed → no finalized records
        return Note.search([
            ('order_id.patient_id', '=', self.patient_id.id),
            ('emr_state', '=', 'final'),
        ], order='signed_datetime desc, id desc', limit=100)

    def _records_ctx(self):
        self.ensure_one()
        rows = []
        for note in self._records():
            when = note.signed_datetime
            rows.append({
                'id': note.id,
                'when': (when + _VN_OFFSET).strftime('%d/%m/%Y') if when else '',
                'visit': note.order_id.name or '',
                'signer': self._given_name(note.signed_by_id.name
                                           if note.signed_by_id else ''),
            })
        return {'patient_name': self.patient_id.name or '', 'token': self.token,
                'records': rows}

    def _note_or_false(self, note_id):
        """The note IFF it is this patient's own finalized record."""
        self.ensure_one()
        Note = self.env['health.clinical.note'].sudo()
        if 'emr_state' not in Note._fields:
            return Note.browse()
        note = Note.browse(int(note_id)).exists()
        if (not note or note.emr_state != 'final'
                or note.order_id.patient_id.id != self.patient_id.id):
            return Note.browse()
        return note

    def _note_sections(self, note):
        secs = []
        for label, fname, is_html in (
                ('Ghi chú lâm sàng', 'clinical_notes', True),
                ('Chẩn đoán', 'diagnosis', False),
                ('Điều trị đã thực hiện', 'treatment_performed', False),
                ('Thuốc đã kê', 'medications_prescribed', False),
                ('Sinh hiệu', 'vital_signs', False),
                ('Tình trạng trước', 'patient_condition_before', False),
                ('Tình trạng sau', 'patient_condition_after', False)):
            val = note[fname]
            if is_html:
                val = html2plaintext(val or '')
            val = (val or '').strip()
            if val:
                secs.append((label, val))
        return secs

    def _note_ctx(self, note):
        when = note.signed_datetime
        return {
            'token': self.token,
            'note_id': note.id,
            'when': (when + _VN_OFFSET).strftime('%d/%m/%Y %H:%M') if when else '',
            'visit': note.order_id.name or '',
            'signer': self._given_name(note.signed_by_id.name
                                       if note.signed_by_id else ''),
            'sections': self._note_sections(note),
        }

    def _note_text(self, note):
        when = note.signed_datetime
        lines = [
            'HO SO BENH AN / MEDICAL RECORD',
            'Benh nhan: %s' % (self.patient_id.name or ''),
            'Ngay ky: %s' % ((when + _VN_OFFSET).strftime('%d/%m/%Y %H:%M')
                             if when else ''),
            '',
        ]
        for label, val in self._note_sections(note):
            lines.append('%s:' % label)
            lines.append(val)
            lines.append('')
        return '\n'.join(lines)


    # -- My Consents (4C): patient view + withdraw + grant-with-signature ----
    # Only the patient-controllable preferences; care-delivery consents
    # (service, emergency_treatment) are captured by staff at intake, never
    # portal-toggled.
    MANAGED_CONSENT_TYPES = (
        ('data_sharing', 'Chia sẻ dữ liệu y tế'),
        ('photography', 'Chụp ảnh / quay phim'),
        ('marketing', 'Nhận thông tin tiếp thị'),
    )

    def _consents_ctx(self):
        self.ensure_one()
        Consent = self.env['health.consent'].sudo()
        rows = []
        for ctype, label in self.MANAGED_CONSENT_TYPES:
            active = bool(Consent._find_active_consent(self.patient_id.id, ctype))
            rows.append({'type': ctype, 'label': label, 'active': active})
        return {'token': self.token, 'patient_name': self.patient_id.name or '',
                'consents': rows}

    def _consent_label(self, ctype):
        return dict(self.MANAGED_CONSENT_TYPES).get(ctype)

    def _portal_withdraw(self, ctype):
        """Withdraw the patient's active consent of `ctype`. Feeds the Phase-2
        FHIR consent gate (withdraw data_sharing → external sharing stops)."""
        self.ensure_one()
        if ctype not in dict(self.MANAGED_CONSENT_TYPES):
            return False
        Consent = self.env['health.consent'].sudo()
        active = Consent._find_active_consent(self.patient_id.id, ctype)
        if active:
            active.with_context(
                withdrawal_reason='Bệnh nhân thu hồi qua cổng My Care'
            ).action_withdraw()
        return True

    def _portal_grant(self, ctype, signature_b64):
        """Grant `ctype` with the patient's on-screen signature (digital_
        signature evidence). No-op if already active. Returns True on success,
        False on a bad type / missing signature."""
        self.ensure_one()
        if ctype not in dict(self.MANAGED_CONSENT_TYPES) or not signature_b64:
            return False
        Consent = self.env['health.consent'].sudo()
        if Consent._find_active_consent(self.patient_id.id, ctype):
            return True  # already active
        # Savepoint so a malformed signature (image validation raises) rolls
        # back cleanly and the public page shows an error, never a 500.
        try:
            with self.env.cr.savepoint():
                consent = Consent.create({
                    'client_id': self.patient_id.id,
                    'consent_type': ctype,
                    'self_granted': True,
                    'method': 'digital_signature',
                    'signature': signature_b64,
                    'scope_note': 'Granted by the patient via the My Care portal.',
                })
                consent.action_grant()
        except Exception:
            _logger.warning('Portal consent grant failed (patient %s, type %s)',
                            self.patient_id.id, ctype)
            return False
        return True


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
