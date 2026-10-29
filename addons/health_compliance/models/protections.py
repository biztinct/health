import json
import logging
from urllib.parse import urlparse
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.ai_egress import egress
from odoo.addons.health_phi_encryption.models import phi_crypto
from .assurance import require_manager

_logger = logging.getLogger('odoo.health_compliance.audit')


def audit_event(env, operation, model, identifiers, outcome='allowed', field_names=None):
    # Structured server log survives request rollback. Never log narrative,
    # patient names, identifiers, credentials or URLs with query strings.
    payload = json.dumps({'database': env.cr.dbname, 'actor_uid': env.uid,
        'timestamp': fields.Datetime.to_string(fields.Datetime.now()), 'operation': operation,
        'model': model, 'record_ids': list(identifiers), 'outcome': outcome,
        'fields': sorted(field_names or [])}, sort_keys=True)
    _logger.info('HC_AUDIT %s', payload)
    try:
        import syslog
        syslog.syslog(syslog.LOG_AUTHPRIV | syslog.LOG_INFO, 'HC_AUDIT ' + payload)
    except (ImportError, OSError):
        _logger.warning('Independent syslog sink unavailable; server log only')


class PartnerProtection(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        records=super().create(vals_list)
        audit_event(self.env, 'create', self._name, records.ids,
                    field_names={k for v in vals_list for k in v})
        return records

    def write(self, vals):
        try:
            result=super().write(vals)
        except Exception:
            audit_event(self.env, 'write', self._name, self.ids, 'denied', vals.keys())
            raise
        audit_event(self.env, 'write', self._name, self.ids, field_names=vals.keys())
        return result

    def _fetch_query(self, query, fields):
        records = super()._fetch_query(query, fields)
        audit_event(self.env, 'fetch', self._name, records.ids, field_names=[f.name for f in fields])
        return records

    def read(self, fields=None, load='_classic_read'):
        try:
            result = super().read(fields=fields, load=load)
        except Exception:
            audit_event(self.env, 'read', self._name, self.ids, 'denied', fields)
            raise
        audit_event(self.env, 'read', self._name, self.ids, field_names=fields)
        return result

    def unlink(self):
        patients = self.filtered('is_patient')
        holds = self.env['health.compliance.hold'].sudo().search_count([('patient_id', 'in', self.ids)])
        notes = self.env['health.clinical.note'].sudo().search_count([('order_id.patient_id', 'in', patients.ids)]) if patients else 0
        if holds or notes:
            audit_event(self.env, 'unlink', self._name, self.ids, 'retention_refused')
            raise UserError(_('Clinical records or retention holds prevent patient deletion. Use a reviewed rights/retention process.'))
        audit_event(self.env, 'unlink', self._name, self.ids)
        return super().unlink()


class NoteProtection(models.Model):
    _inherit = 'health.clinical.note'
    correction_reason_enc = fields.Text(string='Correction Reason (encrypted)')
    correction_reason = fields.Text(string='Correction Reason', compute='_compute_correction_reason', inverse='_inverse_correction_reason')

    @api.depends('correction_reason_enc')
    def _compute_correction_reason(self):
        for row in self:
            row.correction_reason = phi_crypto.decrypt(self.env, row.correction_reason_enc) or False

    def _inverse_correction_reason(self):
        for row in self:
            row.correction_reason_enc = phi_crypto.encrypt(self.env, row.correction_reason) if row.correction_reason else False

    def action_finalize(self):
        try:
            for row in self.sudo():
                row._ensure_can_finalize()
                attachments = row.image_ids | row.audio_ids
                attachments._health_encrypt_existing()
            result = super().action_finalize()
        except Exception:
            audit_event(self.env, 'finalize', self._name, self.ids, 'denied')
            raise
        audit_event(self.env, 'finalize', self._name, self.ids)
        return result

    def action_create_addendum(self):
        self.ensure_one()
        self.check_access('read')
        if self.emr_state != 'final':
            raise UserError(_('Only a finalized note can receive an addendum.'))
        # Retain the named action so the CMS shell recognises this form.
        action = self.env['ir.actions.actions']._for_xml_id('health_emr.action_unsigned_clinical_notes')
        action.update({'view_mode': 'form', 'views': [(False, 'form')], 'res_id': False,
            'target': 'current', 'context': dict(self.env.context,
                default_order_id=self.order_id.id, default_amends_note_id=self.id,
                default_author_id=self.env.uid)})
        return action


class AttachmentProtection(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        records=super().create(vals_list)
        sensitive=records.filtered(lambda a:a._health_sensitive())
        if sensitive:audit_event(self.env, 'attachment_create', self._name, sensitive.ids)
        return records

    def write(self, vals):
        sensitive=self.filtered(lambda a:a._health_sensitive(vals))
        try:
            result=super().write(vals)
        except Exception:
            if sensitive:audit_event(self.env, 'attachment_write', self._name, sensitive.ids, 'denied', vals.keys())
            raise
        if sensitive:audit_event(self.env, 'attachment_write', self._name, sensitive.ids, field_names=vals.keys())
        return result

    def unlink(self):
        identifiers=self.filtered(lambda a:a._health_sensitive()).ids
        try:
            result=super().unlink()
        except Exception:
            if identifiers:audit_event(self.env, 'attachment_unlink', self._name, identifiers, 'denied')
            raise
        if identifiers:audit_event(self.env, 'attachment_unlink', self._name, identifiers)
        return result

    def _to_http_stream(self):
        result = super()._to_http_stream()
        if self._health_sensitive():
            audit_event(self.env, 'attachment_stream', self._name, self.ids)
        return result

    def _health_check_evidence_lock(self):
        super()._health_check_evidence_lock()
        for row in self:
            Rights=self.env['health.compliance.rights'].sudo()
            if (Rights.search_count([('ack_proof_id','=',row.id),('ack_at','!=',False)])
                    or Rights.search_count([('extension_notice_id','=',row.id),('extended_at','!=',False)])
                    or Rights.search_count([('outcome_proof_id','=',row.id),('completed_at','!=',False)])):
                raise UserError(_('Recorded rights communication proof cannot be replaced or deleted.'))
            if self.env['health.compliance.destination'].sudo().search_count([
                    ('processor_terms_id','=',row.id),('approved_at','!=',False)]):
                raise UserError(_('Approved processing terms cannot be replaced; submit revised terms and request approval.'))
            if row.res_model == 'health.compliance.evidence' and row.res_id:
                record = self.env[row.res_model].sudo().browse(row.res_id).exists()
                if record and record.state == 'approved':
                    raise UserError(_('Reviewed evidence files cannot be replaced or deleted.'))
            if row.res_model == 'res.partner' and row.res_id and self.env['health.compliance.hold'].sudo().search_count([('patient_id', '=', row.res_id)]):
                raise UserError(_('An active retention hold prevents attachment deletion or replacement.'))


class ScribeProtection(models.Model):
    _inherit = 'health.scribe.job'
    transcript_enc = fields.Text(string='Transcript (encrypted)', groups='health_base.group_healthcare_manager')
    transcript = fields.Text(string='Transcript', compute='_compute_transcript', inverse='_inverse_transcript')

    @api.depends('transcript_enc')
    def _compute_transcript(self):
        for row in self:
            row.transcript = phi_crypto.decrypt(self.env, row.transcript_enc) or False

    def _inverse_transcript(self):
        for row in self:
            row.transcript_enc = phi_crypto.encrypt(self.env, row.transcript) if row.transcript else False

    def _process_job(self, endpoint, language, timeout):
        destination = self.env['health.compliance.destination']._approved(endpoint, 'ai_processing')
        consent = self.env['health.consent'].get_consent(self.note_id.order_id.patient_id, 'ai_processing')
        if not self.env['health.consent'].check_consent(self.note_id.order_id.patient_id, 'ai_processing'):
            self.write({'state': 'failed', 'error': 'consent'})
            audit_event(self.env, 'speech_transmission', self._name, self.ids, 'purpose_consent_missing')
            return False
        if not destination or not consent or destination not in consent.destination_ids:
            self.write({'state': 'failed', 'error': 'destination_not_approved'})
            audit_event(self.env, 'speech_transmission', self._name, self.ids, 'destination_refused')
            return False
        return super()._process_job(endpoint, language, timeout)


class Destination(models.Model):
    _name = 'health.compliance.destination'
    _description = 'Approved Processing Destination'
    name = fields.Char(required=True)
    endpoint = fields.Char(required=True, help='Exact HTTPS endpoint (or loopback demo endpoint), including path. No credentials/query strings.')
    country = fields.Char(required=True, help='Actual hosting/processing country confirmed by the reviewer; no inference from vendor or private hostname.')
    purpose = fields.Selection([('ai_processing', 'AI processing'), ('support_access', 'Support'),
                               ('analytics', 'Analytics'), ('model_training', 'Model training'),
                               ('national', 'National health'), ('bhxh', 'BHXH')], required=True)
    legal_basis = fields.Text(required=True)
    processor_terms_id = fields.Many2one('ir.attachment', required=True)
    approved_by_id = fields.Many2one('res.users', readonly=True)
    approved_at = fields.Datetime(readonly=True)
    valid_until = fields.Date(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)

    @api.constrains('endpoint')
    def _check_endpoint(self):
        for row in self:
            parsed = urlparse(row.endpoint)
            if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
                raise UserError(_('Use an exact endpoint without credentials, query or fragment.'))
            if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')):
                raise UserError(_('Processing endpoints require HTTPS, except explicit loopback demo services.'))

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('approved_by_id') or v.get('approved_at') for v in vals_list):
            raise UserError(_('Use destination approval after reviewing processor terms and country.'))
        rows = super().create(vals_list)
        rows._check_endpoint()
        if any(r.approved_by_id or r.approved_at for r in rows):
            raise UserError(_('Approval cannot be supplied through defaults.'))
        return rows

    def action_approve(self):
        require_manager(self.env)
        self._check_endpoint()
        for row in self:
            if not row.processor_terms_id or row.valid_until < fields.Date.context_today(row):
                raise UserError(_('Current processor terms and review validity are required.'))
            super(Destination, row).write({'approved_by_id': self.env.uid, 'approved_at': fields.Datetime.now()})

    def write(self, vals):
        if {'approved_by_id', 'approved_at'} & vals.keys():
            raise UserError(_('Use the processing destination approval action.'))
        if vals:
            vals = dict(vals, approved_by_id=False, approved_at=False)
        return super().write(vals)

    @api.model
    def _approved(self, endpoint, purpose):
        return self.sudo().search([('endpoint', '=', endpoint), ('purpose', '=', purpose),
            ('company_id', '=', self.env.company.id), ('approved_at', '!=', False),
            ('valid_until', '>=', fields.Date.context_today(self))], limit=1)


class AIProviderProtection(models.Model):
    _inherit = 'bi.ai.provider'

    def _complete(self, system, user_message, force_json=True, classification=egress.RECORDS, patient=None):
        self.ensure_one()
        text = (system or '') + '\n' + (user_message or '')
        try:
            egress.check(text, classification, self.provider, self.endpoint)
            if classification == egress.RECORDS and (not patient or not self.env['health.consent'].check_consent(patient, 'ai_processing')):
                raise egress.EgressRefused('purpose_consent_missing')
            if classification == egress.RECORDS:
                destination = self.env['health.compliance.destination']._approved(self.endpoint, 'ai_processing')
                consent = self.env['health.consent'].get_consent(patient, 'ai_processing')
                if not destination or destination not in consent.destination_ids:
                    raise egress.EgressRefused('destination_not_approved_or_not_consented')
        except egress.EgressRefused as exc:
            audit_event(self.env, 'ai_transmission', self._name, self.ids, exc.reason)
            raise
        audit_event(self.env, 'ai_transmission', self._name, self.ids)
        return super()._complete(system, user_message, force_json=force_json, classification=classification, patient=patient)


class IntegrationReadiness(models.Model):
    _name = 'health.compliance.integration'
    _description = 'Authority Integration Readiness'
    name = fields.Char(required=True)
    kind = fields.Selection([('signing', 'Certified digital signing'), ('national', 'National health / VNeID'),
                             ('bhxh', 'BHXH')], required=True)
    provider = fields.Char()
    approved_specification_id = fields.Many2one('ir.attachment')
    authority_onboarding_id = fields.Many2one('ir.attachment')
    test_acceptance_id = fields.Many2one('ir.attachment')
    credential_location = fields.Char(help='Secret store reference only; never paste credentials.')
    pending_action = fields.Text(required=True)
    status = fields.Selection([('pending', 'Provider and authority onboarding pending'),
                               ('review', 'Documents ready for technical integration')], compute='_compute_status')
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)

    @api.depends('provider', 'approved_specification_id', 'authority_onboarding_id', 'test_acceptance_id', 'credential_location')
    def _compute_status(self):
        for row in self:
            row.status = 'review' if all((row.provider, row.approved_specification_id,
                row.authority_onboarding_id, row.test_acceptance_id, row.credential_location)) else 'pending'


