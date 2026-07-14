# -*- coding: utf-8 -*-
"""Event hook: recompute a client's twin risk row when a NEW NEWS2 score
lands. Lives here (via ``_inherit``) so the telemonitoring module is never
edited (handover §2.3 / §2.7). NEVER-BLOCK: a twin recompute must never break
a vitals capture — the recompute is wrapped in a guarded try/except.
"""
import logging

from odoo import api, models

from . import twin_config

_logger = logging.getLogger(__name__)


class HealthEwsScore(models.Model):
    _inherit = 'health.ews.score'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        try:
            if twin_config.get_bool(self.env, 'twin_enabled', True):
                clients = records.mapped('client_id')
                if clients:
                    self.env['health.twin.risk'].sudo()\
                        ._recompute_for_patients(clients)
        except Exception:  # noqa: BLE001 — twin recompute must never block capture
            _logger.exception(
                'Twin: risk recompute failed after NEWS2 score create.')
        return records
