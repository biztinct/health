# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFSOEquipmentWizard(models.TransientModel):
    """
    Wizard for managing equipment requirements for FSO
    """
    _name = 'health.fso.equipment.wizard'
    _description = 'FSO Equipment Wizard'

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
    required_equipment_ids = fields.Many2many(
        'product.product',
        'fso_equipment_wizard_product_rel',
        'wizard_id',
        'product_id',
        string='Required Equipment',
        domain=[('type', '=', 'product')],
        help='Equipment items required for this service'
    )

    equipment_notes = fields.Text(
        string='Equipment Notes',
        help='Special instructions or notes about equipment'
    )

    equipment_checklist_done = fields.Boolean(
        string='Equipment Checklist Completed',
        default=False
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with FSO data"""
        res = super().default_get(fields_list)

        fso_id = self.env.context.get('default_fso_id')
        if fso_id:
            fso = self.env['health.fieldservice.order'].browse(fso_id)
            # Initialize with any existing equipment data if needed
            # res['equipment_notes'] = fso.equipment_notes

        return res

    def action_save_equipment(self):
        """Save equipment information and return to dashboard"""
        self.ensure_one()

        # Update FSO with equipment information
        # This can be extended to link equipment to FSO
        equipment_names = ', '.join(self.required_equipment_ids.mapped('name'))

        # Post message to chatter
        self.fso_id.message_post(
            body=_('Equipment updated: %s items - %s') % (
                len(self.required_equipment_ids),
                equipment_names or 'No equipment'
            ),
            subject='Equipment Requirements Updated',
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
