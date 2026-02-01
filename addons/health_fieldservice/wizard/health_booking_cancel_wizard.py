# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HealthBookingCancelWizard(models.TransientModel):
    """Wizard for structured booking cancellation"""
    _name = 'health.booking.cancel.wizard'
    _description = 'Booking Cancellation Wizard'

    booking_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        readonly=True
    )

    booking_reference = fields.Char(
        related='booking_id.name',
        string='Booking Reference',
        readonly=True
    )

    patient_name = fields.Char(
        related='booking_id.patient_id.name',
        string='Client',
        readonly=True
    )

    scheduled_datetime = fields.Datetime(
        related='booking_id.scheduled_datetime',
        string='Scheduled Date & Time',
        readonly=True
    )

    cancellation_reason_id = fields.Many2one(
        'health.booking.cancellation.reason',
        string='Cancellation Reason',
        required=True,
        help='Select the reason for cancellation'
    )

    cancellation_notes = fields.Text(
        'Cancellation Notes',
        required=True,
        help='Provide detailed notes about why this booking is being cancelled'
    )

    show_invoice_warning = fields.Boolean(
        'Has Invoice',
        compute='_compute_show_invoice_warning'
    )

    # WHO CANCELLED fields
    canceller_name = fields.Char(
        string='Name (on client side)',
        help='Name of the person who requested the cancellation (e.g., Mrs. Nguyen, Son of patient)'
    )

    canceller_relationship = fields.Selection([
        ('patient_client', 'Patient/Client'),
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('sibling', 'Sibling'),
        ('caregiver', 'Caregiver'),
        ('other', 'Other'),
    ], string='Their Relationship to Client', default='patient_client',
       help='Relationship of the canceller to the client')

    reported_by = fields.Char(
        string='Reported By (us)',
        help='Name of staff who received the cancellation request'
    )

    reporter_position = fields.Char(
        string='Position/Role',
        help='Position or role of the staff who took the call (e.g., Receptionist, OM)'
    )

    last_staff_id = fields.Many2one(
        'res.partner',
        string='Last Staff Who Visited This Client',
        compute='_compute_last_staff',
        help='The staff member who last visited this client'
    )

    @api.depends('booking_id.patient_id')
    def _compute_last_staff(self):
        """Compute the last staff who visited this client"""
        for wizard in self:
            last_staff = False
            if wizard.booking_id and wizard.booking_id.patient_id:
                # Find the last completed FSO for this patient
                last_fso = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', wizard.booking_id.patient_id.id),
                    ('state', '=', 'completed'),
                    ('id', '!=', wizard.booking_id.id),
                ], order='scheduled_datetime desc', limit=1)
                if last_fso and last_fso.primary_nurse_id:
                    last_staff = last_fso.primary_nurse_id
            wizard.last_staff_id = last_staff

    @api.depends('booking_id.invoice_id')
    def _compute_show_invoice_warning(self):
        """Check if booking has an associated invoice"""
        for wizard in self:
            wizard.show_invoice_warning = bool(wizard.booking_id.invoice_id)

    @api.constrains('cancellation_notes')
    def _check_cancellation_notes(self):
        """Validate that cancellation notes are meaningful"""
        for wizard in self:
            if wizard.cancellation_notes and len(wizard.cancellation_notes.strip()) < 10:
                raise ValidationError(_('Cancellation notes must be at least 10 characters long. Please provide detailed information.'))

    def action_confirm_cancellation(self):
        """Confirm and process the cancellation"""
        self.ensure_one()

        if not self.cancellation_reason_id:
            raise ValidationError(_('Please select a cancellation reason.'))

        if not self.cancellation_notes:
            raise ValidationError(_('Cancellation notes are mandatory. Please provide details.'))

        # Call the FSO's cancel method with structured data
        self.booking_id.cancel_with_reason(
            self.cancellation_reason_id.id,
            self.cancellation_notes
        )

        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Booking Cancelled'),
                'message': _('Booking %s has been cancelled successfully.') % self.booking_id.name,
                'type': 'success',
                'sticky': False,
            }
        }
