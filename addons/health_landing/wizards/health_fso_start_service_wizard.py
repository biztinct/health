# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFSOStartServiceWizard(models.TransientModel):
    """
    Wizard for starting service with confirmation of start time
    """
    _name = 'health.fso.start.service.wizard'
    _description = 'FSO Start Service Wizard'

    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        ondelete='cascade'
    )

    patient_id = fields.Many2one(
        'res.partner',
        related='fso_id.patient_id',
        string='Patient',
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

    assigned_staff = fields.Char(
        string='Assigned Staff',
        compute='_compute_assigned_staff',
        readonly=True
    )

    # Editable Fields
    actual_start_datetime = fields.Datetime(
        string='Actual Start Time',
        default=fields.Datetime.now,
        required=True,
        help='Actual time when service started'
    )

    start_notes = fields.Text(
        string='Start Notes',
        help='Any notes or observations at service start'
    )

    patient_present = fields.Boolean(
        string='Patient Present and Verified',
        default=False,
        help='Confirm that patient is present and identity verified'
    )

    equipment_ready = fields.Boolean(
        string='Equipment Ready',
        default=False,
        help='Confirm that all required equipment is ready'
    )

    @api.depends('fso_id.lead_staff_id')
    def _compute_assigned_staff(self):
        """Compute assigned staff name"""
        for wizard in self:
            if wizard.fso_id.lead_staff_id:
                wizard.assigned_staff = wizard.fso_id.lead_staff_id.name
            else:
                wizard.assigned_staff = _('Not assigned')

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with FSO data"""
        res = super().default_get(fields_list)

        fso_id = self.env.context.get('default_fso_id')
        if fso_id:
            fso = self.env['health.fieldservice.order'].browse(fso_id)
            # Set actual start time from FSO if already set
            if fso.actual_start_datetime:
                res['actual_start_datetime'] = fso.actual_start_datetime

        return res

    def action_start_service(self):
        """Start service and update FSO state"""
        self.ensure_one()

        if not self.patient_present:
            raise UserError(_('Please confirm that the patient is present and verified before starting the service.'))

        # Update FSO with actual start time and change state
        self.fso_id.write({
            'actual_start_datetime': self.actual_start_datetime,
            'state': 'in_progress',
        })

        # Post message to chatter
        self.fso_id.message_post(
            body=_('Service started at %s. Patient present: %s, Equipment ready: %s') % (
                self.actual_start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'Yes' if self.patient_present else 'No',
                'Yes' if self.equipment_ready else 'No'
            ),
            subject='Service Started',
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
