from odoo import models, fields, api


class HealthFieldServiceStage(models.Model):
    """
    Field Service Order Stages - Standalone model for FSO workflow stages
    """
    _name = 'health.fieldservice.stage'
    _description = 'Healthcare Field Service Order Stages'
    _order = 'sequence, name'
    
    name = fields.Char('Stage Name', required=True, translate=True)
    description = fields.Text('Description', translate=True)
    sequence = fields.Integer('Sequence', default=10)
    
    # Kanban view configuration
    color = fields.Integer('Color Index', default=0)
    fold = fields.Boolean('Folded in Kanban', default=False)
    
    # Stage behavior
    is_closed = fields.Boolean('Is Closed Stage', default=False, 
                              help="Indicates this is a final stage (completed/cancelled)")
    is_default = fields.Boolean('Default Stage', default=False,
                               help="This stage is used as default for new FSOs")
    
    # Stage constraints and automation
    allow_edit = fields.Boolean('Allow Editing', default=True,
                               help="Whether FSOs in this stage can be edited")
    require_confirmation = fields.Boolean('Require Confirmation', default=False,
                                         help="Require confirmation before moving to this stage")
    
    # Related fields
    fso_count = fields.Integer('FSO Count', compute='_compute_fso_count')
    
    @api.depends()
    def _compute_fso_count(self):
        """Count FSOs in this stage"""
        for stage in self:
            stage.fso_count = self.env['health.fieldservice.order'].search_count([
                ('stage_id', '=', stage.id)
            ])
    
    @api.model
    def _get_default_stage(self):
        """Get the default stage for new FSOs"""
        return self.search([('is_default', '=', True)], limit=1) or self.search([], limit=1)
    
    def action_view_fsos(self):
        """Action to view FSOs in this stage"""
        self.ensure_one()
        return {
            'name': f'Field Service Orders - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'view_mode': 'list,form,kanban',
            'domain': [('stage_id', '=', self.id)],
            'context': {'default_stage_id': self.id}
        }