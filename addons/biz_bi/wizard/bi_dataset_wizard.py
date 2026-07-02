# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class BiDatasetWizard(models.TransientModel):
    """Guided 'new dataset from Odoo model' flow: pick a model, get the
    source + root node + scanned fields + suggested lookup joins in one go."""
    _name = 'bi.dataset.wizard'
    _description = 'New Dataset Wizard'

    name = fields.Char(required=True)
    workspace_id = fields.Many2one(
        'bi.workspace', required=True,
        default=lambda self: self.env['bi.workspace'].search(
            [('is_default', '=', True)], limit=1))
    model_id = fields.Many2one(
        'ir.model', required=True, string='Root Model',
        domain=[('transient', '=', False), ('abstract', '=', False)])
    auto_join_lookups = fields.Boolean(
        default=True, string='Auto-join common lookups',
        help="Automatically join frequently useful lookup entities "
             "(partner, product, employee, company...) discovered from the "
             "model's relations.")

    AUTO_JOIN_COMODELS = (
        'res.partner', 'product.product', 'product.template', 'hr.employee',
        'res.company', 'res.users', 'res.currency', 'crm.team',
    )

    def action_create(self):
        self.ensure_one()
        Source = self.env['bi.source']

        def get_or_create_source(ir_model):
            source = Source.search([('model_id', '=', ir_model.id)], limit=1)
            if not source:
                source = Source.create({
                    'name': ir_model.name,
                    'type': 'odoo_model',
                    'model_id': ir_model.id,
                    'state': 'ready',
                })
            return source

        dataset = self.env['bi.dataset'].create({
            'name': self.name,
            'workspace_id': self.workspace_id.id,
        })
        root = self.env['bi.dataset.node'].create({
            'dataset_id': dataset.id,
            'source_id': get_or_create_source(self.model_id).id,
            'is_root': True,
        })
        root.action_scan_fields()

        if self.auto_join_lookups:
            for suggestion in root.suggest_relationships():
                if suggestion['comodel'] not in self.AUTO_JOIN_COMODELS:
                    continue
                comodel_ir = self.env['ir.model']._get(suggestion['comodel'])
                child = self.env['bi.dataset.node'].create({
                    'dataset_id': dataset.id,
                    'source_id': get_or_create_source(comodel_ir).id,
                })
                self.env['bi.relationship'].create({
                    'dataset_id': dataset.id,
                    'parent_node_id': root.id,
                    'child_node_id': child.id,
                    'parent_field': suggestion['parent_field'],
                    'child_field': 'id',
                    'cardinality': 'many2one',
                    'origin': 'auto',
                })
                child.action_scan_fields()
                # prefix joined-node business names for disambiguation
                for field in child.field_ids:
                    field.name = '%s → %s' % (suggestion['label'], field.name)
                    field.folder = suggestion['label']

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bi.dataset',
            'res_id': dataset.id,
            'view_mode': 'form',
            'target': 'current',
        }
