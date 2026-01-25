# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthEscalationWizard(models.TransientModel):
    """
    Escalation & Consultation Transfer Wizard
    
    This wizard handles transferring/escalating contacts to:
    - Duty Doctor (for telemedicine/consultation)
    - Head Nurse (for clinical escalation)
    - Operations Manager (for operational issues)
    
    Used for both:
    - Consultation button: Transfer for consultation
    - Escalate button: Full contact transfer
    """
    _name = 'health.escalation.wizard'
    _description = 'Contact Escalation/Consultation Wizard'

    # =========================================================================
    # WIZARD FIELDS
    # =========================================================================
    
    lead_id = fields.Many2one(
        'crm.lead',
        string='Contact',
        required=True,
        ondelete='cascade',
        help='The contact being escalated'
    )
    
    escalation_type = fields.Selection([
        ('consultation', 'Consultation Request'),
        ('transfer', 'Full Transfer'),
    ], string='Escalation Type', required=True, default='consultation',
       help='Consultation = Temporary transfer for advice; Transfer = Full handover')
    
    escalate_to = fields.Selection([
        ('duty_doctor', 'Duty Doctor'),
        ('head_nurse', 'Head Nurse'),
        ('om', 'Operations Manager'),
    ], string='Escalate To', required=True,
       help='Person/role to escalate this contact to')
    
    # Optional: specific person selection
    escalate_to_user_id = fields.Many2one(
        'res.users',
        string='Specific Person',
        help='Optionally select a specific person to handle this'
    )
    
    urgency = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Urgency', default='normal', required=True)
    
    reason = fields.Text(
        'Reason for Escalation',
        required=True,
        help='Explain why this contact needs escalation/consultation'
    )
    
    additional_notes = fields.Text(
        'Additional Notes',
        help='Any additional context or information for the recipient'
    )
    
    # Contact summary (readonly, for context)
    contact_name = fields.Char(
        'Contact Name',
        related='lead_id.name',
        readonly=True
    )
    
    contact_phone = fields.Char(
        'Phone',
        related='lead_id.phone',
        readonly=True
    )
    
    contact_status = fields.Selection(
        related='lead_id.contact_status',
        readonly=True
    )
    
    # Note: Domain filtering for escalate_to_user_id removed to avoid
    # conflicts with synconics_bi_dashboard module's name_search override.
    # Users can select any active user.
    
    # =========================================================================
    # WIZARD ACTIONS
    # =========================================================================
    
    def action_confirm_escalation(self):
        """
        Confirm and process the escalation/consultation transfer.
        """
        self.ensure_one()
        
        if not self.reason:
            raise ValidationError(_('Please provide a reason for escalation.'))
        
        # Update the lead with escalation information
        self.lead_id.write({
            'escalated_to': self.escalate_to,
            'escalation_datetime': fields.Datetime.now(),
            'escalation_notes': self._format_escalation_notes(),
        })
        
        # Create activity for the assigned person
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if activity_type:
            # Determine user to assign
            if self.escalate_to_user_id:
                assigned_user = self.escalate_to_user_id
            else:
                # Find default user based on role
                assigned_user = self._get_default_user_for_role()
            
            if assigned_user:
                # Create activity
                self.lead_id.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=self._get_activity_summary(),
                    note=self._format_escalation_notes(),
                    user_id=assigned_user.id,
                    date_deadline=fields.Date.today(),
                )
        
        # Post message to chatter
        escalate_to_label = dict(self._fields['escalate_to'].selection).get(self.escalate_to, self.escalate_to)
        urgency_label = dict(self._fields['urgency'].selection).get(self.urgency, self.urgency)
        
        message_body = _(
            '<strong>Contact Escalated</strong><br/>'
            '<b>Type:</b> %(type)s<br/>'
            '<b>Escalated To:</b> %(to)s<br/>'
            '<b>Urgency:</b> %(urgency)s<br/>'
            '<b>Reason:</b> %(reason)s'
        ) % {
            'type': 'Consultation Request' if self.escalation_type == 'consultation' else 'Full Transfer',
            'to': escalate_to_label,
            'urgency': urgency_label,
            'reason': self.reason,
        }
        
        if self.additional_notes:
            message_body += _('<br/><b>Additional Notes:</b> %s') % self.additional_notes
        
        self.lead_id.message_post(
            body=message_body,
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
        
        # Return notification and reload form
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Escalation Submitted'),
                'message': _('Contact has been escalated to %s.') % escalate_to_label,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close',
                }
            }
        }
    
    def _format_escalation_notes(self):
        """Format escalation notes for storage"""
        notes = []
        notes.append(_('Type: %s') % ('Consultation' if self.escalation_type == 'consultation' else 'Transfer'))
        notes.append(_('Urgency: %s') % self.urgency)
        notes.append(_('Reason: %s') % self.reason)
        if self.additional_notes:
            notes.append(_('Notes: %s') % self.additional_notes)
        return '\n'.join(notes)
    
    def _get_activity_summary(self):
        """Generate activity summary based on escalation type"""
        if self.escalation_type == 'consultation':
            return _('Consultation Request: %s') % self.lead_id.name
        else:
            return _('Escalated Contact: %s') % self.lead_id.name
    
    def _get_default_user_for_role(self):
        """
        Find a default user for the selected role.
        Falls back to admin if no specific user found.
        """
        User = self.env['res.users']
        
        if self.escalate_to == 'duty_doctor':
            # Try to find a user with doctor in their groups or job title
            doctor = User.search([
                ('active', '=', True),
                '|',
                ('groups_id.name', 'ilike', 'doctor'),
                ('employee_id.job_title', 'ilike', 'doctor'),
            ], limit=1)
            if doctor:
                return doctor
        
        elif self.escalate_to == 'head_nurse':
            nurse = User.search([
                ('active', '=', True),
                '|',
                ('groups_id.name', 'ilike', 'head nurse'),
                ('employee_id.job_title', 'ilike', 'head nurse'),
            ], limit=1)
            if nurse:
                return nurse
        
        elif self.escalate_to == 'om':
            # Try to find operations manager
            om = User.search([
                ('active', '=', True),
                '|',
                ('groups_id.name', 'ilike', 'operations'),
                ('employee_id.job_title', 'ilike', 'operations'),
            ], limit=1)
            if om:
                return om
        
        # Fallback to first admin user
        return User.search([('groups_id', 'in', [self.env.ref('base.group_system').id])], limit=1)
    
    def action_cancel(self):
        """Cancel the escalation wizard"""
        return {'type': 'ir.actions.act_window_close'}
