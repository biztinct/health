# -*- coding: utf-8 -*-
"""``health.ai.code.suggestion`` — the AI retro-coding review queue.

An LLM reads the (redacted) free text of a clinical note and SUGGESTS ICD-10
codes; a doctor or head nurse approves or rejects. Approving is the ONLY thing
that writes a code onto ``clinical_note.condition_code_ids`` — the AI never
writes a code, not even at confidence 1.0.

The nightly ``cron_ai_coding_sweep`` (03:00 ICT) walks un-coded notes,
consent-gates each, builds a pseudonymised prompt, calls the configured
``bi.ai.provider`` in JSON mode, validates every proposed code against the
``medical.code`` catalog, and files one review row per (note, code). The
sweep is defensive by construction: every note runs in its own savepoint, a
provider/parse error just marks the attempt and moves on, and it must end
green with Ollama down (vietuat's reality).
"""
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# Fixed system prompt (vi + en) — never tuned from the UI (handover §2.4).
_SYSTEM_PROMPT = (
    "Bạn là trợ lý mã hóa lâm sàng. Nhiệm vụ: đọc văn bản lâm sàng tiếng Việt "
    "hoặc tiếng Anh và đề xuất các mã ICD-10 CÓ MẶT trong văn bản.\n"
    "You are a clinical coding assistant. Read the Vietnamese or English "
    "clinical text and suggest ICD-10 codes PRESENT in the text.\n\n"
    "Return ONLY a JSON object of the form:\n"
    '{"codes": [{"code": "<ICD-10 code>", "confidence": <0-1>, '
    '"evidence": "<verbatim fragment, <=20 words, from the text>"}]}\n\n'
    "Rules:\n"
    "- Only codes clearly supported by the text. Never invent codes.\n"
    "- confidence is your certainty from 0 to 1.\n"
    "- evidence must be a short verbatim quote (<=20 words) from the text.\n"
    '- Return {"codes": []} when nothing is codable.\n'
    "- Output JSON only, no prose, no markdown."
)

_DEFAULTS = {
    'batch_cap': 25,
    'max_prompt_chars': 4000,
    'max_attempts': 3,
}