class ConsentProtection(models.Model):
    _inherit = 'health.consent'
    destination_ids = fields.Many2many('health.compliance.destination', string='Approved Recipients',
        help='Exact reviewed destinations covered by this consent notice. Empty does not permit AI transmission.')

    @api.constrains('destination_ids', 'consent_type_id')
    def _check_destinations(self):
        for row in self:
            if any(d.purpose != row.consent_type_code or not d.approved_at or
                   d.valid_until < fields.Date.context_today(row) or d.company_id != row.company_id
                   for d in row.destination_ids):
                raise UserError(_('Recipients must be currently approved for this purpose and company.'))

    def write(self, vals):
        if 'destination_ids' in vals and any(r.state != 'draft' for r in self):
            raise UserError(_('Consented recipients are immutable after grant. Capture a new consent for new recipients.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_destinations()
        return records

    def action_grant(self):
        self.evidence_attachment_ids._health_encrypt_existing()
        result = super().action_grant()
        audit_event(self.env, 'consent_grant', self._name, self.ids)
        return result

    def action_withdraw(self):
        result = super().action_withdraw()
        audit_event(self.env, 'consent_withdrawal', self._name, self.ids)
        return result


class IdentityReview(models.Model):
    _inherit = 'res.partner'
    identity_exception = fields.Text(help='Approved documented reason for missing/nonstandard identity (e.g. emergency care, child, foreign patient).')
    identity_review = fields.Text(compute='_compute_identity_review', string='Identity Readiness')
    vneid_verified = fields.Boolean(string='VNeID Checked Manually',
        help='Manual staff assertion only; no government VNeID authentication is performed by this checkbox.')

    @api.depends('cccd_number', 'national_id', 'identity_exception')
    def _compute_identity_review(self):
        import re
        for row in self:
            issues = []
            if not row.cccd_number and not row.national_id:
                issues.append(_('No identity recorded; review lawful care/export exception.'))
            if row.cccd_number and not re.fullmatch(r'\d{12}', row.cccd_number):
                issues.append(_('CCCD must contain 12 digits; verify the document or record an approved exception.'))
            if row.cccd_number and row.national_id and row.cccd_number != row.national_id:
                issues.append(_('CCCD and national identity differ; review before external submission.'))
            if row.identity_exception:
                issues.append(_('A documented identity exception needs custodian approval for the specific destination.'))
            row.identity_review = '\n'.join(issues) or _('Format checks passed; identity ownership and authority verification remain separate.')


class ClaimSubmissionGuard(models.Model):
    _inherit = 'bhyt.claim'

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('state') in ('submitted', 'acked') for v in vals_list):
            raise UserError(_('BHXH submission and acknowledgement require an onboarded authority integration.'))
        rows = super().create(vals_list)
        if any(r.state in ('submitted', 'acked') for r in rows):
            raise UserError(_('BHXH acceptance cannot be supplied through defaults.'))
        return rows

    def write(self, vals):
        if vals.get('state') in ('submitted', 'acked'):
            raise UserError(_('BHXH submission and acknowledgement remain disabled until approved integration and test acceptance.'))
        return super().write(vals)


class NationalReceiptGuard(models.AbstractModel):
    _inherit = 'fhir.adapter.vn'

    def reconcile(self, receipt):
        if receipt.get('state', 'acked') in ('acked', 'submitted', 'sent'):
            raise UserError(_('National authority acknowledgement is unavailable without the approved government integration. File export is not acceptance.'))
        return super().reconcile(receipt)


class SubmissionLogGuard(models.Model):
    _inherit = 'fhir.submission.log'

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('adapter_code') == 'vn' and v.get('state') in ('submitted', 'acked') for v in vals_list):
            raise UserError(_('An exported Vietnam bundle cannot be recorded as government acceptance.'))
        rows = super().create(vals_list)
        if any(r.adapter_code == 'vn' and r.state in ('submitted', 'acked') for r in rows):
            raise UserError(_('Government acceptance cannot be supplied through defaults.'))
        return rows

    def write(self, vals):
        if vals.get('state') in ('submitted', 'acked') and any(r.adapter_code == 'vn' for r in self):
            raise UserError(_('National submission and acknowledgement require approved authority transport.'))
        return super().write(vals)


