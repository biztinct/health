"""Transparent authenticated encryption of sensitive attachment bytes.

Plaintext checksum semantics are preserved so historical clinical seals remain
verifiable. Encrypted HTTP downloads use data streams, never ciphertext paths.
"""
import os
import tempfile
from contextvars import ContextVar

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from odoo import _, api, models
from odoo.exceptions import UserError
from . import phi_crypto

MAGIC = b'H19ATT\x01\x00'
_ENCRYPTING = ContextVar('health_sensitive_attachment', default=False)


def _seal(env, data):
    nonce = os.urandom(12)
    key, _ = phi_crypto._get_keys(env)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, data, MAGIC)


def _open(env, data):
    if not data.startswith(MAGIC):
        return data
    key, _ = phi_crypto._get_keys(env)
    offset = len(MAGIC)
    return AESGCM(key).decrypt(data[offset:offset + 12], data[offset + 12:], MAGIC)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _health_sensitive(self, values=None):
        values = values or {}
        model = values.get('res_model') or (self.res_model if len(self) == 1 else '') or ''
        return (model.startswith('health.') or model.startswith('bhyt.')
                or model in ('res.partner', 'account.move')
                or (len(self) == 1 and (self.store_fname or '').startswith('hphi/')))

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            if self._health_sensitive(values) and values.get('public'):
                raise UserError(_('Sensitive healthcare attachments cannot be public.'))
            token = _ENCRYPTING.set(self._health_sensitive(values))
            try:
                records |= super().create([values])
            finally:
                _ENCRYPTING.reset(token)
        for record in records:
            if record._health_sensitive():
                if record.public:
                    raise UserError(_('Sensitive healthcare attachments cannot be public.'))
                record._health_encrypt_existing()
        return records

    def _health_encrypt_existing(self):
        for record in self:
            if not (record.store_fname or '').startswith('hphi/') and record.raw:
                token = _ENCRYPTING.set(True)
                try:
                    super(IrAttachment, record).write({'raw': record.raw, 'mimetype': record.mimetype,
                                                       'public': False, 'index_content': False})
                finally:
                    _ENCRYPTING.reset(token)

    def _health_check_evidence_lock(self):
        for attachment in self:
            Note = self.env['health.clinical.note']
            if 'emr_state' in Note._fields:
                Note.flush_model(['emr_state', 'image_ids'])
                self.env.cr.execute('''SELECT 1 FROM health_clinical_note n
                    JOIN health_clinical_note_image_rel i ON i.note_id=n.id
                    WHERE n.emr_state='final' AND i.attachment_id=%s LIMIT 1''',
                    (attachment.id,))
                if self.env.cr.fetchone():
                    raise UserError(_('Attachments of finalized clinical notes cannot be replaced or deleted.'))
            if attachment.res_model == 'health.clinical.note' and attachment.res_id:
                note = self.env['health.clinical.note'].sudo().browse(attachment.res_id).exists()
                if note and 'emr_state' in note._fields and note.emr_state == 'final':
                    raise UserError(_('Attachments of finalized clinical notes cannot be replaced or deleted.'))
            if 'health.consent' in self.env.registry.models:
                self.env['health.consent'].flush_model(['state', 'evidence_attachment_ids'])
                self.env.cr.execute('''SELECT 1 FROM health_consent c
                    LEFT JOIN health_consent_attachment_rel r ON r.consent_id=c.id
                    WHERE c.state <> 'draft' AND (r.attachment_id=%s OR
                    (%s='health.consent' AND c.id=%s)) LIMIT 1''',
                    (attachment.id, attachment.res_model or '', attachment.res_id or 0))
                if self.env.cr.fetchone():
                    raise UserError(_('Granted consent evidence cannot be replaced or deleted.'))

    def write(self, vals):
        if vals.get('public') and any(a._health_sensitive(vals) for a in self):
            raise UserError(_('Sensitive healthcare attachments cannot be public.'))
        if {'raw', 'datas', 'db_datas', 'store_fname', 'checksum', 'res_model', 'res_id'} & vals.keys():
            self._health_check_evidence_lock()
        result = True
        for attachment in self:
            token = _ENCRYPTING.set(attachment._health_sensitive(vals))
            try:
                result = super(IrAttachment, attachment).write(vals) and result
            finally:
                _ENCRYPTING.reset(token)
        for record in self:
            if record._health_sensitive():
                record._health_encrypt_existing()
        return result

    def unlink(self):
        self._health_check_evidence_lock()
        return super().unlink()

    def _get_datas_related_values(self, data, mimetype):
        values = super()._get_datas_related_values(data, mimetype)
        if _ENCRYPTING.get() and data:
            values['index_content'] = False
            if self._storage() == 'db':
                values['db_datas'] = _seal(self.env, data)
        return values

    @api.model
    def _get_path(self, bin_data, sha):
        if not _ENCRYPTING.get():
            return super()._get_path(bin_data, sha)
        fname = 'hphi/' + sha[:2] + '/' + sha
        path = self._full_path(fname)
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        if os.path.isfile(path) and not self._same_content(bin_data, path):
            raise UserError(_('The attachment collides with an existing encrypted file.'))
        return fname, path

    @api.model
    def _same_content(self, bin_data, filepath):
        with open(filepath, 'rb') as source:
            raw = source.read()
        return _open(self.env, raw) == bin_data

    @api.model
    def _file_write(self, bin_value, checksum):
        if not _ENCRYPTING.get():
            return super()._file_write(bin_value, checksum)
        fname, path = self._get_path(bin_value, checksum)
        if not os.path.exists(path):
            fd, temporary = tempfile.mkstemp(prefix='.encrypt-', dir=os.path.dirname(path))
            try:
                with os.fdopen(fd, 'wb') as output:
                    output.write(_seal(self.env, bin_value))
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, path)
                self._mark_for_gc(fname)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return fname

    @api.model
    def _file_read(self, fname, size=None):
        data = super()._file_read(fname)
        data = _open(self.env, data)
        return data if size is None else data[:size]

    @api.depends('store_fname', 'db_datas')
    def _compute_raw(self):
        super()._compute_raw()
        for attachment in self:
            if attachment.raw and attachment.raw.startswith(MAGIC):
                attachment.raw = _open(self.env, attachment.raw)

    def _to_http_stream(self):
        stream = super()._to_http_stream()
        if (self.store_fname or '').startswith('hphi/') or (
                self.db_datas and self.db_datas.startswith(MAGIC)):
            stream.type = 'data'
            stream.data = self.raw
            stream.path = None
            stream.size = len(stream.data)
        return stream

    @api.model
    def _migrate_health_attachment_encryption(self, limit=200):
        """Bounded privileged maintenance; never change sealed content/checksum."""
        candidates = self.sudo().search([
            ('type', '=', 'binary'), ('file_size', '>', 0), ('res_model', '!=', False),
            ('store_fname', 'not like', 'hphi/%'),
            '|', '|', ('res_model', '=like', 'health.%'),
            ('res_model', '=like', 'bhyt.%'),
            ('res_model', 'in', ['res.partner', 'account.move']),
            '|', ('res_field', '=', False), ('res_field', '!=', False)], limit=limit)
        moved = 0
        for attachment in candidates:
            if not attachment._health_sensitive():
                continue
            raw = attachment.raw
            token = _ENCRYPTING.set(True)
            try:
                # Maintenance preserves the bytes; user-facing write lock stays unconditional.
                super(IrAttachment, attachment).write({'raw': raw, 'mimetype': attachment.mimetype})
                moved += 1
            finally:
                _ENCRYPTING.reset(token)
        return moved
