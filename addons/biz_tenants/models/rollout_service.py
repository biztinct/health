# -*- coding: utf-8 -*-
"""Running a rollout: the worker, the health gate, and the buttons.

THE SHAPE OF THIS FILE. Every judgement is next door in `rollout_rules.py`,
pure and tested. What is left here is the ACTING: restore a copy, run the "bring
one system in step" unit on one database, ask the address for a page, read the
log, put a message on somebody's screen and take it down again. Each of those
is a few lines, and every one of them is a thing that can only be done on a live
machine.

RAIL R1, WHICH IS THE WHOLE PHASE. Nothing here starts a rollout. A person
presses Start; that writes down the list of systems and the order; the worker
then does exactly that list and stops at the first failure. The scheduled job
that warns a customer's people only ever speaks to a customer already on
somebody's list. Every step leaves a line in that customer's own trail, so the
answer to "why did my system pause last night" is on their record rather than
in a log file nobody can read.

RAIL R4, WHICH IS THE REASON THE FIRST RING EXISTS. A release reaches a real
clinic only after it has been applied to a throwaway copy of a real clinic's
system, and that copy is deleted afterwards WHATEVER HAPPENED — the drop is in
a `finally` that wraps the restore itself, because a restore that falls over
halfway leaves a part-built system on a machine with two gigabytes of memory
(ledger F26).
"""
import json
import logging
import os
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import tenants_common as common
from .rollout_rules import (
    CUSTOMER_RINGS, DEFAULT_HOURS, DEFAULT_START_HOUR, DEFAULT_TZ,
    PRE_NOTICE_HOURS, RING_LABEL, RING_MEANING, RING_ORDER, advance,
    health_verdict, notice_for, plan_tasks, say_window, to_local,
    watch_hours_for, window_bounds, window_open,
)
from .sync_rules import log_lines_of_interest, master_behind_files

_logger = logging.getLogger(__name__)

#: How many error lines to keep on one step. Enough to read; not a log viewer.
LOG_KEEP = 12


