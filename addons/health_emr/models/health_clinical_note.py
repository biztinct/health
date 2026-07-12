# -*- coding: utf-8 -*-
"""EMR record spine (Circular 13/2025 phase 1).

Turns `health.clinical.note` from editable scratch text into a legally-valid
electronic medical record entry: a clinician finalizes and signs it, after
which its content is immutable, sealed by a tamper-evident sha256 hash, and
corrections are appended as addenda (never overwrites).

Design precedents cloned:
  * Immutability write/unlink guards — `health.consent` evidence-lock
    (EVIDENCE_LOCKED_FIELDS + state-filtered UserError, NO superuser escape:
    uid 1 forces su=True, so a su bypass would void the lock entirely).
  * Deterministic hash — `fhir.adapter.vn` (sha256 over a fixed key order;
    volatile fields excluded so a re-hash of the sealed content reproduces it).

The narrative fields are PHI-encrypted computes (health_phi_encryption); they
decrypt transparently through the ORM, so the hash reads them normally (never
raw SQL).
"""
import hashlib
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# Current hashing scheme. Stored on each sealed note so a future algorithm
# change can be versioned without re-sealing historical records.
HASH_VERSION = 'v1'

# Fields frozen once the note is finalized. Signature/state/seal fields are
# included: they are SET by the finalizing write (which passes the guard
# because the record is still draft at guard time) and locked forever after.
# `signature_ref` is deliberately EXCLUDED — the Phase-3 CA digital signature
# attaches to an already-finalized record and must remain writable.
EMR_LOCKED_FIELDS = (
    'clinical_notes', 'diagnosis', 'treatment_performed',
    'medications_prescribed', 'vital_signs',
    'patient_condition_before', 'patient_condition_after',
    # The narrative fields above are non-stored computes over these encrypted
    # columns (health_phi_encryption). Freeze the ciphertext columns too so a
    # direct-to-storage write cannot bypass the lock. Harmless string entries
    # when encryption is not installed (they never appear in vals).
    'clinical_notes_enc', 'diagnosis_enc', 'treatment_performed_enc',
    'medications_prescribed_enc', 'vital_signs_enc',
    'patient_condition_before_enc', 'patient_condition_after_enc',
    'injection_count', 'medication_count', 'wound_count', 'iv_fluid_count',
    'image_ids',
    'emr_state', 'signed_by_id', 'signed_role', 'signed_datetime',
    'content_hash', 'hash_version', 'amends_note_id',
)

# Content fields that make up the sealed medical record, in the FIXED order the
# hash canonicalizes. Changing this tuple's membership/order is a hash-scheme
# change → bump HASH_VERSION.
_HASH_TEXT_FIELDS = (
    'clinical_notes', 'diagnosis', 'treatment_performed',
    'medications_prescribed', 'vital_signs',
    'patient_condition_before', 'patient_condition_after',
)
_HASH_COUNT_FIELDS = (
    'injection_count', 'medication_count', 'wound_count', 'iv_fluid_count',
)


