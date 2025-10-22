# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HealthStaffAssignmentWizard(models.TransientModel):
    """
    Wizard for manual staff assignment to Field Service Orders
    """
    _name = 'health.staff.assignment.wizard'
    _description = 'Staff Assignment Wizard'
    
    # FSO Information (read-only)
    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Field Service Order',
        required=True,
        readonly=True
    )
    
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='fso_id.patient_id',
        readonly=True
    )
    
    service_type = fields.Selection([
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('consultation', 'Consultation'),
        ('emergency', 'Emergency Care'),
        ('follow_up', 'Follow-up Care'),
        ('preventive', 'Preventive Care'),
        ('rehabilitation', 'Rehabilitation'),
        ('telemedicine', 'Telemedicine/Online'),
        ('vaccination', 'Vaccination'),
        ('diagnostic', 'Diagnostic Services'),
    ], string='Service Type', related='fso_id.service_type', readonly=True)
    
    scheduled_datetime = fields.Datetime(
        'Current Scheduled Date/Time',
        related='fso_id.scheduled_datetime',
        readonly=True
    )
    
    new_scheduled_datetime = fields.Datetime(
        'New Scheduled Date/Time',
        help='Update the scheduled date/time for this service (optional)'
    )
    
    # Staff Assignment Fields
    doctor_id = fields.Many2one(
        'hr.employee',
        string='Assign Doctor',
        domain="[('is_healthcare_staff', '=', True), ('healthcare_role', '=', 'doctor'), ('employment_status', '=', 'active')]",
        help='Optional: Assign a doctor to this service'
    )

    assigned_staff_ids = fields.Many2many(
        'hr.employee',
        'wizard_staff_assignment_rel',
        'wizard_id',
        'employee_id',
        string='Assigned Nurses/Staff',
        domain="[('is_healthcare_staff', '=', True), ('employment_status', '=', 'active')]",
        help='Select healthcare staff members (nurses) to assign to this service'
    )

    lead_staff_id = fields.Many2one(
        'hr.employee',
        string='Lead Nurse',
        help='Primary nurse responsible for this service'
    )
    
    assignment_notes = fields.Text(
        'Assignment Notes',
        help='Optional notes about the staff assignment'
    )
    
    @api.onchange('assigned_staff_ids')
    def _onchange_assigned_staff_ids(self):
        """Update lead staff domain based on assigned staff"""
        if self.assigned_staff_ids:
            # If lead staff is not in assigned staff, clear it
            if self.lead_staff_id and self.lead_staff_id not in self.assigned_staff_ids:
                self.lead_staff_id = False
            
            # Set first assigned staff as default lead if none selected
            if not self.lead_staff_id and self.assigned_staff_ids:
                self.lead_staff_id = self.assigned_staff_ids[0]
                
        return {'domain': {'lead_staff_id': [('id', 'in', self.assigned_staff_ids.ids)]}}
    
    @api.model
    def default_get(self, fields_list):
        """Set default values based on FSO context"""
        defaults = super().default_get(fields_list)
        
        if self.env.context.get('default_fso_id'):
            fso = self.env['health.fieldservice.order'].browse(self.env.context['default_fso_id'])
            if fso.assigned_staff_ids:
                defaults['assigned_staff_ids'] = [(6, 0, fso.assigned_staff_ids.ids)]
                if fso.lead_staff_id:
                    defaults['lead_staff_id'] = fso.lead_staff_id.id
        
        return defaults
    
    def action_assign_staff(self):
        """Assign selected staff (doctor and nurses) to the FSO"""
        self.ensure_one()

        if not self.assigned_staff_ids and not self.doctor_id:
            raise UserError(_('Please select at least one staff member (doctor or nurse) to assign.'))

        # Update FSO with assigned staff and optionally new schedule
        update_vals = {
            'assigned_staff_ids': [(6, 0, self.assigned_staff_ids.ids)],
            'lead_staff_id': self.lead_staff_id.id if self.lead_staff_id else False,
            'primary_doctor_id': self.doctor_id.id if self.doctor_id else False,
        }

        # Update scheduled time if provided
        if self.new_scheduled_datetime:
            update_vals['scheduled_datetime'] = self.new_scheduled_datetime

        self.fso_id.write(update_vals)

        # Create individual staff assignment records
        existing_assignments = self.env['health.staff.assignment'].search([
            ('fso_id', '=', self.fso_id.id)
        ])
        existing_assignments.unlink()  # Remove existing assignments

        # Create doctor assignment if selected
        if self.doctor_id:
            self.env['health.staff.assignment'].create({
                'fso_id': self.fso_id.id,
                'staff_id': self.doctor_id.id,
                'assignment_role': 'doctor',
                'assignment_date': self.new_scheduled_datetime or self.scheduled_datetime or fields.Datetime.now(),
                'planned_start_time': self.new_scheduled_datetime or self.scheduled_datetime,
                'assignment_status': 'assigned',
                'state': 'assigned',
                'assignment_notes': self.assignment_notes or 'Manually assigned doctor via wizard',
            })

        # Create nurse assignments
        for staff in self.assigned_staff_ids:
            role = 'lead' if staff == self.lead_staff_id else 'support'
            self.env['health.staff.assignment'].create({
                'fso_id': self.fso_id.id,
                'staff_id': staff.id,
                'assignment_role': role,
                'assignment_date': self.new_scheduled_datetime or self.scheduled_datetime or fields.Datetime.now(),
                'planned_start_time': self.new_scheduled_datetime or self.scheduled_datetime,
                'assignment_status': 'assigned',
                'state': 'assigned',
                'assignment_notes': self.assignment_notes or 'Manually assigned nurse via wizard',
            })

        # Trigger state transition to Assigned stage
        self.fso_id._handle_staff_assignment()

        # Log the assignment
        staff_list = []
        if self.doctor_id:
            staff_list.append(f"Doctor: {self.doctor_id.name}")
        if self.assigned_staff_ids:
            staff_list.append(f"Nurses: {', '.join(self.assigned_staff_ids.mapped('name'))}")
        if self.lead_staff_id:
            staff_list.append(f"Lead Nurse: {self.lead_staff_id.name}")

        message_body = f"👥 Staff manually assigned:\n{chr(10).join(staff_list)}"

        if self.new_scheduled_datetime:
            message_body += f"\n📅 Rescheduled to: {self.new_scheduled_datetime.strftime('%Y-%m-%d %H:%M')}"

        self.fso_id.message_post(
            body=message_body,
            subject="Staff Assignment & Schedule Updated"
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Staff successfully assigned. Booking moved to Assigned stage.'),
                'type': 'success',
                'sticky': False,
            },
            'next': {'type': 'ir.actions.act_window_close'},
        }