class HealthAiCodeSuggestion(models.Model):
    _name = 'health.ai.code.suggestion'
    _description = 'AI ICD-10 Code Suggestion'
    _order = 'confidence desc, id desc'
    _rec_name = 'code_id'

    note_id = fields.Many2one(
        'health.clinical.note', string='Clinical Note',
        required=True, index=True, ondelete='cascade')
    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Service Order',
        related='note_id.order_id', store=True, index=True)
    patient_id = fields.Many2one(
        'res.partner', string='Patient',
        related='note_id.order_id.patient_id', store=True, index=True)
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Province',
        compute='_compute_catchment_province_id', store=True, index=True)
    code_id = fields.Many2one(
        'medical.code', string='ICD-10 Code', required=True,
        ondelete='cascade', domain="[('system_id.code', '=', 'icd10')]")
    code_display = fields.Char(
        related='code_id.display_name', string='Code', store=False)
    confidence = fields.Float(
        string='Confidence', digits=(3, 2),
        help='The model\'s certainty, 0-1 (shown as %).')
    confidence_pct = fields.Integer(
        string='Confidence %', compute='_compute_confidence_pct')
    evidence = fields.Char(
        string='Evidence', size=200,
        help='The redacted note fragment that triggered the code.')
    state = fields.Selection([
        ('suggested', 'Suggested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='suggested', required=True, index=True)
    reviewed_by = fields.Many2one('res.users', string='Reviewed By', readonly=True)
    reviewed_at = fields.Datetime(string='Reviewed At', readonly=True)
    log_id = fields.Many2one(
        'health.ai.coding.log', string='Source Call', ondelete='set null')

    # Readonly source text for the reviewer's form (the clinician judges the
    # suggestion against the note). These are non-stored relateds onto the
    # note's PHI compute fields — display only, never persisted here.
    note_diagnosis = fields.Text(
        related='note_id.diagnosis', string='Diagnosis', readonly=True)
    note_clinical_notes = fields.Html(
        related='note_id.clinical_notes', string='Clinical Notes', readonly=True)
    note_date = fields.Datetime(
        related='note_id.create_date', string='Note Date', store=True)

    @api.depends('patient_id', 'patient_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = rec.patient_id.catchment_province_id

    @api.depends('confidence')
    def _compute_confidence_pct(self):
        for rec in self:
            rec.confidence_pct = int(round((rec.confidence or 0.0) * 100))

    # ==================================================================
    # Config helpers
    # ==================================================================
    @api.model
    def _cfg(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(
            'health_ai_coding.%s' % key)

    @api.model
    def _cfg_bool(self, key):
        return str(self._cfg(key)).lower() in ('1', 'true', 'yes')

    @api.model
    def _cfg_int(self, key):
        val = self._cfg(key)
        try:
            return int(val) if val not in (None, False, '') else _DEFAULTS[key]
        except (TypeError, ValueError):
            return _DEFAULTS[key]

    @api.model
    def _provider(self):
        """The configured bi.ai.provider, or empty recordset."""
        raw = self._cfg('provider_id')
        if raw:
            try:
                provider = self.env['bi.ai.provider'].browse(int(raw)).exists()
                if provider:
                    return provider
            except (TypeError, ValueError):
                pass
        return self.env['bi.ai.provider']

    # ==================================================================
    # Redaction (handover §2.3) — plain string ops, no NLP, keep it dumb.
    # ==================================================================
    @api.model
    def _redact(self, text, patient):
        """Pseudonymise: strip the patient's name (and each name token >=3
        chars), phone, mobile, email, street & vietnamese_address; collapse
        whitespace; truncate to max_prompt_chars. The SAME string goes to the
        model and into the log."""
        if not text:
            return ''
        result = text
        # Longest, most-specific values first so a name inside an address is
        # not half-replaced.
        pairs = []
        if patient:
            for val in (patient.vietnamese_address, patient.street):
                if val and len(val.strip()) >= 3:
                    pairs.append((val.strip(), '[ĐC]'))
            if patient.email and patient.email.strip():
                pairs.append((patient.email.strip(), '[EMAIL]'))
            for val in (patient.phone, patient.mobile):
                if val and val.strip():
                    pairs.append((val.strip(), '[SĐT]'))
            if patient.name and patient.name.strip():
                pairs.append((patient.name.strip(), '[BN]'))
        pairs.sort(key=lambda kv: len(kv[0]), reverse=True)
        for needle, token in pairs:
            result = re.sub(re.escape(needle), token, result, flags=re.IGNORECASE)
        # Then each name token >=3 chars, to catch partial mentions.
        if patient and patient.name:
            for tok in re.split(r'\s+', patient.name.strip()):
                if len(tok) >= 3:
                    result = re.sub(
                        r'\b%s\b' % re.escape(tok), '[BN]', result,
                        flags=re.IGNORECASE)
        result = re.sub(r'\s+', ' ', result).strip()
        cap = self._cfg_int('max_prompt_chars')
        if len(result) > cap:
            result = result[:cap]
        return result

    @api.model
    def _build_user_prompt(self, note):
        """Assemble + redact the note's free-text fields into the user
        message. Returns '' when there is nothing to code."""
        patient = note.order_id.patient_id
        parts = []
        if note.diagnosis:
            parts.append('Chẩn đoán / Diagnosis: %s' % note.diagnosis)
        if note.clinical_notes:
            parts.append('Ghi chú / Notes: %s' % html2plaintext(note.clinical_notes))
        if note.treatment_performed:
            parts.append('Điều trị / Treatment: %s' % note.treatment_performed)
        if note.patient_condition_after:
            parts.append('Tình trạng sau / Condition after: %s'
                         % note.patient_condition_after)
        return self._redact('\n'.join(parts), patient)

    # ==================================================================
    # Response parsing
    # ==================================================================
    @staticmethod
    def _parse_items(raw):
        """Parse the model's JSON into a list of {code, confidence, evidence}
        dicts. Returns (items, error) — error is '' on success. Accepts a bare
        array, a {"codes": [...]} object, or an object whose first list value
        is the array (JSON-mode providers wrap arrays in an object)."""
        text = (raw or '').strip()
        if not text:
            return [], 'empty response'
        if text.startswith('```'):
            text = text.strip('`')
            if text[:4].lower() == 'json':
                text = text[4:]
        # Locate the outermost JSON value.
        candidates = []
        for op, cl in (('[', ']'), ('{', '}')):
            start, end = text.find(op), text.rfind(cl)
            if start != -1 and end != -1 and end > start:
                candidates.append((start, text[start:end + 1]))
        candidates.sort()
        for _start, blob in candidates:
            try:
                data = json.loads(blob)
            except (ValueError, TypeError):
                continue
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)], ''
            if isinstance(data, dict):
                if isinstance(data.get('codes'), list):
                    return [d for d in data['codes'] if isinstance(d, dict)], ''
                for value in data.values():
                    if isinstance(value, list):
                        return [d for d in value if isinstance(d, dict)], ''
                return [], ''  # valid object, no code list → nothing codable
        return [], 'no JSON array/object in response'

    # ==================================================================
    # Nightly sweep (handover §2.2)
    # ==================================================================
    @api.model
    def cron_ai_coding_sweep(self):
        if not self._cfg_bool('enabled'):
            _logger.info('AI coding sweep: disabled (config param off).')
            return True

        provider = self._provider()
        if not provider:
            _logger.warning('AI coding sweep: no provider configured — skipped.')
            return True
        if provider.provider != 'ollama' and not self._cfg_bool('allow_cloud'):
            _logger.warning(
                'AI coding sweep: provider %s is not Ollama and allow_cloud is '
                'off — refusing to call a cloud model.', provider.name)
            return True

        notes = self._eligible_notes()
        if not notes:
            _logger.info('AI coding sweep: no eligible notes.')
            return True

        processed = suggested = errors = 0
        for note in notes:
            try:
                with self.env.cr.savepoint():
                    created, ok = self._process_note(note, provider)
                    suggested += created
                    if not ok:
                        errors += 1
                processed += 1
            except Exception as exc:  # noqa: BLE001 — one bad note must not abort
                _logger.warning('AI coding sweep: note %s failed: %s',
                                note.id, exc)
                errors += 1
        _logger.info('AI coding sweep: notes=%s suggestions=%s errors=%s',
                     processed, suggested, errors)
        return True

    @api.model
    def _eligible_notes(self):
        """Un-coded notes with free text, no prior suggestion, attempts left,
        newest first, capped at batch_cap.

        PHI gotcha: ``diagnosis`` / ``clinical_notes`` are non-stored compute
        fields (health_phi_encryption) — they CANNOT be filtered in an ORM
        domain. When encryption is installed we filter the stored ``*_enc``
        backing columns (non-empty iff the plaintext was non-empty); otherwise
        the plaintext columns are searchable.
        """
        Note = self.env['health.clinical.note']
        if 'diagnosis_enc' in Note._fields:
            text_domain = ['|', ('diagnosis_enc', '!=', False),
                           ('clinical_notes_enc', '!=', False)]
        else:
            text_domain = ['|', ('diagnosis', '!=', False),
                           ('clinical_notes', '!=', False)]
        domain = [
            ('condition_code_ids', '=', False),
            ('ai_attempts', '<', self._cfg_int('max_attempts')),
        ] + text_domain
        # Exclude notes that already have any suggestion row (build the clause
        # conditionally — an empty 'not in []' is a no-op we simply omit).
        already = self.sudo().search([]).mapped('note_id').ids
        if already:
            domain.append(('id', 'not in', already))
        return Note.sudo().search(
            domain, order='create_date desc, id desc',
            limit=self._cfg_int('batch_cap'))

    def _process_note(self, note, provider):
        """Process ONE note. Returns (suggestions_created, ok). ``ok`` is False
        on a consent skip / provider error / parse error. Runs inside the
        caller's savepoint."""
        patient = note.order_id.patient_id
        # 1. consent gate — deny-by-default; the check log row is the evidence.
        if not self.env['health.consent'].check_consent(patient, 'data_sharing'):
            note._mark_ai_attempt()
            return 0, False
        # 2. redacted prompt
        user_prompt = self._build_user_prompt(note)
        if not user_prompt:
            note._mark_ai_attempt()
            return 0, True
        # 3. call the model
        started = fields.Datetime.now()
        raw = ''
        try:
            raw = provider._complete(_SYSTEM_PROMPT, user_prompt, force_json=True)
        except Exception as exc:  # noqa: BLE001 — sweep survives Ollama down
            note._mark_ai_attempt()
            self._create_log(note, provider, user_prompt, raw, started,
                             0, 0, str(exc))
            return 0, False
        # 4. parse + validate
        items, parse_err = self._parse_items(raw)
        if parse_err:
            note._mark_ai_attempt()
            self._create_log(note, provider, user_prompt, raw, started,
                             0, 0, parse_err)
            return 0, False
        final, dropped = self._validate_items(note, items)
        # 5. one log row, then the suggestion rows referencing it.
        log = self._create_log(note, provider, user_prompt, raw, started,
                               len(final), dropped, '')
        for vals in final:
            vals.update({'note_id': note.id, 'log_id': log.id,
                         'state': 'suggested'})
            self.sudo().create(vals)
        # attempts: leave untouched when we actually produced suggestions (the
        # "no prior suggestion" scope excludes the note next run); mark the
        # attempt otherwise so an un-codable note is not retried forever.
        if not final:
            note._mark_ai_attempt()
        return len(final), True

    def _validate_items(self, note, items):
        """Resolve each proposed code against the ICD-10 catalog; drop unknown
        codes (counted) and de-dup against codes already on the note and codes
        already suggested. Returns (vals_list, dropped_count)."""
        existing = set(note.condition_code_ids.ids)
        existing |= set(self.sudo().search(
            [('note_id', '=', note.id)]).mapped('code_id').ids)
        final, dropped, seen = [], 0, set()
        for item in items:
            code = (item.get('code') or '').strip()
            if not code:
                continue
            rec = self.env['medical.code'].get('icd10', code)
            if not rec:
                dropped += 1
                continue
            if rec.id in existing or rec.id in seen:
                continue
            seen.add(rec.id)
            final.append({
                'code_id': rec.id,
                'confidence': self._coerce_confidence(item.get('confidence')),
                'evidence': (item.get('evidence') or '')[:200],
            })
        return final, dropped

    @staticmethod
    def _coerce_confidence(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @api.model
    def _create_log(self, note, provider, user_prompt, raw, started,
                    suggested_count, dropped, error):
        duration = int((fields.Datetime.now() - started).total_seconds() * 1000)
        return self.env['health.ai.coding.log'].sudo().create({
            'note_id': note.id,
            'provider_id': provider.id,
            'request_json': {'system': _SYSTEM_PROMPT, 'user': user_prompt},
            'response_json': {'raw': raw},
            'duration_ms': duration,
            'suggested_count': suggested_count,
            'dropped_codes': dropped,
            'error': error or False,
        })

    # ==================================================================
    # Review actions (handover §2.1)
    # ==================================================================
    _APPROVER_GROUPS = (
        'health_base.group_healthcare_doctor',
        'health_base.group_healthcare_head_nurse',
        'health_base.group_healthcare_manager',
        'health_base.group_healthcare_admin',
        'health_base.group_healthcare_owner',
    )

    def _check_approver(self):
        """Server-side guard (not just the view): approve/reject is doctor +
        head-nurse and manager-up only."""
        if any(self.env.user.has_group(g) for g in self._APPROVER_GROUPS):
            return
        raise AccessError(_(
            "Only a doctor, head nurse, or manager may approve or reject AI "
            "code suggestions."))

    def action_approve(self):
        """Append the code to the note's coded sidecar and stamp the review.
        Multi-safe: each row in its own try/except so one bad note does not
        abort a batch approve."""
        self._check_approver()
        approved = self.env['health.ai.code.suggestion']
        for rec in self:
            if rec.state != 'suggested':
                continue
            try:
                with self.env.cr.savepoint():
                    rec.note_id.sudo().write({
                        'condition_code_ids': [(4, rec.code_id.id)]})
                    rec.sudo().write({
                        'state': 'approved',
                        'reviewed_by': self.env.uid,
                        'reviewed_at': fields.Datetime.now(),
                    })
                approved |= rec
            except Exception as exc:  # noqa: BLE001 — one bad row, batch survives
                _logger.warning('AI coding approve: suggestion %s failed: %s',
                                rec.id, exc)
        return True

    def action_reject(self):
        """State + reviewer stamp only; the sidecar is untouched."""
        self._check_approver()
        self.filtered(lambda r: r.state == 'suggested').sudo().write({
            'state': 'rejected',
            'reviewed_by': self.env.uid,
            'reviewed_at': fields.Datetime.now(),
        })
        return True
