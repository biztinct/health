# -*- coding: utf-8 -*-
"""Telemonitoring hooks on ``health.observation``.

Two seams (handover §2.5 / §2.7):
1. NEWS2 scoring fires after every create and after value-amending
   writes — always inside a never-block guard.
2. The existing per-client threshold escalation is mirrored into the
   deterioration inbox; super() runs first (existing behaviour preserved
   bit-for-bit).
"""
import logging

from odoo import api, models

from . import tm_config

_logger = logging.getLogger(__name__)


class HealthObservation(models.Model):
    _inherit = 'health.observation'

    # ------------------------------------------------------------------
    # NEWS2 scoring trigger
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._telemonitoring_score(records)
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'value_quantity', 'value_text'} & set(vals):
            # Amendment path: base flips final rows to 'amended'.
            self._telemonitoring_score(self)
        return result

    def _telemonitoring_score(self, records):
        if not tm_config.get_bool(self.env, 'ews_enabled', True):
            return
        try:
            self.env['health.ews.score'].sudo()._score_from_observations(
                records)
        except Exception:  # noqa: BLE001 — scoring must never block capture
            _logger.exception(
                'Telemonitoring: NEWS2 scoring failed for observations %s',
                records.ids)

    # ------------------------------------------------------------------
    # Threshold breach mirror
    # ------------------------------------------------------------------
    def _escalate_threshold_breach(self, threshold):
        res = super()._escalate_threshold_breach(threshold)
        try:
            self.env['health.monitor.alert'].sudo()._raise_for_threshold(
                self, threshold)
        except Exception:  # noqa: BLE001 — alerting must never block capture
            _logger.exception(
                'Telemonitoring: threshold mirror failed for observation %s',
                self.id)
        return res
