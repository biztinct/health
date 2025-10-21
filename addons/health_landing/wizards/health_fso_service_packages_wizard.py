# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFSOServicePackagesWizard(models.TransientModel):
    """
    Wizard for viewing and managing service packages for FSO
    """
    _name = 'health.fso.service.packages.wizard'
    _description = 'FSO Service Packages Wizard'

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

    # Editable Fields
    assigned_package_ids = fields.Many2many(
        'product.product',
        string='Assigned Service Packages',
        domain=[('type', '=', 'service'), ('sale_ok', '=', True)],
        help='Service packages assigned to this booking'
    )

    package_notes = fields.Text(
        string='Package Notes',
        help='Additional notes about service packages'
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with FSO data"""
        res = super().default_get(fields_list)

        fso_id = self.env.context.get('default_fso_id')
        if fso_id:
            fso = self.env['health.fieldservice.order'].browse(fso_id)
            # Get packages from sale order line items if exists
            if fso.sale_order_id:
                package_products = fso.sale_order_id.order_line.mapped('product_id').filtered(
                    lambda p: p.type == 'service'
                )
                res['assigned_package_ids'] = [(6, 0, package_products.ids)]

        return res

    def action_save_packages(self):
        """Save service packages and return to dashboard"""
        self.ensure_one()

        # Update FSO or related records with package information
        # This can be extended based on your data model

        # Post message to chatter
        self.fso_id.message_post(
            body=_('Service packages updated: %s packages assigned') % len(self.assigned_package_ids),
            subject='Service Packages Updated',
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
