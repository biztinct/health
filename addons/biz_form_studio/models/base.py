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
"""
from odoo import _, models
from odoo.exceptions import UserError
from odoo.orm.models import fix_import_export_id_paths

from .fs_common import FS_PREFIX


class Base(models.AbstractModel):
    _inherit = 'base'

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
                source = field
                while source.related and getattr(source, 'related_field', None):
                    source = source.related_field
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
