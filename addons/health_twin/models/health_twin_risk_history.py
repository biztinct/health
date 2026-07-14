# -*- coding: utf-8 -*-
"""``health.twin.risk.history`` — append-only per-patient risk trajectory.

Phase 1 said WHICH patients are high-risk; Phase 2 charted their vitals; this
model answers "is this patient rising or falling?" by keeping a bounded trail
of the composite risk score over time (handover twin-phase3 §2.1). Points are
captured on recompute but ONLY at change-points (band flip / meaningful score
move) plus one daily heartbeat — never one-per-hook — so a busy patient does
not flood the table.

Writes are engine-sudo + append-only (unconditional guard, §5.4, cloned from
``health.twin.risk``); users get read-only, catchment-scoped access (security/).
This is OBSERVED history only — NO forecasting, NO ML, NO LLM.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import twin_config

_logger = logging.getLogger(__name__)


class HealthTwinRiskHistory(models.Model):
    _name = 'health.twin.risk.history'
    _description = 'Deterioration Risk History Point'
    _order = 'computed_at desc, id desc'
    _rec_name = 'patient_id'

    display_name = fields.Char(compute='_compute_display_name')

    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, index=True,
        ondelete='cascade', domain=[('is_patient', '=', True)])

    computed_at = fields.Datetime(
        string='Point Time', required=True, index=True,
        help='When this trajectory point was captured.')

    composite_score = fields.Integer(string='Risk Score', index=True)
    risk_band = fields.Selection([
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Risk Band')

    # Component snapshot for a rich trajectory (same 0-100 point values the
    # worklist form shows).
    news2_points = fields.Integer(string='NEWS2 Points')
    alert_points = fields.Integer(string='Alert Points')
    trend_points = fields.Integer(string='Trend Points')
    staleness_points = fields.Integer(string='Staleness Points')

    trigger = fields.Selection([
        ('band_change', 'Band change'),
        ('delta', 'Score move'),
        ('daily', 'Daily'),
        ('first', 'First'),
    ], string='Captured Because', index=True,
        help='Why this point was appended (audit/debugging).')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # ------------------------------------------------------------------
    # DB index (§5.1 — _sql_constraints are not materialized). NON-unique:
    # many points per patient; a plain composite index for the per-patient
    # time-ordered reads (last-point lookup + chart window query).
    # ------------------------------------------------------------------
    def init(self):
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS health_twin_risk_history_patient_time
            ON health_twin_risk_history (patient_id, computed_at)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('patient_id.name', 'composite_score', 'risk_band',
                 'computed_at')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                '%(name)s — risk %(score)s (%(band)s)',
                name=rec.patient_id.name or '',
                score=rec.composite_score,
                band=rec.risk_band or 'low')

    @api.depends('patient_id.catchment_province_id',
                 'patient_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.patient_id._get_health_catchment_province()
                if rec.patient_id else False)

    # ------------------------------------------------------------------
    # Append-only guard (unconditional, §5.4 — clone of health.twin.risk).
    # The engine appends via sudo; end users get read-only. History points
    # are a trajectory record: never edited, never hand-deleted (only the GC
    # cron prunes, and it runs as admin/su so the guard lets it through).
    # ------------------------------------------------------------------
    def _engine_or_admin(self):
        return (
            self.env.su
            or self.env.user._is_admin()
            or self.env.user.has_group('health_base.group_healthcare_admin')
            or self.env.user.has_group('health_base.group_healthcare_owner'))

    def write(self, vals):
        if not self._engine_or_admin():
            raise UserError(_(
                'Deterioration risk history is append-only and cannot be '
                'edited.'))
        return super().write(vals)

    def unlink(self):
        if not self._engine_or_admin():
            raise UserError(_(
                'Deterioration risk history is append-only and cannot be '
                'deleted.'))
        return super().unlink()

    # ==================================================================
    # Append logic (handover §2.3) — called sudo from _upsert_one.
    # ==================================================================
    @api.model
    def _maybe_append(self, patient_id, score, band, components,
                      prev_snapshot, now):
        """Append a trajectory point for `patient_id` IF it is a change-point
        or the once-a-day heartbeat; otherwise no-op (avoids flooding from the
        frequent hook recomputes).

        Decision keys off the patient's LAST history point (not the snapshot —
        `prev_snapshot` is accepted for interface fidelity with the handover
        but the last point is the source of truth):
          - no last point            → 'first'
          - band changed vs last     → 'band_change'
          - |score - last| >= min    → 'delta'
          - last point on an earlier calendar day (UTC) → 'daily'
          - else                     → do NOT append
        Returns the trigger code appended, or False when nothing was written.
        """
        env = self.env
        last = self.sudo().search(
            [('patient_id', '=', patient_id)], limit=1)  # _order desc → latest
        if not last:
            trigger = 'first'
        elif last.risk_band != band:
            trigger = 'band_change'
        elif abs(score - last.composite_score) >= twin_config.get_int(
                env, 'history_min_delta', 8):
            trigger = 'delta'
        elif last.computed_at and now and last.computed_at.date() < now.date():
            trigger = 'daily'
        else:
            return False

        self.sudo().create({
            'patient_id': patient_id,
            'computed_at': now,
            'composite_score': score,
            'risk_band': band,
            'news2_points': int(round(components.get('news2', 0))),
            'alert_points': int(round(components.get('alert', 0))),
            'trend_points': int(round(components.get('trend', 0))),
            'staleness_points': int(round(components.get('staleness', 0))),
            'trigger': trigger,
        })
        return trigger

    # ------------------------------------------------------------------
    # Retention GC (handover §2.6) — daily cron, config-gated.
    # ------------------------------------------------------------------
    @api.model
    def cron_twin_history_gc(self):
        env = self.env
        if not twin_config.get_bool(env, 'history_gc_enabled', True):
            _logger.info('Twin history GC: disabled (config param off).')
            return True
        days = twin_config.get_int(env, 'history_retention_days', 365)
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.sudo().search([('computed_at', '<', cutoff)])
        count = len(old)
        if old:
            old.unlink()
        _logger.info(
            'Twin history GC: pruned %s point(s) older than %sd.', count, days)
        return True
