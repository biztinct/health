# -*- coding: utf-8 -*-
from odoo import _, api, models


class FsStudio(models.AbstractModel):
    _inherit = 'fs.studio'

    @api.model
    def _fs_extra_references(self, field):
        """Field Requirements rules naming the field block its deletion: a
        rule pointing at a deleted field would vanish without a word."""
        refs = super()._fs_extra_references(field)
        if 'field.requirement.rule' not in self.env:
            return refs
        rules = self.env['field.requirement.rule'].sudo().with_context(
            active_test=False).search([('field_id', '=', field.id)])
        if rules:
            refs.append({
                'kind': 'requirement', 'blocker': True, 'count': len(rules),
                'label': _("Field Requirements rules: %s", len(rules)),
            })
        return refs