class BizTenantsRollout(models.AbstractModel):
    """The rollout half of the cockpit."""
    _inherit = 'biz.tenants'

    # =====================================================================
    #  SMALL HELPERS
    # =====================================================================
    def _tenant_tz(self, tenant):
        """What time is it where this customer is?

        Read ONCE off their own company record — plain read-only SQL, no
        registry opened — and then kept on our side. A customer with nothing
        set falls back to the zone every customer of this product has so far
        been in, which is a better guess than the machine's own UTC and is
        never silently wrong for long: it is shown on screen, named, beside
        every window it decides.
        """
        if tenant.tz:
            return tenant.tz
        tz = ''
        try:
            with self._pg_cursor(tenant.slug) as cr:
                cr.execute("SELECT p.tz FROM res_company c "
                           "JOIN res_partner p ON p.id = c.partner_id "
                           "WHERE p.tz IS NOT NULL ORDER BY c.id LIMIT 1")
                row = cr.fetchone()
                tz = (row and row[0]) or ''
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: could not read the time zone of %s",
                            tenant.slug, exc_info=True)
        tz = tz or DEFAULT_TZ
        tenant.sudo().write({'tz': tz})
        return tz

    def _task_window(self, task):
        """`(tz, start_hour, hours)` for one step's customer."""
        t = task.tenant_id
        if not t:
            return DEFAULT_TZ, DEFAULT_START_HOUR, DEFAULT_HOURS
        return (self._tenant_tz(t),
                t.maintenance_start or DEFAULT_START_HOUR,
                t.maintenance_hours or DEFAULT_HOURS)

    def _task_snapshot(self, task):
        """One step as the pure state machine reads it."""
        tz, start, hours = self._task_window(task)
        return {
            'id': task.id, 'ring': task.ring, 'state': task.state,
            'run_now': task.run_now, 'label': task.label,
            'tz': tz, 'maintenance_start': start, 'maintenance_hours': hours,
            'started_at': task.started_at, 'error': task.error or '',
        }

    def _rollout_snapshot(self, rollout, watch_health=None):
        return {
            'state': rollout.state,
            'current_ring': rollout.ring,
            'ring_done_at': rollout.ring_done_at,
            'watch_skipped': rollout.watch_skipped,
            'watch_hours': {'canary': rollout.watch_hours_canary,
                            'early': rollout.watch_hours_early},
            'watch_health': watch_health or [],
            'tasks': [self._task_snapshot(t) for t in rollout.task_ids],
        }

    # =====================================================================
    #  THE HEALTH GATE
    # =====================================================================
    def _log_tail_lines(self):
        """The last part of the machine's log, as lines. Never fatal.

        A log that cannot be read is reported as "could not check" — `None` —
        and never as a healthy nought (ledger F27).
        """
        from .service import LOG_PATH, LOG_TAIL_BYTES
        try:
            size = os.path.getsize(LOG_PATH)
            with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as fh:
                if size > LOG_TAIL_BYTES:
                    fh.seek(size - LOG_TAIL_BYTES)
                    fh.readline()        # drop the half line we landed in
                return fh.readlines()
        except OSError:
            _logger.warning("biz_tenants: the machine's log could not be read")
            return None

    def _health_gate(self, dbname, since, skipped, host=None):
        """Is this system well after its update? The three checks, together.

        Returns the dict stored on the step: what was measured, and the verdict
        in one sentence.

        ⚠ `since` IS WHEN THE UPDATE STARTED, NOT WHEN THE RESTORE DID
        (ledger F26). Restoring a system writes errors of its own, because the
        framework asks a half-built database what version it is on. That is the
        restore talking, not the update, and counting it failed a practice run
        whose copy was in perfect health.
        """
        code, ms = (None, -1)
        if host:
            code, ms = self._probe(host)
        lines = self._log_tail_lines()
        stamp = (since.strftime('%Y-%m-%d %H:%M:%S')
                 if isinstance(since, datetime) else str(since or ''))
        if lines is None:
            errors, ignored, read_ok = [], [], False
        else:
            split = log_lines_of_interest(lines, dbname, stamp,
                                          common.health_ignore(self.env))
            errors, ignored, read_ok = split['errors'], split['ignored'], True
        ok, reason = health_verdict(code, skipped, errors if read_ok else [])
        if not read_ok and ok:
            reason = reason or ("The machine's log could not be read, so "
                                "nothing in it could be checked.")
        return {
            'ok': bool(ok), 'reason': reason,
            'probe_code': code, 'probe_ms': ms, 'host': host or '',
            'skipped': -1 if skipped is None else int(skipped),
            'errors': errors[:LOG_KEEP],
            'error_count': -1 if not read_ok else len(errors),
            # ⚠ RECORDED, NEVER DROPPED (ledger F25).
            'ignored': ignored[:LOG_KEEP],
            'ignored_count': len(ignored),
            'checked_at': fields.Datetime.now().isoformat(sep=' ',
                                                          timespec='seconds'),
        }

    # =====================================================================
    #  PLANNING
    # =====================================================================
    def _rehearsal_source(self):
        """Whose system the practice run is done on.

        The first customer marked "first to get it" who has a usable copy, then
        the BIGGEST live customer with one. Biggest, because the practice run's
        job is to find the slow, awkward migration, and the system most likely
        to have one is the system with the most in it.
        """
        Tenant = self._tenants()
        live = Tenant.search([('state', 'in', ('live', 'error'))])

        def usable(t):
            b = self.env['biz.tenant.backup'].sudo().search(
                [('tenant_id', '=', t.id), ('state', '=', 'done')],
                order='taken_at desc', limit=1)
            return bool(b and b.path and os.path.exists(b.path))

        canaries = [t for t in live if t.ring == 'canary' and usable(t)]
        pool = canaries or sorted([t for t in live if usable(t)],
                                  key=lambda t: -(t.db_size or 0))
        if not pool:
            return None
        t = pool[0]
        return {'id': t.id, 'name': t.name, 'slug': t.slug}

    def _plan_for(self, rel):
        tenants = [{'id': t.id, 'name': t.name, 'slug': t.slug,
                    'state': t.state, 'ring': t.ring}
                   for t in self._tenants().search([])]
        return plan_tasks({'id': rel.id, 'name': rel.name}, tenants,
                          self._rehearsal_source(), self._template_db())

    def _master_behind(self):
        master = self._master_modules()
        return master_behind_files(
            [(n, d['have'], d['file']) for n, d in master.items()])

    @api.model
    def rollout_plan(self, release_id=None):
        """What a rollout WOULD do. Reads only, and refuses nothing.

        The whole content of the Start dialog: every step in order, when each
        one would happen IN THE CUSTOMER'S OWN WORDS, what is being left out
        and why, and every reason this could not be started right now.
        """
        self._require_platform_admin()
        Release = self.env['biz.release'].sudo()
        rel = (Release.browse(int(release_id)).exists() if release_id
               else Release.current())
        if not rel:
            raise UserError(self.env._(
                "Cut a release first — a rollout sends a release out, and there "
                "is not one yet. The button is on \"In step with master\"."))
        plan = self._plan_for(rel)
        now = fields.Datetime.now()
        rows, missing_link = [], []
        for task in plan['tasks']:
            row = dict(task)
            row['ring_label'] = RING_LABEL.get(task['ring'], task['ring'])
            if task['ring'] in CUSTOMER_RINGS and task['tenant_id']:
                t = self._tenants().browse(task['tenant_id'])
                tz = self._tenant_tz(t)
                opens, closes = window_bounds(
                    now, tz, t.maintenance_start or DEFAULT_START_HOUR,
                    t.maintenance_hours or DEFAULT_HOURS)
                # ⚠ SAID IN THEIR CLOCK, WITH THE ZONE NAMED (ledger F32). The
                # person reading this plan has to be looking at the same window
                # their customer's own bar will show them, or the two screens
                # disagree about what was scheduled.
                row['when'] = say_window(to_local(opens, tz),
                                         to_local(closes, tz),
                                         to_local(now, tz), tz)
                row['tz'] = tz
                if not self._tenancy_installed(t.slug):
                    missing_link.append(t.name)
            else:
                row['when'] = "right away"
                row['tz'] = ''
            rows.append(row)
        return {
            'release': {'id': rel.id, 'name': rel.name,
                        'notes': rel.notes or '',
                        'module_count': rel.module_count},
            'tasks': rows,
            'excluded': plan['excluded'],
            'warnings': plan['warnings'],
            'blockers': self._rollout_blockers(rel, missing_link, plan),
            'watch_canary': 24, 'watch_early': 48,
            'ring_meaning': dict(RING_MEANING),
        }

    def _rollout_blockers(self, rel, missing_link=None, plan=None):
        """Everything that stops Start, each with the next step in the sentence.

        ⚠ RAIL R4 IS ENFORCED HERE, NOT HOPED FOR (ledger F31). With the only
        usable copy moved aside, the planner shrugged, left the practice run
        out and offered to update a real customer with nobody having rehearsed
        anything. A warning is not enough for this one: the practice run is the
        whole reason the first real clinic is not the experiment. So it is a
        BLOCKER, and it names the customer and the button that takes a copy.
        """
        out = []
        if plan is not None:
            customers = [t for t in plan['tasks'] if t['ring'] in CUSTOMER_RINGS]
            rehearsal = any(t['ring'] == 'rehearsal' for t in plan['tasks'])
            if customers and not rehearsal:
                out.append(
                    "There is no copy to practise on, and a release never "
                    "reaches a real customer without a practice run first. "
                    "Open %s, go to their Copies tab, press \"Copy now\", and "
                    "start again." % customers[0]['label'])
        if not (rel.notes or '').strip():
            out.append("Write down what changed on this release first — the "
                       "customers read it on their own About screen. The notes "
                       "box is on \"In step with master\".")
        behind = self._master_behind()
        if behind:
            out.append(
                "This platform has not caught up with its own files yet — %d "
                "parts are waiting, starting with %s. Nothing goes out from a "
                "system that is halfway through its own update."
                % (len(behind), behind[0]))
        busy = self.env['biz.rollout'].sudo().search(
            [('state', 'in', ('rehearsing', 'running', 'waiting', 'paused'))],
            limit=1)
        if busy:
            out.append(
                "Release %s is already going out (%s). Finish that one or call "
                "it off first — the practice copy has one name, and two "
                "rollouts destroy each other's."
                % (busy.release_id.name,
                   dict(busy._fields['state'].selection).get(busy.state)))
        for name in (missing_link or ()):
            out.append("%s cannot be told anything yet. Bring it in step once "
                       "by hand first, which puts the platform link on it."
                       % name)
        return out

    # =====================================================================
    #  START
    # =====================================================================
    @api.model
    def rollout_start(self, release_id=None, watch_canary=24, watch_early=48):
        """A PERSON PRESSES THIS, AND NOTHING ELSE EVER DOES.

        It writes the list down and then runs the first step — the practice run
        — while they watch, so the answer to "did that work" is on the screen
        rather than in an hour's time.

        ⚠ ONE PERSON, TWICE, IS TWO ROLLOUTS, AND THEY FIGHT OVER THE PRACTICE
        COPY (ledger F50). "Already going out" is checked below, but this whole
        call runs the practice run before it commits, which takes a minute and a
        half. A second press inside that minute cannot see the first rollout at
        all, writes a second one, and the two then restore and drop the same
        throwaway system underneath each other: the first dies with "connection
        already closed", the second with "could not serialize access", and both
        stop with nothing having reached a customer.

        The lock below is held to the END OF THE TRANSACTION, so the second
        press waits for the first to finish and then gets the refusal it should
        have had. Advisory rather than a row lock, because there is no row to
        lock until the very thing being guarded has happened.
        """
        self._require_platform_admin()
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtext('biz_tenants.rollout_start'))")
        Release = self.env['biz.release'].sudo()
        rel = (Release.browse(int(release_id)).exists() if release_id
               else Release.current())
        if not rel:
            raise UserError(self.env._("Cut a release first."))
        plan = self._plan_for(rel)
        missing = []
        for task in plan['tasks']:
            if task['ring'] in CUSTOMER_RINGS and task['tenant_id']:
                t = self._tenants().browse(task['tenant_id'])
                if not self._tenancy_installed(t.slug):
                    missing.append(t.name)
        blockers = self._rollout_blockers(rel, missing, plan)
        if blockers:
            raise UserError('\n\n'.join(blockers))

        first_ring = plan['tasks'][0]['ring'] if plan['tasks'] else 'everyone'
        rollout = self.env['biz.rollout'].sudo().create({
            'release_id': rel.id,
            'state': 'rehearsing' if first_ring == 'rehearsal' else 'running',
            'ring': first_ring,
            'watch_hours_canary': max(0, int(watch_canary or 0)),
            'watch_hours_early': max(0, int(watch_early or 0)),
            'started_at': fields.Datetime.now(),
            'ring_started_at': fields.Datetime.now(),
            'started_by': self.env.uid,
        })
        for task in plan['tasks']:
            self.env['biz.rollout.task'].sudo().create({
                'rollout_id': rollout.id,
                'sequence': task['sequence'], 'ring': task['ring'],
                'tenant_id': task['tenant_id'] or False,
                'source_tenant_id': task['source_tenant_id'] or False,
                'label': task['label'], 'target_db': task['target_db'],
            })
        rollout.log_line("%s started release %s going out to %d systems."
                         % (self.env.user.name, rel.name, len(plan['tasks'])))
        for w in plan['warnings']:
            rollout.log_line(w, 'warn')
        self._refresh_schedule(rollout)
        # The first step is the practice run and it needs nobody's window: run
        # it now, so the person who pressed Start sees the answer.
        self._rollout_tick(rollout)
        return self.rollout_state()

    def _refresh_schedule(self, rollout):
        """When each waiting customer's window next opens, and whether it is
        open NOW. Stored as UTC; the screen converts and names the zone."""
        now = fields.Datetime.now()
        for task in rollout.task_ids:
            if task.state not in ('waiting', 'due'):
                continue
            if task.ring not in CUSTOMER_RINGS:
                continue
            tz, start, hours = self._task_window(task)
            opens, closes = window_bounds(now, tz, start, hours)
            open_now = window_open(now, tz, start, hours)
            task.sudo().write({
                'window_start': opens, 'window_end': closes,
                'state': 'due' if (open_now or task.run_now) else 'waiting',
            })

    # =====================================================================
    #  THE WORKER
    # =====================================================================
    def _lock_rollout(self, rollout):
        """Nobody works on this rollout twice at once.

        The scheduled worker and a person pressing "Run now" are two threads
        reaching for the same customer, and the second would find a system
        being rebuilt underneath it. `SKIP LOCKED` means the loser walks away
        rather than queueing behind a job that takes minutes.
        """
        self.env.cr.execute(
            "SELECT id FROM biz_rollout WHERE id = %s FOR UPDATE SKIP LOCKED",
            (rollout.id,))
        return bool(self.env.cr.fetchone())

    @api.model
    def rollout_tick(self, rollout_id=None):
        """One step of the worker, asked for by a person."""
        self._require_platform_admin()
        rollout = self._current_rollout(rollout_id)
        if not rollout:
            return self.rollout_state()
        self._rollout_tick(rollout)
        return self.rollout_state()

    def _current_rollout(self, rollout_id=None):
        R = self.env['biz.rollout'].sudo()
        if rollout_id:
            return R.browse(int(rollout_id)).exists()
        return R.search([('state', 'in', ('rehearsing', 'running', 'waiting'))],
                        order='id desc', limit=1)

    def _rollout_tick(self, rollout):
        """THE WORKER. One decision, one act, and back for another look."""
        if rollout.state not in ('rehearsing', 'running', 'waiting'):
            return {'ok': False, 'reason': 'not running'}
        if not self._lock_rollout(rollout):
            _logger.info("biz_tenants: rollout %s is already being worked on",
                         rollout.id)
            return {'ok': False, 'reason': 'busy'}
        now = fields.Datetime.now()
        self._refresh_schedule(rollout)
        watch = self._watch_probes(rollout, now)
        decision = advance(self._rollout_snapshot(rollout, watch), now)
        kind = decision[0]

        if kind == 'run':
            task = self.env['biz.rollout.task'].sudo().browse(decision[1]['id'])
            rollout.sudo().write({
                'state': 'rehearsing' if task.ring == 'rehearsal' else 'running'})
            self._run_task(task)
            # Look again immediately: a finished step usually means the next
            # one may start, and waiting five minutes to notice is five minutes
            # of somebody's quiet window spent idle.
            return self._rollout_tick(rollout)
        if kind == 'ring_done':
            rollout.sudo().write({'ring_done_at': now})
            rollout.log_line("%s finished."
                             % RING_LABEL.get(decision[1], decision[1]))
            return self._rollout_tick(rollout)
        if kind == 'advance_ring':
            ring = decision[1]
            rollout.sudo().write({'ring': ring, 'state': 'running',
                                  'ring_started_at': now, 'ring_done_at': False,
                                  'watch_skipped': False})
            rollout.log_line("Moving on to %s." % RING_LABEL.get(ring, ring))
            self._refresh_schedule(rollout)
            return self._rollout_tick(rollout)
        if kind == 'wait':
            rollout.sudo().write({'state': 'waiting'})
            self._refresh_schedule(rollout)
            return {'ok': True, 'reason': 'waiting', 'until': decision[1]}
        if kind == 'pause':
            self._pause(rollout, decision[1])
            return {'ok': False, 'reason': decision[1]}
        if kind == 'done':
            rollout.sudo().write({'state': 'done', 'finished_at': now})
            rollout.log_line("Release %s is out." % rollout.release_id.name)
            return {'ok': True, 'reason': 'done'}
        return {'ok': False, 'reason': 'nothing to do'}

    def _pause(self, rollout, reason):
        rollout.sudo().write({'state': 'paused', 'note': reason})
        rollout.log_line(reason, 'error')
        _logger.warning("biz_tenants: rollout %s stopped: %s",
                        rollout.id, reason)

    def _watch_probes(self, rollout, now):
        """Is the ring being watched still healthy?

        Only asked while a watch period is actually running, and only of the
        customers that ring updated. One request each and no writes anywhere.

        ⚠ THE ADDRESS ONLY, AND DELIBERATELY. Straight after an update, an
        error in the log is evidence the update broke something. A day later it
        is evidence somebody typed something odd into a form, and stopping a
        whole rollout for that would teach the owner to ignore the watch
        period. What is being watched here is "is this customer still
        answering".
        """
        if rollout.state != 'waiting' or not rollout.ring_done_at:
            return []
        if not watch_hours_for(rollout.ring,
                               {'canary': rollout.watch_hours_canary,
                                'early': rollout.watch_hours_early}):
            return []
        out = []
        for task in rollout.task_ids:
            if task.ring != rollout.ring or task.state != 'done':
                continue
            if not task.tenant_id:
                continue
            code, ms = self._probe(self._tenant_host(task.tenant_id.slug))
            ok, reason = health_verdict(code, 0, [])
            out.append({'name': task.label, 'ok': ok, 'reason': reason,
                        'ms': ms})
        return out

    # ------------------------------------------------------------ one step
    def _run_task(self, task):
        rollout = task.rollout_id
        started = fields.Datetime.now()
        task.sudo().write({'state': 'running', 'started_at': started,
                           'attempts': (task.attempts or 0) + 1,
                           'error': False})
        rollout.log_line("Updating %s…" % task.label)
        try:
            if task.ring == 'rehearsal':
                res, health = self._run_rehearsal(task)
            elif task.ring == 'template':
                res, health = self._run_template(task, started)
            else:
                res, health = self._run_tenant(task, started)
        except Exception as exc:                             # noqa: BLE001
            _logger.exception("biz_tenants: rollout step %s failed", task.id)
            msg = (str(exc).strip().split('\n')[0][:400]
                   or "It did not finish.")
            self._finish_task(task, 'failed', {}, {}, msg, started)
            self._pause(rollout, "%s could not be updated: %s"
                        % (task.label, msg))
            return
        if health.get('ok'):
            self._finish_task(task, 'done', res, health, '', started)
            rollout.log_line("%s is done (%ss)."
                             % (task.label, task.duration_s))
        else:
            self._finish_task(task, 'failed', res, health,
                              health.get('reason')
                              or "It did not look well afterwards.", started)
            self._pause(rollout, "%s: %s"
                        % (task.label, health.get('reason') or ''))

    def _finish_task(self, task, state, result, health, error, started):
        end = fields.Datetime.now()
        task.sudo().write({
            'state': state, 'finished_at': end,
            'duration_s': int((end - started).total_seconds()),
            'result': json.dumps(result or {}, default=str)[:200000],
            'health_verdict': json.dumps(health or {}, default=str)[:60000],
            # Recorded rather than dropped (F25): both lists, and the count.
            'error_lines': json.dumps(
                {'errors': (health or {}).get('errors') or [],
                 'ignored': (health or {}).get('ignored') or []},
                default=str)[:60000],
            'ignored_count': int((health or {}).get('ignored_count') or 0),
            'error': error or False,
        })

    def _run_unit(self, target):
        """The whole "bring one system in step" unit, on one target.

        A method of its own so a test can replace it with something that does
        not need a second database.

        ⚠ THE RELEASE STAMP IS DEFERRED. The unit would normally tell a system
        it is on the new release the moment the install finishes; in a rollout
        that announcement has to wait until the health checks have passed. A
        customer must never be shown "you are on release X — here is what
        changed" about an update that is about to be called a failure.
        """
        return self.with_context(
            biz_defer_release_stamp=True).sync_bring_in_step(target,
                                                             dry_run=False)

    def _run_rehearsal(self, task):
        """Rail R4: practise on a copy, then delete the copy. ALWAYS."""
        rollout = task.rollout_id
        src = task.source_tenant_id
        if not src:
            raise UserError(self.env._("There is no customer to practise on."))
        res, health = {}, {}
        # ⚠ THE RESTORE IS INSIDE THE `try`, AND THAT IS RAIL R4 RATHER THAN
        # TIDINESS (ledger F26). A restore that falls over halfway leaves a
        # part-built system behind, and the `finally` below is the only thing
        # that takes it away again.
        try:
            rollout.log_line("Restoring a throwaway copy of %s…" % src.name)
            try:
                restored = self.restore_to_staging(src.id)
            except Exception as exc:                         # noqa: BLE001
                _logger.exception("biz_tenants: the practice restore failed")
                raise UserError(self.env._(
                    "The practice copy of %(who)s could not be made from their "
                    "last copy — the file may be damaged or half-written. Open "
                    "%(who)s, go to Copies, press \"Copy now\", and try this "
                    "step again. Nothing has been done to %(who)s themselves.",
                    who=src.name)) from exc
            rollout.log_line("Copy restored from %s."
                             % restored.get('from_backup', '?'))
            # ⚠ THE CLOCK STARTS AFTER THE RESTORE (ledger F26). What is being
            # judged here is what the UPDATE did, not what the restore did.
            since = fields.Datetime.now()
            res = self._run_unit(task.target_db)
            health = self._health_gate(task.target_db, since,
                                       res.get('skipped_count'), None)
        finally:
            # THE COPY GOES, WHATEVER HAPPENED. A failed practice run that left
            # a multi-gigabyte system behind would cost this machine its memory
            # headroom on the day it is least able to spare it.
            try:
                self.drop_staging(src.id)
                rollout.log_line("Practice copy deleted.")
            except Exception:                                # noqa: BLE001
                _logger.exception("biz_tenants: could not drop %s",
                                  task.target_db)
                rollout.log_line(
                    "The practice copy %s could NOT be deleted — remove it by "
                    "hand." % task.target_db, 'error')
        return res, health

    def _run_template(self, task, started):
        """The blank system new customers are made from. Nobody is looking."""
        res = self._run_unit('template')
        # No address, so nothing to ask: the blank system is never served.
        health = self._health_gate(task.target_db, started,
                                   res.get('skipped_count'), None)
        # ⚠ CHECKED RATHER THAN ASSUMED (ledger F9). Installing or upgrading
        # anything switches a system's scheduled jobs back ON, and the unit
        # switches them off again; this reads the system back and says what it
        # found. A blank system with a live job wakes itself up and holds
        # memory on a machine that has none to spare.
        crons, recorded = self._template_cron_state()
        res['template_active_crons'] = crons
        res['template_recorded_crons'] = recorded
        if crons and health.get('ok'):
            health['ok'] = False
            health['reason'] = (
                "%s scheduled jobs are still switched on in the blank system. A "
                "blank system with a live job wakes itself up and holds "
                "memory." % crons)
        task.rollout_id.log_line(
            "Blank system checked: %s scheduled jobs still on, %s recorded for "
            "new customers." % (crons, recorded))
        return res, health

    def _template_cron_state(self):
        """How many of the blank system's jobs are on, and how many are written
        down for a new customer to get back."""
        db = self._template_db()
        try:
            with self._pg_cursor(db) as cr:
                cr.execute("SELECT count(*) FROM ir_cron WHERE active")
                active = cr.fetchone()[0]
                cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s",
                           (common.P_TEMPLATE_CRONS,))
                row = cr.fetchone()
                recorded = len([c for c in ((row and row[0]) or '').split(',')
                                if c.strip()])
            return active, recorded
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: could not read the blank system's jobs",
                            exc_info=True)
            return -1, -1

    def _run_tenant(self, task, started):
        """A real customer: tell them, do it, check it, take the message down."""
        t = task.tenant_id
        rollout = task.rollout_id
        self._notice_now(task)
        try:
            res = self._run_unit(t.id)
            health = self._health_gate(t.slug, started,
                                       res.get('skipped_count'),
                                       self._tenant_host(t.slug))
        finally:
            # The "being updated right now" bar comes down whatever happened.
            # Leaving it up on a customer whose update failed would tell their
            # people their system was mid-update for the rest of the week.
            try:
                self.notice_clear([t.id])
            except Exception:                                # noqa: BLE001
                _logger.warning("biz_tenants: could not take the bar down on %s",
                                t.slug, exc_info=True)
        if health.get('ok'):
            # ONLY NOW. The release stamp — and with it the note their people
            # get about what changed — is the last thing that happens, after
            # the checks have passed.
            try:
                self._push_release_stamp(
                    t.id, {'release_state': res.get('release_state')},
                    rollout.release_id,
                    lambda line, level='info': rollout.log_line(line, level))
            except Exception:                                # noqa: BLE001
                _logger.warning("biz_tenants: could not stamp the release on %s",
                                t.slug, exc_info=True)
        return res, health

    def _notice_now(self, task):
        """The "being updated right now" bar on their own screens."""
        t = task.tenant_id
        try:
            payload = notice_for('now', common.brand(self.env))
            self.notice_send([t.id], payload['kind'], payload['text'], '', '')
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: could not put the bar up on %s",
                            t.slug, exc_info=True)

    # =====================================================================
    #  THE WARNING THE EVENING BEFORE
    # =====================================================================
    @api.model
    def _cron_rollout_notices(self):
        """Tell tomorrow's customers, the evening before.

        RAIL R1. This only ever speaks to a customer already on a list somebody
        made: a waiting step, in a rollout a person started. It sends nothing to
        anybody else and it installs nothing anywhere.
        """
        now = fields.Datetime.now()
        horizon = now + timedelta(hours=PRE_NOTICE_HOURS)
        tasks = self.env['biz.rollout.task'].sudo().search([
            ('state', 'in', ('waiting', 'due')),
            ('ring', 'in', list(CUSTOMER_RINGS)),
            ('notified_at', '=', False),
            ('rollout_id.state', 'in', ('rehearsing', 'running', 'waiting')),
        ])
        sent = 0
        brand = common.brand(self.env)
        for task in tasks:
            t = task.tenant_id
            if not t:
                continue
            tz, start, hours = self._task_window(task)
            opens, closes = window_bounds(now, tz, start, hours)
            if not task.run_now and opens > horizon:
                continue
            try:
                payload = notice_for('pre', brand)
                self.notice_send([t.id], payload['kind'], payload['text'],
                                 opens.strftime('%Y-%m-%d %H:%M:%S'),
                                 closes.strftime('%Y-%m-%d %H:%M:%S'))
            except Exception:                                # noqa: BLE001
                _logger.warning("biz_tenants: could not warn %s", t.slug,
                                exc_info=True)
                continue
            task.write({'notified_at': now, 'window_start': opens,
                        'window_end': closes})
            task.rollout_id.log_line(
                "%s told their people the update is coming — %s."
                % (task.label, say_window(to_local(opens, tz),
                                          to_local(closes, tz),
                                          to_local(now, tz), tz)))
            sent += 1
            self.env.cr.commit()
        return sent

    @api.model
    def _cron_rollout_worker(self):
        """Every five minutes: one step of whatever a PERSON started.

        Does nothing at all when nobody has started anything, which is most of
        the time and is exactly the point.
        """
        rollout = self._current_rollout()
        if not rollout:
            return False
        self._rollout_tick(rollout)
        self.env.cr.commit()
        return True

    # =====================================================================
    #  THE CONTROLS — every one of them says what it will do
    # =====================================================================
    def _get_rollout(self, rollout_id):
        r = self.env['biz.rollout'].sudo().browse(int(rollout_id)).exists()
        if not r:
            raise UserError(self.env._("That rollout is not there any more."))
        return r

    @api.model
    def rollout_pause(self, rollout_id, reason=''):
        self._require_platform_admin()
        r = self._get_rollout(rollout_id)
        if r.state not in ('rehearsing', 'running', 'waiting'):
            raise UserError(self.env._("It is not running."))
        self._pause(r, (reason or '').strip()
                    or "%s stopped it by hand." % self.env.user.name)
        return self.rollout_state()

    @api.model
    def rollout_resume(self, rollout_id):
        """Carry on. A failed step has to be dealt with first, BY NAME."""
        self._require_platform_admin()
        r = self._get_rollout(rollout_id)
        if r.state != 'paused':
            raise UserError(self.env._("It is not stopped."))
        stuck = r.task_ids.filtered(lambda t: t.state == 'failed')
        if stuck:
            raise UserError(self.env._(
                "%(who)s is still marked failed. Try it again, or leave it "
                "behind, before carrying on — carrying on around a failure is "
                "how a customer gets forgotten.", who=stuck[0].label))
        r.sudo().write({'state': 'running', 'note': False})
        r.log_line("%s carried on with it." % self.env.user.name)
        self._rollout_tick(r)
        return self.rollout_state()

    @api.model
    def rollout_continue_now(self, rollout_id):
        """End the watch period early, on purpose, with a name against it."""
        self._require_platform_admin()
        r = self._get_rollout(rollout_id)
        if r.state != 'waiting':
            raise UserError(self.env._("Nothing is being watched right now."))
        r.sudo().write({'watch_skipped': True, 'state': 'running'})
        r.log_line("%s ended the watch period on %s early."
                   % (self.env.user.name, RING_LABEL.get(r.ring, r.ring)))
        self._rollout_tick(r)
        return self.rollout_state()

    def _get_task(self, task_id):
        t = self.env['biz.rollout.task'].sudo().browse(int(task_id)).exists()
        if not t:
            raise UserError(self.env._("That step is not there any more."))
        return t

    @api.model
    def task_retry(self, task_id):
        self._require_platform_admin()
        task = self._get_task(task_id)
        if task.state not in ('failed', 'skipped'):
            raise UserError(self.env._("That step has not failed."))
        task.write({'state': 'waiting', 'error': False})
        task.rollout_id.log_line("%s put %s back in the queue."
                                 % (self.env.user.name, task.label))
        if task.rollout_id.state == 'paused':
            task.rollout_id.sudo().write({'state': 'running', 'note': False})
        self._rollout_tick(task.rollout_id)
        return self.rollout_state()

    @api.model
    def task_skip(self, task_id, confirm=''):
        """Leave one system behind. A CUSTOMER HAS TO BE NAMED to do it."""
        self._require_platform_admin()
        task = self._get_task(task_id)
        if task.state in ('done', 'skipped'):
            raise UserError(self.env._("There is nothing to leave behind."))
        if task.tenant_id and (confirm or '').strip().lower() != task.tenant_id.slug:
            raise UserError(self.env._(
                'Type "%s" to leave this customer behind. They stay on the old '
                'release until somebody brings them in step on their own.',
                task.tenant_id.slug))
        task.write({'state': 'skipped'})
        task.rollout_id.log_line(
            "%s left %s behind — it stays on the old release."
            % (self.env.user.name, task.label), 'warn')
        if task.rollout_id.state == 'paused':
            task.rollout_id.sudo().write({'state': 'running', 'note': False})
        self._rollout_tick(task.rollout_id)
        return self.rollout_state()

    @api.model
    def task_run_now(self, task_id):
        """Do not wait for their night. Recorded, because somebody chose it.

        ⚠ IT SKIPS THE WINDOW, NOT THE QUEUE (ledger F30). The order of the
        rings is the whole safety argument of a rollout, so a customer in a
        LATER ring cannot be pulled forward with this. `advance()` only ever
        looks at the current ring, so setting the flag on a later one would do
        nothing at all — silently — which is why this is a refusal BY NAME that
        points at the button that does what the person actually meant.
        """
        self._require_platform_admin()
        task = self._get_task(task_id)
        if task.state not in ('waiting', 'due'):
            raise UserError(self.env._("That step is not waiting."))
        if task.ring != task.rollout_id.ring:
            raise UserError(self.env._(
                "%(who)s is in a later ring (%(ring)s), and the rings happen in "
                "order — that is what makes a rollout safe. To get there "
                "sooner, end the watch period on the %(now)s with \"Continue "
                "now\".",
                who=task.label,
                ring=RING_LABEL.get(task.ring, task.ring),
                now=RING_LABEL.get(task.rollout_id.ring, '').lower()))
        task.write({'run_now': True, 'run_now_by': self.env.uid,
                    'state': 'due'})
        task.rollout_id.log_line(
            "%s asked for %s to be updated now rather than in their own window."
            % (self.env.user.name, task.label), 'warn')
        self._rollout_tick(task.rollout_id)
        return self.rollout_state()

    @api.model
    def rollout_abort(self, rollout_id, confirm=''):
        """Call the whole thing off. Everything not yet done is left behind.

        ⚠ A PAUSED ROLLOUT MUST BE CALLED OFF RATHER THAN LEFT LYING ABOUT
        (ledger F51). The practice copy is a shared resource with ONE name, so
        a rollout started later would restore over the same one.
        """
        self._require_platform_admin()
        r = self._get_rollout(rollout_id)
        if r.state in ('done', 'aborted'):
            raise UserError(self.env._("It is already over."))
        if (confirm or '').strip() != r.release_id.name:
            raise UserError(self.env._(
                'Type "%s" to call this rollout off.', r.release_id.name))
        left = r.task_ids.filtered(
            lambda t: t.state in ('waiting', 'due', 'failed'))
        left.write({'state': 'skipped'})
        r.sudo().write({'state': 'aborted',
                        'finished_at': fields.Datetime.now(),
                        'note': "%s called it off." % self.env.user.name})
        r.log_line("%s called it off — %d systems left on the old release."
                   % (self.env.user.name, len(left)), 'warn')
        return self.rollout_state()

    # =====================================================================
    #  THE SCREEN
    # =====================================================================
    @api.model
    def rollout_state(self):
        """Everything the rollout screen draws. Read-only, cheap enough to poll.

        WHAT "CURRENT" MEANS, AND WHY IT IS NOT "STILL RUNNING". A rollout that
        has just finished is the thing the person watching it most wants to see
        — "Release X is on 1 of 1 customers, and it took fourteen minutes."
        Scoping this to unfinished rollouts made the whole panel vanish the
        second the last ring landed, and the screen went back to inviting them
        to roll out a release they had just rolled out.
        """
        self._require_platform_admin()
        R = self.env['biz.rollout'].sudo()
        rel = self.env['biz.release'].sudo().current()
        current = R.search(
            [('state', 'in', ('draft', 'rehearsing', 'running', 'waiting',
                              'paused'))], order='id desc', limit=1)
        if not current and rel:
            current = R.search([('release_id', '=', rel.id)],
                               order='id desc', limit=1)
        past = R.search([('id', '!=', current.id or 0),
                         ('state', 'in', ('done', 'aborted'))], limit=8)
        return {
            'current': self._rollout_brief(current) if current else None,
            'past': [{
                'id': p.id, 'release': p.release_id.name, 'state': p.state,
                'when': (p.finished_at or p.create_date).isoformat(
                    sep=' ', timespec='minutes'),
                'minutes': self._rollout_minutes(p),
                'done': p.done_count, 'total': p.task_count,
            } for p in past],
            'release': ({'id': rel.id, 'name': rel.name,
                         'notes': rel.notes or '',
                         'cut_on': self._stamp(rel.cut_on)} if rel else None),
            'ring_order': list(RING_ORDER),
            'ring_label': dict(RING_LABEL),
            'ring_meaning': dict(RING_MEANING),
            'customer_rings': list(CUSTOMER_RINGS),
            'blockers': (self._rollout_blockers(rel, [], self._plan_for(rel))
                         if rel and not current else []),
        }

    @staticmethod
    def _rollout_minutes(r):
        if not r.started_at:
            return 0
        end = r.finished_at or fields.Datetime.now()
        return max(0, int((end - r.started_at).total_seconds() // 60))

    def _rollout_brief(self, r):
        now = fields.Datetime.now()
        rings = []
        for ring in RING_ORDER:
            tasks = r.task_ids.filtered(lambda t, ring=ring: t.ring == ring)
            if not tasks:
                continue
            rings.append({
                'ring': ring, 'label': RING_LABEL[ring],
                'meaning': RING_MEANING[ring],
                'active': r.ring == ring and r.state != 'done',
                'passed': (RING_ORDER.index(ring)
                           < RING_ORDER.index(r.ring or 'rehearsal')),
                'tasks': [self._task_brief(t) for t in tasks],
            })
        watch = watch_hours_for(r.ring, {'canary': r.watch_hours_canary,
                                         'early': r.watch_hours_early})
        watch_until = None
        if r.state == 'waiting' and r.ring_done_at and watch and not r.watch_skipped:
            watch_until = r.ring_done_at + timedelta(hours=watch)
        upcoming = [t.window_start for t in r.task_ids
                    if t.state in ('waiting', 'due') and t.window_start]
        next_at = min(upcoming) if upcoming else None
        return {
            'id': r.id, 'release': r.release_id.name,
            'notes': r.release_id.notes or '',
            'state': r.state,
            'state_label': dict(r._fields['state'].selection).get(r.state,
                                                                  r.state),
            'ring': r.ring,
            'ring_label': RING_LABEL.get(r.ring, ''),
            'note': r.note or '',
            'started_at': r.started_at and r.started_at.isoformat(
                sep=' ', timespec='minutes'),
            'finished_at': r.finished_at and r.finished_at.isoformat(
                sep=' ', timespec='minutes'),
            'minutes': self._rollout_minutes(r),
            'started_by': r.started_by.name or '',
            'rings': rings,
            'task_count': r.task_count, 'done_count': r.done_count,
            'failed_count': r.failed_count, 'queued_count': r.queued_count,
            'customer_total': r.customer_total,
            'customer_done': r.customer_done,
            'watch_hours': watch,
            'watch_until': watch_until and watch_until.isoformat(
                sep=' ', timespec='minutes'),
            'watch_left_h': (max(0, round((watch_until - now).total_seconds()
                                          / 3600, 1)) if watch_until else 0),
            'watch_skipped': r.watch_skipped,
            'next_at': next_at and next_at.isoformat(sep=' ',
                                                     timespec='minutes'),
            'log': r.log_rows()[-60:],
        }

    def _task_brief(self, t):
        health = t.health_dict()
        res = t.result_dict()
        tz = t.tenant_id and (t.tenant_id.tz or DEFAULT_TZ) or ''
        when = ''
        if t.window_start and t.state in ('waiting', 'due'):
            when = say_window(to_local(t.window_start, tz),
                              to_local(t.window_end, tz),
                              to_local(fields.Datetime.now(), tz), tz)
        return {
            'id': t.id, 'ring': t.ring, 'label': t.label,
            'target_db': t.target_db, 'state': t.state,
            'tenant_id': t.tenant_id.id or 0,
            'slug': t.tenant_id.slug or '',
            'initial': (t.label or '?')[0].upper(),
            'run_now': t.run_now,
            'tz': tz,
            'when': when,
            'notified_at': t.notified_at and t.notified_at.isoformat(
                sep=' ', timespec='minutes'),
            'window_start': t.window_start and t.window_start.isoformat(
                sep=' ', timespec='minutes'),
            'started_at': t.started_at and t.started_at.isoformat(
                sep=' ', timespec='minutes'),
            'finished_at': t.finished_at and t.finished_at.isoformat(
                sep=' ', timespec='minutes'),
            'duration_s': t.duration_s, 'attempts': t.attempts,
            'error': t.error or '',
            'health_ok': health.get('ok'),
            'health_reason': health.get('reason', ''),
            'health': health,
            'ignored_count': t.ignored_count or 0,
            'added': len(res.get('installed') or []),
            'updated': len(res.get('updated') or []),
            'skipped_count': res.get('skipped_count', -1),
        }

    # =====================================================================
    #  ONE CUSTOMER'S OWN UPDATE SETTINGS
    # =====================================================================
    @api.model
    def tenant_updates(self, tenant_id):
        """One customer's ring, window and history of updates. Read-only."""
        self._require_platform_admin()
        t = self._tenants().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(self.env._("That customer is not on the list."))
        now = fields.Datetime.now()
        tz = self._tenant_tz(t)
        opens, closes = window_bounds(
            now, tz, t.maintenance_start or DEFAULT_START_HOUR,
            t.maintenance_hours or DEFAULT_HOURS)
        tasks = self.env['biz.rollout.task'].sudo().search(
            [('tenant_id', '=', t.id)], order='id desc', limit=40)
        return {
            'id': t.id, 'name': t.name, 'slug': t.slug,
            'ring': t.ring, 'ring_label': RING_LABEL.get(t.ring, ''),
            'rings': [{'key': r, 'label': RING_LABEL[r],
                       'meaning': RING_MEANING[r]} for r in CUSTOMER_RINGS],
            'maintenance_start': t.maintenance_start or DEFAULT_START_HOUR,
            'maintenance_hours': t.maintenance_hours or DEFAULT_HOURS,
            'tz': tz,
            'next_window': say_window(to_local(opens, tz), to_local(closes, tz),
                                      to_local(now, tz), tz),
            'next_window_at': opens.isoformat(sep=' ', timespec='minutes'),
            'release': t.release_id.name or '',
            'release_state': t.release_state,
            'linked': self._tenancy_installed(t.slug),
            'history': [{
                **self._task_brief(task),
                'rollout_id': task.rollout_id.id,
                'release': task.rollout_id.release_id.name,
                'rollout_state': task.rollout_id.state,
            } for task in tasks],
        }

    @api.model
    def tenant_set_window(self, tenant_id, ring=None, start_hour=None,
                          hours=None):
        """Which ring this customer is in, and when their night is.

        ⚠ THE OPERATOR TYPES AN HOUR IN THE CUSTOMER'S CLOCK, NOT THEIR OWN
        (ledger F17, the other direction). The field is an HOUR and the zone is
        named beside it, which is the only shape of this that cannot be
        misread — a moment typed here would be the operator's moment and would
        land somewhere else entirely for the customer.
        """
        self._require_platform_admin()
        t = self._tenants().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(self.env._("That customer is not on the list."))
        vals = {}
        if ring is not None:
            if ring not in CUSTOMER_RINGS:
                raise UserError(self.env._("That is not one of the rings."))
            vals['ring'] = ring
        if start_hour is not None:
            h = int(start_hour)
            if not 0 <= h <= 23:
                raise UserError(self.env._(
                    "The hour has to be between 0 and 23."))
            vals['maintenance_start'] = h
        if hours is not None:
            n = int(hours)
            if not 1 <= n <= 12:
                raise UserError(self.env._(
                    "A window between 1 and 12 hours, please — longer than "
                    "that is not a window."))
            vals['maintenance_hours'] = n
        if vals:
            t.write(vals)
            t.log("Update settings changed: %s, %02d:00 for %s hours (%s)."
                  % (RING_LABEL.get(t.ring, t.ring), t.maintenance_start,
                     t.maintenance_hours, self._tenant_tz(t)))
        return self.tenant_updates(t.id)
