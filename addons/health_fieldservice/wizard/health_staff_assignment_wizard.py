# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class HealthStaffAssignmentWizard(models.TransientModel):
    _name = 'health.staff.assignment.wizard'
    _description = 'Staff Assignment Wizard'

    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
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

    doctor_id = fields.Many2one(
        'hr.employee',
        string='Assign Doctor',
        domain="[('is_healthcare_staff', '=', True), ('is_doctor_role', '=', True), ('employment_status', '=', 'active')]",
        help='Optional: Assign a doctor to this service'
    )

    assigned_staff_ids = fields.Many2many(
        'hr.employee',
        'wizard_staff_assignment_rel',
        'wizard_id',
        'employee_id',
        string='Assigned Nurses/Staff',
        domain="[('is_healthcare_staff', '=', True), ('employment_status', '=', 'active'), ('is_nurse_role', '=', True)]",
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

    ai_suggestions_json = fields.Text(
        'AI Suggestions Data',
        compute='_compute_ai_suggestions',
    )

    selected_suggestion_staff_id = fields.Many2one(
        'hr.employee',
        string='AI-Selected Staff',
        domain="[('is_healthcare_staff', '=', True), ('employment_status', '=', 'active'), ('is_nurse_role', '=', True)]",
        help='Staff member selected from AI recommendations'
    )
    
    @api.depends('fso_id')
    def _compute_ai_suggestions(self):
        for wizard in self:
            if not wizard.fso_id:
                wizard.ai_suggestions_json = '[]'
                continue
            try:
                suggestions = wizard._get_fso_staff_suggestions(wizard.fso_id, limit=5)
                wizard.ai_suggestions_json = json.dumps(suggestions)
            except Exception as e:
                _logger.warning("AI suggestions failed for FSO %s: %s", wizard.fso_id.id, e)
                wizard.ai_suggestions_json = '[]'

    def _get_fso_staff_suggestions(self, fso, limit=5):
        available_staff = self.env['hr.employee'].search([
            ('is_healthcare_staff', '=', True),
            ('employment_status', '=', 'active'),
            ('active', '=', True),
        ])
        if not available_staff:
            return []

        fso_date = fso.scheduled_datetime or fields.Datetime.now()
        date_obj = fso_date.date() if hasattr(fso_date, 'date') else fso_date
        duration = fso.estimated_duration or 2.0

        required_skills = []
        if hasattr(fso, 'service_type_id') and fso.service_type_id:
            if hasattr(fso.service_type_id, 'required_skills_json') and fso.service_type_id.required_skills_json:
                try:
                    required_skills = json.loads(fso.service_type_id.required_skills_json)
                except Exception:
                    pass

        suggestions = []
        for staff in available_staff:
            skill_score = self._calc_skill_score(staff, required_skills)
            workload_score = self._calc_workload_score(staff, date_obj)
            availability_score = self._calc_availability_score(staff, fso_date, duration, date_obj)
            proximity_score = self._calc_proximity_score(staff, fso)

            total_score = (
                skill_score * 0.35 +
                availability_score * 0.30 +
                workload_score * 0.20 +
                proximity_score * 0.15
            )

            daily_assignments = self.env['health.staff.assignment'].search_count([
                ('staff_id', '=', staff.id),
                ('assignment_date', '>=', date_obj),
                ('assignment_date', '<', date_obj + timedelta(days=1)),
                ('state', 'in', ['assigned', 'confirmed', 'in_progress']),
            ])

            week_start = date_obj - timedelta(days=date_obj.weekday())
            week_end = week_start + timedelta(days=7)
            week_assignments = self.env['health.staff.assignment'].search_count([
                ('staff_id', '=', staff.id),
                ('assignment_date', '>=', week_start),
                ('assignment_date', '<', week_end),
                ('state', 'in', ['assigned', 'confirmed', 'in_progress', 'completed']),
            ])

            schedule_blocks = self._get_staff_schedule_blocks(staff, date_obj)

            staff_skills = staff.healthcare_skill_ids.mapped('name') if hasattr(staff, 'healthcare_skill_ids') else []
            skill_tags = []
            if required_skills:
                for sk in required_skills:
                    if sk in staff_skills:
                        skill_tags.append({'name': sk, 'status': 'match'})
                    else:
                        skill_tags.append({'name': sk, 'status': 'missing'})
                for sk in staff_skills:
                    if sk not in required_skills:
                        skill_tags.append({'name': sk, 'status': 'extra'})
            else:
                for sk in staff_skills[:6]:
                    skill_tags.append({'name': sk, 'status': 'match'})

            name = staff.name or ''
            initials = ''.join(w[0].upper() for w in name.split() if w)[:2]
            status = 'available'
            if staff.assignment_status == 'on_assignment':
                status = 'busy'
            elif staff.assignment_status == 'off_duty':
                status = 'off'

            has_conflict = any(
                b.get('conflict', False) for b in schedule_blocks
            )

            suggestions.append({
                'staff_id': staff.id,
                'staff_name': name,
                'initials': initials,
                'role': staff.job_title or 'Nurse',
                'status': status,
                'total_score': round(total_score, 1),
                'skill_score': round(skill_score, 1),
                'workload_score': round(workload_score, 1),
                'availability_score': round(availability_score, 1),
                'proximity_score': round(proximity_score, 1),
                'today_assignments': daily_assignments,
                'week_assignments': week_assignments,
                'skill_tags': skill_tags,
                'schedule_blocks': schedule_blocks,
                'has_conflict': has_conflict,
                'reason': self._get_suggestion_reason(
                    skill_score, proximity_score, workload_score, availability_score
                ),
            })

        suggestions.sort(key=lambda x: x['total_score'], reverse=True)
        return suggestions[:limit]

    def _calc_skill_score(self, staff, required_skills):
        if not required_skills:
            return 85.0
        staff_skills = staff.healthcare_skill_ids.mapped('name') if hasattr(staff, 'healthcare_skill_ids') else []
        if not staff_skills:
            return 50.0
        matched = set(required_skills) & set(staff_skills)
        match_pct = len(matched) / len(required_skills) * 100
        bonus = min(len(staff_skills) - len(required_skills), 3) * 5
        return min(match_pct + max(bonus, 0), 100)

    def _calc_workload_score(self, staff, date_obj):
        daily = self.env['health.staff.assignment'].search_count([
            ('staff_id', '=', staff.id),
            ('assignment_date', '>=', date_obj),
            ('assignment_date', '<', date_obj + timedelta(days=1)),
            ('state', 'in', ['assigned', 'confirmed', 'in_progress']),
        ])
        return max(0, 100 - (daily / 8) * 100)

    def _calc_availability_score(self, staff, fso_datetime, duration_hours, date_obj):
        if not fso_datetime:
            return 70.0
        start_hour = fso_datetime.hour + fso_datetime.minute / 60.0
        end_hour = start_hour + duration_hours

        conflicts = self.env['health.staff.assignment'].search([
            ('staff_id', '=', staff.id),
            ('assignment_date', '>=', date_obj),
            ('assignment_date', '<', date_obj + timedelta(days=1)),
            ('state', 'in', ['assigned', 'confirmed', 'in_progress']),
        ])
        for asg in conflicts:
            asg_start = asg.planned_start_time
            if asg_start:
                asg_start_h = asg_start.hour + asg_start.minute / 60.0
                asg_end_h = asg_start_h + (asg.planned_duration or 2.0)
                if asg_start_h < end_hour and asg_end_h > start_hour:
                    return 0.0
        return 90.0

    def _calc_proximity_score(self, staff, fso):
        service_type = fso.service_type
        if service_type == 'telemedicine':
            return 95.0
        if service_type in ('clinic_visit', 'consultation'):
            return 80.0
        return 75.0

    def _get_staff_schedule_blocks(self, staff, date_obj):
        assignments = self.env['health.staff.assignment'].search([
            ('staff_id', '=', staff.id),
            ('assignment_date', '>=', date_obj),
            ('assignment_date', '<', date_obj + timedelta(days=1)),
            ('state', 'in', ['assigned', 'confirmed', 'in_progress']),
        ])
        blocks = []
        for asg in assignments:
            start_h = 8.0
            if asg.planned_start_time:
                start_h = asg.planned_start_time.hour + asg.planned_start_time.minute / 60.0
            end_h = start_h + (asg.planned_duration or 2.0)
            blocks.append({
                'start_hour': round(start_h, 2),
                'end_hour': round(end_h, 2),
                'booking_name': asg.fso_id.name or '',
                'service_type': asg.fso_id.service_type or '',
                'type': 'existing',
            })
        return blocks

    def _get_suggestion_reason(self, skill, proximity, workload, availability):
        reasons = []
        if skill >= 90:
            reasons.append("Perfect skill match")
        elif skill >= 75:
            reasons.append("Good skill match")
        if availability >= 85:
            reasons.append("Excellent availability")
        elif availability < 50:
            reasons.append("Limited availability")
        if workload >= 80:
            reasons.append("Balanced workload")
        elif workload < 50:
            reasons.append("High current load")
        if proximity >= 85:
            reasons.append("Optimal location")
        return " • ".join(reasons) if reasons else "Standard assignment"

    @api.onchange('selected_suggestion_staff_id')
    def _onchange_selected_suggestion(self):
        if self.selected_suggestion_staff_id:
            if self.selected_suggestion_staff_id not in self.assigned_staff_ids:
                self.assigned_staff_ids = [(4, self.selected_suggestion_staff_id.id)]
            self.lead_staff_id = self.selected_suggestion_staff_id

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

        try:
            self.fso_id.message_post(
                body=message_body,
                subject="Staff Assignment & Schedule Updated"
            )
        except Exception:
            pass  # Silently fail - no email notifications required

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