from odoo import models, fields, api


class HealthFieldServiceTeam(models.Model):
    """
    Healthcare Field Service Teams - Manage teams of field workers
    """
    _name = 'health.fieldservice.team'
    _description = 'Healthcare Field Service Teams'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    
    name = fields.Char('Team Name', required=True, tracking=True)
    description = fields.Text('Description')
    
    # Team composition
    leader_id = fields.Many2one('res.users', string='Team Leader', tracking=True)
    member_ids = fields.Many2many('res.users', 'fieldservice_team_member_rel', 
                                  'team_id', 'user_id', string='Team Members')
    
    # Healthcare staff integration
    healthcare_staff_ids = fields.Many2many('hr.employee', 
                                           string='Healthcare Staff',
                                           domain=[('is_healthcare_staff', '=', True)])
    
    # Service areas and capabilities
    service_area_ids = fields.Many2many('health.service.area', 
                                       string='Service Areas',
                                       help="Geographic areas this team covers")
    
    service_type_ids = fields.Many2many('health.service.type',
                                       string='Service Types',
                                       help="Types of healthcare services this team can provide")
    
    # Team configuration
    active = fields.Boolean('Active', default=True)
    color = fields.Integer('Color Index', default=0)
    
    # Team statistics
    current_fso_count = fields.Integer('Current FSOs', compute='_compute_team_stats')
    completed_fso_count = fields.Integer('Completed FSOs', compute='_compute_team_stats')
    team_efficiency = fields.Float('Team Efficiency %', compute='_compute_team_stats',
                                  help="Percentage of FSOs completed on time")
    
    # Equipment management
    equipment_ids = fields.Many2many('health.portable.equipment',
                                    string='Team Equipment',
                                    help="Equipment assigned to this team")
    
    @api.depends()
    def _compute_team_stats(self):
        """Compute team performance statistics"""
        for team in self:
            # Current active FSOs
            current_fsos = self.env['health.fieldservice.order'].search([
                ('team_id', '=', team.id),
                ('current_status', 'not in', ['completed', 'cancelled'])
            ])
            team.current_fso_count = len(current_fsos)
            
            # Completed FSOs
            completed_fsos = self.env['health.fieldservice.order'].search([
                ('team_id', '=', team.id),
                ('current_status', '=', 'completed')
            ])
            team.completed_fso_count = len(completed_fsos)
            
            # Team efficiency (simplified calculation)
            if completed_fsos:
                on_time_count = sum(1 for fso in completed_fsos 
                                  if fso.actual_end and fso.scheduled_date 
                                  and fso.actual_end <= fso.scheduled_date)
                team.team_efficiency = (on_time_count / len(completed_fsos)) * 100
            else:
                team.team_efficiency = 0.0
    
    def action_view_current_fsos(self):
        """View current active FSOs for this team"""
        self.ensure_one()
        return {
            'name': f'{self.name} - Current Field Service Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'view_mode': 'kanban,list,form',
            'domain': [
                ('team_id', '=', self.id),
                ('current_status', 'not in', ['completed', 'cancelled'])
            ],
            'context': {'default_team_id': self.id}
        }
    
    def action_view_team_performance(self):
        """View team performance dashboard"""
        self.ensure_one()
        return {
            'name': f'{self.name} - Performance Dashboard',
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'view_mode': 'graph,pivot,list',
            'domain': [('team_id', '=', self.id)],
            'context': {
                'group_by': ['stage_id', 'current_status'],
                'default_team_id': self.id
            }
        }