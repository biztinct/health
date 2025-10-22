# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFSOConfirmBookingWizard(models.TransientModel):
    """
    Wizard for confirming booking details before finalization
    """
    _name = 'health.fso.confirm.booking.wizard'
    _description = 'FSO Confirm Booking Wizard'

    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        ondelete='cascade'
    )

    patient_id = fields.Many2one(
        'res.partner',
        related='fso_id.patient_id',
        string='Client',
        readonly=True
    )

    service_type = fields.Selection(
        related='fso_id.service_type',
        string='Service Type',
        readonly=True
    )

    scheduled_datetime = fields.Datetime(
        related='fso_id.scheduled_datetime',
        string='Scheduled Date & Time',
        readonly=True
    )

    # Editable Fields
    confirmation_notes = fields.Text(
        string='Confirmation Notes',
        help='Any special instructions or notes for this booking confirmation'
    )

    patient_contacted = fields.Boolean(
        string='Client Contacted',
        default=False,
        help='client has been contacted about this booking'
    )

    staff_notified = fields.Boolean(
        string='Staff Notified',
        default=False,
        help='Confirm that assigned staff has been notified'
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with FSO data"""
        res = super().default_get(fields_list)

        fso_id = self.env.context.get('default_fso_id')
        if fso_id:
            fso = self.env['health.fieldservice.order'].browse(fso_id)
            # Pre-populate any existing confirmation data if needed

        return res

    def action_confirm_booking(self):
        """Confirm booking and update FSO state"""
        self.ensure_one()

        if not self.patient_contacted:
            raise UserError(_('Please confirm that the patient has been contacted before confirming the booking.'))

        # Update FSO state to confirmed
        if self.fso_id.state == 'draft':
            self.fso_id.write({
                'state': 'confirmed',
            })

        # Post message to chatter
        self.fso_id.message_post(
            body=_('Booking confirmed. Patient contacted: %s, Staff notified: %s') % (
                'Yes' if self.patient_contacted else 'No',
                'Yes' if self.staff_notified else 'No'
            ),
            subject='Booking Confirmed',
            message_type='notification'
        )

        return self._return_to_dashboard()

    def _return_to_dashboard(self):
        """Return to FSO dashboard after saving"""
        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing.fso_hub_spoke_action',
            'params': {
                'fso_id': self.fso_id.id,
                'fso_name': self.fso_id.name,
            }
        }
