# -*- coding: utf-8 -*-
"""Server support for the schedule canvas (draw-to-create + overlay thinning).

Three additions on the health.staff.assignment inherit:
  * ``can_schedule_create`` — the ops-group gate the double-click UI consults so a
    nurse gets a friendly refusal toast rather than a dialog they cannot complete
    (server-side enforcement still rides the FSO builder's own ACLs).
  * ``schedule_canvas_prefill`` — converts a UTC timeline click into the builder's
    FACILITY-LOCAL (date, time_hour) plus the staff's facility, and surfaces an
    off-hours warning. This is the +7h-bug seam, so the conversion lives here
    (server-side, unit-tested) not in JS.
  * ``get_schedule_overlay`` override — an optional trailing ``granularity`` kwarg
    that drops 'off' backgrounds at month scale (keeps 'leave'). Existing 4-arg
    callers are unaffected.
"""
import logging

import pytz

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Same ops ladder the drag gate uses (health_schedule_drag). Creating a booking is
# an operations decision.
_OPS_GROUPS = (
    'health_base.group_healthcare_operations_manager',
    'health_base.group_healthcare_head_nurse',
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)


class HealthStaffAssignment(models.Model):
    _inherit = 'health.staff.assignment'

    @api.model
    def can_schedule_create(self):
        """True when the current user may create bookings from the schedule
        (double-click). Ops ladder only — nurses get the friendly refusal."""
        return any(self.env.user.has_group(g) for g in _OPS_GROUPS)

    @api.model
    def schedule_canvas_prefill(self, staff_id, start_iso):
        """Prepare the quick-booking dialog for a double-click on a staff lane.

        ``start_iso`` is a REAL-UTC wall-clock string (the timeline item basis).
        Returns the builder-ready facility-local (date, time_hour) for that staff's
        facility, plus display labels, an ops-can-create flag and an off-hours
        warning (creating off-hours is allowed — it is only surfaced, never
        blocked). Never raises for expected conditions.
        """
        # sudo the employee read: a non-HR ops user tripping the public-profile
        # prefetch guard otherwise (conventions §5.24).
        emp = self.env['hr.employee'].sudo().browse(staff_id).exists()
        if not emp:
            return {'ok': False, 'message': _('Unknown staff member.')}
        start_utc = self._sched_parse_iso(start_iso)
        if not start_utc:
            return {'ok': False, 'message': _('Invalid time.')}

        fac = emp.healthcare_facility_id
        tz_name = fac.timezone if (fac and fac.timezone) else self._schedule_tz_name()
        tz = pytz.timezone(tz_name)
        local = pytz.utc.localize(start_utc).astimezone(tz)
        time_hour = local.hour + local.minute / 60.0

        # Off-hours warning (visible, not blocking — the whole point of draw-create).
        warning = ''
        try:
            from datetime import timedelta
            # sudo: validate_drop reads hr.employee fields (name/working hours);
            # a non-HR ops user would otherwise trip the public-profile guard
            # (§5.24). The availability logic is user-independent, so sudo is safe.
            vd = self.sudo().validate_drop(
                staff_id,
                start_utc.strftime('%Y-%m-%d %H:%M:%S'),
                (start_utc + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S'),
                None)
            if vd.get('hard_block'):
                warning = vd.get('message') or _('Outside working hours.')
        except Exception as exc:  # noqa: BLE001 — a warning must never break create
            _logger.info('schedule_canvas_prefill: validate_drop skipped: %s', exc)

        return {
            'ok': True,
            'can_create': self.can_schedule_create(),
            'staff_id': emp.id,
            'staff_name': emp.name,
            'facility_id': fac.id if fac else False,
            'facility_name': fac.name if fac else '',
            'date': local.strftime('%Y-%m-%d'),
            'time_hour': time_hour,
            'date_label': local.strftime('%a %d %b'),
            'time_label': local.strftime('%H:%M'),
            'warning': warning,
        }

    @api.model
    def get_schedule_overlay(self, date_start, date_end, staff_ids=None,
                             facility_id=None, granularity=None):
        """Adds an optional ``granularity`` kwarg to the shipped overlay: at
        month scale the per-day 'off' background segments (≈2,700 for a 30-staff
        month) are pointless noise — drop them, keep 'leave'. The 4-arg signature
        the timeline JS already uses is preserved (granularity defaults None)."""
        res = super().get_schedule_overlay(
            date_start, date_end, staff_ids=staff_ids, facility_id=facility_id)
        if granularity == 'month' and isinstance(res, dict) and res.get('backgrounds'):
            res['backgrounds'] = [
                b for b in res['backgrounds'] if b.get('kind') != 'off'
            ]
        return res