class HealthClinicalNote(models.Model):
    _name = 'health.clinical.note'
    # Add the audit-trail mixins the base note lacked — the finalize event and
    # every tracked change land in chatter as Circular-13 audit evidence.
    _inherit = ['health.clinical.note', 'mail.thread', 'mail.activity.mixin']

    emr_state = fields.Selection(
        [('draft', 'Draft'), ('final', 'Finalized')],
        string='EMR Status', default='draft', required=True,
        tracking=True, copy=False, index=True,
        help='Draft notes are editable. A finalized note is a signed, '
             'immutable medical record.')
    signed_by_id = fields.Many2one(
        'res.users', string='Signed By', readonly=True, copy=False,
        tracking=True)
    signed_role = fields.Char(
        string='Signer Role', readonly=True, copy=False,
        help='Snapshot of the signer role at the moment of finalization.')
    signed_datetime = fields.Datetime(
        string='Signed On', readonly=True, copy=False, tracking=True)
    content_hash = fields.Char(
        string='Integrity Seal (SHA-256)', readonly=True, copy=False,
        help='Tamper-evident hash of the sealed content, computed at '
             'finalization. Anchors the Phase-3 CA digital signature.')
    hash_version = fields.Char(string='Seal Version', readonly=True, copy=False)
    signature_ref = fields.Char(
        string='Digital Signature Ref', readonly=True, copy=False,
        help='Reserved for the CA (VNPT-CA/Viettel-CA) digital signature '
             'attached to a finalized note (Phase 3).')

    amends_note_id = fields.Many2one(
        'health.clinical.note', string='Amends Note', copy=False,
        ondelete='restrict', index=True,
        help='Set on an addendum: the finalized note this one corrects or '
             'supplements. The original is never modified.')
    amendment_ids = fields.One2many(
        'health.clinical.note', 'amends_note_id', string='Addenda',
        readonly=True)
    is_amendment = fields.Boolean(
        string='Is Addendum', compute='_compute_is_amendment', store=True)

    @api.depends('amends_note_id')
    def _compute_is_amendment(self):
        for note in self:
            note.is_amendment = bool(note.amends_note_id)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('amends_note_id')
    def _check_amends(self):
        for note in self:
            target = note.amends_note_id
            if not target:
                continue
            if target.id == note.id:
                raise ValidationError(_('A clinical note cannot amend itself.'))
            if target.emr_state != 'final':
                raise ValidationError(_(
                    'An addendum can only amend a finalized (signed) note.'))
            if target.order_id.patient_id != note.order_id.patient_id:
                raise ValidationError(_(
                    'An addendum must concern the same patient as the note '
                    'it amends.'))

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------
    def action_finalize(self):
        """Finalize and sign the note(s): capture the signer, seal the content
        with a tamper-evident hash, and freeze it. Nurses have no write ACL on
        notes (only create), so the state write runs sudo AFTER an explicit
        authorization check — the pattern the PWA finalize endpoint mirrors."""
        for note in self:
            note._ensure_can_finalize()
            if note.emr_state != 'draft':
                raise UserError(_(
                    'This clinical note is already finalized.'))
            if not note._has_content():
                raise UserError(_(
                    'Cannot finalize an empty clinical note — record the '
                    'clinical content first.'))

            signer = note.env.user
            vals = {
                'emr_state': 'final',
                'signed_by_id': signer.id,
                'signed_role': note._role_name_of(signer),
                'signed_datetime': fields.Datetime.now(),
                'hash_version': HASH_VERSION,
            }
            # Seal over the about-to-be-final content + signature values (the
            # signed_datetime in vals, not the unset field). Computed sudo: the
            # hash traverses order_id.patient_id, and FSO read is catchment-
            # gated by record rule — a point-of-care nurse signing her own note
            # is not necessarily in that catchment. Authorization is already
            # settled by _ensure_can_finalize (author/head-nurse) above; the
            # signer stays the REAL user.
            vals['content_hash'] = note.sudo()._compute_content_hash(vals)
            # Guard passes: the record is still draft at guard-check time.
            note.sudo().write(vals)
            note.sudo().message_post(body=_(
                'Finalized & signed by %(signer)s (%(role)s) at %(ts)s. '
                'Integrity seal %(algo)s:%(hash)s…',
                signer=signer.name, role=vals['signed_role'],
                ts=fields.Datetime.to_string(vals['signed_datetime']),
                algo=HASH_VERSION, hash=vals['content_hash'][:12]))
        return True

    def _ensure_can_finalize(self):
        """Only the note author (self-sign) or a head-nurse+ (supervisory
        co-sign) may finalize. Deny-by-default."""
        self.ensure_one()
        user = self.env.user
        if user == self.author_id:
            return
        if user.has_group('health_base.group_healthcare_head_nurse'):
            return
        raise UserError(_(
            'Only the note author or a head nurse can finalize and sign this '
            'clinical note.'))

    def _has_content(self):
        self.ensure_one()
        if html2plaintext(self.clinical_notes or '').strip():
            return True
        for fname in _HASH_TEXT_FIELDS[1:]:  # skip clinical_notes (handled)
            if (self[fname] or '').strip():
                return True
        if any(self[c] for c in _HASH_COUNT_FIELDS):
            return True
        if self.image_ids:
            return True
        return False

    def _role_name_of(self, user):
        """Resolve a display role for `user`, mirroring _compute_author_role."""
        role = ''
        if user.access_role_id:
            role = user.access_role_id.name
        if not role:
            employee = self.env['hr.employee'].sudo().search(
                [('user_id', '=', user.id)], limit=1)
            if employee and employee.access_role_display:
                role = employee.access_role_display
        return role or 'Staff'

    # ------------------------------------------------------------------
    # Integrity seal
    # ------------------------------------------------------------------
    def _compute_content_hash(self, overrides=None):
        """Deterministic sha256 over the sealed content + identity + signature.
        `overrides` lets action_finalize hash values it is about to write
        (signed_datetime etc.) before they hit the DB. Recomputing later over
        the STORED fields (overrides=None) must reproduce the stored hash —
        that equality IS the tamper check."""
        self.ensure_one()
        overrides = overrides or {}

        def _scalar(fname):
            # overrides carry primitives (strings, datetimes); self carries the
            # stored field value.
            return overrides[fname] if fname in overrides else self[fname]

        def _id_of(fname):
            # overrides carry m2o values as ints; the ORM carries recordsets.
            if fname in overrides:
                val = overrides[fname]
                return int(val) if val else 0
            rec = self[fname]
            return rec.id if rec else 0

        signed_dt = _scalar('signed_datetime')
        payload = {
            'note_id': self.id,
            'order_id': self.order_id.id,
            'patient_id': self.order_id.patient_id.id,
            'author_id': self.author_id.id,
            'amends_note_id': _id_of('amends_note_id'),
            'signed_by_id': _id_of('signed_by_id'),
            'signed_role': _scalar('signed_role') or '',
            'signed_datetime': fields.Datetime.to_string(signed_dt) if signed_dt else '',
            # Content — read through the ORM (PHI decrypts transparently).
            'text': {f: (self[f] or '') for f in _HASH_TEXT_FIELDS},
            'counts': {f: int(self[f] or 0) for f in _HASH_COUNT_FIELDS},
            # Image content, not just ids: ir.attachment.checksum is the sha1 of
            # the bytes, so a swapped image is detectable. Drop any falsy
            # checksum (e.g. URL attachments) so sorted() never compares
            # str vs bool.
            'images': sorted(filter(None, self.image_ids.mapped('checksum'))),
        }
        canonical = json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def verify_integrity(self):
        """Return True iff a finalized note's stored seal matches a fresh hash
        of its current stored content (tamper check). Non-finalized → True
        (nothing sealed yet)."""
        self.ensure_one()
        if self.emr_state != 'final' or not self.content_hash:
            return True
        return self._compute_content_hash() == self.content_hash

    # ------------------------------------------------------------------
    # Immutability guards (clone of health.consent evidence-lock)
    # ------------------------------------------------------------------
    def write(self, vals):
        locked = [f for f in EMR_LOCKED_FIELDS if f in vals]
        if locked:
            # No superuser escape (uid 1 forces su=True) — an EMR whose signed
            # records can be silently altered is worse than none.
            frozen = self.filtered(lambda n: n.emr_state == 'final')
            if frozen:
                raise UserError(_(
                    'This clinical note is finalized and signed (%(names)s); '
                    'its content is a locked medical record and cannot be '
                    'changed. Create an addendum to add or correct '
                    'information.',
                    names=', '.join(frozen.mapped('display_name'))))
        return super().write(vals)

    def unlink(self):
        frozen = self.filtered(lambda n: n.emr_state == 'final')
        if frozen:
            raise UserError(_(
                'Finalized clinical notes are permanent medical records and '
                'cannot be deleted (%(names)s). Archive the record instead.',
                names=', '.join(frozen.mapped('display_name'))))
        return super().unlink()
