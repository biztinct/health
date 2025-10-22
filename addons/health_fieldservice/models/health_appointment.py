from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HealthAppointment(models.Model):
    """
    Healthcare appointment model that automatically generates FSO for home visits
    """
    _name = 'health.appointment'
    _description = 'Healthcare Appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'
    
    # ============================================================================
    # Core Appointment Fields
    # ============================================================================
    
    name = fields.Char('Appointment Reference', required=True, default='New Appointment')
    
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        domain=[('is_patient', '=', True)],
        help='Client for this appointment'
    )
    
    start_datetime = fields.Datetime(
        'Start Date & Time',
        required=True,
        help="When the appointment starts"
    )
    
    end_datetime = fields.Datetime(
        'End Date & Time',
        help="When the appointment ends"
    )
    
    duration = fields.Integer(
        'Duration (minutes)',
        default=60,
        help="Appointment duration in minutes"
    )
    
    appointment_type_id = fields.Many2one(
        'health.service.type',
        string='Appointment Type',
        required=True,
        help="Type of appointment/service"
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show')
    ], string='Status', default='draft', tracking=True)
    
    priority = fields.Selection([
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency')
    ], string='Priority', default='routine')
    
    notes = fields.Text('Notes')
    
    # Field Service Order relationship
    fieldservice_order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Field Service Order',
        readonly=True,
        help="Automatically generated field service order for home visits"
    )
    
    # CRM integration - Lead that generated this appointment
    lead_id = fields.Many2one(
        'crm.lead',
        string='Originating Lead',
        help="CRM lead that generated this appointment"
    )
    
    has_fieldservice_order = fields.Boolean(
        'Has Field Service Order',
        compute='_compute_has_fieldservice_order',
        help="Indicates if this appointment has a field service order"
    )
    
    # Enhanced location tracking
    location_type = fields.Selection([
        ('clinic', 'Clinic Visit'),
        ('home', 'Home Visit'),
        ('facility', 'Healthcare Facility'),
        ('emergency', 'Emergency Location')
    ], string='Location Type', compute='_compute_location_type', store=True)
    
    patient_address = fields.Char(
        'Patient Address',
        related='patient_id.street',
        readonly=True,
        help='Client address for home visits'
    )
    
    # ============================================================================
    # Staff Assignment Workflow Fields
    # ============================================================================
    
    # Assignment workflow state
    assignment_state = fields.Selection([
        ('draft', 'Draft'),
        ('sales_review', 'Sales Review'),
        ('ops_manager_review', 'Ops Manager Review'),
        ('head_nurse_assign', 'Head Nurse Assignment'),
        ('staff_assigned', 'Staff Assigned'),
        ('staff_confirmed', 'Staff Confirmed'),
        ('ready', 'Ready for Service')
    ], string='Assignment State', default='draft', tracking=True)
    
    # Assignment priority
    assignment_priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency')
    ], string='Assignment Priority', default='normal', tracking=True)
    
    # Staff assignment fields
    assigned_staff_ids = fields.Many2many(
        'hr.employee',
        'appointment_staff_rel',
        'appointment_id', 'employee_id',
        string='Assigned Staff',
        domain=[('is_healthcare_staff', '=', True)]
    )
    
    lead_staff_id = fields.Many2one(
        'hr.employee',
        string='Lead Staff',
        domain=[('is_healthcare_staff', '=', True)]
    )
    
    staff_assignment_id = fields.Many2one(
        'health.staff.assignment',
        string='Staff Assignment Record',
        readonly=True
    )
    
    assignment_score = fields.Float(
        'Assignment Score',
        readonly=True,
        help="AI-calculated assignment optimization score"
    )
    
    # Real-time status tracking
    real_time_status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('staff_notified', 'Staff Notified'),
        ('en_route', 'En Route'),
        ('arrived', 'Arrived'),
        ('in_service', 'Service in Progress'),
        ('service_complete', 'Service Complete'),
        ('returning', 'Returning'),
        ('completed', 'Completed')
    ], string='Real-time Status', default='scheduled', tracking=True)
    
    status_last_updated = fields.Datetime('Status Last Updated', readonly=True)
    status_updated_by = fields.Many2one('res.users', 'Status Updated By', readonly=True)
    staff_current_location = fields.Char('Staff Current Location', readonly=True)
    estimated_arrival_time = fields.Datetime('Estimated Arrival Time', readonly=True)
    
    # Approval tracking
    sales_approved_by = fields.Many2one('res.users', 'Sales Approved By', readonly=True)
    sales_approved_date = fields.Datetime('Sales Approved Date', readonly=True)
    ops_manager_approved_by = fields.Many2one('res.users', 'Ops Manager Approved By', readonly=True)
    ops_manager_approved_date = fields.Datetime('Ops Manager Approved Date', readonly=True)
    head_nurse_assigned_by = fields.Many2one('res.users', 'Head Nurse Assigned By', readonly=True)
    head_nurse_assigned_date = fields.Datetime('Head Nurse Assigned Date', readonly=True)
    
    # Travel and timing
    estimated_travel_time = fields.Float('Estimated Travel Time (hours)', readonly=True)
    
    # Required skills for assignment
    required_skills = fields.Text('Required Skills', readonly=True)
    
    @api.depends('fieldservice_order_id')
    def _compute_has_fieldservice_order(self):
        """Check if appointment has associated field service order"""
        for appointment in self:
            appointment.has_fieldservice_order = bool(appointment.fieldservice_order_id)
    
    @api.depends('appointment_type_id', 'appointment_type_id.name')
    def _compute_location_type(self):
        """Determine location type based on appointment type"""
        for appointment in self:
            if appointment.appointment_type_id:
                service_name = appointment.appointment_type_id.name.lower()
                if any(keyword in service_name for keyword in ['home', 'visit', 'house', 'domicile']):
                    appointment.location_type = 'home'
                elif any(keyword in service_name for keyword in ['emergency', 'urgent', 'ambulance']):
                    appointment.location_type = 'emergency'
                elif any(keyword in service_name for keyword in ['facility', 'hospital', 'center']):
                    appointment.location_type = 'facility'
                else:
                    appointment.location_type = 'clinic'
            else:
                appointment.location_type = 'clinic'
    
    def action_confirm(self):
        """Override confirm to automatically generate FSO for home visits"""
        result = super().action_confirm()
        
        # Generate FSO only for home visits
        for appointment in self:
            if appointment.location_type == 'home' and not appointment.fieldservice_order_id:
                try:
                    fso = appointment._create_field_service_order()
                    if fso:
                        _logger.info(f"Field Service Order {fso.name} created for appointment {appointment.name}")
                except Exception as e:
                    _logger.error(f"Failed to create FSO for appointment {appointment.name}: {str(e)}")
                    # Don't block appointment confirmation if FSO creation fails
        
        return result
    
    def _create_field_service_order(self):
        """Create field service order when appointment is confirmed for home visits"""
        self.ensure_one()
        
        if self.location_type != 'home':
            return False
            
        if self.fieldservice_order_id:
            raise UserError(_("Field Service Order already exists for this appointment."))
        
        # Validate required data
        if not self.patient_id:
            raise UserError(_("Patient is required to create Field Service Order."))
        
        if not self.appointment_type_id:
            raise UserError(_("Service type is required to create Field Service Order."))
        
        # Get appropriate clinical protocol
        protocol = self.env['health.clinical.protocol'].get_protocol_for_service(
            self.appointment_type_id.id
        )
        
        # Create FSO
        fso_vals = {
            'appointment_id': self.id,
            'priority': self._map_urgency_to_priority(),
            'clinical_protocol_id': protocol.id if protocol else False,
            'team_id': self._get_appropriate_team(),
        }
        
        fso = self.env['health.fieldservice.order'].create(fso_vals)
        self.fieldservice_order_id = fso.id
        
        # Trigger staff assignment workflow after FSO creation (if module available)
        try:
            if 'health.staff.assignment' in self.env.registry:
                staff_assignment = fso.action_trigger_staff_assignment()
                _logger.info(f"Staff assignment {staff_assignment.name} created for FSO {fso.name}")
            else:
                _logger.info(f"FSO {fso.name} created. Install health_staff_assignment module for AI staff optimization.")
        except Exception as e:
            _logger.warning(f"Failed to create staff assignment for FSO {fso.name}: {str(e)}")
            # FSO is still created, assignment can be done manually
        
        return fso
    
    def _map_urgency_to_priority(self):
        """Map appointment urgency to FSO priority"""
        urgency_mapping = {
            'low': '0',
            'normal': '1', 
            'high': '2',
            'urgent': '3',
            'emergency': '4'
        }
        
        # Get urgency from appointment (add this field if needed)
        urgency = getattr(self, 'urgency', 'normal')
        return urgency_mapping.get(urgency, '1')
    
    def _get_appropriate_team(self):
        """Get appropriate field service team for this appointment"""
        # Find team based on service area or service type
        team = self.env['health.fieldservice.team'].search([
            ('service_type_ids', 'in', self.appointment_type_id.id),
            ('active', '=', True)
        ], limit=1)
        
        if not team:
            # Fallback to any active team
            team = self.env['health.fieldservice.team'].search([
                ('active', '=', True)
            ], limit=1)
        
        return team.id if team else False
    
    def action_complete(self):
        """Override complete to finalize FSO"""
        result = super().action_complete()
        
        # Complete associated FSO
        for appointment in self:
            if appointment.fieldservice_order_id and appointment.fieldservice_order_id.current_status != 'completed':
                try:
                    appointment.fieldservice_order_id.action_complete_service()
                except Exception as e:
                    _logger.warning(f"Failed to complete FSO {appointment.fieldservice_order_id.name}: {str(e)}")
        
        return result
    
    def action_cancel(self):
        """Override cancel to cancel FSO"""
        result = super().action_cancel()
        
        # Cancel associated FSO
        for appointment in self:
            if appointment.fieldservice_order_id and appointment.fieldservice_order_id.current_status not in ['completed', 'cancelled']:
                try:
                    appointment.fieldservice_order_id.action_cancel_service()
                except Exception as e:
                    _logger.warning(f"Failed to cancel FSO {appointment.fieldservice_order_id.name}: {str(e)}")
        
        return result
    
    def action_view_fieldservice_order(self):
        """View associated field service order"""
        self.ensure_one()
        
        if not self.fieldservice_order_id:
            raise UserError(_("No Field Service Order exists for this appointment."))
        
        return {
            'name': f'Field Service Order - {self.fieldservice_order_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'res_id': self.fieldservice_order_id.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    def action_create_fieldservice_order(self):
        """Manually create field service order"""
        self.ensure_one()
        
        if self.fieldservice_order_id:
            raise UserError(_("Field Service Order already exists for this appointment."))
        
        if self.state != 'confirmed':
            raise UserError(_("Appointment must be confirmed before creating Field Service Order."))
        
        fso = self._create_field_service_order()
        
        if fso:
            return self.action_view_fieldservice_order()
        else:
            raise UserError(_("Failed to create Field Service Order. Please check appointment details."))
    
    # ============================================================================
    # Staff Assignment Workflow Methods
    # ============================================================================
    
    def action_sales_approve(self):
        """Sales team approval for appointment"""
        self.ensure_one()
        
        self.assignment_state = 'ops_manager_review'
        self.sales_approved_by = self.env.user.id
        self.sales_approved_date = fields.Datetime.now()
        
        self.message_post(
            body=f"Sales approval completed by {self.env.user.name}",
            subject="Sales Approval",
            subtype_xmlid='mail.mt_comment'
        )
        
        return True
    
    def action_ops_manager_review(self):
        """Operations manager review and approval"""
        self.ensure_one()
        
        self.assignment_state = 'head_nurse_assign'
        self.ops_manager_approved_by = self.env.user.id
        self.ops_manager_approved_date = fields.Datetime.now()
        
        self.message_post(
            body=f"Operations review completed by {self.env.user.name}",
            subject="Operations Approval",
            subtype_xmlid='mail.mt_comment'
        )
        
        return True
    
    def action_head_nurse_assign_staff(self):
        """Head nurse assigns staff to appointment"""
        self.ensure_one()
        
        # This will open a wizard or form to assign staff
        self.assignment_state = 'staff_assigned'
        self.head_nurse_assigned_by = self.env.user.id
        self.head_nurse_assigned_date = fields.Datetime.now()
        
        self.message_post(
            body=f"Staff assignment initiated by {self.env.user.name}",
            subject="Staff Assignment",
            subtype_xmlid='mail.mt_comment'
        )
        
        # Open staff assignment wizard if available
        return {
            'name': 'Assign Staff',
            'type': 'ir.actions.act_window',
            'res_model': 'health.appointment',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'assignment_mode': True}
        }
    
    def action_staff_confirm_assignment(self):
        """Staff confirms assignment acceptance"""
        self.ensure_one()
        
        self.assignment_state = 'staff_confirmed'
        
        self.message_post(
            body=f"Assignment confirmed by {self.env.user.name}",
            subject="Assignment Confirmation",
            subtype_xmlid='mail.mt_comment'
        )
        
        # Trigger final preparation if all conditions met
        if self.assignment_state == 'staff_confirmed':
            self._check_ready_for_service()
        
        return True
    
    def _check_ready_for_service(self):
        """Check if appointment is ready for service delivery"""
        self.ensure_one()
        
        # Check if all requirements are met
        ready_conditions = [
            self.assignment_state == 'staff_confirmed',
            bool(self.assigned_staff_ids),
            self.state == 'confirmed'
        ]
        
        if all(ready_conditions):
            self.assignment_state = 'ready'
            self.message_post(
                body="Appointment ready for service delivery",
                subject="Ready for Service",
                subtype_xmlid='mail.mt_comment'
            )