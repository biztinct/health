# -*- coding: utf-8 -*-
"""FSO extension: per-visit medication checklist (spec §3.2.5).

NOTE: ``health.clinical.note.medication_count`` (billing count of
medications given) already exists and is NOT repurposed — the eMAR
counts below are separate computed fields on the FSO.
"""
from odoo import _, fields, models


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    medication_administration_ids = fields.One2many(
        'health.medication.administration', 'fso_id',
        string='Medication Administrations')
    medication_admin_count = fields.Integer(
        compute='_compute_medication_admin_counts',
        string='Medication Slots')
    medication_admin_done_count = fields.Integer(
        compute='_compute_medication_admin_counts',
        string='Medications Done')

    def _compute_medication_admin_counts(self):
        totals, done = {}, {}
        if self.ids:
            for group in self.env['health.medication.administration'] \
                    ._read_group([('fso_id', 'in', self.ids)],
                                 ['fso_id', 'state'], ['__count']):
                fso_id = group[0].id
                totals[fso_id] = totals.get(fso_id, 0) + group[2]
                if group[1] != 'planned':
                    done[fso_id] = done.get(fso_id, 0) + group[2]
        for order in self:
            order.medication_admin_count = totals.get(order.id, 0)
            order.medication_admin_done_count = done.get(order.id, 0)

    def write(self, vals):
        result = super().write(vals)
        # Re-link medication slots when the visit moves or changes state
        # (spec §3.4 — write-hook mirror of the schedule/cron linker).
        if {'scheduled_datetime', 'state'} & set(vals):
            Admin = self.env['health.medication.administration'].sudo()
            linked = Admin.search([
                ('fso_id', 'in', self.ids), ('state', '=', 'planned')])
            stale = linked.filtered(
                lambda a: a.fso_id.state not in
                ('confirmed', 'assigned', 'in_progress')
                or not a._fso_date_matches())
            if stale:
                stale.write({'fso_id': False})
            Admin.search([
                ('client_id', 'in', self.mapped('patient_id').ids),
                ('state', '=', 'planned'),
                ('fso_id', '=', False),
            ])._link_administrations_to_fso()
        return result

    def action_view_medication_administrations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Medication Administrations'),
            'res_model': 'health.medication.administration',
            'view_mode': 'list,form',
            'domain': [('fso_id', '=', self.id)],
            'context': {'default_fso_id': self.id},
        }
