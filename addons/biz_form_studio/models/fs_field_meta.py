# -*- coding: utf-8 -*-
"""What Studio knows about a field it made, beyond what the field row holds."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .fs_common import NO_LIST_TYPES


class FsFieldMeta(models.Model):
    _name = 'fs.field.meta'
    _description = 'Form Studio field settings'
    _order = 'model, sequence, id'

    field_id = fields.Many2one(
        'ir.model.fields', required=True, ondelete='cascade', index=True)
    name = fields.Char(related='field_id.name', store=True, index=True)
    model = fields.Char(related='field_id.model', store=True, index=True)
    vis = fields.Selection(
        [('all', 'Everyone'), ('staff', 'Staff'), ('admin', 'Admins')],
        string='Who sees it', default='all', required=True)
    phi = fields.Boolean(string='Health information', default=False)
    pwa = fields.Boolean(string='Mobile app', default=False)
    required = fields.Boolean(
        default=False,
        help="Must be filled on the screen. A rule of the screen, not of the "
             "database: records made elsewhere are not refused.")
    list_ok = fields.Boolean(
        string='Show in lists', default=False,
        help="A column of the screen's list once the field is placed on the "
             "screen. Never for health information, files or long text.")
    label_vi = fields.Char(string='Vietnamese label')
    help_vi = fields.Char(string='Vietnamese help text')
    sequence = fields.Integer(default=10)
    created_by = fields.Many2one('res.users', string='Made by', ondelete='set null')
    publish_version = fields.Integer(string='First published in version')
    warned_phi = fields.Boolean(string='Warning shown', default=False)
    retired_values = fields.Json(string='Retired options', default=list)

    def init(self):
        # `_sql_constraints` are not materialised on this version (ledger §5.1).
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS fs_field_meta_field_uniq "
            "ON fs_field_meta (field_id)")

    @api.model_create_multi
    def create(self, vals_list):
        ttypes = {f.id: f.ttype for f in self.env['ir.model.fields'].sudo()
                  .browse([v['field_id'] for v in vals_list
                           if v.get('field_id')]).exists()}
        for vals in vals_list:
            if vals.get('phi') or ttypes.get(vals.get('field_id')) in \
                    NO_LIST_TYPES:
                vals['list_ok'] = False
        records = super().create(vals_list)
        records._check_phi_list()
        return records

    def write(self, vals):
        if vals.get('phi'):
            vals = dict(vals, list_ok=False)
        res = super().write(vals)
        self._check_phi_list()
        return res

    @api.model
    def _list_reason(self, ttype, phi=False):
        """Why a field of this type can never be a list column ('' when it
        can)."""
        if phi:
            return _("Health information is never a column.")
        if ttype == 'binary':
            return _("Files cannot be list columns.")
        if ttype == 'text':
            return _("Long text cannot be a list column.")
        return ''

    @api.constrains('phi', 'list_ok')
    def _check_phi_list(self):
        for meta in self:
            if not meta.list_ok:
                continue
            if meta.phi:
                raise ValidationError(_(
                    "A field that holds health information cannot be offered "
                    "as a list column."))
            reason = self._list_reason(meta.field_id.ttype)
            if reason:
                raise ValidationError(reason)
