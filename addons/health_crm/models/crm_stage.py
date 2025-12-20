# -*- coding: utf-8 -*-

from odoo import api, fields, models


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    type = fields.Selection(
        [
            ('lead', 'Lead'),
            ('opportunity', 'Opportunity'),
        ],
        string='Type',
        compute='_compute_type',
        inverse='_inverse_type',
        search='_search_type',
        readonly=False,
        store=False,
        help='Stage applies to leads or opportunities.',
    )

    def _compute_type(self):
        for stage in self:
            stage.type = 'opportunity'

    def _inverse_type(self):
        # Kept for compatibility with views that allow editing this field.
        return

    def _search_type(self, operator, value):
        def match_opportunity(val):
            return val == 'opportunity'

        if operator in ('=', '=='):
            return [('id', '!=', False)] if match_opportunity(value) else [('id', '=', False)]
        if operator in ('!=', '<>'):
            return [('id', '=', False)] if match_opportunity(value) else [('id', '!=', False)]
        if operator == 'in':
            return [('id', '!=', False)] if 'opportunity' in (value or []) else [('id', '=', False)]
        if operator == 'not in':
            return [('id', '=', False)] if 'opportunity' in (value or []) else [('id', '!=', False)]
        return [('id', '!=', False)]
