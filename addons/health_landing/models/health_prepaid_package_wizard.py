# -*- coding: utf-8 -*-

from odoo import _, models


class HealthPrepaidPackageWizard(models.TransientModel):
    _inherit = 'health.prepaid.package.wizard'

    def action_create_package(self):
        action = super().action_create_package()
        if not self.env.context.get('return_to_packages_modal'):
            return action
        if action.get('type') != 'ir.actions.act_window' or action.get('res_model') != 'health.service.package':
            return action

        patient = self.patient_id
        if not patient:
            return action

        try:
            view = self.env.ref('health_landing.view_patient_packages_modal')
        except ValueError:
            return action

        return {
            'name': _('Service Packages'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': patient.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'new',
            'context': dict(self.env.context),
        }
