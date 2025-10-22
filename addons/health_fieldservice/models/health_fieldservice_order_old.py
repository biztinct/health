from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class HealthFieldServiceOrder(models.Model):
    """
    Healthcare Field Service Order - Standalone model inspired by fieldservice but no inheritance
    Central orchestration point for home visit service delivery
    """
    _name = 'health.fieldservice.order'
    _description = 'Healthcare Field Service Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, priority desc'
    _rec_name = 'name'
    
    # ============================================================================
    # Core Identification & References
    # ============================================================================
    
    name = fields.Char(
        'FSO Reference', 
        required=True, 
        copy=False, 
        readonly=True,
        default=lambda self: _('New FSO'),
        tracking=True
    )
    
    # Healthcare workflow links (corrected relationship)
    appointment_id = fields.Many2one(
        'health.appointment', 
        string='Appointment',
        required=True, 
        ondelete='cascade',
        tracking=True,
        help="The appointment that triggered this field service order"
    )
    
    patient_id = fields.Many2one(
        related='appointment_id.patient_id', 
        string='Client',
        store=True,
        readonly=True
    )
    
    # Direct staff assignment (FSO is independent - staff assignment references this)
    assigned_staff_ids = fields.Many2many(
        'hr.employee',
        'fieldservice_staff_rel',
        'fso_id', 'employee_id',
        string='Assigned Staff',
        domain=[('is_healthcare_staff', '=', True)],
        tracking=True,
        help="Staff assigned to this field service order"
    )
    
    lead_staff_id = fields.Many2one(
        'hr.employee',
        string='Lead Staff',
        domain=[('is_healthcare_staff', '=', True)],
        tracking=True,
        help='Primary staff member responsible for this field service'
    )
    
    # ============================================================================
    # Field Service Workflow Management
    # ============================================================================
    
    stage_id = fields.Many2one(
        'health.fieldservice.stage',
        string='Stage',
        required=True,
        tracking=True,
        group_expand='_read_group_stage_ids',
        default=lambda self: self._get_default_stage()
    )
    
    team_id = fields.Many2one(
        'health.fieldservice.team',
        string='Field Service Team',
        tracking=True
    )
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
        ('4', 'Emergency')
    ], string='Priority', default='1', tracking=True)
    
    # ============================================================================
    # Equipment Management
    # ============================================================================
    
    required_equipment_ids = fields.Many2many(
        'health.portable.equipment',
        'fso_required_equipment_rel',
        'fso_id', 'equipment_id',
        string='Required Equipment',
        help="Medical equipment required for this service"
    )
    
    assigned_equipment_ids = fields.Many2many(
        'health.portable.equipment',
        'fso_assigned_equipment_rel',
        'fso_id', 'equipment_id',
        string='Assigned Equipment',
        help="Equipment actually assigned to this service order"
    )
    
    equipment_checklist_complete = fields.Boolean(
        'Equipment Checklist Complete',
        help="Indicates if all required equipment has been verified and assigned"
    )
    
    # ============================================================================
    # Clinical Protocol Integration (Your Template Requirement)
    # ============================================================================
    
    clinical_protocol_id = fields.Many2one(
        'health.clinical.protocol',
        string='Clinical Protocol',
        help="Clinical protocol template with action steps for this service type"
    )
    
    service_steps_json = fields.Json(
        'Service Action Steps',
        help="Dynamic action steps loaded from clinical protocol template"
    )
    
    completed_steps_json = fields.Json(
        'Completed Steps',
        help="Track which action steps have been completed by field staff"
    )
    
    protocol_completion_percentage = fields.Float(
        'Protocol Completion %',
        compute='_compute_protocol_completion',
        store=True,
        help="Percentage of protocol steps completed"
    )
    
    # ============================================================================
    # Real-time Status & Communication (Your Highest Priority)
    # ============================================================================
    
    current_status = fields.Selection([
        ('draft', 'Draft'),
        ('dispatched', 'Dispatched'),
        ('en_route', 'En Route'),
        ('arrived', 'Arrived at Patient'),
        ('in_progress', 'Service in Progress'),
        ('completed', 'Service Completed'),
        ('cancelled', 'Cancelled')
    ], string='Real-time Status', default='draft', tracking=True)
    
    communication_ids = fields.One2many(
        'health.fieldservice.communication',
        'fieldservice_order_id',
        string='Communications',
        help="Real-time communication log for this field service"
    )
    
    urgent_communications = fields.Integer(
        'Urgent Messages',
        compute='_compute_urgent_communications',
        help="Count of urgent/unread communications"
    )
    
    # ============================================================================
    # Location & Scheduling
    # ============================================================================
    
    patient_location = fields.Char(
        'Patient Address',
        related='appointment_id.patient_address',
        readonly=True
    )
    
    scheduled_date = fields.Datetime(
        'Scheduled Date/Time',
        related='appointment_id.appointment_datetime',
        readonly=True
    )
    
    actual_start = fields.Datetime(
        'Actual Start Time',
        tracking=True
    )
    
    actual_end = fields.Datetime(
        'Actual End Time',
        tracking=True
    )
    
    duration_minutes = fields.Integer(
        'Actual Duration (minutes)',
        compute='_compute_duration',
        store=True
    )
    
    # GPS tracking fields
    gps_latitude = fields.Float('Current GPS Latitude', digits=(10, 6))
    gps_longitude = fields.Float('Current GPS Longitude', digits=(10, 6))
    last_location_update = fields.Datetime('Last Location Update')
    
    # ============================================================================
    # Invoice Integration (Vietnamese Compliance)
    # ============================================================================
    
    draft_invoice_id = fields.Many2one(
        'account.move',
        string='Draft Invoice',
        help="Draft invoice created automatically when FSO is generated"
    )
    
    final_invoice_id = fields.Many2one(
        'account.move',
        string='Final Invoice',
        help="Final invoice confirmed upon service completion"
    )
    
    invoice_status = fields.Selection([
        ('draft', 'Draft Invoice Created'),
        ('confirmed', 'Invoice Confirmed'),
        ('paid', 'Invoice Paid')
    ], string='Invoice Status', default='draft', tracking=True)
    
    # ============================================================================
    # Computed Fields
    # ============================================================================
    
    @api.depends('service_steps_json', 'completed_steps_json')
    def _compute_protocol_completion(self):
        """Calculate completion percentage of clinical protocol steps"""
        for record in self:
            if not record.service_steps_json or not record.completed_steps_json:
                record.protocol_completion_percentage = 0.0
                continue
                
            try:
                total_steps = len(record.service_steps_json)
                completed_steps = len(record.completed_steps_json)
                record.protocol_completion_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0.0
            except (TypeError, ValueError):
                record.protocol_completion_percentage = 0.0
    
    @api.depends('communication_ids.priority', 'communication_ids.is_read')
    def _compute_urgent_communications(self):
        """Count urgent/unread communications"""
        for record in self:
            urgent_count = record.communication_ids.filtered(
                lambda c: c.priority == 'high' and not c.is_read
            )
            record.urgent_communications = len(urgent_count)
    
    @api.depends('actual_start', 'actual_end')
    def _compute_duration(self):
        """Calculate actual service duration"""
        for record in self:
            if record.actual_start and record.actual_end:
                delta = record.actual_end - record.actual_start
                record.duration_minutes = int(delta.total_seconds() / 60)
            else:
                record.duration_minutes = 0
    
    # ============================================================================
    # Default Methods
    # ============================================================================
    
    def _get_default_stage(self):
        """Get default stage for new FSO"""
        return self.env['health.fieldservice.stage'].search([('sequence', '=', 10)], limit=1)
    
    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Enable stage grouping in kanban view"""
        return self.env['health.fieldservice.stage'].search([])
    
    # ============================================================================
    # CRUD Methods
    # ============================================================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate FSO reference and draft invoice"""
        for vals in vals_list:
            if vals.get('name', _('New FSO')) == _('New FSO'):
                vals['name'] = self.env['ir.sequence'].next_by_code('health.fieldservice.order') or _('New FSO')
        
        records = super().create(vals_list)
        
        # Create draft invoices for Vietnamese compliance
        for record in records:
            record._create_draft_invoice()
            record._load_clinical_protocol()
            
        return records
    
    # ============================================================================
    # Business Logic Methods
    # ============================================================================
    
    def _create_draft_invoice(self):
        """Create draft invoice immediately upon FSO creation for Vietnamese tax compliance"""
        self.ensure_one()
        
        if self.draft_invoice_id:
            return self.draft_invoice_id
            
        # Get service details from appointment
        service_type = self.appointment_id.service_type_id
        if not service_type:
            raise UserError(_("Appointment must have a service type to generate invoice."))
        
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.id,
            'invoice_date': fields.Date.today(),
            'state': 'draft',
            'ref': f"FSO-{self.name}",
            'invoice_origin': self.appointment_id.name,
            'invoice_line_ids': [(0, 0, {
                'name': f"Healthcare Field Service - {service_type.name}",
                'quantity': 1,
                'price_unit': service_type.list_price or 0.0,
                'account_id': self._get_service_account_id(),
            })]
        }
        
        draft_invoice = self.env['account.move'].create(invoice_vals)
        self.draft_invoice_id = draft_invoice.id
        self.invoice_status = 'draft'
        
        _logger.info(f"Draft invoice {draft_invoice.name} created for FSO {self.name}")
        return draft_invoice
    
    def _get_service_account_id(self):
        """Get appropriate account for healthcare services"""
        # This should be configured per company/localization
        account = self.env['account.account'].search([
            ('code', 'like', '400%'),  # Revenue account
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not account:
            # Fallback to any income account
            account = self.env['account.account'].search([
                ('account_type', '=', 'income'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            
        return account.id if account else False
    
    def _load_clinical_protocol(self):
        """Load clinical protocol steps based on appointment service type"""
        self.ensure_one()
        
        if not self.appointment_id.service_type_id:
            return
            
        # Find matching clinical protocol
        protocol = self.env['health.clinical.protocol'].search([
            ('service_type_ids', 'in', self.appointment_id.service_type_id.id)
        ], limit=1)
        
        if protocol:
            self.clinical_protocol_id = protocol.id
            self.service_steps_json = protocol.action_steps_template
            self.required_equipment_ids = [(6, 0, protocol.required_equipment_ids.ids)]
    
    def action_trigger_staff_assignment(self):
        """Trigger AI staff assignment after FSO creation (requires health_staff_assignment module)"""
        self.ensure_one()
        
        # Check if staff assignment module is available
        if 'health.staff.assignment' not in self.env.registry:
            raise UserError(_("Staff assignment functionality requires the health_staff_assignment module to be installed."))
        
        # Create staff assignment record with FSO link
        assignment_vals = {
            'appointment_id': self.appointment_id.id,
            'assignment_date': self.scheduled_date,
            'assignment_type': 'home_visit',  # FSO is always for home visits
            'priority': self.priority,
            'fieldservice_order_id': self.id,  # Link assignment to this FSO
            # Add equipment requirements for AI consideration
            'required_skills_json': json.dumps({
                'service_type': self.appointment_id.service_type_id.name,
                'required_equipment': [eq.name for eq in self.required_equipment_ids],
                'clinical_protocol': self.clinical_protocol_id.name if self.clinical_protocol_id else None
            })
        }
        
        staff_assignment = self.env['health.staff.assignment'].create(assignment_vals)
        
        # Update assignment with FSO requirements
        if hasattr(staff_assignment, 'update_from_fieldservice_order'):
            staff_assignment.update_from_fieldservice_order()
        
        # Trigger AI optimization
        if hasattr(staff_assignment, 'action_apply_ai_optimization'):
            staff_assignment.action_apply_ai_optimization()
        
        # Copy assigned staff from assignment to FSO
        if staff_assignment.assigned_staff_ids:
            self.assigned_staff_ids = [(6, 0, staff_assignment.assigned_staff_ids.ids)]
            self.lead_staff_id = staff_assignment.lead_staff_id.id
        
        # Update FSO stage
        dispatched_stage = self.env['health.fieldservice.stage'].search([('name', '=', 'Dispatched')], limit=1)
        if dispatched_stage:
            self.stage_id = dispatched_stage.id
            
        self.current_status = 'dispatched'
        
        # Send mobile dispatch notification
        self._send_mobile_dispatch_notification()
        
        return staff_assignment
    
    def _send_mobile_dispatch_notification(self):
        """Send mobile dispatch notification to assigned staff"""
        self.ensure_one()
        
        if not self.assigned_staff_ids:
            return
            
        # Create communication record
        message = f"""
🚨 NEW FIELD SERVICE ASSIGNMENT

Patient: {self.patient_id.name}
Service: {self.appointment_id.service_type_id.name}
Location: {self.patient_location}
Scheduled: {self.scheduled_date}

Equipment Required:
{chr(10).join(['• ' + eq.name for eq in self.required_equipment_ids])}

Please confirm receipt and estimated arrival time.
        """
        
        communication = self.env['health.fieldservice.communication'].create({
            'fieldservice_order_id': self.id,
            'message_type': 'urgent_request',
            'message': message,
            'priority': 'high',
            'requires_response': True,
        })
        
        # Send notification to each assigned staff member
        for staff in self.assigned_staff_ids:
            if staff.user_id:
                self.message_post(
                    body=message,
                    subject=f"Field Service Assignment - {self.name}",
                    partner_ids=[staff.user_id.partner_id.id],
                    subtype_xmlid='mail.mt_comment'
                )
    
    def action_start_service(self):
        """Start field service execution"""
        self.ensure_one()
        
        self.actual_start = fields.Datetime.now()
        self.current_status = 'in_progress'
        
        # Update stage
        in_progress_stage = self.env['health.fieldservice.stage'].search([('name', '=', 'In Progress')], limit=1)
        if in_progress_stage:
            self.stage_id = in_progress_stage.id
    
    def action_complete_service(self):
        """Complete field service and finalize invoice"""
        self.ensure_one()
        
        # Validate protocol completion
        if self.protocol_completion_percentage < 100:
            raise UserError(_("All clinical protocol steps must be completed before finishing service."))
        
        self.actual_end = fields.Datetime.now()
        self.current_status = 'completed'
        
        # Update stage
        completed_stage = self.env['health.fieldservice.stage'].search([('name', '=', 'Completed')], limit=1)
        if completed_stage:
            self.stage_id = completed_stage.id
        
        # Finalize invoice
        if self.draft_invoice_id:
            self.final_invoice_id = self.draft_invoice_id
            self.final_invoice_id.action_post()  # Confirm invoice
            self.invoice_status = 'confirmed'
            
        # Update appointment status
        if self.appointment_id:
            self.appointment_id.action_complete()
            
        _logger.info(f"Field service {self.name} completed successfully")
    
    def action_cancel_service(self):
        """Cancel field service order"""
        self.ensure_one()
        
        self.current_status = 'cancelled'
        
        # Update stage
        cancelled_stage = self.env['health.fieldservice.stage'].search([('name', '=', 'Cancelled')], limit=1)
        if cancelled_stage:
            self.stage_id = cancelled_stage.id
            
        # Cancel draft invoice if exists
        if self.draft_invoice_id and self.draft_invoice_id.state == 'draft':
            self.draft_invoice_id.button_cancel()
    
    def update_gps_location(self, latitude, longitude):
        """Update GPS location from mobile app"""
        self.ensure_one()
        
        self.gps_latitude = latitude
        self.gps_longitude = longitude
        self.last_location_update = fields.Datetime.now()
        
        # Create location update communication
        self.env['health.fieldservice.communication'].create({
            'fieldservice_order_id': self.id,
            'message_type': 'status_update',
            'message': f"Location updated: {latitude}, {longitude}",
            'gps_latitude': latitude,
            'gps_longitude': longitude,
            'priority': 'low'
        })