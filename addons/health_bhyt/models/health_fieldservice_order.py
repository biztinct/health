# -*- coding: utf-8 -*-
"""FSO hook: a "Generate BHYT Claim" action on a completed+invoiced visit.

The button lives here (an ``_inherit`` inside health_bhyt), NEVER by editing
health_fieldservice (handover §2.8). It defers all logic to
``bhyt.claim._build_claim_for`` and opens the resulting claim.
"""
from odoo import _, models
from odoo.exceptions import UserError


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    def action_generate_bhyt_claim(self):
        self.ensure_one()
        claim = self.env['bhyt.claim']._build_claim_for(self)
        if not claim:
            raise UserError(_(
                'This visit is not eligible for a BHYT claim — it must be '
                'completed, invoiced (posted), and the patient must hold a '
                'valid BHYT card.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('BHYT Claim'),
            'res_model': 'bhyt.claim',
            'res_id': claim.id,
            'view_mode': 'form',
            'target': 'current',
        }
