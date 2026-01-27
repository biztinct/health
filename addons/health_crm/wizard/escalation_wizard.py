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
    
    When confirmed, sends Zalo message and email to the selected person.
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
    
    # Display the auto-selected person
    selected_person_name = fields.Char(
        'Selected Person',
        compute='_compute_selected_person',
        store=False,
        help='The person who will receive this escalation'
    )
    
    selected_person_id = fields.Many2one(
        'res.users',
        string='Selected Person Record',
        compute='_compute_selected_person',
        store=False
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
    
    # =========================================================================
    # COMPUTED FIELDS
    # =========================================================================
    
    @api.depends('escalate_to', 'escalate_to_user_id', 'lead_id')
    def _compute_selected_person(self):
        """Compute the selected person based on escalate_to role and catchment province"""
        for wizard in self:
            if wizard.escalate_to_user_id:
                wizard.selected_person_id = wizard.escalate_to_user_id
                wizard.selected_person_name = wizard.escalate_to_user_id.name
            else:
                person = wizard._get_person_for_role()
                wizard.selected_person_id = person
                wizard.selected_person_name = person.name if person else ''
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _get_person_for_role(self):
        """
        Find a person for the selected role from the same catchment province as the lead.
        Returns the first matching user.
        """
        self.ensure_one()
        
        if not self.escalate_to:
            return False
        
        User = self.env['res.users']
        Employee = self.env['hr.employee']
        
        # Get the lead's catchment province
        catchment_province = self.lead_id.catchment_province_id if self.lead_id else False
        
        # Map escalate_to selection to healthcare_role
        role_mapping = {
            'duty_doctor': 'duty_doctor',
            'head_nurse': 'head_nurse',
            'om': 'operations_manager',
        }
        healthcare_role = role_mapping.get(self.escalate_to)
        
        if not healthcare_role:
            return False
        
        # First try to find by user's catchment_province_id and healthcare_role
        user_domain = [
            ('active', '=', True),
            ('healthcare_role', '=', healthcare_role),
        ]
        
        if catchment_province:
            # Try with catchment province filter first
            user_domain.append(('catchment_province_id', '=', catchment_province.id))
            user = User.search(user_domain, limit=1)
            if user:
                return user
            
            # If not found, try without catchment province filter
            user_domain = [
                ('active', '=', True),
                ('healthcare_role', '=', healthcare_role),
            ]
        
        user = User.search(user_domain, limit=1)
        if user:
            return user
        
        # Try finding via employee record
        employee_domain = [
            ('active', '=', True),
            ('is_healthcare_staff', '=', True),
            ('healthcare_role', '=', healthcare_role),
            ('user_id', '!=', False),
        ]
        
        employee = Employee.search(employee_domain, limit=1)
        if employee and employee.user_id:
            return employee.user_id
        
        # Fallback to first admin user (using sudo to access internal users)
        # Find any user that has admin access
        try:
            admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
            if admin_group:
                admin_users = admin_group.users
                if admin_users:
                    return admin_users[0]
        except Exception:
            pass
        
        # Final fallback - return first active internal user
        return User.search([('active', '=', True), ('share', '=', False)], limit=1)
    
    # =========================================================================
    # WIZARD ACTIONS
    # =========================================================================
    
    def action_confirm_escalation(self):
        """
        Confirm and process the escalation/consultation transfer.
        Sends Zalo message and email to the selected person.
        """
        self.ensure_one()
        
        if not self.reason:
            raise ValidationError(_('Please provide a reason for escalation.'))
        
        # Get the person to notify
        assigned_user = self.escalate_to_user_id or self._get_person_for_role()
        
        if not assigned_user:
            raise ValidationError(_('Could not find a person to handle this escalation. Please select a specific person.'))
        
        # Update the lead with escalation information
        self.lead_id.write({
            'escalated_to': self.escalate_to,
            'escalation_datetime': fields.Datetime.now(),
            'escalation_notes': self._format_escalation_notes(),
        })
        
        # Create activity for the assigned person
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if activity_type:
            self.lead_id.activity_schedule(
                activity_type_id=activity_type.id,
                summary=self._get_activity_summary(),
                note=self._format_escalation_notes(),
                user_id=assigned_user.id,
                date_deadline=fields.Date.today(),
            )
        
        # Send notifications (Zalo + Email)
        self._send_notifications(assigned_user)
        
        # Post message to chatter
        escalate_to_label = dict(self._fields['escalate_to'].selection).get(self.escalate_to, self.escalate_to)
        urgency_label = dict(self._fields['urgency'].selection).get(self.urgency, self.urgency)
        
        message_body = _(
            '<strong>Contact Escalated</strong><br/>'
            '<b>Type:</b> %(type)s<br/>'
            '<b>Escalated To:</b> %(to)s (%(person)s)<br/>'
            '<b>Urgency:</b> %(urgency)s<br/>'
            '<b>Reason:</b> %(reason)s'
        ) % {
            'type': 'Consultation Request' if self.escalation_type == 'consultation' else 'Full Transfer',
            'to': escalate_to_label,
            'person': assigned_user.name,
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
        notification_message = _('Consultation request sent to %s.') if self.escalation_type == 'consultation' else _('Contact has been escalated to %s.')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Request Sent') if self.escalation_type == 'consultation' else _('Escalation Submitted'),
                'message': notification_message % assigned_user.name,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close',
                }
            }
        }
    
    def _send_notifications(self, user):
        """Send Zalo message and email to the assigned user"""
        self.ensure_one()
        
        # Prepare notification content
        escalate_to_label = dict(self._fields['escalate_to'].selection).get(self.escalate_to, self.escalate_to)
        urgency_label = dict(self._fields['urgency'].selection).get(self.urgency, self.urgency)
        
        subject = _('%(type)s: %(contact)s') % {
            'type': 'Consultation Request' if self.escalation_type == 'consultation' else 'Escalation',
            'contact': self.contact_name,
        }
        
        message_body = _(
            '%(type)s from %(from_user)s\n\n'
            'Contact: %(contact)s\n'
            'Phone: %(phone)s\n'
            'Urgency: %(urgency)s\n'
            'Reason: %(reason)s\n'
        ) % {
            'type': 'Consultation Request' if self.escalation_type == 'consultation' else 'Escalation',
            'from_user': self.env.user.name,
            'contact': self.contact_name,
            'phone': self.contact_phone or 'N/A',
            'urgency': urgency_label,
            'reason': self.reason,
        }
        
        if self.additional_notes:
            message_body += _('\nAdditional Notes: %s') % self.additional_notes
        
        # Send Email
        try:
            if user.email:
                mail_values = {
                    'subject': subject,
                    'body_html': message_body.replace('\n', '<br/>'),
                    'email_to': user.email,
                    'email_from': self.env.user.email or self.env.company.email,
                    'auto_delete': True,
                }
                mail = self.env['mail.mail'].sudo().create(mail_values)
                mail.send()
        except Exception as e:
            # Log but don't fail
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning('Failed to send email notification: %s', str(e))
        
        # Send Zalo message (if Zalo integration is available)
        try:
            # Check if zalo integration exists
            if hasattr(self.env, 'zalo.message') or 'zalo.message' in self.env:
                ZaloMessage = self.env['zalo.message']
                if user.partner_id and user.partner_id.phone:
                    ZaloMessage.sudo().create({
                        'phone': user.partner_id.phone,
                        'message': message_body,
                        'auto_send': True,
                    })
        except Exception as e:
            # Zalo integration not available or failed - log but don't fail
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info('Zalo message not sent (integration may not be available): %s', str(e))
    
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
    
    def action_cancel(self):
        """Cancel the escalation wizard"""
        return {'type': 'ir.actions.act_window_close'}
