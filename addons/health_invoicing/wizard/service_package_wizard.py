# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ServicePackageWizard(models.TransientModel):
    """Wizard to select a service package for an FSO booking."""
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

    line_ids = fields.One2many(
        'health.service.package.wizard.line',
        'wizard_id',
        string='Client Packages',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        fso_id = res.get('fso_id') or self.env.context.get('default_fso_id')
        if not fso_id:
            return res

        fso = self.env['health.fieldservice.order'].browse(fso_id)
        res['patient_id'] = fso.patient_id.id

        # Load all active packages for the client
        packages = self.env['health.service.package'].search([
            ('patient_id', '=', fso.patient_id.id),
            ('state', '=', 'active'),
        ])

        lines = []
        for pkg in packages:
            lines.append((0, 0, {
                'package_id': pkg.id,
                'package_name': pkg.name,
                'service_type': pkg.service_type,
                'total_services': pkg.total_services,
                'consumed_services': pkg.consumed_services,
                'remaining_services': pkg.remaining_services,
                'is_selectable': pkg.remaining_services > 0,
                'selected': fso.package_id.id == pkg.id,  # Pre-select current
            }))
        res['line_ids'] = lines
        return res

    def action_confirm(self):
        """Assign the selected package to the FSO."""
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

    package_name = fields.Char('Package Name', readonly=True)
    service_type = fields.Char('Service Type', readonly=True)
    total_services = fields.Integer('Total Services', readonly=True)
    consumed_services = fields.Integer('Services Used', readonly=True)
    remaining_services = fields.Integer('Remaining', readonly=True)
    is_selectable = fields.Boolean('Selectable', readonly=True, default=True)
    selected = fields.Boolean('Select')

    def action_view_history(self):
        """Open the booking history for this package."""
        self.ensure_one()
        return {
            'name': _('Package Booking History — %s') % self.package_name,
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'domain': [('package_id', '=', self.package_id.id)],
            'view_mode': 'list',
            'target': 'new',
            'context': {'create': False},
        }
