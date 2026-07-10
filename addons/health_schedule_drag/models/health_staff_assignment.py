# -*- coding: utf-8 -*-
"""``reschedule_from_drag`` — the single gate every schedule-timeline drag goes
through (handover §2.1).

The correct reschedule primitive is "write the FSO's scheduled_datetime": the
shipped FSO write path resyncs every sibling assignment's planned times, fires
the staff push notification, and records a chatter entry (scheduled_datetime is
tracking=True). This gate adds what the shipped drag flow lacked: an ops-group
guard, a confirmed/assigned state guard, a same-facility guard, DURATION
IMMUNITY (the end is recomputed from scheduled_duration so a resize can never
change the duration), availability-matrix release+rebook, and a patient ZNS.
"""
import logging
from datetime import timedelta

import pytz

from odoo import _, api, models

_logger = logging.getLogger(__name__)

_OPS_GROUPS = (
    'health_base.group_healthcare_operations_manager',
    'health_base.group_healthcare_head_nurse',
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)


class HealthStaffAssignment(models.Model):
    _inherit = 'health.staff.assignment'

    @staticmethod
    def _dt_to_iso(dt):
        return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else False

    def _is_ops(self):
        return any(self.env.user.has_group(g) for g in _OPS_GROUPS)

    # ------------------------------------------------------------------
    # Availability-matrix release / rebook (inverse of book_staff_slot)
    # ------------------------------------------------------------------
    def _matrix_release(self, fso):
        """Unlink the FSO's booked + buffer matrix rows (both carry fso_id).
        No-op when the visit was never matrix-booked (most legacy ones)."""
        if not fso:
            return
        rows = self.env['health.staff.availability.matrix'].sudo().search([
            ('fso_id', '=', fso.id),
            ('status', 'in', ('booked', 'buffer')),
        ])
        if rows:
            rows.unlink()

    def _matrix_rebook(self, fso, staff, start_utc, duration_min, assignment):
        """Best-effort re-book of the new slot (routes precedent: a matrix
        hiccup must never fail the reschedule)."""
        try:
            self.env['health.staff.availability.matrix'].sudo().book_staff_slot(
                staff.id, start_utc, duration_min,
                fso_id=fso.id, assignment_id=assignment.id)
        except Exception as exc:  # noqa: BLE001
            _logger.info('Schedule drag: matrix rebook skipped for fso %s: %s',
                         fso.id, exc)

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------
    @api.model
    def reschedule_from_drag(self, assignment_id, start_iso, end_iso,
                             new_staff_id, confirmed=False, mode='day'):
        """Reschedule the whole booking behind a dragged block. Returns a
        structured dict, never raises for expected conditions:
        {status: 'ok'|'needs_confirm'|'refused'|'noop', message, fso_id}.

        ``mode`` (day/week/month) is a minimal extension of the handover
        signature so the shipped Week/Month "keep the time-of-day, move only
        the date" behaviour is preserved (see _effective_reschedule_times)."""
        def refused(message):
            return {'status': 'refused', 'message': message}

        a = self.browse(assignment_id).exists()
        if not a or a.state == 'template':
            return refused(_('Unknown assignment.'))
        fso = a.fso_id
        if not fso:
            return refused(_('This block has no booking to reschedule.'))
        if fso.state not in ('confirmed', 'assigned'):
            return refused(_(
                'Only confirmed or assigned bookings can be rescheduled by '
                'dragging. This one is %s.') % fso.state)
        if not self._is_ops():
            return refused(_(
                'Rescheduling is an operations decision — ask an operations '
                'manager or head nurse.'))
        # Dispatch guard (the superseded validate_timeline_change had this):
        # once anyone is en route / on site, the visit must not move under
        # them even while fso.state is still 'assigned'.
        dispatched = fso.assignment_ids.filtered(
            lambda x: x.state not in ('cancelled', 'template')
            and getattr(x, 'assignment_status', '') in (
                'en_route', 'arrived', 'in_progress'))
        if dispatched:
            return refused(_(
                'Staff are already en route or on site for this visit — it '
                'can no longer be rescheduled by dragging.'))

        # sudo the employee records: reading any hr.employee field as a non-HR
        # ops user trips the public-profile prefetch guard (access_role_id etc.).
        old_staff = a.staff_id.sudo()
        new_staff = (self.env['hr.employee'].sudo().browse(new_staff_id).exists()
                     if new_staff_id else old_staff)
        if not new_staff:
            return refused(_('Drop the block on a staff member.'))
        staff_changed = bool(new_staff_id) and new_staff.id != old_staff.id
        if staff_changed and new_staff.healthcare_facility_id and fso.facility_id \
                and new_staff.healthcare_facility_id.id != fso.facility_id.id:
            return refused(_(
                'Cross-facility moves are not allowed — pick a staff member in '
                'the same facility.'))

        ns = self._sched_parse_iso(start_iso)
        ne = self._sched_parse_iso(end_iso) or (ns and ns + timedelta(hours=1))
        if not ns:
            return refused(_('Invalid time.'))
        # Day = dropped time verbatim; Week/Month = keep time-of-day, move date.
        eff_start, _eff_end = self._effective_reschedule_times(fso, ns, ne, mode)
        # DURATION IMMUNITY: recompute the end from the booking's duration and
        # ignore the client's end entirely (a resize can never smuggle through).
        dur = fso.scheduled_duration or 60
        eff_end = eff_start + timedelta(minutes=dur)

        if not staff_changed and fso.scheduled_datetime \
                and eff_start == fso.scheduled_datetime:
            return {'status': 'noop', 'fso_id': fso.id}

        res = self.validate_drop(new_staff.id, self._dt_to_iso(eff_start),
                                 self._dt_to_iso(eff_end), assignment_id)
        if res.get('hard_block'):
            return refused(res.get('message') or _("That change isn't allowed."))
        # Sibling guard (superseded-flow parity): the whole booking moves, so
        # EVERY other assigned staff must be free at the new window too —
        # hard reasons (leave/off-hours) refuse; soft overlaps join the
        # confirm warning.
        conflicts, sib_warnings = [], []
        for sib in fso.assignment_ids.filtered(
                lambda x: x.id != a.id
                and x.state not in ('cancelled', 'template') and x.staff_id):
            r = self._check_emp_slot(sib.staff_id.sudo(), eff_start, eff_end,
                                     exclude_assignment_id=sib.id)
            if r.get('hard'):
                conflicts.append('%s (%s)' % (sib.staff_id.name,
                                              r.get('message')))
            elif r.get('overlap') and r.get('message'):
                sib_warnings.append(r['message'])
        if conflicts:
            return refused(_('Cannot reschedule — ') + '; '.join(conflicts))
        warning = res.get('message')   # overlap / travel warnings when ok
        if sib_warnings:
            warning = ' '.join(filter(None, [warning] + sib_warnings))
        if warning and not confirmed:
            return {'status': 'needs_confirm', 'message': warning,
                    'fso_id': fso.id}

        # The ops-group guard above is the authorization; sudo the mutations so
        # the reschedule never trips the HR public-profile field restriction
        # (an ops manager without full HR access still reschedules — the
        # ai_coding both-layers precedent: guard by group, then sudo the write).
        fso_su = fso.sudo()
        a_su = a.sudo()
        with self.env.cr.savepoint():
            self._matrix_release(fso)
            if staff_changed:
                a_su.write({'staff_id': new_staff.id})
                try:
                    fso_su._send_staff_assignment_notification(new_staff, a_su)
                    if old_staff:
                        fso_su._send_staff_cancellation_notification(old_staff)
                except Exception as exc:  # noqa: BLE001
                    _logger.warning('Schedule drag: reassign notify failed: %s',
                                    exc)
            if not fso.scheduled_datetime or eff_start != fso.scheduled_datetime:
                # scheduled_duration is intentionally NOT written (immunity) —
                # the shipped write path resyncs siblings + pushes the staff.
                fso_su.write({'scheduled_datetime': eff_start})
            # scheduled_datetime is tracking=True but the FSO write path posts
            # NO tracking message (verified: 0 tracking values) — post an
            # explicit audit note so the reschedule is always on the record.
            try:
                fso_su.message_post(body=self._reschedule_ok_text(
                    fso, new_staff, eff_start, staff_changed))
            except Exception as exc:  # noqa: BLE001 — audit note is best-effort
                _logger.info('Schedule drag: chatter note skipped: %s', exc)
            self._matrix_rebook(fso, new_staff, eff_start, dur, a)
            try:
                fso_su._send_rescheduled_zns()
            except Exception as exc:  # noqa: BLE001 — a send must never break it
                _logger.warning('Schedule drag: reschedule ZNS failed: %s', exc)

        return {'status': 'ok', 'fso_id': fso.id,
                'message': self._reschedule_ok_text(fso, new_staff, eff_start,
                                                    staff_changed)}

    # ------------------------------------------------------------------
    # Close the legacy side door
    # ------------------------------------------------------------------
    @api.model
    def apply_timeline_change(self, assignment_id, new_start_iso, new_end_iso,
                              new_staff_id, mode='day'):
        """The shipped endpoint has NO ops/state/facility guards and writes
        scheduled_duration (duration-immunity bypass). The UI no longer calls
        it, but it stays RPC-callable by anyone with assignment write rights —
        route it through the gate so a direct RPC obeys the same rules.
        confirmed=True preserves the legacy 'apply' semantics (its callers
        validated separately); every HARD guard still applies."""
        res = self.reschedule_from_drag(
            assignment_id, new_start_iso, new_end_iso, new_staff_id,
            confirmed=True, mode=mode)
        ok = res.get('status') in ('ok', 'noop')
        return {'ok': ok, 'message': res.get('message', ''),
                'status': res.get('status')}

    def _reschedule_ok_text(self, fso, new_staff, eff_start, staff_changed):
        try:
            tz = pytz.timezone(fso.booking_timezone or 'Asia/Ho_Chi_Minh')
            local = pytz.utc.localize(eff_start).astimezone(tz)
            when = local.strftime('%a %d %b %H:%M')
        except Exception:  # noqa: BLE001
            when = ''
        who = fso.patient_id.name or _('booking')
        if staff_changed:
            return _('%(who)s moved to %(staff)s — %(when)s.') % {
                'who': who, 'staff': new_staff.name, 'when': when}
        return _('%(who)s rescheduled to %(when)s.') % {'who': who, 'when': when}
