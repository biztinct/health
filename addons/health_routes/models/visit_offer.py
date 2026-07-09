# -*- coding: utf-8 -*-
"""Slot-proposer travel guard (handover §2.5).

Post-super inherit of ``_propose_slots_for_partner`` (the partner-level core
shared by BOTH the first-visit offer and the client self-booking invite — so
both consume this improvement for free). Drops any proposed slot whose either
transition would be travel-CRITICAL against the slot staff's existing
non-online visits that day; keeps 'warn' (availability beats perfection when
slots are scarce). Wrapped: on ANY exception the base list is returned
untouched.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class HealthVisitOffer(models.Model):
    _inherit = 'health.visit.offer'

    @api.model
    def _propose_slots_for_partner(self, partner, count=3, horizon_days=7):
        slots = super()._propose_slots_for_partner(
            partner, count=count, horizon_days=horizon_days)
        try:
            if not partner:
                return slots
            return self.env['health.route.transition']._filter_slots_travel(
                partner, slots)
        except Exception as exc:  # noqa: BLE001 — proposer must never break
            _logger.debug('route proposer guard skipped: %s', exc)
            return slots
