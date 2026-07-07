# -*- coding: utf-8 -*-
"""Vietnam EMR adapter (Circular 13/2025) — architecture-interop.md §3/§3.1.

Builds a per-patient FHIR R4 EMR Bundle by REUSING the facade's REGISTRY
serializers (one canonical mapping, never a second), adds bundle-only
ICD-10 Condition entries from the clinical-note coding sidecar, runs a VN
profile validation, and exports the bundle as a downloadable attachment on
an audit submission-log row. Transport is file export (the national LGSP
endpoints are not open yet); transform/reconcile are trivial but tested,
ready for the LGSP day."""

import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.health_fhir_core.serializers import REGISTRY, fso_common
from odoo.addons.health_fhir_core.serializers.base import fhir_instant

ICD10_SYSTEM = 'http://hl7.org/fhir/sid/icd-10'
CONDITION_CLINICAL_SYSTEM = (
    'http://terminology.hl7.org/CodeSystem/condition-clinical')

# Facade resource types collected into the patient bundle (Patient itself is
# added separately via read_record). Each is pulled with the serializer's own
# `patient` search-param domain so the field paths stay canonical.
BUNDLE_RESOURCE_TYPES = (
    'Encounter', 'Observation', 'CarePlan', 'Goal', 'MedicationRequest',
    'MedicationAdministration', 'QuestionnaireResponse', 'AdverseEvent',
    'Flag', 'Consent', 'DocumentReference',
)

EXPORT_GROUPS = (
    'health_base.group_healthcare_operations_manager',
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)


