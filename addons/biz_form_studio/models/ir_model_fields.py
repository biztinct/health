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
module's column exists the row dict carries `fs_vis` and no extra query is
needed. Before the column exists (the install itself), `.get` answers None.

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
"""
from odoo import fields, models

from .fs_common import FS_PREFIX, vis_group_xmlid


def _fs_options(field_id):
    """The options of one Studio dropdown, read when asked, labels in the
    language of the environment that asks."""
    def options(model):
        rows = model.env['ir.model.fields.selection'].sudo().search(
            [('field_id', '=', field_id)], order='sequence, id')
        return [(row.value, row.name) for row in rows]
    return options


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    fs_vis = fields.Char(
        string='Studio visibility', readonly=True, copy=False,
        help="Who sees a field made in Form Studio: all, staff or admin. "
             "Empty on every other field.")

    def _instanciate_attrs(self, field_data):
        attrs = super()._instanciate_attrs(field_data)
        if attrs and (field_data.get('name') or '').startswith(FS_PREFIX):
            xmlid = vis_group_xmlid(self.env.cr, field_data.get('fs_vis'))
            if xmlid:
                attrs['groups'] = xmlid
            if field_data.get('ttype') == 'selection':
                attrs['selection'] = _fs_options(field_data['id'])
        return attrs
