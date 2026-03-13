# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthBookingCancellationWizard(models.TransientModel):
    """
    Booking Cancellation Wizard
    
    This wizard handles recording cancellations with detailed information:
    - Date/Time stamp (auto)
    - Reason for cancellation
    - Who cancelled (on client side)
    - Who reported the cancellation (name/position)
    - For repeat clients: Last person who visited
    """
    _name = 'health.booking.cancellation.wizard'
    _description = 'Booking Cancellation Wizard'

    # =========================================================================
    # WIZARD FIELDS
    # =========================================================================
    
    lead_id = fields.Many2one(
        'crm.lead',
        string='Contact',
        required=True,
        ondelete='cascade',
        help='The contact with the booking to cancel'
    )
    
    booking_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        help='The booking being cancelled (auto-detected from contact)'
    )
    
    # Cancellation Details
    cancellation_datetime = fields.Datetime(
        'Cancellation Date/Time',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        help='When the cancellation was recorded'
    )
    
    cancellation_reason_id = fields.Many2one(
        'health.booking.cancellation.reason',
        string='Cancellation Reason',
        help='Structured reason for cancellation'
    )
    
    cancellation_reason_text = fields.Text(
        'Reason Details',
        required=True,
        help='Detailed explanation for the cancellation'
    )
    
    # Who cancelled (on client side)
    cancelled_by_client = fields.Char(
        'Cancelled By (Client Side)',
        required=True,
        help='Name of the person on the client side who initiated the cancellation'
    )
    
    cancelled_by_relationship = fields.Selection([
        ('patient', 'Patient/Client'),
        ('family', 'Family Member'),
        ('caregiver', 'Caregiver'),
        ('representative', 'Representative'),
        ('other', 'Other'),
    ], string='Relationship to Client', default='patient',
       help='Relationship of the person who cancelled to the client')
    
    # Who reported the cancellation
    reported_by_name = fields.Char(
        'Reported By',
        required=True,
        help='Name of the person who reported this cancellation to us'
    )
    
    reported_by_position = fields.Char(
        'Reporter Position',
        help='Position/role of the person who reported (e.g., "Son", "Nurse", "Receptionist")'
    )
    
    # For repeat clients
    is_repeat_client = fields.Boolean(
        'Repeat Client?',
        compute='_compute_is_repeat_client',
        store=False
    )
    
    last_visiting_staff_id = fields.Many2one(
        'hr.employee',
        string='Last Person Who Visited',
        domain=[('is_healthcare_staff', '=', True)],
        help='For repeat clients - which staff member last visited this client'
    )
    
    # Reschedule option
    wants_reschedule = fields.Boolean(
        'Client Wants to Reschedule?',
        default=False,
        help='Does the client want to reschedule the appointment?'
    )
    
    reschedule_notes = fields.Text(
        'Reschedule Preferences',
        help='Client preferences for rescheduling (preferred dates/times)'
    )
    
    # Contact summary (readonly)
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
    
    # =========================================================================
    # COMPUTED FIELDS
    # =========================================================================
    
    @api.depends('lead_id')
    def _compute_is_repeat_client(self):
        """Check if this is a repeat client"""
        for wizard in self:
            wizard.is_repeat_client = wizard.lead_id.contact_type == 'repeat'
    
    @api.model
    def default_get(self, fields_list):
        """Auto-detect booking from lead if available"""
        defaults = super().default_get(fields_list)
        
        if defaults.get('lead_id'):
            lead = self.env['crm.lead'].browse(defaults['lead_id'])
            
            # Find related booking
            booking = self.env['health.fieldservice.order'].search([
                ('crm_lead_id', '=', lead.id),
                ('state', 'not in', ['cancelled', 'completed', 'closed'])
            ], limit=1, order='create_date desc')
            
            if booking:
                defaults['booking_id'] = booking.id
            
            # Pre-fill last visiting staff for repeat clients
            if lead.contact_type == 'repeat' and lead.patient_id:
                # Find last completed booking for this patient
                last_booking = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', lead.patient_id.id),
                    ('state', '=', 'completed'),
                ], limit=1, order='actual_end_datetime desc')
                
                if last_booking and last_booking.lead_staff_id:
                    defaults['last_visiting_staff_id'] = last_booking.lead_staff_id.id
        
        return defaults
    
    # =========================================================================
    # WIZARD ACTIONS
    # =========================================================================
    
    def action_confirm_cancellation(self):
        """
        Confirm and process the booking cancellation.
        """
        self.ensure_one()
        
        if not self.cancellation_reason_text:
            raise ValidationError(_('Please provide a reason for cancellation.'))
        
        if not self.cancelled_by_client:
            raise ValidationError(_('Please specify who cancelled the booking.'))
        
        # Update the booking if exists
        if self.booking_id:
            self.booking_id.write({
                'state': 'cancelled',
                'cancellation_date': self.cancellation_datetime,
                'cancellation_reason_id': self.cancellation_reason_id.id if self.cancellation_reason_id else False,
                'cancellation_notes': self.cancellation_reason_text,
                'cancelled_by': self.env.user.id,
                'cancelled_by_client': self.cancelled_by_client,
                'cancellation_reported_by': self.reported_by_name,
                'cancellation_reporter_position': self.reported_by_position,
                'last_visiting_staff_id': self.last_visiting_staff_id.id if self.last_visiting_staff_id else False,
            })
        
        # Update the lead/contact
        self.lead_id.write({
            'contact_status': 'lost_booking',
            'contact_outcome': 'booking_lost',
            'booking_status': 'cancelled',
            'booking_lost_reason': self._format_cancellation_message(),
        })
        
        # Post message to chatter
        message_body = self._format_cancellation_message(html=True)
        
        self.lead_id.message_post(
            body=message_body,
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
        
        # If client wants to reschedule, create a follow-up activity
        if self.wants_reschedule:
            activity_type = self.env.ref('mail.mail_activity_data_call', raise_if_not_found=False)
            if activity_type:
                self.lead_id.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=_('Reschedule Booking: %s') % self.lead_id.name,
                    note=_('Client requested reschedule.\nPreferences: %s') % (self.reschedule_notes or 'Not specified'),
                    user_id=self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
        
        # Close the wizard dialog
        return {'type': 'ir.actions.act_window_close'}
    
    def _format_cancellation_message(self, html=False):
        """Format cancellation details for storage/display"""
        if html:
            message = _(
                '<strong>Booking Cancelled</strong><br/>'
                '<b>Date/Time:</b> %(datetime)s<br/>'
                '<b>Cancelled By:</b> %(cancelled_by)s (%(relationship)s)<br/>'
                '<b>Reported By:</b> %(reported_by)s %(position)s<br/>'
                '<b>Reason:</b> %(reason)s'
            ) % {
                'datetime': self.cancellation_datetime,
                'cancelled_by': self.cancelled_by_client,
                'relationship': dict(self._fields['cancelled_by_relationship'].selection).get(
                    self.cancelled_by_relationship, self.cancelled_by_relationship
                ),
                'reported_by': self.reported_by_name,
                'position': ('(%s)' % self.reported_by_position) if self.reported_by_position else '',
                'reason': self.cancellation_reason_text,
            }
            
            if self.last_visiting_staff_id:
                message += _('<br/><b>Last Staff Who Visited:</b> %s') % self.last_visiting_staff_id.name
            
            if self.wants_reschedule:
                message += _('<br/><b>Client Wants to Reschedule:</b> Yes')
                if self.reschedule_notes:
                    message += _('<br/><b>Reschedule Preferences:</b> %s') % self.reschedule_notes
        else:
            lines = [
                _('Cancelled by: %s (%s)') % (self.cancelled_by_client, self.cancelled_by_relationship),
                _('Reported by: %s %s') % (self.reported_by_name, self.reported_by_position or ''),
                _('Reason: %s') % self.cancellation_reason_text,
            ]
            if self.last_visiting_staff_id:
                lines.append(_('Last staff who visited: %s') % self.last_visiting_staff_id.name)
            message = '\n'.join(lines)
        
        return message
    
    def action_cancel(self):
        """Cancel the wizard"""
        return {'type': 'ir.actions.act_window_close'}
