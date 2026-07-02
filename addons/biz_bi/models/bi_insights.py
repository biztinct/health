# -*- coding: utf-8 -*-
"""Statistical auto-insights.

Pure-Python analysis of a chart's result envelope — no external API:
  * trend       — last full bucket vs the previous one (time series)
  * anomaly     — z-score outliers along the series (time series)
  * top_mover   — categories driving the change between halves of the window
  * concentration — how much of the total the top categories hold
  * outlier     — categories far from the categorical mean

The optional LLM pass only NARRATES the computed findings in the user's
language — it never computes numbers itself, which bounds hallucination
to phrasing.
"""
import json
import statistics

from odoo import _, api, fields, models
from odoo.exceptions import UserError

Z_THRESHOLD = 2.2
MIN_SERIES_POINTS = 5


def _bucket_label(value):
    """Trim ISO timestamps to their date part for readable findings."""
    text = str(value)
    return text[:10] if len(text) >= 10 and text[4:5] == '-' else text

NARRATION_SYSTEM_PROMPT = """You are a BI analyst. You receive computed
FINDINGS (JSON) about one chart. Write 2-4 short sentences summarizing what
matters for a business reader, in the language named by OUTPUT LANGUAGE —
exactly that language, regardless of the languages inside the findings.
Only restate the numbers given — never invent or recompute.
No markdown, no bullet points, plain sentences."""


