# -*- coding: utf-8 -*-
"""Health information never leaves through an export.

The export dialog already leaves out every field built `exportable=False`
(Studio's health-information fields and their encrypted columns, see
`ir_model_fields.py`). But a saved export list, or a request written by hand,
names fields by path and is not filtered by anyone: the framework's
`export_data` checks only whether the person may export at all. This walks
every requested path, segment by segment through the records it crosses, and
refuses the whole export when one segment is a Studio field that may not be
exported — naming the fields by their labels, never by technical names.

A RELATED COPY OF A FIELD THAT MAY NOT BE EXPORTED IS NOT OFFERED EITHER. A
record type that `_inherits` another one (a user and its contact) carries the
parent's fields as related copies, and the framework does not copy
`exportable` onto them, so the export dialog of the child would list them
again. `fields_get` follows each related field to its source and says
`exportable: False` when the source says so.

A STUDIO DROPDOWN REFUSES A VALUE THAT IS NOT ONE OF ITS OPTIONS. Its options
are read when asked (a callable selection, so that they come in the reader's
language), and the framework checks a written value only against a FIXED
list: with a callable one, any text is accepted on create and write. `create`
and `write` check Studio dropdowns here. The check looks only at keys that
start with the Studio prefix, so a record type without Studio fields pays one
string test per written key and reads nothing.
"""
from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.orm.models import fix_import_export_id_paths

from .fs_common import FS_PREFIX


def _source_field(field):
    """The field a related field finally points at (itself otherwise)."""
    source = field
    while source.related and getattr(source, 'related_field', None):
        source = source.related_field
    return source


class Base(models.AbstractModel):
    _inherit = 'base'

    # ------------------------------------------------------------------
    #  A Studio dropdown accepts only its options
    # ------------------------------------------------------------------
    def _fs_check_selections(self, vals_list):
        for vals in vals_list:
            for name, value in vals.items():
                if not value or not name.startswith(FS_PREFIX):
                    continue
                field = self._fields.get(name)
                if field is None or field.type != 'selection' \
                        or not field.manual:
                    continue
                # `get_values` answers the option VALUES (not pairs), read
                # from the callable as the framework itself does
                if value in field.get_values(self.env):
                    continue
                label = self.env['ir.model.fields'].get_field_string(
                    self._name).get(name) or field.string
                raise UserError(_(
                    "\"%(value)s\" is not one of the options of %(field)s.",
                    value=value, field=label))

    @api.model_create_multi
    def create(self, vals_list):
        self._fs_check_selections(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._fs_check_selections([vals])
        return super().write(vals)

    # ------------------------------------------------------------------
    #  The export dialog: related copies keep "not exportable"
    # ------------------------------------------------------------------
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields, attributes)
        for name, desc in res.items():
            if not desc.get('exportable'):
                continue
            field = self._fields.get(name)
            if field is None or not field.related:
                continue
            if not _source_field(field).exportable:
                desc['exportable'] = False
        return res

    def _fs_unexportable(self, paths):
        """Labels of the Studio fields in `paths` that may not be exported,
        in the reader's language, each once, in request order."""
        labels = []
        for path in paths or []:
            if not isinstance(path, str):
                continue
            model = self
            for segment in fix_import_export_id_paths(path):
                field = model._fields.get(segment)
                if field is None:
                    break
                # A record type that `_inherits` another one (a user and its
                # contact) carries the parent's fields as related copies, and
                # a related copy does not inherit `exportable`: judge the
                # field it points at.
                source = _source_field(field)
                if (source.name.startswith(FS_PREFIX) and source.manual
                        and not source.exportable):
                    label = self.env['ir.model.fields'].get_field_string(
                        source.model_name).get(source.name) or source.string
                    if label not in labels:
                        labels.append(label)
                    break
                if not field.relational:
                    break
                model = self.env[field.comodel_name]
        return labels

    def export_data(self, fields_to_export):
        labels = self._fs_unexportable(fields_to_export)
        if labels:
            raise UserError(_("Health information cannot be exported: %s",
                              ', '.join(labels)))
        return super().export_data(fields_to_export)
