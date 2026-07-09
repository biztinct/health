# -*- coding: utf-8 -*-
"""Timeline soft warning (handover §2.4).

Post-super inherit of ``validate_drop``: when the base already says the drop is
allowed (``ok`` and not ``hard_block``), append a travel-feasibility note to
the message the schedule UI already shows. This NEVER hard-blocks and NEVER
flips ``ok``/``hard_block`` — a tight day is a nudge, not a wall. The whole
inherit is wrapped: on ANY exception the base result is returned untouched (the
timeline must not break because OSRM is down).
"""
import logging
from datetime import timedelta

from odoo import api, models

_logger = logging.getLogger(__name__)


class HealthStaffAssignment(models.Model):
    _inherit = 'health.staff.assignment'

    @api.model
    def validate_drop(self, staff_id, start_iso, end_iso, assignment_id=None):
        res = super().validate_drop(staff_id, start_iso, end_iso,
                                    assignment_id=assignment_id)
        try:
            if not res.get('ok') or res.get('hard_block'):
                return res
            emp = self.env['hr.employee'].browse(staff_id).exists()
            if not emp:
                return res
            start_utc = self._sched_parse_iso(start_iso)
            end_utc = self._sched_parse_iso(end_iso) or (
                start_utc and start_utc + timedelta(hours=1))
            if not start_utc:
                return res
            dropped_fso = False
            if assignment_id:
                assignment = self.browse(assignment_id).exists()
                dropped_fso = assignment.fso_id if assignment else False
            if not dropped_fso:
                return res
            warnings = self.env['health.route.transition']._drop_warnings(
                emp, start_utc, end_utc, dropped_fso)
            if warnings:
                res = dict(res)
                extra = ' '.join(warnings)
                res['message'] = (res.get('message') + ' ' + extra
                                  if res.get('message') else extra)
        except Exception as exc:  # noqa: BLE001 — never break the timeline
            _logger.debug('route drop warning skipped: %s', exc)
            return res
        return res
