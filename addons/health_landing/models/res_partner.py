# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fso_upcoming_ids = fields.Many2many(
        'health.fieldservice.order',
        compute='_compute_fso_bookings',
        string='Upcoming Bookings',
        help='Upcoming field service orders'
    )

    fso_past_ids = fields.Many2many(
        'health.fieldservice.order',
        compute='_compute_fso_bookings',
        string='Past Bookings',
        help='Past field service orders'
    )

    @api.depends('is_patient')
    def _compute_fso_bookings(self):
        """Compute upcoming and past FSO bookings"""
        FSO = self.env['health.fieldservice.order']
        now = fields.Datetime.now()

        for partner in self:
            if partner.is_patient:
                # Upcoming bookings
                partner.fso_upcoming_ids = FSO.search([
                    ('patient_id', '=', partner.id),
                    ('scheduled_datetime', '>=', now),
                    ('state', 'not in', ['cancelled', 'done'])
                ], order='scheduled_datetime asc', limit=20)

                # Past bookings
                partner.fso_past_ids = FSO.search([
                    ('patient_id', '=', partner.id),
                    '|',
                    ('scheduled_datetime', '<', now),
                    ('state', 'in', ['cancelled', 'done'])
                ], order='scheduled_datetime desc', limit=20)
            else:
                partner.fso_upcoming_ids = FSO
                partner.fso_past_ids = FSO

    def action_open_hub_spoke(self):
        """Open hub-and-spoke dashboard for this patient"""
        self.ensure_one()

        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing_patient_hub',
            'name': f'Patient Hub: {self.name}',
            'params': {
                'patient_id': self.id,
                'patient_name': self.name,
            },
        }
