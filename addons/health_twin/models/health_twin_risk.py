# -*- coding: utf-8 -*-
"""``health.twin.risk`` — one deterioration-risk snapshot per patient.

Engine-maintained, overwritten on recompute (NO history this phase). The
composite score + band + factor breakdown are derived by the transparent
kernel in ``twin_score`` from the shipped telemonitoring signals (current
NEWS2 band, open deterioration alerts, open trend alerts, visit recency).
No ML, no LLM (report FB-064).

Writes are sudo + engine-only; users get read-only, catchment-scoped access
(security/). The row is a snapshot, not evidence — but it is still not
user-editable, so write()/unlink() carry an engine/admin-only guard cloned
from ``health.ews.score``.
"""
import json
import logging
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import twin_config
from . import twin_score

_logger = logging.getLogger(__name__)

# Completed-visit states (handover §1, verified FSO pattern at :3770).
_COMPLETED_STATES = ('completed', 'completed_pending_invoice', 'closed')
# Sentinel "days since last visit" when the client has no completed visit —
# large but kept low-weight by the staleness weight so it never dominates.
_NO_VISIT_SENTINEL = 999


class HealthTwinRisk(models.Model):
    _name = 'health.twin.risk'
    _description = 'Deterioration Risk Snapshot'
    _order = 'composite_score desc, id desc'
    _rec_names_search = ['patient_id.name']

    display_name = fields.Char(compute='_compute_display_name')

    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, index=True,
        ondelete='cascade', domain=[('is_patient', '=', True)])

    composite_score = fields.Integer(
        string='Risk Score', index=True,
        help='Composite 0-100 deterioration-risk score (weighted average of '
             'the NEWS2, alert, trend and staleness components).')
    risk_band = fields.Selection([
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Risk Band', index=True)

    # --- Factor snapshot (the transparent breakdown the worklist shows) ---
    news2_total = fields.Integer(string='NEWS2 Total')
    news2_band = fields.Char(
        string='NEWS2 Band',
        help='The current NEWS2 band code snapshotted at recompute time.')
    news2_at = fields.Datetime(string='NEWS2 Time')
    ews_score_id = fields.Many2one(
        'health.ews.score', string='Latest NEWS2', ondelete='set null')

    open_alert_count = fields.Integer(string='Open Alerts')
    open_critical_count = fields.Integer(string='Open Critical')
    trend_alert_count = fields.Integer(string='Open Trend Alerts')

    days_since_last_visit = fields.Integer(string='Days Since Last Visit')
    last_visit_at = fields.Datetime(string='Last Completed Visit')

    # Per-component 0-100 point values (the "contribution" the form shows
    # alongside each factor — snapshot, kept for the plain breakdown).
    news2_points = fields.Integer(string='NEWS2 Points')
    alert_points = fields.Integer(string='Alert Points')
    trend_points = fields.Integer(string='Trend Points')
    staleness_points = fields.Integer(string='Staleness Points')

    factors_json = fields.Text(
        string='Factors (machine)',
        help='Full machine breakdown (components + weights + raw inputs) for '
             'auditability/debugging.')
    computed_at = fields.Datetime(string='Computed At', index=True)

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # ------------------------------------------------------------------
    # DB uniqueness (§5.1 — _sql_constraints are not materialized)
    # ------------------------------------------------------------------
    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_twin_risk_patient_uniq
            ON health_twin_risk (patient_id)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('patient_id.name', 'composite_score', 'risk_band')
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
    # Engine/admin-only write + unlink (clone of health.ews.score shape).
    # The engine writes via sudo (env.su True); end users get read-only.
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
                'Deterioration risk snapshots are system-generated and '
                'cannot be edited.'))
        return super().write(vals)

    def unlink(self):
        if not self._engine_or_admin():
            raise UserError(_(
                'Deterioration risk snapshots are system-generated and '
                'cannot be deleted.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Smart buttons (form header — handover §2.4)
    # ------------------------------------------------------------------
    def action_open_patient(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Patient'),
            'res_model': 'res.partner',
            'res_id': self.patient_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_alerts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Open Alerts'),
            'res_model': 'health.monitor.alert',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.patient_id.id),
                       ('state', 'in', ('new', 'acknowledged'))],
            'context': {'search_default_open': 1},
            'target': 'current',
        }

    def action_open_news2(self):
        self.ensure_one()
        if not self.ews_score_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Latest NEWS2'),
            'res_model': 'health.ews.score',
            'res_id': self.ews_score_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ==================================================================
    # Recompute engine (handover §2.3) — sudo, engine-only.
    # ==================================================================
    def _recompute_for_patients(self, patients):
        """Upsert the single risk row for each of `patients`, deriving the
        four components from the shipped signals in BULK (read_group / search,
        never per-patient queries in a loop). Each patient's body runs in its
        own savepoint so one bad patient can't abort the batch."""
        env = self.env
        if not twin_config.get_bool(env, 'twin_enabled', True):
            return
        patients = patients.filtered('is_patient') if patients else patients
        if not patients:
            return

        cfg = self._load_config()
        signals = self._gather_signals(patients.ids)

        for patient in patients:
            try:
                with env.cr.savepoint():
                    self._upsert_one(patient, cfg, signals)
            except Exception as exc:  # noqa: BLE001 — one bad patient survives
                _logger.warning(
                    'Twin recompute: patient %s failed: %s', patient.id, exc)

    def _load_config(self):
        env = self.env
        gf, gi = twin_config.get_float, twin_config.get_int
        return {
            'weights': {
                'news2': gf(env, 'w_news2', 0.5),
                'alert': gf(env, 'w_alert', 0.35),
                'trend': gf(env, 'w_trend', 0.1),
                'staleness': gf(env, 'w_staleness', 0.05),
            },
            'thresholds': {
                'moderate': gi(env, 'band_moderate', 25),
                'high': gi(env, 'band_high', 50),
                'critical': gi(env, 'band_critical', 75),
            },
            'decay_hours': gf(env, 'news2_decay_hours', 336.0),
            'staleness_threshold': gi(env, 'staleness_threshold_days', 10),
        }

    def _gather_signals(self, ids):
        """Bulk-load every signal for the given patient ids into dicts keyed
        by patient id (handover §2.3 step 3)."""
        env = self.env
        # Current (non-superseded) NEWS2 per client — latest wins on the
        # (theoretically impossible) chance of duplicates.
        Score = env['health.ews.score'].sudo()
        score_by = {}
        scores = Score.search([('client_id', 'in', ids),
                               ('superseded', '=', False)])
        for s in scores.sorted(key=lambda r: (r.score_datetime or
                                              fields.Datetime.now(), r.id)):
            score_by[s.client_id.id] = s

        # Open alert counts by (client, severity) + open trend counts.
        Alert = env['health.monitor.alert'].sudo()
        open_dom = [('client_id', 'in', ids),
                    ('state', 'in', ('new', 'acknowledged'))]
        crit_by = defaultdict(int)
        warn_by = defaultdict(int)
        open_by = defaultdict(int)
        for client, severity, count in Alert._read_group(
                open_dom, ['client_id', 'severity'], ['__count']):
            if not client:
                continue
            open_by[client.id] += count
            if severity == 'critical':
                crit_by[client.id] += count
            elif severity == 'warning':
                warn_by[client.id] += count
        trend_by = {}
        for client, count in Alert._read_group(
                open_dom + [('rule', 'like', 'trend_%')],
                ['client_id'], ['__count']):
            if client:
                trend_by[client.id] = count

        # Last completed visit datetime per client.
        FSO = env['health.fieldservice.order'].sudo()
        last_visit_by = {}
        for patient, last in FSO._read_group(
                [('patient_id', 'in', ids),
                 ('state', 'in', _COMPLETED_STATES)],
                ['patient_id'], ['scheduled_datetime:max']):
            if patient:
                last_visit_by[patient.id] = last

        return {
            'score_by': score_by, 'crit_by': crit_by, 'warn_by': warn_by,
            'open_by': open_by, 'trend_by': trend_by,
            'last_visit_by': last_visit_by,
        }

    def _upsert_one(self, patient, cfg, signals):
        env = self.env
        now = fields.Datetime.now()
        pid = patient.id

        score = signals['score_by'].get(pid)
        band_code = score.band if score else ''
        news2_total = score.total if score else 0
        news2_at = score.score_datetime if score else False
        if score and score.score_datetime:
            age_hours = max(
                0.0, (now - score.score_datetime).total_seconds() / 3600.0)
        else:
            age_hours = 0.0

        crit = signals['crit_by'].get(pid, 0)
        warn = signals['warn_by'].get(pid, 0)
        open_total = signals['open_by'].get(pid, 0)
        trend = signals['trend_by'].get(pid, 0)

        last_visit = signals['last_visit_by'].get(pid)
        if last_visit:
            days = max(0, (now - last_visit).days)
        else:
            days = _NO_VISIT_SENTINEL

        components = {
            'news2': twin_score.news2_component(
                band_code, age_hours, cfg['decay_hours']),
            'alert': twin_score.alert_component(crit, warn),
            'trend': twin_score.trend_component(trend),
            'staleness': twin_score.staleness_component(
                days, cfg['staleness_threshold']),
        }
        score_val = twin_score.composite(components, cfg['weights'])
        band = twin_score.band_for(score_val, cfg['thresholds'])

        factors = {
            'components': {k: round(v, 2) for k, v in components.items()},
            'weights': cfg['weights'],
            'raw': {
                'news2_band': band_code or '',
                'news2_total': news2_total,
                'news2_age_hours': round(age_hours, 2),
                'open_critical': crit,
                'open_warning': warn,
                'open_alerts': open_total,
                'open_trend': trend,
                'days_since_last_visit': days,
            },
        }

        vals = {
            'patient_id': pid,
            'composite_score': score_val,
            'risk_band': band,
            'news2_total': news2_total,
            'news2_band': band_code or '',
            'news2_at': news2_at,
            'ews_score_id': score.id if score else False,
            'open_alert_count': open_total,
            'open_critical_count': crit,
            'trend_alert_count': trend,
            'days_since_last_visit': days,
            'last_visit_at': last_visit or False,
            'news2_points': int(round(components['news2'])),
            'alert_points': int(round(components['alert'])),
            'trend_points': int(round(components['trend'])),
            'staleness_points': int(round(components['staleness'])),
            'factors_json': json.dumps(factors, sort_keys=True),
            'computed_at': now,
        }
        existing = self.sudo().search([('patient_id', '=', pid)], limit=1)
        if existing:
            existing.write(vals)
            return existing
        return self.sudo().create(vals)

    # ------------------------------------------------------------------
    # Cron sweep (handover §2.3)
    # ------------------------------------------------------------------
    @api.model
    def cron_twin_sweep(self):
        env = self.env
        if not twin_config.get_bool(env, 'twin_sweep_enabled', True):
            _logger.info('Twin sweep: disabled (config param off).')
            return True
        horizon = twin_config.get_int(env, 'twin_stale_horizon_days', 30)
        cap = twin_config.get_int(env, 'twin_sweep_batch_cap', 500)
        now = fields.Datetime.now()

        Score = env['health.ews.score'].sudo()
        Alert = env['health.monitor.alert'].sudo()
        FSO = env['health.fieldservice.order'].sudo()

        cand = set()
        for client, _c in Score._read_group(
                [('superseded', '=', False)], ['client_id'], ['__count']):
            if client:
                cand.add(client.id)
        for client, _c in Alert._read_group(
                [('state', 'in', ('new', 'acknowledged'))],
                ['client_id'], ['__count']):
            if client:
                cand.add(client.id)
        for patient, _c in FSO._read_group(
                [('state', 'in', _COMPLETED_STATES),
                 ('scheduled_datetime', '>=', now - timedelta(days=horizon))],
                ['patient_id'], ['__count']):
            if patient:
                cand.add(patient.id)

        candidates = env['res.partner'].sudo().browse(
            sorted(cand)).filtered('is_patient')
        total = len(candidates)
        if total > cap:
            _logger.info(
                'Twin sweep: %s candidates, capping at %s (dropped %s).',
                total, cap, total - cap)
            candidates = candidates[:cap]

        self.sudo()._recompute_for_patients(candidates)
        pruned = self.sudo()._prune_empty()
        _logger.info('Twin sweep: recomputed=%s pruned=%s',
                     len(candidates), pruned)
        return True

    def _prune_empty(self):
        """Delete zero-score snapshots to keep the worklist clean. A
        composite of 0 means every component was 0 (no live NEWS2, no open
        alert, no open trend, not stale enough to register), so the row
        carries no triage value (handover §2.3 — optional prune)."""
        rows = self.sudo().search([('composite_score', '=', 0)])
        count = len(rows)
        if rows:
            rows.unlink()
        return count
