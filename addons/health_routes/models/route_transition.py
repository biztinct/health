# -*- coding: utf-8 -*-
"""``health.route.transition`` — the feasibility judge (handover §2.2/§2.3).

Holds the ONE shared transition checker (``_check_transition``) that every
consumer in this module reuses — the nightly sweep, the timeline drop warning,
and the slot-proposer guard — plus the nightly cron that materializes a stored
``warn``/``critical`` row per infeasible consecutive-visit pair and raises ONE
ops activity per infeasible staff-day.

v1 is warnings-only: nothing here blocks a booking, moves an assignment, or
re-orders a day. Travel is symmetric; online visits carry no travel (they are
skipped entirely, so the visit before and after an online visit form a direct
pair). An ``unknown`` transition (coords + districts both missing on either
endpoint) NEVER produces a row or a warning — it must not cry wolf.
"""
import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_DEFAULT_BUFFER_MIN = 10
_DEFAULT_HORIZON_DAYS = 7
# FSO states that represent a still-planned visit worth checking.
_ACTIVE_STATES = ('confirmed', 'assigned', 'in_progress')


class HealthRouteTransition(models.Model):
    _name = 'health.route.transition'
    _description = 'Route Transition Feasibility'
    _order = 'date desc, staff_id, id'

    staff_id = fields.Many2one('hr.employee', string='Staff', required=True,
                               index=True, ondelete='cascade')
    date = fields.Date('Date', required=True, index=True)
    prev_fso_id = fields.Many2one('health.fieldservice.order',
                                  string='From Visit', ondelete='cascade')
    next_fso_id = fields.Many2one('health.fieldservice.order',
                                  string='To Visit', ondelete='cascade')
    gap_min = fields.Float('Gap (min)')
    travel_min = fields.Float('Travel (min)')
    buffer_min = fields.Float('Buffer (min)')
    method = fields.Char('Travel Method')
    status = fields.Selection([
        ('warn', 'Warning (tight)'),
        ('critical', 'Critical (infeasible)'),
    ], string='Status', required=True, index=True)
    sweep_batch = fields.Datetime('Sweep Batch')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True)

    @api.depends('staff_id.staff_catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = \
                rec.staff_id.staff_catchment_province_id.id \
                if rec.staff_id else False

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------
    def _icp(self):
        return self.env['ir.config_parameter'].sudo()

    def _buffer_minutes(self):
        val = self._icp().get_param('health_routes.buffer_minutes')
        try:
            return int(val) if val else _DEFAULT_BUFFER_MIN
        except (TypeError, ValueError):
            return _DEFAULT_BUFFER_MIN

    def _enabled(self):
        val = self._icp().get_param('health_routes.enabled')
        # Default ON — warnings are passive.
        return val is None or str(val).lower() in ('1', 'true', 'yes')

    # ------------------------------------------------------------------
    # Travel between two endpoints (leg cache → district fallback → unknown)
    # ------------------------------------------------------------------
    @api.model
    def _endpoint(self, fso):
        """(lat, lng, district) for a visit — the patient's home."""
        p = fso.patient_id
        if not p:
            return (0.0, 0.0, self.env['health.vietnamese.district'])
        return (p.partner_latitude, p.partner_longitude, p.district_id)

    @api.model
    def _travel_between(self, a, b):
        """(minutes, method) for two (lat,lng,district) endpoints.

        Tier 1: cached road minutes via health.route.leg. Tier 2 (coords
        missing on either side): district ``average_travel_time`` — only when
        BOTH endpoints have a district (same → its average; different → the
        max of the two). Otherwise (None, 'unknown')."""
        leg = self.env['health.route.leg'].leg_minutes(a[0], a[1], b[0], b[1])
        if leg.get('minutes') is not None and leg.get('method') != 'unknown':
            return leg['minutes'], leg['method']
        ad, bd = a[2], b[2]
        if ad and bd:
            if ad.id == bd.id:
                avg = float(ad.average_travel_time or 0)
            else:
                avg = float(max(ad.average_travel_time or 0,
                                bd.average_travel_time or 0))
            # A falsy district average is missing data, not zero travel —
            # returning 0 would classify a teleport pair as 'ok'.
            if avg > 0:
                return avg, 'district'
        return None, 'unknown'

    # ------------------------------------------------------------------
    # The one shared checker
    # ------------------------------------------------------------------
    @api.model
    def _classify(self, gap_min, travel_min):
        """ok / warn / critical from a gap and a travel estimate (buffer from
        config). travel_min None → 'unknown'."""
        if travel_min is None:
            return 'unknown'
        buffer_min = self._buffer_minutes()
        if gap_min >= travel_min + buffer_min:
            return 'ok'
        if gap_min >= travel_min:
            return 'warn'
        return 'critical'

    @api.model
    def _check_transition(self, prev_fso, next_fso):
        """{gap_min, travel_min, buffer_min, status, method} for two
        consecutive visits. gap = next.scheduled − prev.estimated_end (UTC
        math, no tz conversion). Endpoint of a visit = patient coords; the
        day's first-visit origin is NOT checked in v1."""
        buffer_min = self._buffer_minutes()
        end = prev_fso.estimated_end_datetime
        start = next_fso.scheduled_datetime
        if not (end and start):
            return {'gap_min': None, 'travel_min': None,
                    'buffer_min': buffer_min, 'status': 'unknown',
                    'method': 'unknown'}
        gap_min = (start - end).total_seconds() / 60.0
        travel_min, method = self._travel_between(
            self._endpoint(prev_fso), self._endpoint(next_fso))
        status = self._classify(gap_min, travel_min)
        return {'gap_min': gap_min, 'travel_min': travel_min,
                'buffer_min': buffer_min, 'status': status, 'method': method}

    @api.model
    def _warning_text(self, travel_min, gap_min):
        """The bilingual soft-warning string (handover §2.4)."""
        return self.env._(
            "Cần ~%(t)s phút di chuyển, chỉ còn %(g)s phút "
            "(needs ~%(t)s min travel, only %(g)s min gap)",
            t=int(round(travel_min)), g=int(round(gap_min)))

    # ------------------------------------------------------------------
    # Day sequence queries
    # ------------------------------------------------------------------
    @api.model
    def _nonline_fsos_between(self, staff, start_dt, end_dt, exclude_fso=None):
        """Non-online, still-planned FSOs for a staff whose scheduled_datetime
        falls in [start_dt, end_dt), ordered by time."""
        domain = [
            ('assignment_ids.staff_id', '=', staff.id),
            ('scheduled_datetime', '>=', start_dt),
            ('scheduled_datetime', '<', end_dt),
            ('service_location', '!=', 'online'),
            ('state', 'in', _ACTIVE_STATES),
        ]
        if exclude_fso:
            domain.append(('id', '!=', exclude_fso))
        return self.env['health.fieldservice.order'].sudo().search(
            domain, order='scheduled_datetime')

    # ------------------------------------------------------------------
    # Nightly feasibility sweep (§2.3)
    # ------------------------------------------------------------------
    @api.model
    def cron_route_feasibility_sweep(self):
        if not self._enabled():
            return True
        val = self._icp().get_param('health_routes.horizon_days')
        try:
            horizon = int(val) if val else _DEFAULT_HORIZON_DAYS
        except (TypeError, ValueError):
            horizon = _DEFAULT_HORIZON_DAYS
        today = fields.Date.today()
        batch = fields.Datetime.now()
        for offset in range(horizon):
            self._sweep_day(today + timedelta(days=offset), batch)
        return True

    @api.model
    def _sweep_day(self, day, batch):
        # Clear the WHOLE day up front: a staff whose visits were all
        # cancelled since the last sweep never reaches _sweep_staff_day,
        # and their stale warn/critical rows would otherwise survive.
        self.sudo().search([('date', '=', day)]).unlink()
        # Bucket by LOCAL (ICT, UTC+7) midnight, not UTC midnight — a
        # 06:30→08:00 local pair straddles the UTC boundary and would
        # never be zipped. VN deployment is single-timezone; revisit if
        # multi-country.
        day_start = datetime.combine(day, time.min) - timedelta(hours=7)
        day_end = day_start + timedelta(days=1)
        fsos = self.env['health.fieldservice.order'].sudo().search([
            ('scheduled_datetime', '>=', day_start),
            ('scheduled_datetime', '<', day_end),
            ('service_location', '!=', 'online'),
            ('state', 'in', _ACTIVE_STATES),
        ], order='scheduled_datetime')
        by_staff = {}
        for fso in fsos:
            for staff in fso.assignment_ids.mapped('staff_id'):
                by_staff.setdefault(staff.id, self.env['health.fieldservice.order'])
                by_staff[staff.id] |= fso
        for staff_id, staff_fsos in by_staff.items():
            # staff_fsos preserves scheduled order (search was ordered, union
            # keeps ascending ids only — re-sort defensively).
            ordered = staff_fsos.sorted('scheduled_datetime')
            self._sweep_staff_day(staff_id, day, ordered, batch)

    @api.model
    def _sweep_staff_day(self, staff_id, day, fsos, batch):
        # We own the whole (staff, day) slice: clear and rebuild (idempotent —
        # the partial-unique pattern is unnecessary here).
        self.sudo().search([('staff_id', '=', staff_id),
                            ('date', '=', day)]).unlink()
        if len(fsos) < 2:
            return
        criticals = []
        for prev, nxt in zip(fsos, fsos[1:]):
            r = self._check_transition(prev, nxt)
            # Bonus: fill the matrix travel floats (inert data) — never blocks.
            self._fill_matrix_travel(prev, nxt, r)
            if r['status'] not in ('warn', 'critical'):
                continue
            row = self.sudo().create({
                'staff_id': staff_id, 'date': day,
                'prev_fso_id': prev.id, 'next_fso_id': nxt.id,
                'gap_min': r['gap_min'], 'travel_min': r['travel_min'],
                'buffer_min': r['buffer_min'], 'method': r['method'],
                'status': r['status'], 'sweep_batch': batch,
            })
            if r['status'] == 'critical':
                criticals.append((row, r))
        if criticals:
            self._ensure_ops_activity(staff_id, day, criticals)

    def _fill_matrix_travel(self, prev_fso, next_fso, r):
        """Bonus (handover §2.3): write travel_time_to_next on the prev FSO's
        matrix row and travel_time_from_previous on the next FSO's matrix row,
        in HOURS. Skip silently when rows are absent or the travel is unknown.
        """
        if r.get('travel_min') is None:
            return
        hours = r['travel_min'] / 60.0
        Matrix = self.env['health.staff.availability.matrix'].sudo()
        try:
            prev_rows = Matrix.search([('fso_id', '=', prev_fso.id)])
            if prev_rows:
                prev_rows.write({'travel_time_to_next': hours})
            next_rows = Matrix.search([('fso_id', '=', next_fso.id)])
            if next_rows:
                next_rows.write({'travel_time_from_previous': hours})
        except Exception as exc:  # noqa: BLE001 — bonus data, never abort a sweep
            _logger.debug('route sweep: matrix fill skipped: %s', exc)

    def _ensure_ops_activity(self, staff_id, day, criticals):
        """ONE mail.activity on the FIRST critical transition's next FSO,
        summarizing all that day's critical pairs; dedup: skip if an open
        activity with our marker already sits on that FSO."""
        act_type = self.env.ref('mail.mail_activity_data_todo',
                                raise_if_not_found=False)
        if not act_type:
            return
        first_row = criticals[0][0]
        fso = first_row.next_fso_id
        staff = self.env['hr.employee'].browse(staff_id)
        marker = self.env._("Infeasible route")
        summary = self.env._(
            "%(staff)s — infeasible route on %(date)s "
            "(%(n)s critical transition(s))",
            staff=staff.name or staff_id, date=day, n=len(criticals))
        # Dedup on marker + FSO (todo type is generic; the summary marker is
        # what makes ours identifiable).
        existing = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'health.fieldservice.order'),
            ('res_id', '=', fso.id),
            ('activity_type_id', '=', act_type.id),
            ('summary', 'ilike', marker),
        ], limit=1)
        if existing:
            return
        lines = []
        for row, r in criticals:
            lines.append(self.env._(
                "%(a)s → %(b)s: needs ~%(t)s min travel, only %(g)s min gap",
                a=(row.prev_fso_id.patient_id.name or row.prev_fso_id.name or ''),
                b=(row.next_fso_id.patient_id.name or row.next_fso_id.name or ''),
                t=int(round(r['travel_min'])), g=int(round(r['gap_min']))))
        note = "%s:<br/>%s" % (marker, "<br/>".join(lines))
        assignee = self._activity_assignee(fso)
        try:
            fso.sudo().activity_schedule(
                'mail.mail_activity_data_todo',
                summary=summary, note=note,
                user_id=assignee.id or self.env.uid)
        except Exception as exc:  # noqa: BLE001 — reporting must not abort the sweep
            _logger.warning('route sweep: could not create ops activity: %s', exc)

    def _activity_assignee(self, fso):
        """Assignee rule (precedent: redinvoice_batch / visit_offer use a
        group's first user or the cron user): the first operations-manager
        user, else the cron/current user."""
        grp = self.env.ref('health_base.group_healthcare_operations_manager',
                           raise_if_not_found=False)
        if grp and grp.user_ids:
            return grp.user_ids[0]
        return self.env.user

    # ------------------------------------------------------------------
    # Timeline drop warnings (§2.4) — used by the staff.assignment inherit
    # ------------------------------------------------------------------
    @api.model
    def _transient_fso(self, patient, start_utc, duration_min):
        """An in-memory FSO carrying a proposed window + a patient, so the drop
        and slot paths can reuse the SAME ``_check_transition`` (it reads
        scheduled_datetime, the computed estimated_end_datetime and patient
        coords). Never persisted."""
        return self.env['health.fieldservice.order'].new({
            'patient_id': patient.id if patient else False,
            'scheduled_datetime': start_utc,
            'scheduled_duration': int(duration_min) or 60,
        })

    @api.model
    def _drop_warnings(self, staff, start_utc, end_utc, dropped_fso):
        """Warning strings for a proposed drop window against the staff's
        neighboring non-online visits that day. Uses the PROPOSED window
        (start_utc/end_utc) via a transient FSO, so it flows through the one
        shared ``_check_transition``."""
        if not dropped_fso:
            return []
        lo = start_utc - timedelta(days=1)
        hi = end_utc + timedelta(days=1)
        fsos = self._nonline_fsos_between(staff, lo, hi, exclude_fso=dropped_fso.id)
        dur = (end_utc - start_utc).total_seconds() / 60.0
        transient = self._transient_fso(dropped_fso.patient_id, start_utc, dur)
        out = []
        prevs = [f for f in fsos
                 if f.estimated_end_datetime and f.estimated_end_datetime <= start_utc]
        if prevs:
            r = self._check_transition(prevs[-1], transient)
            if r['status'] in ('warn', 'critical'):
                out.append(self._warning_text(r['travel_min'], r['gap_min']))
        nexts = [f for f in fsos
                 if f.scheduled_datetime and f.scheduled_datetime >= end_utc]
        if nexts:
            r = self._check_transition(transient, nexts[0])
            if r['status'] in ('warn', 'critical'):
                out.append(self._warning_text(r['travel_min'], r['gap_min']))
        return out

    # ------------------------------------------------------------------
    # Slot-proposer guard (§2.5)
    # ------------------------------------------------------------------
    @api.model
    def _filter_slots_travel(self, partner, slots):
        """Drop slots whose either transition would be travel-CRITICAL against
        the slot staff's existing non-online visits that day. Keeps 'warn'
        (availability beats perfection when slots are scarce). Day queries are
        batched per (staff, date) — this runs on a public page path."""
        if not slots:
            return slots
        import pytz
        cache = {}
        kept = []
        for slot in slots:
            staff = self.env['hr.employee'].browse(slot['staff_id'])
            day = slot['date']
            # Convert the slot's local (facility) start_time to UTC.
            tzname = (staff.healthcare_facility_id.timezone
                      if staff.healthcare_facility_id else None) \
                or 'Asia/Ho_Chi_Minh'
            try:
                tz = pytz.timezone(tzname)
            except Exception:  # noqa: BLE001
                tz = pytz.timezone('Asia/Ho_Chi_Minh')
            hours = slot.get('start_time') or 0.0
            local_dt = tz.localize(datetime.combine(day, time.min)
                                   + timedelta(hours=hours))
            start_utc = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            end_utc = start_utc + timedelta(minutes=60)
            transient = self._transient_fso(partner, start_utc, 60)
            key = (slot['staff_id'], day)
            if key not in cache:
                cache[key] = self._nonline_fsos_between(
                    staff, start_utc - timedelta(days=1),
                    start_utc + timedelta(days=1))
            day_fsos = cache[key]
            critical = False
            prevs = [f for f in day_fsos
                     if f.estimated_end_datetime and f.estimated_end_datetime <= start_utc]
            if prevs:
                if self._check_transition(prevs[-1], transient)['status'] == 'critical':
                    critical = True
            if not critical:
                nexts = [f for f in day_fsos
                         if f.scheduled_datetime and f.scheduled_datetime >= end_utc]
                if nexts and self._check_transition(
                        transient, nexts[0])['status'] == 'critical':
                    critical = True
            if not critical:
                kept.append(slot)
        return kept
