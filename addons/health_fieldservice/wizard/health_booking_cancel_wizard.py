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
