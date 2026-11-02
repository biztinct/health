# -*- coding: utf-8 -*-
"""Who may see a Studio field — enforced where the field is BUILT.

Core's `ir.model.fields.groups` is an unimplemented many2many: nothing ever
turns it into the Python field's `groups`. So "Who sees it" cannot be a write
to that column. Instead the visibility is stored on the row (`fs_vis`) and
turned into `groups` at the one place every custom field passes through when
the registry builds it, `_instanciate_attrs`. From then on the ORM itself
refuses the field to anybody outside the group: `fields_get` leaves it out,
`read` raises, and views drop the node — every door, not only the form.

`_all_manual_field_data` selects `*` from `ir_model_fields`, so once this
module's columns exist the row dict carries `fs_vis`, `fs_phi` and
`fs_companion`, and no extra query is needed. Before the columns exist (the
install itself), `.get` answers None.

A STUDIO DROPDOWN READS ITS OPTIONS FROM THEIR ROWS, IN THE READER'S LANGUAGE.
A custom selection field is normally built with a fixed list of (value,
English label), and its translated labels are looked up later through
`ir.model.fields.get_field_selection`. A product may replace that lookup — a
debranding layer that rebuilds labels from the fixed list never reads the
translated rows, so a Vietnamese option name would never reach a form. A
CALLABLE selection is honoured by every reader (the field description and any
such replacement call it with the reader's environment), so Studio's dropdowns
are built with one that reads `ir.model.fields.selection` in the reader's
language.

HEALTH INFORMATION IS NOT EXPORT MATERIAL. A field marked health information
(`fs_phi`) and the column that holds an encrypted value (`fs_companion`) are
built `exportable=False`: the export dialog leaves them out, the server
refuses them in `export_data` (`models/base.py`), and reporting tools that
honour the flag skip them.

AN ENCRYPTED FIELD HAS NO COLUMN OF ITS OWN. On a screen that stores health
information encrypted, a text field marked health information is built like
the product's own encrypted fields: the field people see (`x_fs_<name>`) is
computed from a hidden text column (`x_fs_<name>_enc`, the "companion") that
holds a token, and writing the field writes the token. Every ORM read path
goes through the compute, and the plain value is never stored. The cipher is
NOT this module's: a product supplies it by overriding `_fs_cipher` (its key,
its token format). Without one, an encrypted field is built empty and
read-only rather than stored in the clear.
"""
import logging

from odoo import api, fields, models

from .fs_common import ENC_SUFFIX, FS_PREFIX, vis_group_xmlid

_logger = logging.getLogger(__name__)


def _fs_options(field_id):
    """The options of one Studio dropdown, read when asked, labels in the
    language of the environment that asks."""
    def options(model):
        rows = model.env['ir.model.fields.selection'].sudo().search(
            [('field_id', '=', field_id)], order='sequence, id')
        return [(row.value, row.name) for row in rows]
    return options


def _fs_encrypted(name, enc, cipher):
    """compute / inverse for an encrypted Studio field. `cipher` is the
    product's `(encrypt(env, text), decrypt(env, token), failure marker)`.

    The compute runs as the superuser (`compute_sudo`, set with it), so it
    may read the companion whoever asks; the inverse writes
    the companion with `sudo()` for the same reason — whether this person may
    write the FIELD was already decided by the write that called it."""
    encrypt, decrypt = cipher[0], cipher[1]

    def fs_decrypt_value(records):
        for rec in records:
            token = rec[enc]
            rec[name] = (decrypt(rec.env, token) if token else False) or False

    def fs_encrypt_value(records):
        for rec in records:
            value = rec[name]
            rec.sudo()[enc] = encrypt(rec.env, value) if value else False

    return fs_decrypt_value, fs_encrypt_value


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    fs_vis = fields.Char(
        string='Studio visibility', readonly=True, copy=False,
        help="Who sees a field made in Form Studio: all, staff or admin. "
             "Empty on every other field.")
    fs_phi = fields.Boolean(
        string='Studio health information', readonly=True, copy=False,
        help="A field made in Form Studio that holds health information: "
             "never exported.")
    fs_companion = fields.Boolean(
        string='Studio encrypted column', readonly=True, copy=False,
        help="The hidden column that holds the encrypted value of a Form "
             "Studio field. Never shown, never exported.")

    @api.model
    def _fs_cipher(self):
        """Hook: the product's cipher, or None when this system has no way
        to encrypt a value: `(encrypt(env, text) -> token, decrypt(env,
        token) -> text, failure marker)`. `decrypt` never raises (a value it
        cannot read comes back as the marker, so a wrong key never takes a
        screen down); the marker lets a conversion refuse such a value."""
        return None

    def _instanciate_attrs(self, field_data):
        attrs = super()._instanciate_attrs(field_data)
        name = field_data.get('name') or ''
        if not attrs or not name.startswith(FS_PREFIX):
            return attrs
        cr = self.env.cr
        xmlid = vis_group_xmlid(cr, field_data.get('fs_vis'))
        if xmlid:
            attrs['groups'] = xmlid
        if field_data.get('ttype') == 'selection':
            attrs['selection'] = _fs_options(field_data['id'])
        if field_data.get('fs_phi') or field_data.get('fs_companion'):
            attrs['exportable'] = False
        if field_data.get('fs_companion'):
            # the token column: administrators only, never copied
            attrs['groups'] = vis_group_xmlid(cr, 'admin')
            attrs['copy'] = False
        elif field_data.get('fs_phi') and not field_data.get('store'):
            enc = name + ENC_SUFFIX
            companion = self._get_manual_field_data(
                field_data['model']).get(enc)
            if companion and companion.get('fs_companion'):
                attrs.update(self._fs_encrypted_attrs(name, enc))
        return attrs

    def _fs_encrypted_attrs(self, name, enc):
        cipher = self._fs_cipher()
        if not cipher:
            # Never stored in the clear: without a cipher the field stays
            # empty and read-only until one is available again. While the
            # modules load one by one the product's cipher may simply not be
            # loaded yet — only a finished registry without one is a problem.
            log = _logger.warning if self.pool.ready else _logger.debug
            log("Form Studio: %s is stored encrypted but this system has no "
                "cipher; the field reads empty.", name)
            return {'store': False, 'readonly': True}
        compute, inverse = _fs_encrypted(name, enc, cipher)
        # `compute_sudo`: a non-stored computed field is computed as the
        # reader by default, and the reader may not read the hidden column
        # (administrators only). Whether they may read THIS field was already
        # decided by its own `groups`.
        return {'compute': compute, 'inverse': inverse, 'store': False,
                'readonly': False, 'depends': (enc,), 'copy': False,
                'compute_sudo': True}