class FhirAdapterVN(models.AbstractModel):
    _name = 'fhir.adapter.vn'
    _inherit = 'fhir.country.adapter'
    _description = 'Vietnam FHIR EMR Adapter'
    adapter_code = 'vn'
    adapter_name = 'Vietnam (Circular 13/2025)'

    # ------------------------------------------------------------------
    # Bundle builder
    # ------------------------------------------------------------------
    def build_patient_bundle(self, patient):
        """Canonical patient EMR Bundle (type=collection) dict."""
        patient.ensure_one()
        env = self.env
        resources = []

        patient_serializer = REGISTRY['Patient']
        patient_record = patient_serializer.read_record(env, patient.id)
        if patient_record:
            resources.append(
                patient_serializer.serialize_batch(patient_record)[0])

        for rtype in BUNDLE_RESOURCE_TYPES:
            serializer = REGISTRY[rtype]
            # Reuse the serializer's own `patient` search-param domain — one
            # canonical field path, no guessing / no drift.
            patient_domain = serializer.search_params['patient']['domain'](
                'Patient/%s' % patient.id)
            records = env[serializer.odoo_model].search(
                serializer.base_domain(env) + patient_domain)
            resources.extend(serializer.serialize_batch(records))

        resources.extend(self._condition_resources(patient))

        # Deterministic ordering → stable sha256 (numeric ids first, in order).
        resources.sort(key=self._resource_sort_key)
        return {
            'resourceType': 'Bundle',
            'type': 'collection',
            'timestamp': fhir_instant(fields.Datetime.now()),
            'entry': [{
                'fullUrl': 'urn:health19:%s/%s' % (
                    resource['resourceType'], resource['id']),
                'resource': resource,
            } for resource in resources],
        }

    @staticmethod
    def _resource_sort_key(resource):
        rid = str(resource.get('id', ''))
        ordinal = (0, int(rid)) if rid.isdigit() else (1, rid)
        return (resource.get('resourceType', ''), ordinal)

    def _condition_resources(self, patient):
        """Bundle-only Condition per (clinical note, ICD-10 code) from the
        terminology sidecar."""
        env = self.env
        notes = env['health.clinical.note'].search(
            [('order_id.patient_id', '=', patient.id)])
        encounter_serializer = REGISTRY['Encounter']
        conditions = []
        for note in notes:
            for code in note.condition_code_ids:
                condition = {
                    'resourceType': 'Condition',
                    'id': 'cond-%s-%s' % (note.id, code.id),
                    'clinicalStatus': {
                        'coding': [{
                            'system': CONDITION_CLINICAL_SYSTEM,
                            'code': 'active',
                        }],
                    },
                    'code': {
                        'coding': [{
                            'system': ICD10_SYSTEM,
                            'code': code.code,
                            'display': code.display,
                        }],
                        'text': code.display_vi or code.display,
                    },
                    'subject': {
                        'reference': 'Patient/%s' % patient.id,
                        'display': patient.name,
                    },
                }
                if note.create_date:
                    condition['recordedDate'] = fhir_instant(note.create_date)
                encounter = fso_common.encounter_ref_if_qualifies(
                    encounter_serializer, note.order_id)
                if encounter:
                    condition['encounter'] = encounter
                conditions.append(condition)
        return conditions

    @staticmethod
    def bundle_sha256(bundle):
        """Deterministic content hash — canonical JSON with the volatile
        `timestamp` excluded (so re-building the same data yields the same
        sha, which the export/integrity contract relies on)."""
        hashable = {key: value for key, value in bundle.items()
                    if key != 'timestamp'}
        return hashlib.sha256(json.dumps(
            hashable, sort_keys=True, ensure_ascii=False).encode('utf-8')
        ).hexdigest()

    # ------------------------------------------------------------------
    # VN profile validation
    # ------------------------------------------------------------------
    def validate_vn_profile(self, bundle, patient):
        """Return a list of {severity, code, message} issues. Errors do NOT
        block export — a facility must see its own gaps."""
        env = self.env
        issues = []
        # national_id / cccd_number are PHI-encrypted computes — plain ORM
        # reads (they decrypt transparently), never raw SQL.
        if not (patient.national_id or patient.cccd_number):
            issues.append({
                'severity': 'error', 'code': 'patient-no-national-id',
                'message': 'Patient has no national ID (CCCD) on file.'})
        facility = patient.primary_facility_id
        if not facility or not facility.moh_facility_code:
            issues.append({
                'severity': 'error', 'code': 'facility-no-moh-code',
                'message': "Patient's primary facility has no MOH facility "
                           'code (mã cơ sở KCB).'})
        has_notes = bool(env['health.clinical.note'].search_count(
            [('order_id.patient_id', '=', patient.id)]))
        condition_count = sum(
            1 for entry in bundle.get('entry', [])
            if entry['resource'].get('resourceType') == 'Condition')
        if has_notes and not condition_count:
            issues.append({
                'severity': 'warning', 'code': 'encounter-uncoded-diagnosis',
                'message': 'Patient has clinical notes but no ICD-10 coded '
                           'diagnoses (coding-density gap).'})
        has_consent = env['health.consent'].with_context(
            consent_check_source='fhir_vn_export').check_consent(
            patient, 'service')
        if not has_consent:
            issues.append({
                'severity': 'warning', 'code': 'no-consent-on-file',
                'message': 'No active service consent on file for this '
                           'patient.'})
        return issues

    @staticmethod
    def format_issues(issues):
        return '\n'.join(
            '[%s] %s: %s' % (issue['severity'].upper(), issue['code'],
                             issue['message'])
            for issue in issues)

    # ------------------------------------------------------------------
    # Country-adapter interface
    # ------------------------------------------------------------------
    def transform(self, bundle):
        # VN phase A: canonical FHIR IS the payload (identity).
        return bundle

    def transport(self, payload):
        # No live LGSP endpoint yet — file export only. The receipt records
        # that the bundle was exported; real submission lands here on the
        # LGSP day.
        return {'state': 'exported'}

    def reconcile(self, receipt):
        """Map an ack/error receipt back onto a submission-log row.
        Receipt carries the log id + resulting state/refs."""
        log = self.env['fhir.submission.log'].browse(
            receipt.get('submission_log_id'))
        if not log.exists():
            return log
        vals = {'state': receipt.get('state', 'acked')}
        if receipt.get('receipt_ref'):
            vals['receipt_ref'] = receipt['receipt_ref']
        if receipt.get('error_text'):
            vals['error_text'] = receipt['error_text']
        log.write(vals)
        return log

    # ------------------------------------------------------------------
    # Export orchestration
    # ------------------------------------------------------------------
    def _check_export_allowed(self):
        user = self.env.user
        if self.env.su or user._is_admin():
            return
        if not any(user.has_group(group) for group in EXPORT_GROUPS):
            raise AccessError(_(
                'Only operations managers and above may export EMR '
                'bundles.'))

    def export_patient_bundle(self, patient):
        """Build → validate → transform → log + attach. Returns the
        fhir.submission.log record."""
        patient.ensure_one()
        self._check_export_allowed()
        env = self.env
        bundle = self.build_patient_bundle(patient)
        issues = self.validate_vn_profile(bundle, patient)
        payload = self.transform(bundle)
        sha = self.bundle_sha256(payload)
        # Create in draft, attach, then flip to exported — the attachment_id
        # write happens while still draft, before the evidence-lock engages.
        log = env['fhir.submission.log'].create({
            'adapter_code': self.adapter_code,
            'patient_id': patient.id,
            'bundle_sha256': sha,
            'entry_count': len(payload.get('entry', [])),
            'issue_text': self.format_issues(issues) or False,
            'exported_by_id': env.uid,
            'exported_at': fields.Datetime.now(),
        })
        attachment = env['ir.attachment'].create({
            'name': 'emr_vn_%s_%s.json' % (patient.id, log.name),
            'res_model': 'fhir.submission.log',
            'res_id': log.id,
            'type': 'binary',
            'mimetype': 'application/fhir+json',
            'raw': json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        })
        log.write({'attachment_id': attachment.id, 'state': 'exported'})
        return log