def _subject_path(env, model_name, depth=0, visited=()):
    if depth > 4 or model_name in visited:
        return None
    Model = env[model_name]
    for name in ('patient_id', 'client_id'):
        field = Model._fields.get(name)
        if field and field.type == 'many2one' and field.comodel_name == 'res.partner':
            return name
    for name in ('order_id', 'fso_id', 'visit_id', 'note_id', 'claim_id', 'submission_id', 'response_id', 'plan_id', 'careplan_id', 'case_id'):
        field = Model._fields.get(name)
        if field and field.type == 'many2one' and field.comodel_name.startswith(('health.', 'bhyt.')):
            tail = _subject_path(env, field.comodel_name, depth+1, visited+(model_name,))
            if tail:
                return name+'.'+tail
    return None


class HealthcareAudit(models.AbstractModel):
    _inherit = 'base'

    def _compliance_audited_model(self):
        transaction_models = {
            'crm.lead', 'sale.order', 'sale.order.line', 'account.move',
            'account.payment', 'product.pricelist', 'product.pricelist.item',
            'product.product', 'product.template', 'advanced.pricing.engine',
            'advanced.pricing.rule', 'res.users', 'biz.access.role',
        }
        return not self._transient and (
            self._name.startswith(('health.', 'bhyt.')) or self._name in transaction_models
        )

    def _fetch_query(self, query, fields):
        records = super()._fetch_query(query, fields)
        if self._compliance_audited_model():
            audit_event(self.env, 'fetch', self._name, records.ids, field_names=[f.name for f in fields])
        return records

    def read(self, fields=None, load='_classic_read'):
        try:
            result = super().read(fields=fields, load=load)
        except Exception:
            if self._compliance_audited_model():
                audit_event(self.env, 'read', self._name, self.ids, 'denied', fields)
            raise
        if self._compliance_audited_model():
            audit_event(self.env, 'read', self._name, self.ids, field_names=fields)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self._compliance_audited_model():
            audit_event(self.env, 'create', self._name, records.ids,
                        field_names={key for vals in vals_list for key in vals})
        return records

    def write(self, vals):
        try:
            result = super().write(vals)
        except Exception:
            if self._compliance_audited_model():
                audit_event(self.env, 'write', self._name, self.ids, 'denied', vals.keys())
            raise
        if self._compliance_audited_model():
            audit_event(self.env, 'write', self._name, self.ids, field_names=vals.keys())
        return result

    def unlink(self):
        if self._compliance_audited_model() and not self._name.startswith('health.compliance.'):
            path = _subject_path(self.env, self._name)
            if path:
                patients = self.sudo().mapped(path)
                if patients and self.env['health.compliance.hold'].sudo().search_count([('patient_id', 'in', patients.ids)]):
                    audit_event(self.env, 'unlink', self._name, self.ids, 'retention_refused')
                    raise UserError(_('An active legal/retention hold prevents deletion of these healthcare records.'))
        identifiers=self.ids
        result=super().unlink()
        if self._compliance_audited_model():
            audit_event(self.env, 'unlink', self._name, identifiers)
        return result


