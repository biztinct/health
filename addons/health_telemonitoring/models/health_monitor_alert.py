# -*- coding: utf-8 -*-
"""``health.monitor.alert`` — deterioration triage inbox.

Fed by (a) NEWS2 bands, (b) existing per-client threshold breaches
(mirrored, super() behaviour preserved), and (c) a nightly statistical
baseline/trend sweep (pure Python — no LLM). Alerts are created sudo by
the engine only; clinical groups triage them through the lifecycle
buttons (method gates enforce who may transition each state).
"""
import json
import logging
import statistics
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import tm_config

_logger = logging.getLogger(__name__)

# Trend sweep looks at these observation codes over the trailing window.
_TREND_CANDIDATE_CODES = ('hr', 'bp_sys', 'spo2', 'spo2_po', 'weight')


class HealthMonitorAlert(models.Model):
    _name = 'health.monitor.alert'
    _description = 'Deterioration Alert'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    client_id = fields.Many2one(
        'res.partner', string='Client', required=True, index=True,
        ondelete='restrict', domain=[('is_patient', '=', True)],
        tracking=True)
    order_id = fields.Many2one(
        'health.fieldservice.order', string='Visit', index=True,
        ondelete='set null')
    rule = fields.Selection([
        ('ews_high', 'NEWS2 high'),
        ('ews_medium', 'NEWS2 medium'),
        ('ews_single3', 'NEWS2 single-parameter 3'),
        ('threshold', 'Threshold breach'),
        ('trend_hr_drift', 'Resting HR drift'),
        ('trend_sbp_drift', 'Systolic BP drift'),
        ('trend_spo2_decline', 'SpO2 decline'),
        ('trend_weight_loss', 'Weight loss'),
    ], string='Rule', required=True, index=True)
    severity = fields.Selection([
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string='Severity', required=True, index=True, tracking=True)
    state = fields.Selection([
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ], string='Status', default='new', required=True, index=True,
        tracking=True)
    title = fields.Char(string='Title', required=True)
    body = fields.Text(string='Evidence')
    evidence_json = fields.Text(string='Evidence (machine)')

    vitals_type_id = fields.Many2one(
        'health.vitals.type', string='Vitals Type', ondelete='set null')
    ews_score_id = fields.Many2one(
        'health.ews.score', string='NEWS2 Score', ondelete='set null')
    observation_ids = fields.Many2many(
        'health.observation', string='Evidence observations')

    ack_user_id = fields.Many2one(
        'res.users', string='Acknowledged by', readonly=True)
    ack_date = fields.Datetime(string='Acknowledged on', readonly=True)
    closed_user_id = fields.Many2one(
        'res.users', string='Closed by', readonly=True)
    closed_date = fields.Datetime(string='Closed on', readonly=True)
    close_note = fields.Text(string='Closing note')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.client_id._get_health_catchment_province()
                if rec.client_id else False)

    # ------------------------------------------------------------------
    # Dedup helper (handover §2.7 — verbatim)
    # ------------------------------------------------------------------
    def _open_exists(self, client_id, rule, vitals_type_id=False):
        dom = [('client_id', '=', client_id), ('rule', '=', rule),
               ('state', 'in', ('new', 'acknowledged'))]
        if vitals_type_id:
            dom.append(('vitals_type_id', '=', vitals_type_id))
        return bool(self.search_count(dom))

    # ------------------------------------------------------------------
    # Raisers — engine-only (sudo). Each: dedup → create → escalate.
    # ------------------------------------------------------------------
    _BAND_LABELS = {
        'high': 'cao', 'medium': 'trung bình', 'low_medium': 'thấp-trung bình',
        'low': 'thấp',
    }

    def _raise_for_ews(self, score):
        band = score.band
        if band == 'high':
            rule, severity = 'ews_high', 'critical'
        elif band == 'medium':
            rule, severity = 'ews_medium', 'warning'
        elif band == 'low_medium':
            rule, severity = 'ews_single3', 'warning'
        else:
            return  # low band → no alert
        if self._open_exists(score.client_id.id, rule):
            return
        band_label = self._BAND_LABELS.get(band, band)
        title = _('NEWS2 %(total)s — %(band)s — %(name)s',
                  total=score.total, band=band_label,
                  name=score.client_id.name or '')
        body = _(
            'NEWS2 %(total)s (%(band)s)\n'
            '• Nhịp thở / RR: %(rr)s (điểm %(rr_s)s)\n'
            '• SpO₂: %(spo2)s (điểm %(spo2_s)s) — thang %(scale)s\n'
            '• Thở oxy / O₂: %(o2)s (điểm %(o2_s)s)\n'
            '• Huyết áp tâm thu / SBP: %(sbp)s (điểm %(bp_s)s)\n'
            '• Nhịp tim / HR: %(hr)s (điểm %(hr_s)s)\n'
            '• Nhiệt độ / Temp: %(temp)s (điểm %(temp_s)s)\n'
            '• Ý thức / ACVPU: %(acvpu)s (điểm %(cons_s)s)%(defaulted)s',
            total=score.total, band=band_label,
            rr=score.rr_value, rr_s=score.rr_score,
            spo2=score.spo2_value, spo2_s=score.spo2_score,
            scale=score.spo2_scale or '1',
            o2=_('có') if score.on_oxygen else _('không'),
            o2_s=score.o2_score,
            sbp=score.sbp_value, bp_s=score.bp_score,
            hr=score.hr_value, hr_s=score.hr_score,
            temp=score.temp_value, temp_s=score.temp_score,
            acvpu=score.acvpu_value or 'A', cons_s=score.consciousness_score,
            defaulted=_(' (ý thức mặc định A)')
            if score.defaulted_consciousness else '')
        alert = self.create({
            'client_id': score.client_id.id,
            'order_id': score.order_id.id or False,
            'rule': rule,
            'severity': severity,
            'title': title,
            'body': body,
            'ews_score_id': score.id,
            'observation_ids': [(6, 0, score.observation_ids.ids)],
        })
        alert._escalate_if_critical()
        return alert

    def _raise_for_threshold(self, observation, threshold):
        if self._open_exists(observation.client_id.id, 'threshold',
                             vitals_type_id=observation.vitals_type_id.id):
            return
        title = _('%(type)s %(value)s%(unit)s — %(sev)s — %(name)s',
                  type=observation.vitals_type_id.name,
                  value=observation.value_quantity,
                  unit=observation.vitals_type_id.unit_display or '',
                  sev=threshold.severity,
                  name=observation.client_id.name or '')
        body = _(
            'Ngưỡng cảnh báo bị vượt / Threshold breach\n'
            '• %(type)s: %(value)s%(unit)s\n'
            '• Ngưỡng / threshold: [%(min)s – %(max)s]\n'
            '• Mức độ / severity: %(sev)s',
            type=observation.vitals_type_id.name,
            value=observation.value_quantity,
            unit=observation.vitals_type_id.unit_display or '',
            min=threshold.min_value, max=threshold.max_value,
            sev=threshold.severity)
        alert = self.create({
            'client_id': observation.client_id.id,
            'order_id': observation.order_id.id or False,
            'rule': 'threshold',
            'severity': threshold.severity,
            'title': title,
            'body': body,
            'vitals_type_id': observation.vitals_type_id.id,
            'observation_ids': [(6, 0, observation.ids)],
        })
        # NOTE: threshold-mirror alerts deliberately do NOT self-escalate.
        # The base health_vitals threshold escalation (super() in
        # _escalate_threshold_breach) already schedules the activity for a
        # breach; a second one here would duplicate it and break
        # health_vitals' own test (non-goal: preserve threshold behaviour
        # bit-for-bit). NEWS2 and trend alerts escalate; threshold does not.
        return alert

    # ------------------------------------------------------------------
    # Escalation (handover §2.7)
    # ------------------------------------------------------------------
    def _escalate_if_critical(self):
        self.ensure_one()
        if self.severity != 'critical':
            return
        if not tm_config.get_bool(self.env, 'activity_on_critical', True):
            return
        try:
            user = self._facility_manager_user()
            if not user:
                _logger.warning(
                    'Deterioration alert %s: no facility manager user for '
                    'client %s, cannot create activity.',
                    self.id, self.client_id.name)
                return
            activity_type = self.env.ref(
                'mail.mail_activity_data_todo', raise_if_not_found=False)
            if not activity_type:
                _logger.warning('Todo activity type not found')
                return
            self.client_id.activity_schedule(
                activity_type_id=activity_type.id,
                summary=self.title,
                note=self.body or '',
                date_deadline=fields.Date.today() + timedelta(days=1),
                user_id=user.id)
        except Exception:  # noqa: BLE001 — alerting must never block capture
            _logger.exception(
                'Deterioration alert %s: escalation activity failed.',
                self.id)

    def _facility_manager_user(self):
        """Facility-manager fallback (clone of
        health.observation._get_facility_manager_user)."""
        self.ensure_one()
        facility = self.client_id.primary_facility_id
        manager = facility.facility_manager_id if facility else False
        return manager.user_id if manager and manager.user_id else False

    # ------------------------------------------------------------------
    # Lifecycle (group gates inside the method, ai_coding style)
    # ------------------------------------------------------------------
    _ACK_GROUPS = (
        'health_base.group_healthcare_nurse',
        'health_base.group_healthcare_head_nurse',
        'health_base.group_healthcare_doctor',
        'health_base.group_healthcare_operations_manager',
        'health_base.group_healthcare_manager',
        'health_base.group_healthcare_admin',
        'health_base.group_healthcare_owner',
    )
    _CLOSE_GROUPS = (
        'health_base.group_healthcare_head_nurse',
        'health_base.group_healthcare_doctor',
        'health_base.group_healthcare_manager',
        'health_base.group_healthcare_admin',
        'health_base.group_healthcare_owner',
    )

    def _check_groups(self, groups, message):
        if (self.env.su or self.env.user._is_admin()
                or any(self.env.user.has_group(g) for g in groups)):
            return
        raise UserError(message)

    def action_acknowledge(self):
        self._check_groups(
            self._ACK_GROUPS,
            _('You are not allowed to acknowledge deterioration alerts.'))
        for rec in self:
            if rec.state != 'new':
                raise UserError(_(
                    'Only a new alert can be acknowledged.'))
        self.sudo().write({
            'state': 'acknowledged',
            'ack_user_id': self.env.uid,
            'ack_date': fields.Datetime.now(),
        })
        return True

    def action_resolve(self):
        self._check_groups(
            self._CLOSE_GROUPS,
            _('Only a head nurse, doctor, or manager may resolve alerts.'))
        for rec in self:
            if rec.state not in ('new', 'acknowledged'):
                raise UserError(_(
                    'Only an open alert can be resolved.'))
        self.sudo().write({
            'state': 'resolved',
            'closed_user_id': self.env.uid,
            'closed_date': fields.Datetime.now(),
        })
        return True

    def action_dismiss(self):
        self._check_groups(
            self._CLOSE_GROUPS,
            _('Only a head nurse, doctor, or manager may dismiss alerts.'))
        for rec in self:
            if rec.state not in ('new', 'acknowledged'):
                raise UserError(_(
                    'Only an open alert can be dismissed.'))
            if not (rec.close_note and rec.close_note.strip()):
                raise UserError(_(
                    'A closing note is required to dismiss an alert.'))
        self.sudo().write({
            'state': 'dismissed',
            'closed_user_id': self.env.uid,
            'closed_date': fields.Datetime.now(),
        })
        return True

    # ------------------------------------------------------------------
    # Nightly trend sweep (handover §2.8)
    # ------------------------------------------------------------------
    @api.model
    def cron_trend_sweep(self):
        if not tm_config.get_bool(self.env, 'trend_enabled', True):
            _logger.info('Trend sweep: disabled (config param off).')
            return True
        Obs = self.env['health.observation']
        now = fields.Datetime.now()
        window_start = now - timedelta(days=28)
        min_points = tm_config.get_int(self.env, 'trend_min_points', 5)
        cap = tm_config.get_int(self.env, 'trend_batch_cap', 200)

        groups = Obs._read_group([
            ('state', 'in', ('final', 'amended')),
            ('effective_datetime', '>=', window_start),
            ('vitals_type_id.code', 'in', list(_TREND_CANDIDATE_CODES)),
        ], groupby=['client_id'], aggregates=['__count'], order='client_id')
        eligible = [(client, count) for client, count in groups
                    if client and count >= min_points]
        if len(eligible) > cap:
            _logger.info(
                'Trend sweep: %s eligible clients, capping at %s '
                '(dropped %s).', len(eligible), cap, len(eligible) - cap)
            eligible = eligible[:cap]

        processed = raised = 0
        for client, _count in eligible:
            try:
                with self.env.cr.savepoint():
                    raised += self._trend_sweep_client(client, now)
                processed += 1
            except Exception as exc:  # noqa: BLE001 — one bad client, sweep survives
                _logger.warning(
                    'Trend sweep: client %s failed: %s', client.id, exc)
        _logger.info('Trend sweep: clients=%s alerts=%s', processed, raised)
        return True

    def _series(self, client, codes, date_from):
        """Union of the given codes' trend points (oldest-first), each as
        (datetime, value); merged and sorted by datetime."""
        Obs = self.env['health.observation']
        Type = self.env['health.vitals.type']
        merged = []
        for code in codes:
            vtype = Type.get_by_code(code)
            if not vtype:
                continue
            for point in Obs.get_trend(client.id, vtype.id,
                                       date_from=date_from):
                dt = fields.Datetime.to_datetime(point['datetime'])
                merged.append((dt, point['value']))
        merged.sort(key=lambda p: p[0])
        return merged

    def _trend_sweep_client(self, client, now):
        raised = 0
        recent_start = now - timedelta(days=7)
        prior_start = now - timedelta(days=28)

        def split(series):
            recent = [v for dt, v in series if dt >= recent_start]
            prior = [v for dt, v in series
                     if prior_start <= dt < recent_start]
            return recent, prior

        # --- HR resting drift (warning) --------------------------------
        hr_series = self._series(client, ('hr',), prior_start)
        recent, prior = split(hr_series)
        if len(recent) >= 3 and len(prior) >= 3:
            mr, mp = statistics.median(recent), statistics.median(prior)
            drift = tm_config.get_float(self.env, 'hr_drift_bpm', 15.0)
            if (mr - mp) >= drift:
                raised += self._raise_trend(
                    client, 'trend_hr_drift', 'warning',
                    _('Nhịp tim nghỉ tăng / Resting HR drift'),
                    _('Nhịp tim / HR: trung vị 7 ngày %(mr)s vs 21 ngày '
                      'trước %(mp)s (ngưỡng %(th)s bpm).',
                      mr=mr, mp=mp, th=drift),
                    hr_series, mr, mp, drift)

        # --- SBP drift (warning) ---------------------------------------
        sbp_series = self._series(client, ('bp_sys',), prior_start)
        recent, prior = split(sbp_series)
        if len(recent) >= 3 and len(prior) >= 3:
            mr, mp = statistics.median(recent), statistics.median(prior)
            drift = tm_config.get_float(self.env, 'sbp_drift_mmhg', 20.0)
            if abs(mr - mp) >= drift:
                raised += self._raise_trend(
                    client, 'trend_sbp_drift', 'warning',
                    _('Huyết áp tâm thu thay đổi / Systolic BP drift'),
                    _('SBP: trung vị 7 ngày %(mr)s vs 21 ngày trước '
                      '%(mp)s (ngưỡng %(th)s mmHg).',
                      mr=mr, mp=mp, th=drift),
                    sbp_series, mr, mp, drift)

        # --- SpO2 decline (critical) -----------------------------------
        spo2_series = self._series(client, ('spo2', 'spo2_po'), prior_start)
        recent, prior = split(spo2_series)
        if len(recent) >= 3 and len(prior) >= 3:
            mr, mp = statistics.median(recent), statistics.median(prior)
            drop = tm_config.get_float(self.env, 'spo2_drop_pp', 3.0)
            if mr <= (mp - drop) and mr < 94:
                raised += self._raise_trend(
                    client, 'trend_spo2_decline', 'critical',
                    _('SpO₂ giảm / SpO2 decline'),
                    _('SpO₂: trung vị 7 ngày %(mr)s vs 21 ngày trước '
                      '%(mp)s (giảm ≥ %(th)s điểm, hiện < 94).',
                      mr=mr, mp=mp, th=drop),
                    spo2_series, mr, mp, drop)

        # --- Weight loss (warning) -------------------------------------
        wt_series = self._series(
            client, ('weight',), now - timedelta(days=14))
        if len(wt_series) >= 2:
            first_dt, w_first = wt_series[0]
            last_dt, w_last = wt_series[-1]
            days_between = (last_dt - first_dt).total_seconds() / 86400.0
            if days_between >= 5 and w_first:
                pct_per_week = (
                    (w_first - w_last) / w_first * 7.0 / days_between * 100.0)
                threshold = tm_config.get_float(
                    self.env, 'weight_loss_pct_per_week', 2.0)
                if pct_per_week >= threshold:
                    raised += self._raise_trend(
                        client, 'trend_weight_loss', 'warning',
                        _('Sụt cân / Weight loss'),
                        _('Cân nặng / weight: %(wf)s → %(wl)s kg trong '
                          '%(d).1f ngày (%(p).1f%%/tuần, ngưỡng '
                          '%(th)s%%/tuần).',
                          wf=w_first, wl=w_last, d=days_between,
                          p=pct_per_week, th=threshold),
                        wt_series, w_last, w_first, threshold)
        return raised

    def _raise_trend(self, client, rule, severity, title_stub, body,
                     series, median_recent, median_prior, threshold):
        if self._open_exists(client.id, rule):
            return 0
        title = _('%(stub)s — %(name)s',
                  stub=title_stub, name=client.name or '')
        evidence = json.dumps({
            'points': [
                [fields.Datetime.to_string(dt), v] for dt, v in series],
            'median_recent': median_recent,
            'median_prior': median_prior,
            'threshold': threshold,
        }, sort_keys=True)
        alert = self.create({
            'client_id': client.id,
            'rule': rule,
            'severity': severity,
            'title': title,
            'body': body,
            'evidence_json': evidence,
        })
        alert._escalate_if_critical()
        return 1
