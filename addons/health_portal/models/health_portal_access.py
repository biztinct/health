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
import base64
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
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True,
        help='Area of the patient this portal access belongs to. Staff only '
             'see access records for their own area.')

    @api.depends('patient_id.catchment_province_id',
                 'patient_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.patient_id._get_health_catchment_province()
                if rec.patient_id else False)
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
            'packages': self._packages(),
            'rebook': self._rebook(),
        }

    # -- Balance + Book/rebook (4D) — surface existing packages + self-booking.
    def _packages(self):
        self.ensure_one()
        Pkg = self.env['health.service.package'].sudo()
        pkgs = Pkg.search([('patient_id', '=', self.patient_id.id),
                           ('state', '=', 'active')], order='id desc')
        return [{'name': p.name or '', 'remaining': p.remaining_services,
                 'total': p.total_services}
                for p in pkgs if p.remaining_services]

    def _rebook(self):
        self.ensure_one()
        Invite = self.env['health.selfbook.invite'].sudo()
        invite = Invite.search([('patient_id', '=', self.patient_id.id),
                                ('state', '=', 'sent')], order='id desc', limit=1)
        token = ''
        if invite and not (invite.expires_at
                           and fields.Datetime.now() > invite.expires_at):
            token = invite.token
        facility = self.patient_id.primary_facility_id
        return {'invite_token': token,
                'facility_phone': (facility.phone or '') if facility else ''}

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
        # Signature is legal evidence — require a real PNG (the canvas produces
        # one); reject a valid-base64 non-image so nonsense can't be stored.
        try:
            raw = base64.b64decode(signature_b64, validate=True)
        except Exception:
            return False
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
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

    # -- My Health (4E): active problem list + recent vital-sign readings ----
    # Same doctrine as 4B: a patient reading their OWN diagnoses and vitals is
    # their right (NOT data_sharing-gated — that governs EXTERNAL sharing).
    # Every read is sudo BUT hard-scoped to self.patient_id in the search
    # domain — no browse-by-id from request params, no post-filtering. Risk
    # interpretation (is_abnormal / alert_level / NEWS2) is NEVER surfaced to
    # the patient: raw values + units only (§3 rail).
    def _conditions(self):
        self.ensure_one()
        # active_test drops archived (removed) rows; the status filter keeps
        # the working problem list only (resolved / inactive not shown v1).
        return self.env['health.condition'].sudo().search([
            ('patient_id', '=', self.patient_id.id),
            ('clinical_status', '=', 'active'),
        ], order='recorded_date desc, id desc')

    def _conditions_rows(self):
        self.ensure_one()
        rows = []
        for cond in self._conditions():
            code = cond.code_id
            label = (code.display_vi or code.display or '') if code else ''
            since = cond.recorded_date  # Date (no tz) — format as-is
            rows.append({
                'code': code.code if code else '',
                'label': label,
                'since': since.strftime('%d/%m/%Y') if since else '',
            })
        return rows

    def _vitals(self):
        self.ensure_one()
        # Top-level rows only (panels' children are rendered inline); only
        # clinically-valid states — preliminary / entered_in_error excluded.
        return self.env['health.observation'].sudo().search([
            ('client_id', '=', self.patient_id.id),
            ('state', 'in', ('final', 'amended')),
            ('parent_id', '=', False),
        ], order='effective_datetime desc, id desc', limit=20)

    @staticmethod
    def _vital_value(obs):
        """Numeric value formatted to the type's decimals; text as-is."""
        vtype = obs.vitals_type_id
        if vtype.value_type == 'string':
            return obs.value_text or ''
        decimals = max(vtype.decimals or 0, 0)
        return '%.*f' % (decimals, obs.value_quantity or 0.0)

    def _vitals_rows(self):
        self.ensure_one()
        rows = []
        for obs in self._vitals():
            vtype = obs.vitals_type_id
            unit = vtype.unit_display or ''
            # Children inherit the top-level clinical-validity filter:
            # preliminary / entered_in_error (retracted) components must not
            # reach the patient either.
            children = obs.child_ids.filtered(
                lambda c: c.state in ('final', 'amended'))
            if children:
                # Deterministic component order (creation order = sys then dia
                # for BP); model _order is datetime desc which would flip it.
                children = children.sorted('id')
                child_units = {(c.vitals_type_id.unit_display or '')
                               for c in children}
                if len(child_units) == 1:
                    # Shared unit → slash-join e.g. 120/80 mmHg.
                    value = '/'.join(self._vital_value(c) for c in children)
                    unit = child_units.pop()
                else:
                    # Mixed units → "label value unit" pairs, ; -joined.
                    value = '; '.join(
                        ('%s %s %s' % (
                            c.vitals_type_id.name_vi or c.vitals_type_id.name
                            or '', self._vital_value(c),
                            c.vitals_type_id.unit_display or '')).strip()
                        for c in children)
                    unit = ''
            elif vtype.value_type == 'panel':
                # A panel with no (valid) components carries no value of its
                # own — skip it rather than render a bogus "0".
                continue
            else:
                value = self._vital_value(obs)
            when = obs.effective_datetime
            rows.append({
                'label': vtype.name_vi or vtype.name or '',
                'value': value,
                'unit': unit,
                'when': ((when + _VN_OFFSET).strftime('%d/%m/%Y %H:%M')
                         if when else ''),
            })
        return rows

    def _health_ctx(self):
        self.ensure_one()
        return {
            'patient_name': self.patient_id.name or '',
            'token': self.token,
            'conditions': self._conditions_rows(),
            'vitals': self._vitals_rows(),
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


class HealthPortalAccessOpsTab(models.Model):
    """Read helper for the ops client-profile "Portal Access" tab.

    Re-opens the record model rather than introducing an AbstractModel, so the
    RPC entry point carries the same ACL and record rules as the data it reads
    — and matches the other seven consolidated tabs, which all put their read
    method on the model that owns the records.
    """
    _inherit = 'health.portal.access'

    # ------------------------------------------------------------------
    # Ops client-profile tab (lazy fetch — client_portal_access_widget.js)
    #
    # Not an x2many on the ops arch: the client page loads every arch field in
    # one web_read, so a <field> list would tax every open.
    # ------------------------------------------------------------------
    @api.model
    def get_client_portal_access(self, patient_id):
        """Portal-access status for one patient, as plain dicts.

        SECURITY: ``token`` is group-restricted
        (health_base.group_healthcare_operations_manager) and ``portal_url`` is
        derived from it — the /my/care URL is a capability URL. Neither is ever
        put in this payload; the tab reports status only. Use the record form
        (ops-manager gated) to read or rotate the link.
        """
        if not patient_id:
            return {'access': []}
        records = self.search([('patient_id', '=', patient_id)])
        rows = []
        for rec in records:
            rows.append({
                'id': rec.id,
                'state': rec.state,
                'expires_at': _tab_dt(rec, rec.expires_at),
                'last_access_datetime': _tab_dt(rec, rec.last_access_datetime),
                'access_count': rec.access_count,
            })
        return {'access': rows}


# ---------------------------------------------------------------------------
# Display formatting for the ops record tabs.
#
# Stored datetimes are naive UTC; context_timestamp converts to the user's
# timezone (Asia/Ho_Chi_Minh here) so a tab does not show a visit as 7 hours
# earlier than every other surface. Raw ``to_string`` output ("2026-07-08
# 09:17:30") was also the only place in the ops forms not using the
# "Aug 21, 4:30 PM" house format.
# ---------------------------------------------------------------------------
def _tab_dt(record, value):
    """Naive-UTC datetime -> user-timezone display string."""
    if not value:
        return ''
    return fields.Datetime.context_timestamp(record, value).strftime(
        '%b %d, %Y %I:%M %p')


def _tab_date(value):
    """Date -> display string (dates carry no timezone)."""
    return value.strftime('%b %d, %Y') if value else ''
