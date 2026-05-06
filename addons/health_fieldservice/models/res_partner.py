from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    """Extend res.partner with assignment-related patient data"""
    _inherit = 'res.partner'
    
    # Assignment preferences for patients
    preferred_staff_id = fields.Many2one(
        'hr.employee',
        string='Preferred Healthcare Staff',
        domain=[('is_healthcare_staff', '=', True)],
        help='client\'s preferred healthcare professional'
    )
    
    assignment_notes = fields.Text(
        'Assignment Notes',
        help='Special notes for staff assignment (accessibility, language preferences, etc.)'
    )
    
    # Assignment history
    total_assignments = fields.Integer(
        'Total Assignments',
        compute='_compute_assignment_stats'
    )
    
    last_assignment_date = fields.Datetime(
        'Last Assignment Date',
        compute='_compute_assignment_stats'
    )

    # Client timeline
    timeline_html = fields.Html(
        'Client Timeline',
        compute='_compute_timeline_html'
    )

    @api.depends('name')
    def _compute_timeline_html(self):
        """Generate HTML timeline of upcoming appointments and key events"""
        for partner in self:
            if hasattr(partner, 'is_patient') and partner.is_patient:
                timeline_events = []

                # Get upcoming FSOs (scheduled bookings)
                upcoming_fsos = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id),
                    ('state', 'in', ['draft', 'assigned', 'confirmed', 'in_progress']),
                    ('scheduled_datetime', '!=', False)
                ], order='scheduled_datetime ASC', limit=10)

                for fso in upcoming_fsos:
                    date_str = fso.scheduled_datetime.strftime('%d %b %Y at %H:%M') if fso.scheduled_datetime else 'TBD'
                    status_color = 'primary' if fso.state == 'confirmed' else 'secondary'
                    # Map state to display name
                    state_display = dict(fso._fields['state'].selection).get(fso.state, fso.state)
                    timeline_events.append({
                        'type': 'appointment',
                        'date': date_str,
                        'title': f'📅 {fso.name}',
                        'description': f'Service: {fso.service_type} | Staff: {fso.lead_staff_id.name if fso.lead_staff_id else "Not assigned"} | Status: {state_display}',
                        'color': status_color
                    })

                # Get completed services (past FSOs) for recent activity
                completed_fsos = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id),
                    ('state', '=', 'completed'),
                    ('actual_end_datetime', '!=', False)
                ], order='actual_end_datetime DESC', limit=5)

                for fso in completed_fsos:
                    date_str = fso.actual_end_datetime.strftime('%d %b %Y') if fso.actual_end_datetime else 'TBD'
                    timeline_events.append({
                        'type': 'completed',
                        'date': date_str,
                        'title': f'✓ {fso.name}',
                        'description': f'Service completed: {fso.service_type}',
                        'color': 'success'
                    })

                # Generate HTML timeline
                if timeline_events:
                    html = '<div style="padding: 10px; background: #f8f9fa; border-radius: 5px;"><ul style="list-style: none; padding: 0;">'
                    for event in timeline_events:
                        icon = '📅' if event['type'] == 'appointment' else '✓'
                        color_class = f'badge-{event["color"]}'
                        html += f'''
                        <li style="margin-bottom: 15px; padding-left: 20px; border-left: 3px solid #ddd;">
                            <strong>{event['title']}</strong><br/>
                            <small style="color: #666;">{event['date']}</small><br/>
                            <small>{event['description']}</small>
                        </li>
                        '''
                    html += '</ul></div>'
                    partner.timeline_html = html
                else:
                    partner.timeline_html = '<p style="color: #999; text-align: center; padding: 20px;">No upcoming appointments scheduled</p>'
            else:
                partner.timeline_html = False

    @api.depends('name')
    def _compute_assignment_stats(self):
        """Calculate assignment statistics for patients"""
        for partner in self:
            if hasattr(partner, 'is_patient') and partner.is_patient:
                # Count assignments through unified FSO system
                fso_records = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id)
                ])
                
                assignments = self.env['health.staff.assignment'].search([
                    ('fso_id', 'in', fso_records.ids)
                ])
                
                partner.total_assignments = len(assignments)
                partner.last_assignment_date = max(
                    assignments.mapped('assignment_date')
                ) if assignments else False
            else:
                partner.total_assignments = 0
                partner.last_assignment_date = False
    
    def action_create_fso(self):
        """Open quick booking wizard (2-step: Services + Booking) with client pre-filled"""
        if not self.is_patient:
            raise UserError(_('Only patients can have Bookings created.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Booking'),
            'res_model': 'health.quick.booking.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_client_id': self.id,
            }
        }
    
    def action_view_fso_orders(self):
        """View all Bookings for this patient"""
        if not self.is_patient:
            raise UserError(_('Only patients can have Bookings.'))
        
        fso_orders = self.env['health.fieldservice.order'].search([
            ('patient_id', '=', self.id)
        ])
        
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Bookings'),
            'res_model': 'health.fieldservice.order',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('patient_id', '=', self.id)],
            'context': {
                'default_patient_id': self.id,
                'default_customer_id': self.id,
            }
        }
        
        if len(fso_orders) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = fso_orders.id
        
        return action