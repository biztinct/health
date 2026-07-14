# -*- coding: utf-8 -*-
"""``health.ews.score`` — NEWS2 early-warning score.

System-generated, append-only. One row is created (sudo, by the engine)
whenever a vitals capture completes a scorable set within the assembly
window. The score snapshots the component values + subscores actually used
so the row is auditable without re-reading the source observations.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import tm_config
from .news2 import ACVPU_VALUES, news2_band, news2_component_scores

_logger = logging.getLogger(__name__)

# Observation short codes that can trigger / feed a NEWS2 score.
RELEVANT_CODES = frozenset(
    ('rr', 'spo2', 'spo2_po', 'bp_sys', 'hr', 'temp', 'acvpu', 'o2_flow'))


class HealthEwsScore(models.Model):
    _name = 'health.ews.score'
    _description = 'NEWS2 Early-Warning Score'
    _order = 'score_datetime desc, id desc'
    _rec_names_search = ['client_id.name']

    display_name = fields.Char(
        compute='_compute_display_name')

    client_id = fields.Many2one(
        'res.partner', string='Client', required=True, index=True,
        ondelete='restrict', domain=[('is_patient', '=', True)])
    order_id = fields.Many2one(
        'health.fieldservice.order', string='Visit', index=True,
        ondelete='set null')
    score_datetime = fields.Datetime(
        string='Score Time', required=True, index=True,
        help='Anchor time of the scored set (latest triggering '
             'observation).')

    # Component value snapshot.
    rr_value = fields.Float(string='Respiratory rate')
    spo2_value = fields.Float(string='SpO₂')
    sbp_value = fields.Float(string='Systolic BP')
    hr_value = fields.Float(string='Heart rate')
    temp_value = fields.Float(string='Temperature', digits=(4, 1))
    acvpu_value = fields.Char(string='ACVPU', size=1)
    on_oxygen = fields.Boolean(string='On oxygen')
    spo2_scale = fields.Selection([
        ('1', 'Scale 1'),
        ('2', 'Scale 2'),
    ], string='SpO₂ scale')

    # Component subscores.
    rr_score = fields.Integer(string='RR score')
    spo2_score = fields.Integer(string='SpO₂ score')
    o2_score = fields.Integer(string='O₂ score')
    bp_score = fields.Integer(string='BP score')
    hr_score = fields.Integer(string='HR score')
    temp_score = fields.Integer(string='Temp score')
    consciousness_score = fields.Integer(string='Consciousness score')

    total = fields.Integer(string='NEWS2 total', index=True)
    band = fields.Selection([
        ('low', 'Low'),
        ('low_medium', 'Low-Medium'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Band', index=True)

    defaulted_consciousness = fields.Boolean(
        string='Consciousness defaulted (A)',
        help='ACVPU was not recorded in the window; Alert (A) was assumed.')
    superseded = fields.Boolean(
        string='Superseded', default=False, index=True)

    observation_ids = fields.Many2many(
        'health.observation', string='Evidence observations',
        help='The observation rows actually used to compute this score.')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('total', 'client_id.name', 'score_datetime')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                'NEWS2 %(total)s — %(name)s — %(when)s',
                total=rec.total,
                name=rec.client_id.name or '',
                when=fields.Datetime.to_string(rec.score_datetime) or '')

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.client_id._get_health_catchment_province()
                if rec.client_id else False)

    # ------------------------------------------------------------------
    # Append-only discipline (clone of health.observation guards)
    # ------------------------------------------------------------------
    # Only the supersede flag (and the system-managed catchment recompute)
    # may change after create — everything else is immutable evidence.
    _WRITE_ALLOWED = frozenset(('superseded', 'catchment_province_id'))

    def write(self, vals):
        if set(vals) - self._WRITE_ALLOWED:
            raise UserError(_(
                'NEWS2 scores are system-generated and append-only; only '
                'the superseded flag may change.'))
        return super().write(vals)

    def unlink(self):
        allowed = (
            self.env.su
            or self.env.user._is_admin()
            or self.env.user.has_group('health_base.group_healthcare_admin')
            or self.env.user.has_group('health_base.group_healthcare_owner'))
        if not allowed:
            raise UserError(_(
                'NEWS2 scores are append-only and cannot be deleted.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Scoring engine (handover §2.5)
    # ------------------------------------------------------------------
    @api.model
    def _score_from_observations(self, observations):
        """Assemble a NEWS2 score per client from a batch of freshly
        created / amended observations. Never called for its side effects
        outside a guarded caller — the observation trigger wraps this in a
        never-block try/except (handover §2.5)."""
        relevant = observations.filtered(
            lambda o: o.state in ('final', 'amended')
            and o.vitals_type_id.code in RELEVANT_CODES)
        if not relevant:
            return
        window_min = tm_config.get_int(
            self.env, 'ews_window_minutes', 60)
        by_client = {}
        for obs in relevant:
            by_client.setdefault(
                obs.client_id.id, self.env['health.observation'])
            by_client[obs.client_id.id] |= obs
        for _cid, trig in by_client.items():
            anchor_obs = trig.sorted(
                key=lambda o: (o.effective_datetime, o.id))[-1]
            self._score_one_client(anchor_obs, window_min)

    def _score_one_client(self, anchor_obs, window_min):
        Obs = self.env['health.observation']
        client = anchor_obs.client_id
        anchor = anchor_obs.effective_datetime
        window_start = anchor - timedelta(minutes=window_min)

        def latest(codes):
            return Obs.search([
                ('client_id', '=', client.id),
                ('vitals_type_id.code', 'in', list(codes)),
                ('state', 'in', ('final', 'amended')),
                ('effective_datetime', '>=', window_start),
                ('effective_datetime', '<=', anchor),
            ], order='effective_datetime desc, id desc', limit=1)

        rr = latest(('rr',))
        spo2 = latest(('spo2', 'spo2_po'))
        sbp = latest(('bp_sys',))
        hr = latest(('hr',))
        temp = latest(('temp',))
        if not (rr and spo2 and sbp and hr and temp):
            _logger.debug(
                'EWS: incomplete vitals set for client %s in window '
                '[%s, %s], no score.', client.id, window_start, anchor)
            return

        acvpu_obs = latest(('acvpu',))
        raw = (acvpu_obs.value_text or '').strip().upper()[:1] \
            if acvpu_obs else ''
        if raw in ACVPU_VALUES:
            acvpu = raw
            defaulted = False
        else:
            acvpu = 'A'
            defaulted = True

        o2_obs = Obs.search([
            ('client_id', '=', client.id),
            ('vitals_type_id.code', '=', 'o2_flow'),
            ('state', 'in', ('final', 'amended')),
            ('value_quantity', '>', 0),
            ('effective_datetime', '>=', window_start),
            ('effective_datetime', '<=', anchor),
        ], order='effective_datetime desc, id desc', limit=1)
        on_oxygen = bool(o2_obs)

        scale2 = bool(client.news2_spo2_scale2)
        scores = news2_component_scores(
            rr.value_quantity, spo2.value_quantity, on_oxygen,
            sbp.value_quantity, hr.value_quantity, temp.value_quantity,
            acvpu=acvpu, scale2=scale2)
        total, band = news2_band(scores)

        # Supersede any current score anchored inside the same window.
        self.search([
            ('client_id', '=', client.id),
            ('superseded', '=', False),
            ('score_datetime', '>=', window_start),
        ]).write({'superseded': True})

        used = rr | spo2 | sbp | hr | temp
        if acvpu_obs:
            used |= acvpu_obs
        if o2_obs:
            used |= o2_obs

        score = self.create(dict(scores, **{
            'client_id': client.id,
            'order_id': anchor_obs.order_id.id or False,
            'score_datetime': anchor,
            'rr_value': rr.value_quantity,
            'spo2_value': spo2.value_quantity,
            'sbp_value': sbp.value_quantity,
            'hr_value': hr.value_quantity,
            'temp_value': temp.value_quantity,
            'acvpu_value': acvpu,
            'on_oxygen': on_oxygen,
            'spo2_scale': '2' if scale2 else '1',
            'total': total,
            'band': band,
            'defaulted_consciousness': defaulted,
            'observation_ids': [(6, 0, used.ids)],
        }))
        # Hand off to the triage inbox (never blocks the score create).
        try:
            self.env['health.monitor.alert'].sudo()._raise_for_ews(score)
        except Exception:  # noqa: BLE001 — alerting must never block capture
            _logger.exception(
                'EWS: alert raise failed for score %s', score.id)
        return score
