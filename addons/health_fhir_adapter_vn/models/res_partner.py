# -*- coding: utf-8 -*-
"""VNeID verification capture + the patient EMR export action
(architecture-interop.md §3.1 'capture now')."""

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    vneid_verified = fields.Boolean(
        string='VNeID Verified',
        help='Identity verified against VNeID (captured manually now; OIDC '
             'login integration is a later phase).')
    vneid_verified_date = fields.Date(string='VNeID Verified On')

    @api.onchange('vneid_verified')
    def _onchange_vneid_verified(self):
        if self.vneid_verified and not self.vneid_verified_date:
            self.vneid_verified_date = fields.Date.context_today(self)

    @api.model_create_multi
    def create(self, vals_list):
        # Server-side mirror of the onchange (API/import creates skip it).
        for vals in vals_list:
            if vals.get('vneid_verified') and not vals.get(
                    'vneid_verified_date'):
                vals['vneid_verified_date'] = fields.Date.context_today(self)
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        if vals.get('vneid_verified'):
            for partner in self:
                if not partner.vneid_verified_date:
                    super(ResPartner, partner).write(
                        {'vneid_verified_date': fields.Date.context_today(
                            self)})
        return result

    def action_export_emr_bundle_vn(self):
        """Patient form button — export the VN EMR bundle and open its log."""
        self.ensure_one()
        log = self.env['fhir.adapter.vn'].export_patient_bundle(self)
        return {
            'type': 'ir.actions.act_window',
            'name': _('EMR Submission'),
            'res_model': 'fhir.submission.log',
            'res_id': log.id,
            'view_mode': 'form',
            'target': 'current',
        }
