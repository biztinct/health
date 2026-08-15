# -*- coding: utf-8 -*-
"""``health.monitor.device`` — per-patient home-device registry (Phase 2).

Home monitoring devices (BP monitors, pulse oximeters, glucometers, scales)
are registered here by ops. The ingestion endpoint
(``controllers/ingest.py``) resolves a device by its partner-supplied
``external_id`` and maps incoming readings onto the same
``health.observation`` stream the Phase 1 engines already watch — so a
device reading gets NEWS2 / threshold / trend evaluation for free.

Devices with reading history are retired, not deleted (unlink is ACL-gated
to admin/owner — clone of the Phase 1 alert shape).
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HealthMonitorDevice(models.Model):
    _name = 'health.monitor.device'
    _description = 'Home Monitoring Device'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(
        string='Device Name', required=True, tracking=True,
        help='Human label for this device, e.g. "Omron X5 — bà Lan".')
    client_id = fields.Many2one(
        'res.partner', string='Client', required=True, index=True,
        ondelete='restrict', domain=[('is_patient', '=', True)],
        tracking=True)
    device_type_id = fields.Many2one(
        'health.lookup.value',
        string='Device Type',
        domain="[('category_code', '=', 'monitor_device_type'), ('active', '=', True)]",
        ondelete='restrict',
        required=True,
        tracking=True)
    external_id = fields.Char(
        string='External ID', required=True, index=True, tracking=True,
        help='The identifier the partner/vendor sends per reading (device '
             'serial / uuid). Globally unique — partners address devices '
             'without a client context.')
    vendor = fields.Char(string='Vendor')
    model = fields.Char(string='Model')
    notes = fields.Char(string='Notes')

    state = fields.Selection([
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('retired', 'Retired'),
    ], string='Status', default='active', required=True, index=True,
        tracking=True)

    reading_count = fields.Integer(
        string='Readings', compute='_compute_reading_count')
    last_reading_at = fields.Datetime(
        string='Last Reading', readonly=True,
        help='Stamped by the ingestion engine on each accepted batch.')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    def init(self):
        # §5.1 — Odoo 19 does not materialize _sql_constraints. external_id is
        # the partner's global addressing key for a device, so it must be
        # unique on its own (unique per client is not enough — a partner POST
        # carries only the external_id, no client context).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_monitor_device_ext_uniq
            ON health_monitor_device (external_id)
        """)

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.client_id._get_health_catchment_province()
                if rec.client_id else False)

    def _compute_reading_count(self):
        # Provenance marker: observations carry "<name> (<external_id>)" in
        # their `device` Char (see ingest.py). `like` wraps the value in %…%,
        # so '(external_id)' matches that trailing token. sudo — the count is
        # a display aid and the observation ACL may exclude some rows.
        Obs = self.env['health.observation'].sudo()
        for rec in self:
            rec.reading_count = (
                Obs.search_count([('device', 'like', '(%s)' % rec.external_id)])
                if rec.external_id else 0)

    def action_view_readings(self):
        """Smart-button: observations bearing this device's provenance marker."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'health.observation',
            'view_mode': 'list,form',
            'domain': [('device', 'like', '(%s)' % self.external_id)],
            'context': {'create': False},
        }

    def action_view_receipts(self):
        """Form button: ingestion receipts for this device (readonly)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ingestion Receipts'),
            'res_model': 'health.device.receipt',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {'create': False},
        }

    # ------------------------------------------------------------------
    # State lifecycle (plain writes — ops-gated by the model write ACL)
    # ------------------------------------------------------------------
    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_reactivate(self):
        self.write({'state': 'active'})

    def action_retire(self):
        self.write({'state': 'retired'})
