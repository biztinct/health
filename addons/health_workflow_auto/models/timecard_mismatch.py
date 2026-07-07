import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# Reconciliation threshold and orphan cutoff (spec E.4).
_GAP_THRESHOLD_MINUTES = 15
_ORPHAN_OPEN_HOURS = 16


class HealthTimecardMismatch(models.Model):
    _name = 'health.timecard.mismatch'
    _description = 'Timecard Reconciliation Mismatch'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread']

    employee_id = fields.Many2one('hr.employee', required=True, index=True)
    date = fields.Date(index=True)
    fso_id = fields.Many2one('health.fieldservice.order', string='Field Service Order')
    attendance_id = fields.Many2one('hr.attendance', string='Attendance')
    kind = fields.Selection([
        ('start_gap', 'Start gap >15m'),
        ('end_gap', 'End gap >15m'),
        ('missing_attendance', 'Visit w/o attendance'),
        ('orphan_open', 'Attendance never closed'),
    ], required=True)
    delta_minutes = fields.Float(string='Delta (minutes)')
    state = fields.Selection([
        ('open', 'Open'), ('resolved', 'Resolved'),
    ], default='open', required=True, tracking=True)
    resolution = fields.Selection([
        ('keep_attendance', 'Keep attendance'),
        ('use_fso', 'Use visit times'),
    ])
    resolved_by = fields.Many2one('res.users', readonly=True)

    def init(self):
        # Idempotent guard: at most one OPEN mismatch per (employee, date, fso, kind)
        # so re-running the nightly cron does not duplicate rows (ledger §1/§3).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_timecard_mismatch_open_uidx
            ON health_timecard_mismatch (employee_id, date, fso_id, kind)
            WHERE state = 'open'
        """)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def action_resolve_keep(self):
        for rec in self:
            rec.write({
                'state': 'resolved', 'resolution': 'keep_attendance',
                'resolved_by': self.env.uid,
            })
            rec.message_post(body=_('Mismatch resolved: kept attendance times.'))
        return True

    def action_resolve_use_fso(self):
        """Rewrite the attendance with the FSO times and mark resolved."""
        for rec in self:
            att = rec.attendance_id
            fso = rec.fso_id
            if att and fso:
                vals = {}
                if fso.actual_start_datetime:
                    vals['check_in'] = fso.actual_start_datetime
                if fso.actual_end_datetime:
                    vals['check_out'] = fso.actual_end_datetime
                if vals:
                    try:
                        att.write(vals)
                    except Exception as exc:  # noqa: BLE001
                        _logger.warning('Timecard resolve: could not rewrite '
                                        'attendance %s: %s', att.id, exc)
                att.message_post(body=_(
                    'Attendance times rewritten from visit %s by %s.'
                ) % (fso.name or fso.id, self.env.user.name))
            rec.write({
                'state': 'resolved', 'resolution': 'use_fso',
                'resolved_by': self.env.uid,
            })
            rec.message_post(body=_('Mismatch resolved: used visit times.'))
        return True

    # ------------------------------------------------------------------
    # Nightly reconciliation
    # ------------------------------------------------------------------
    @api.model
    def _record_mismatch(self, vals):
        """Create a mismatch unless an identical OPEN one already exists."""
        existing = self.search([
            ('employee_id', '=', vals['employee_id']),
            ('date', '=', vals.get('date')),
            ('fso_id', '=', vals.get('fso_id', False)),
            ('kind', '=', vals['kind']),
            ('state', '=', 'open'),
        ], limit=1)
        if existing:
            return existing
        return self.create(vals)

    @api.model
    def cron_reconcile_timecards(self, for_date=None):
        """Nightly — reconcile PWA-visit attendances against their FSOs.

        Payroll truth = hr.attendance; only mismatches surface for a human.
        Matches flow silently into pb_hr_workforce timecards/OT.
        """
        if for_date is None:
            for_date = fields.Date.today() - timedelta(days=1)
        elif isinstance(for_date, str):
            for_date = fields.Date.to_date(for_date)

        day_start = fields.Datetime.to_datetime(for_date)
        day_end = day_start + timedelta(days=1)
        threshold = timedelta(minutes=_GAP_THRESHOLD_MINUTES)

        Attendance = self.env['hr.attendance']

        # 1) start_gap / end_gap on pwa_visit attendances vs their FSO.
        pwa_atts = Attendance.search([
            ('attendance_source', '=', 'pwa_visit'),
            ('check_in', '>=', day_start),
            ('check_in', '<', day_end),
            ('fso_id', '!=', False),
        ])
        for att in pwa_atts:
            fso = att.fso_id
            if fso.actual_start_datetime and att.check_in:
                delta = abs((att.check_in - fso.actual_start_datetime).total_seconds())
                if delta > threshold.total_seconds():
                    self._record_mismatch({
                        'employee_id': att.employee_id.id,
                        'date': for_date,
                        'fso_id': fso.id,
                        'attendance_id': att.id,
                        'kind': 'start_gap',
                        'delta_minutes': round(delta / 60.0, 1),
                    })
            if att.check_out and fso.actual_end_datetime:
                delta = abs((att.check_out - fso.actual_end_datetime).total_seconds())
                if delta > threshold.total_seconds():
                    self._record_mismatch({
                        'employee_id': att.employee_id.id,
                        'date': for_date,
                        'fso_id': fso.id,
                        'attendance_id': att.id,
                        'kind': 'end_gap',
                        'delta_minutes': round(delta / 60.0, 1),
                    })

        # 2) FSOs completed on for_date whose staff have no overlapping attendance.
        fsos = self.env['health.fieldservice.order'].search([
            ('state', 'in', ('completed', 'completed_pending_invoice')),
            ('actual_end_datetime', '>=', day_start),
            ('actual_end_datetime', '<', day_end),
        ])
        for fso in fsos:
            for emp in fso._visit_employees():
                overlap = Attendance.search_count([
                    ('employee_id', '=', emp.id),
                    ('check_in', '<=', fso.actual_end_datetime or day_end),
                    '|', ('check_out', '=', False),
                    ('check_out', '>=', fso.actual_start_datetime or day_start),
                ])
                if not overlap:
                    self._record_mismatch({
                        'employee_id': emp.id,
                        'date': for_date,
                        'fso_id': fso.id,
                        'kind': 'missing_attendance',
                    })

        # 3) orphan_open: pwa_visit attendances open longer than 16h — auto-close
        #    at the FSO actual_end_datetime and flag.
        cutoff = fields.Datetime.now() - timedelta(hours=_ORPHAN_OPEN_HOURS)
        orphans = Attendance.search([
            ('attendance_source', '=', 'pwa_visit'),
            ('check_out', '=', False),
            ('check_in', '<=', cutoff),
        ])
        for att in orphans:
            close_at = (att.fso_id.actual_end_datetime
                        or att.check_in + timedelta(hours=1))
            try:
                with self.env.cr.savepoint():
                    att.check_out = close_at
            except Exception as exc:  # noqa: BLE001
                _logger.warning('Timecard reconcile: could not auto-close orphan '
                                'attendance %s: %s', att.id, exc)
                continue
            self._record_mismatch({
                'employee_id': att.employee_id.id,
                'date': att.check_in.date(),
                'fso_id': att.fso_id.id if att.fso_id else False,
                'attendance_id': att.id,
                'kind': 'orphan_open',
            })
        return True