class AICodingPayloadEncryption(models.Model):
    _inherit = 'health.ai.coding.log'
    request_json_enc = fields.Text(readonly=True)
    response_json_enc = fields.Text(readonly=True)
    request_json = fields.Json(string='Request (redacted)', compute='_compute_payloads')
    response_json = fields.Json(string='Raw Response', compute='_compute_payloads')

    @api.depends('request_json_enc', 'response_json_enc')
    def _compute_payloads(self):
        for row in self:
            for name in ('request_json','response_json'):
                plaintext=phi_crypto.decrypt(self.env,row[name+'_enc'])
                row[name]=json.loads(plaintext) if plaintext else False

    @api.model_create_multi
    def create(self, vals_list):
        values=[]
        for vals in vals_list:
            vals=dict(vals)
            for name in ('request_json','response_json'):
                if name in vals:
                    raw=vals.pop(name)
                    vals[name+'_enc']=phi_crypto.encrypt(self.env,json.dumps(raw,ensure_ascii=False)) if raw else False
            values.append(vals)
        return super().create(values)


class FreeTextEgressProtection(models.Model):
    _inherit = 'ai.egress.log'

    @api.model
    def guard(self, prompt, classification, provider_type, endpoint=None, surface='unknown'):
        # A name in a free question cannot be reliably detected by a regex.
        # Fixed authored schema polishing remains available; arbitrary questions
        # need an explicitly reviewed local endpoint and processing basis.
        if surface.startswith('biz_bi.') or surface == 'learn.coach.composer':
            purpose = 'analytics'
            if (not egress.is_local_provider(provider_type, endpoint)
                    or not self.env['health.compliance.destination']._approved(endpoint, purpose)):
                audit_event(self.env, 'free_text_ai', self._name, [], 'unapproved_free_text_destination')
                raise egress.EgressRefused('unapproved_free_text_destination')
        return super().guard(prompt, classification, provider_type, endpoint=endpoint, surface=surface)
