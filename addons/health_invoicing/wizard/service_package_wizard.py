# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ServicePackageWizard(models.TransientModel):
    """Wizard to select an existing package OR purchase a new one for an FSO booking."""
    _name = 'health.service.package.wizard'
    _description = 'Service Package Selection Wizard'

    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        readonly=True,
    )

    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        readonly=True,
    )

    # --- Section 1: Existing active packages for this client ---
    line_ids = fields.One2many(
        'health.service.package.wizard.line',
        'wizard_id',
        string='Client Packages',
    )

    has_existing_packages = fields.Boolean(
        compute='_compute_has_existing_packages',
    )

    # --- Section 2: Available package products to purchase ---
    product_line_ids = fields.One2many(
        'health.service.package.wizard.product.line',
        'wizard_id',
        string='Available Package Products',
    )

    @api.depends('line_ids')
    def _compute_has_existing_packages(self):
        for wiz in self:
            wiz.has_existing_packages = bool(wiz.line_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        fso_id = res.get('fso_id') or self.env.context.get('default_fso_id')
        if not fso_id:
            return res

        fso = self.env['health.fieldservice.order'].browse(fso_id)
        res['patient_id'] = fso.patient_id.id

        # Section 1: Load existing active packages for the client
        packages = self.env['health.service.package'].search([
            ('patient_id', '=', fso.patient_id.id),
            ('state', '=', 'active'),
        ])

        lines = []
        for pkg in packages:
            lines.append((0, 0, {
                'package_id': pkg.id,
                'is_selectable': pkg.remaining_services > 0,
                'selected': fso.package_id.id == pkg.id,
            }))
        res['line_ids'] = lines

        # Section 2: Load all healthcare package products available for purchase
        package_products = self.env['product.template'].search([
            ('is_healthcare_package', '=', True),
        ])

        product_lines = []
        for pt in package_products:
            product_lines.append((0, 0, {
                'product_template_id': pt.id,
                'selected': False,
            }))
        res['product_line_ids'] = product_lines

        return res

    def action_confirm(self):
        """Assign the selected existing package to the FSO."""
        self.ensure_one()

        selected_lines = self.line_ids.filtered(lambda l: l.selected and l.is_selectable)

        if not selected_lines:
            raise UserError(_('Please select a package to use for this booking.'))

        if len(selected_lines) > 1:
            raise UserError(_('Only one package can be selected per booking.'))

        package = selected_lines[0].package_id
        self.fso_id.write({'package_id': package.id})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Package Assigned'),
                'message': _('Package "%s" linked to booking %s. %d service(s) remaining.') % (
                    package.name, self.fso_id.name, package.remaining_services
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_purchase_and_assign(self):
        """Open the existing prepaid package wizard with the selected product pre-filled."""
        self.ensure_one()

        selected_products = self.product_line_ids.filtered(lambda l: l.selected)

        if not selected_products:
            raise UserError(_('Please select a package product to purchase.'))

        if len(selected_products) > 1:
            raise UserError(_('Only one package product can be purchased at a time.'))

        product_line = selected_products[0]

        # Open the full prepaid package wizard (same as "Quick Package Purchase" on client)
        # with product and client pre-filled, and source_fso_id for auto-assignment
        return {
            'name': _('Purchase Package'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.prepaid.package.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_package_product_id': product_line.product_template_id.id,
                'default_source_fso_id': self.fso_id.id,
                'default_currency_id': self.env.company.currency_id.id,
            }
        }

    def action_clear_package(self):
        """Remove any package assignment from the FSO."""
        self.ensure_one()
        self.fso_id.write({'package_id': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Package Removed'),
                'message': _('Service package removed from booking %s.') % self.fso_id.name,
                'type': 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


class ServicePackageWizardLine(models.TransientModel):
    """Line item showing one existing package in the wizard."""
    _name = 'health.service.package.wizard.line'
    _description = 'Service Package Wizard Line'

    wizard_id = fields.Many2one(
        'health.service.package.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )

    package_id = fields.Many2one(
        'health.service.package',
        string='Package',
        required=True,
    )

    # Related fields — pull live data from the actual package record
    package_name = fields.Char(
        'Package Name',
        related='package_id.name',
        readonly=True,
    )
    service_type = fields.Selection(
        related='package_id.service_type',
        readonly=True,
    )
    total_services = fields.Integer(
        'Total Services',
        related='package_id.total_services',
        readonly=True,
    )
    consumed_services = fields.Integer(
        'Services Used',
        related='package_id.consumed_services',
        readonly=True,
    )
    remaining_services = fields.Integer(
        'Remaining',
        related='package_id.remaining_services',
        readonly=True,
    )

    is_selectable = fields.Boolean('Selectable', default=True)
    selected = fields.Boolean('Select')

    def action_view_history(self):
        """Open the booking history for this package."""
        self.ensure_one()
        return {
            'name': _('Package Booking History - %s') % self.package_name,
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'domain': [('package_id', '=', self.package_id.id)],
            'view_mode': 'list',
            'target': 'new',
            'context': {'create': False},
        }


class ServicePackageWizardProductLine(models.TransientModel):
    """Line item showing one available package product for purchase."""
    _name = 'health.service.package.wizard.product.line'
    _description = 'Service Package Wizard Product Line'

    wizard_id = fields.Many2one(
        'health.service.package.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )

    product_template_id = fields.Many2one(
        'product.template',
        string='Package Product',
        required=True,
    )

    # Related fields — pull live data from the actual product record
    product_name = fields.Char(
        'Package',
        related='product_template_id.name',
        readonly=True,
    )
    service_count = fields.Integer(
        'Services',
        related='product_template_id.healthcare_service_count',
        readonly=True,
    )
    price = fields.Float(
        'Price',
        related='product_template_id.list_price',
        readonly=True,
    )
    price_per_service = fields.Monetary(
        'Per Service',
        related='product_template_id.healthcare_price_per_visit',
        readonly=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='product_template_id.currency_id',
    )

    selected = fields.Boolean('Buy')