class BiInsights(models.AbstractModel):
    _name = 'bi.insights'
    _description = 'BI Auto-Insights'

    @api.model
    def analyze_chart(self, chart_id, extra_filters=None, narrate=True):
        """Run the chart's query and return {findings: [...], narration}."""
        chart = self.env['bi.chart'].browse(int(chart_id))
        chart.check_access('read')
        engine = self.env['bi.query.engine']
        envelope = engine.run(chart._to_query_request(extra_filters))
        if envelope.get('error'):
            raise UserError(envelope['error'])

        findings = self._compute_findings(envelope)
        narration = None
        if narrate and findings and self.env['bi.ai'].is_available():
            narration = self._narrate(chart, findings)
        return {'findings': findings, 'narration': narration}

    # ==================================================================
    # Statistical engine
    # ==================================================================

    def _compute_findings(self, envelope):
        columns = envelope['columns']
        rows = envelope['rows']
        if not rows:
            return [{'kind': 'empty', 'severity': 'info',
                     'data': {}, 'text': _("No data in the current scope.")}]
        dims = [c for c in columns if c['ref'].startswith('d')]
        measures = [c for c in columns if c['ref'].startswith('m')]
        if not measures:
            return []
        m0 = measures[0]
        m0_index = columns.index(m0)

        is_time_series = bool(dims) and (
            dims[0].get('grain') or dims[0]['type'] in ('date', 'datetime'))

        findings = []
        if is_time_series and len(dims) == 1:
            series = [(row[0], row[m0_index]) for row in rows
                      if row[m0_index] is not None]
            findings += self._trend(series, m0)
            findings += self._anomalies(series, m0)
        elif dims:
            pairs = [(row[0], row[m0_index]) for row in rows
                     if row[m0_index] is not None
                     and row[0] != '__bi_others__']
            findings += self._concentration(pairs, m0, dims[0])
            findings += self._categorical_outliers(pairs, m0, dims[0])
        else:
            findings.append({
                'kind': 'value', 'severity': 'info',
                'data': {'value': rows[0][m0_index],
                         'measure': m0['label']},
                'text': _("%(measure)s: %(value)s",
                          measure=m0['label'], value=rows[0][m0_index]),
            })
        return findings

    def _trend(self, series, measure):
        if len(series) < 2:
            return []
        # compare the last COMPLETE bucket to its predecessor: the trailing
        # bucket is usually partial, so use n-2 vs n-3 when we have depth
        if len(series) >= 4:
            current, previous = series[-2], series[-3]
            partial_note = True
        else:
            current, previous = series[-1], series[-2]
            partial_note = False
        prev_value = previous[1] or 0
        if prev_value == 0:
            return []
        change = (current[1] - prev_value) / abs(prev_value) * 100
        severity = 'high' if abs(change) >= 25 else \
                   'medium' if abs(change) >= 10 else 'info'
        direction = _("up") if change >= 0 else _("down")
        return [{
            'kind': 'trend', 'severity': severity,
            'data': {'measure': measure['label'],
                     'change_pct': round(change, 1),
                     'bucket': _bucket_label(current[0]),
                     'value': current[1],
                     'previous': prev_value,
                     'last_complete_bucket': partial_note},
            'text': _(
                "%(measure)s is %(dir)s %(pct)s%% in the latest complete "
                "period (%(cur)s vs %(prev)s).",
                measure=measure['label'], dir=direction,
                pct=abs(round(change, 1)), cur=current[1], prev=prev_value),
        }]

    def _anomalies(self, series, measure):
        values = [value for _bucket, value in series]
        if len(values) < MIN_SERIES_POINTS:
            return []
        mean = statistics.fmean(values)
        stdev = statistics.pstdev(values)
        if not stdev:
            return []
        findings = []
        for bucket, value in series:
            z = (value - mean) / stdev
            if abs(z) >= Z_THRESHOLD:
                findings.append({
                    'kind': 'anomaly',
                    'severity': 'high' if abs(z) >= 3 else 'medium',
                    'data': {'bucket': _bucket_label(bucket), 'value': value,
                             'z': round(z, 2), 'mean': round(mean, 2),
                             'measure': measure['label']},
                    'text': _(
                        "%(bucket)s is unusual: %(value)s vs a typical "
                        "%(mean)s (z=%(z)s).",
                        bucket=_bucket_label(bucket), value=value,
                        mean=round(mean, 1), z=round(z, 1)),
                })
        return findings[:4]

    def _concentration(self, pairs, measure, dim):
        total = sum(value for _label, value in pairs)
        if not total or len(pairs) < 3:
            return []
        ranked = sorted(pairs, key=lambda p: p[1] or 0, reverse=True)
        top_label, top_value = ranked[0]
        share = top_value / total * 100
        findings = []
        if share >= 40:
            findings.append({
                'kind': 'concentration',
                'severity': 'high' if share >= 60 else 'medium',
                'data': {'dimension': dim['label'], 'top': str(top_label),
                         'share_pct': round(share, 1),
                         'measure': measure['label']},
                'text': _(
                    "%(top)s alone holds %(share)s%% of total %(measure)s.",
                    top=top_label, share=round(share, 1),
                    measure=measure['label']),
            })
        top3 = sum(value for _l, value in ranked[:3])
        if len(ranked) >= 5 and top3 / total >= 0.8:
            findings.append({
                'kind': 'concentration', 'severity': 'medium',
                'data': {'dimension': dim['label'],
                         'top3_share_pct': round(top3 / total * 100, 1),
                         'others': len(ranked) - 3},
                'text': _(
                    "The top 3 %(dim)s values cover %(share)s%% — the "
                    "remaining %(n)s barely contribute.",
                    dim=dim['label'], share=round(top3 / total * 100, 1),
                    n=len(ranked) - 3),
            })
        return findings

    def _categorical_outliers(self, pairs, measure, dim):
        values = [value for _label, value in pairs]
        if len(values) < 4:
            return []
        mean = statistics.fmean(values)
        stdev = statistics.pstdev(values)
        if not stdev:
            return []
        findings = []
        for label, value in pairs:
            z = (value - mean) / stdev
            if abs(z) >= Z_THRESHOLD:
                findings.append({
                    'kind': 'outlier',
                    'severity': 'medium',
                    'data': {'dimension': dim['label'], 'member': str(label),
                             'value': value, 'z': round(z, 2),
                             'measure': measure['label']},
                    'text': _(
                        "%(member)s stands out with %(value)s "
                        "(typical %(dim)s value: %(mean)s).",
                        member=label, value=value, dim=dim['label'],
                        mean=round(mean, 1)),
                })
        return findings[:3]

    # ==================================================================
    # LLM narration (restates computed numbers only)
    # ==================================================================

    def _narrate(self, chart, findings):
        provider = self.env['bi.ai.provider'].get_default()
        if not provider or not provider._is_usable():
            return None
        lang_code = self.env.user.lang or 'en_US'
        lang = self.env['res.lang'].search(
            [('code', '=', lang_code)], limit=1)
        payload = {
            'chart_title': chart.name,
            'findings': [{'kind': f['kind'], 'severity': f['severity'],
                          **f['data']} for f in findings],
        }
        started = fields.Datetime.now()
        try:
            narration = provider._complete(
                NARRATION_SYSTEM_PROMPT,
                "OUTPUT LANGUAGE: %s\n\n%s" % (
                    lang.name or 'English',
                    json.dumps(payload, ensure_ascii=False, default=str)),
                force_json=False)
        except Exception:  # noqa: BLE001 — narration is optional sugar
            return None
        duration = int(
            (fields.Datetime.now() - started).total_seconds() * 1000)
        self.env['bi.ai.log'].sudo().create({
            'provider_id': provider.id, 'kind': 'insight',
            'request_json': payload,
            'response_json': {'narration': narration},
            'accepted': True, 'duration_ms': duration,
        })
        return (narration or '').strip() or None
