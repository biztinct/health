# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFSOStaffAssignmentWizard(models.TransientModel):
    """
    Wizard for assigning healthcare staff to FSO
    """
    _name = 'health.fso.staff.assignment.wizard'
    _description = 'FSO Staff Assignment Wizard'

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

    # Editable Fields
    assigned_staff_ids = fields.Many2many(
        'hr.employee',
        'fso_staff_wizard_employee_rel',
        'wizard_id',
        'employee_id',
        string='Assigned Staff',
        help='Healthcare staff assigned to this service'
    )

    primary_staff_id = fields.Many2one(
        'hr.employee',
        string='Primary Staff Member',
        help='Main staff member responsible for this service'
    )

    assignment_notes = fields.Text(
        string='Assignment Notes',
        help='Special instructions or notes for assigned staff'
    )

    staff_availability_checked = fields.Boolean(
        string='Staff Availability Verified',
        default=False
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with FSO data"""
        res = super().default_get(fields_list)

        fso_id = self.env.context.get('default_fso_id')
        if fso_id:
            fso = self.env['health.fieldservice.order'].browse(fso_id)
            # Pre-populate with any existing staff assignments
            if fso.lead_staff_id:
                # If lead_staff_id exists, use it as primary staff
                res['primary_staff_id'] = fso.lead_staff_id.id
                res['assigned_staff_ids'] = [(6, 0, [fso.lead_staff_id.id])]

        return res

    def action_assign_staff(self):
        """Assign staff to FSO and return to dashboard"""
        self.ensure_one()

        if not self.assigned_staff_ids:
            raise UserError(_('Please assign at least one staff member before saving.'))

        # Update FSO with staff assignment
        if self.primary_staff_id:
            self.fso_id.write({
                'lead_staff_id': self.primary_staff_id.id,
            })

        # Update state to assigned if currently confirmed
        if self.fso_id.state == 'confirmed':
            self.fso_id.write({
                'state': 'assigned',
            })

        # Post message to chatter
        staff_names = ', '.join(self.assigned_staff_ids.mapped('name'))
        self.fso_id.message_post(
            body=_('Staff assigned: %s. Primary: %s') % (
                staff_names,
                self.primary_staff_id.name if self.primary_staff_id else 'None'
            ),
            subject='Staff Assignment Updated',
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
