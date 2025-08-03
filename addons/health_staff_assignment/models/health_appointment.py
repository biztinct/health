from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json


class HealthAppointment(models.Model):
    """Extend appointment model with advanced staff assignment workflow"""
    _inherit = 'health.appointment'
    
    # ============================================================================
    # Multi-Role Approval Workflow Fields
    # ============================================================================
    
    assignment_state = fields.Selection([
        ('draft', 'Draft'),
        ('sales_review', 'Sales Review'),
        ('ops_manager_review', 'Operations Manager Review'), 
        ('head_nurse_assign', 'Head Nurse Assignment'),
        ('staff_assigned', 'Staff Assigned'),
        ('staff_confirmed', 'Staff Confirmed'),
        ('ready', 'Ready for Service'),
        ('cancelled', 'Cancelled')
    ], string='Assignment Status', default='draft', tracking=True,
       help='Multi-stage approval workflow for staff assignment')
    
    # ============================================================================
    # Staff Assignment Fields
    # ============================================================================
    
    # Primary assigned staff
    assigned_staff_ids = fields.Many2many(
        'hr.employee', 
        'appointment_staff_assignment_rel',
        'appointment_id', 'employee_id',
        string='Assigned Staff',
        domain=[('is_healthcare_staff', '=', True)],
        tracking=True
    )
    
    # Lead staff member (doctor/nurse in charge)
    lead_staff_id = fields.Many2one(
        'hr.employee',
        string='Lead Healthcare Professional',
        domain=[('is_healthcare_staff', '=', True)],
        tracking=True,
        help='Primary healthcare professional responsible for this appointment'
    )
    
    # Assignment tracking
    staff_assignment_id = fields.Many2one(
        'health.staff.assignment',
        string='Staff Assignment Record',
        help='Detailed assignment record with routing and optimization data'
    )
    
    # ============================================================================
    # Approval Workflow Fields
    # ============================================================================
    
    # Approval users
    sales_approved_by = fields.Many2one('res.users', string='Sales Approved By', readonly=True)
    sales_approved_date = fields.Datetime('Sales Approval Date', readonly=True)
    
    ops_manager_approved_by = fields.Many2one('res.users', string='Ops Manager Approved By', readonly=True)
    ops_manager_approved_date = fields.Datetime('Ops Manager Approval Date', readonly=True)
    
    head_nurse_assigned_by = fields.Many2one('res.users', string='Head Nurse Assigned By', readonly=True)
    head_nurse_assigned_date = fields.Datetime('Head Nurse Assignment Date', readonly=True)
    
    # ============================================================================
    # Assignment Intelligence Fields  
    # ============================================================================
    
    assignment_score = fields.Float(
        'Assignment Score',
        help='AI-calculated score for staff assignment quality (0-100)',
        compute='_compute_assignment_score',
        store=True
    )
    
    required_skills = fields.Text(
        'Required Skills',
        help='JSON list of required skills for this appointment'
    )
    
    assignment_priority = fields.Selection([
        ('low', 'Low Priority'),
        ('normal', 'Normal'),
        ('high', 'High Priority'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency')
    ], string='Assignment Priority', default='normal', tracking=True)
    
    # ============================================================================
    # Geographic and Routing Fields
    # ============================================================================
    
    estimated_travel_time = fields.Float(
        'Estimated Travel Time (Hours)',
        help='AI-calculated travel time to appointment location'
    )
    
    optimal_route_data = fields.Text(
        'Route Optimization Data',
        help='JSON data for optimized routing and scheduling'
    )
    
    # ============================================================================
    # Real-time Status Tracking
    # ============================================================================
    
    real_time_status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('assigned', 'Assigned'),
        ('confirmed', 'Staff Confirmed'),
        ('en_route', 'En Route'),
        ('arrived', 'Arrived'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('deferred', 'Deferred'),
        ('cancelled', 'Cancelled')
    ], string='Real-time Status', default='scheduled', tracking=True)
    
    status_last_updated = fields.Datetime('Status Last Updated', default=fields.Datetime.now)
    status_updated_by = fields.Many2one('res.users', 'Status Updated By')
    
    # GPS tracking for home visits
    staff_current_location = fields.Char('Staff Current Location (Coordinates)')
    estimated_arrival_time = fields.Datetime('Estimated Arrival Time')
    
    # ============================================================================
    # Computed Fields
    # ============================================================================
    
    @api.depends('assigned_staff_ids', 'appointment_type_id', 'appointment_date')
    def _compute_assignment_score(self):
        """Calculate AI-powered assignment quality score"""
        for record in self:
            if not record.assigned_staff_ids:
                record.assignment_score = 0.0
                continue
                
            # Get assignment engine to calculate score
            assignment_engine = self.env['health.staff.assignment.engine']
            score = assignment_engine.calculate_assignment_score(
                record.assigned_staff_ids,
                record
            )
            record.assignment_score = score
    
    # ============================================================================
    # Multi-Role Workflow Actions
    # ============================================================================
    
    def action_sales_approve(self):
        """Sales team approves appointment for operations review"""
        if not self.env.user.has_group('health_staff_assignment.group_sales_user'):
            raise UserError(_('Only Sales team members can perform this action.'))
            
        if self.assignment_state != 'sales_review':
            raise UserError(_('Appointment must be in Sales Review state.'))
        
        self.write({
            'assignment_state': 'ops_manager_review',
            'sales_approved_by': self.env.user.id,
            'sales_approved_date': fields.Datetime.now()
        })
        
        # Send notification to Operations Manager
        self._send_assignment_notification('ops_manager_review')
        
        # Log activity
        self.message_post(
            body=_('Sales team approved appointment for operations review.'),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
    
    def action_ops_manager_review(self):
        """Operations manager reviews and approves for head nurse assignment"""
        if not self.env.user.has_group('health_staff_assignment.group_ops_manager'):
            raise UserError(_('Only Operations Managers can perform this action.'))
            
        if self.assignment_state != 'ops_manager_review':
            raise UserError(_('Appointment must be in Operations Manager Review state.'))
        
        self.write({
            'assignment_state': 'head_nurse_assign',
            'ops_manager_approved_by': self.env.user.id,
            'ops_manager_approved_date': fields.Datetime.now()
        })
        
        # Send notification to Head Nurse
        self._send_assignment_notification('head_nurse_assign')
        
        self.message_post(
            body=_('Operations manager approved appointment for staff assignment.'),
            message_type='notification'
        )
    
    def action_head_nurse_assign_staff(self):
        """Head nurse assigns staff to appointment"""
        if not self.env.user.has_group('health_staff_assignment.group_head_nurse'):
            raise UserError(_('Only Head Nurses can perform this action.'))
            
        if self.assignment_state != 'head_nurse_assign':
            raise UserError(_('Appointment must be in Head Nurse Assignment state.'))
        
        if not self.assigned_staff_ids:
            raise UserError(_('Please assign staff members before confirming.'))
        
        # Create detailed staff assignment record
        assignment_vals = {
            'appointment_id': self.id,
            'assigned_staff_ids': [(6, 0, self.assigned_staff_ids.ids)],
            'lead_staff_id': self.lead_staff_id.id,
            'assignment_date': fields.Datetime.now(),
            'assigned_by': self.env.user.id,
            'state': 'assigned'
        }
        
        assignment = self.env['health.staff.assignment'].create(assignment_vals)
        
        self.write({
            'assignment_state': 'staff_assigned',
            'staff_assignment_id': assignment.id,
            'head_nurse_assigned_by': self.env.user.id,
            'head_nurse_assigned_date': fields.Datetime.now(),
            'real_time_status': 'assigned'
        })
        
        # Notify assigned staff
        self._notify_assigned_staff()
        
        self.message_post(
            body=_('Head nurse assigned staff: %s') % ', '.join(self.assigned_staff_ids.mapped('name')),
            message_type='notification'
        )
    
    def action_staff_confirm_assignment(self):
        """Staff member confirms they can handle the assignment"""
        if not self._is_assigned_staff():
            raise UserError(_('Only assigned staff can confirm this appointment.'))
            
        if self.assignment_state != 'staff_assigned':
            raise UserError(_('Assignment must be confirmed by staff first.'))
        
        self.write({
            'assignment_state': 'staff_confirmed',
            'real_time_status': 'confirmed'
        })
        
        # Update staff assignment record
        if self.staff_assignment_id:
            self.staff_assignment_id.write({
                'state': 'confirmed',
                'staff_confirmed_date': fields.Datetime.now()
            })
        
        self.message_post(
            body=_('Staff confirmed assignment: %s') % self.env.user.name,
            message_type='notification'
        )
    
    def action_mark_ready_for_service(self):
        """Mark appointment as ready for service delivery"""
        if self.assignment_state != 'staff_confirmed':
            raise UserError(_('Staff must confirm assignment first.'))
        
        self.write({
            'assignment_state': 'ready',
            'real_time_status': 'scheduled'
        })
        
        # Final preparations and notifications
        self._prepare_for_service_delivery()
    
    # ============================================================================
    # Real-time Status Updates (Mobile Interface)
    # ============================================================================
    
    def action_staff_en_route(self):
        """Staff indicates they are en route to appointment"""
        if not self._is_assigned_staff():
            raise UserError(_('Only assigned staff can update status.'))
        
        self.write({
            'real_time_status': 'en_route',
            'status_last_updated': fields.Datetime.now(),
            'status_updated_by': self.env.user.id
        })
        
        # Calculate and update ETA
        self._calculate_eta()
        
        # Notify patient
        self._notify_patient_status_update()
    
    def action_staff_arrived(self):
        """Staff indicates they have arrived at appointment location"""
        if not self._is_assigned_staff():
            raise UserError(_('Only assigned staff can update status.'))
            
        self.write({
            'real_time_status': 'arrived',
            'status_last_updated': fields.Datetime.now()
        })
        
        self._notify_patient_status_update()
    
    def action_start_appointment(self):
        """Start the actual appointment service"""
        if not self._is_assigned_staff():
            raise UserError(_('Only assigned staff can start appointment.'))
            
        self.write({
            'real_time_status': 'in_progress',
            'state': 'in_progress',  # Update main appointment state too
            'actual_start_time': fields.Datetime.now()
        })
    
    def action_complete_appointment(self):
        """Complete the appointment"""
        if not self._is_assigned_staff():
            raise UserError(_('Only assigned staff can complete appointment.'))
            
        self.write({
            'real_time_status': 'completed',
            'state': 'completed',
            'actual_end_time': fields.Datetime.now()
        })
        
        # Update staff assignment record
        if self.staff_assignment_id:
            self.staff_assignment_id.write({'state': 'completed'})
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def _is_assigned_staff(self):
        """Check if current user is assigned to this appointment"""
        if not self.env.user.employee_id:
            return False
        return self.env.user.employee_id in self.assigned_staff_ids
    
    def _send_assignment_notification(self, stage):
        """Send notification for workflow stage changes"""
        # Implementation for multi-channel notifications
        notification_engine = self.env['health.notification.engine']
        notification_engine.send_workflow_notification(self, stage)
    
    def _notify_assigned_staff(self):
        """Notify staff members of new assignment"""
        for staff in self.assigned_staff_ids:
            if staff.user_id:
                # Create Odoo notification
                self.env['mail.notification'].create({
                    'mail_message_id': self.message_post(
                        body=_('You have been assigned to appointment: %s') % self.name,
                        partner_ids=staff.user_id.partner_id.ids
                    ).id,
                    'res_partner_id': staff.user_id.partner_id.id,
                    'notification_type': 'inbox'
                })
    
    def _notify_patient_status_update(self):
        """Notify patient of appointment status changes"""
        if self.patient_id and self.patient_id.email:
            # Send status update notification
            template = self.env.ref('health_staff_assignment.email_template_status_update', False)
            if template:
                template.send_mail(self.id, force_send=True)
    
    def _calculate_eta(self):
        """Calculate estimated arrival time using Google Maps API"""
        # This will be implemented with Google Maps integration
        pass
    
    def _prepare_for_service_delivery(self):
        """Final preparations before service delivery"""
        # Create calendar event for staff
        # Prepare patient notifications
        # Update availability matrix
        pass
    
    # ============================================================================
    # Workflow Constraints and Validations
    # ============================================================================
    
    @api.constrains('assigned_staff_ids', 'appointment_date')
    def _check_staff_availability(self):
        """Ensure assigned staff are available at appointment time"""
        for record in self:
            if record.assigned_staff_ids and record.appointment_date:
                # Check staff availability matrix
                availability_matrix = self.env['health.staff.availability.matrix']
                for staff in record.assigned_staff_ids:
                    if not availability_matrix.is_staff_available(
                        staff.id, 
                        record.appointment_date,
                        record.appointment_type_id.duration_minutes
                    ):
                        raise ValidationError(
                            _('Staff member %s is not available at %s') % 
                            (staff.name, record.appointment_date)
                        )
    
    # ============================================================================
    # API Methods for Mobile Interface
    # ============================================================================
    
    @api.model
    def get_staff_assignments_mobile(self, staff_id, date_from, date_to):
        """API method for mobile staff dashboard"""
        domain = [
            ('assigned_staff_ids', 'in', [staff_id]),
            ('appointment_date', '>=', date_from),
            ('appointment_date', '<=', date_to)
        ]
        
        appointments = self.search(domain)
        
        result = []
        for apt in appointments:
            result.append({
                'id': apt.id,
                'name': apt.name,
                'patient_name': apt.patient_id.name,
                'appointment_date': apt.appointment_date,
                'appointment_time': apt.appointment_time,
                'address': apt.visit_address or apt.facility_id.name,
                'status': apt.real_time_status,
                'priority': apt.assignment_priority,
                'estimated_duration': apt.appointment_type_id.duration_minutes,
                'service_type': apt.appointment_type_id.name,
            })
        
        return result
    
    @api.model
    def update_staff_status_mobile(self, appointment_id, new_status, location_data=None):
        """API method for mobile status updates"""
        appointment = self.browse(appointment_id)
        
        if not appointment._is_assigned_staff():
            return {'error': 'Not authorized to update this appointment'}
        
        # Update status based on new_status
        status_actions = {
            'en_route': appointment.action_staff_en_route,
            'arrived': appointment.action_staff_arrived,
            'in_progress': appointment.action_start_appointment,
            'completed': appointment.action_complete_appointment
        }
        
        if new_status in status_actions:
            status_actions[new_status]()
            
            # Update location data if provided
            if location_data and new_status == 'en_route':
                appointment.write({
                    'staff_current_location': f"{location_data.get('lat')},{location_data.get('lng')}"
                })
            
            return {'success': True, 'status': appointment.real_time_status}
        
        return {'error': 'Invalid status'}