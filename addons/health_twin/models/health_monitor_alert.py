# -*- coding: utf-8 -*-
"""Event hook: recompute a client's twin risk row when a deterioration alert
is created OR when its `state` changes (acknowledge/resolve/dismiss all move
the open-alert counts that feed the alert component). Lives here (via
``_inherit``) so the telemonitoring module is never edited (handover §2.3 /
§2.7). NEVER-BLOCK + config-gated.
"""
import logging

from odoo import api, models

from . import twin_config

_logger = logging.getLogger(__name__)


class HealthMonitorAlert(models.Model):
    _inherit = 'health.monitor.alert'

    def _twin_recompute(self, clients):
        try:
            if not twin_config.get_bool(self.env, 'twin_enabled', True):
                return
            if clients:
                self.env['health.twin.risk'].sudo()\
                    ._recompute_for_patients(clients)
        except Exception:  # noqa: BLE001 — twin recompute must never block alerts
            _logger.exception(
                'Twin: risk recompute failed after alert change.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._twin_recompute(records.mapped('client_id'))
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            self._twin_recompute(self.mapped('client_id'))
        return res
