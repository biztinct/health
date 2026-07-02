# -*- coding: utf-8 -*-
"""Pluggable AI provider layer.

The LLM only ever sees the dataset card (business metadata, no raw rows) and
only ever produces chart-config JSON, which passes through the exact same
resolver/validation as human-built charts. It never sees or produces SQL.
"""
import base64
import hashlib
import json
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

AI_TIMEOUT_DEFAULT = 60


def _fernet(env):
    from cryptography.fernet import Fernet
    secret = env['ir.config_parameter'].sudo().get_param('database.secret')
    key = base64.urlsafe_b64encode(hashlib.sha256(
        ('biz_bi|%s' % secret).encode()).digest())
    return Fernet(key)


class BiAiProvider(models.Model):
    _name = 'bi.ai.provider'
    _description = 'BI AI Provider'

    name = fields.Char(required=True)
    provider = fields.Selection([
        ('anthropic', 'Anthropic Claude'),
        ('openai', 'OpenAI'),
        ('ollama', 'Ollama (local)'),
    ], required=True)
    endpoint = fields.Char(required=True)
    model_name = fields.Char(required=True)
    api_key_encrypted = fields.Char(readonly=True)
    api_key_input = fields.Char(
        string='API Key', store=False,
        help="Stored encrypted; a database administrator could still recover "
             "it — use a scoped key.")
    has_api_key = fields.Boolean(compute='_compute_has_api_key')
    is_default = fields.Boolean()
    active = fields.Boolean(default=True)
    max_tokens = fields.Integer(default=2000)
    temperature = fields.Float(default=0.0)
    timeout_s = fields.Integer(default=AI_TIMEOUT_DEFAULT)

    def _compute_has_api_key(self):
        for provider in self:
            provider.has_api_key = bool(provider.api_key_encrypted)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._encrypt_key_in_vals(vals)
        providers = super().create(vals_list)
        providers._log_change()
        return providers

    def write(self, vals):
        self._encrypt_key_in_vals(vals)
        result = super().write(vals)
        self._log_change()
        return result

    def _encrypt_key_in_vals(self, vals):
        key = vals.pop('api_key_input', None)
        if key:
            vals['api_key_encrypted'] = _fernet(self.env).encrypt(
                key.encode()).decode()

    def _log_change(self):
        for provider in self:
            self.env['bi.audit.log'].sudo().log(
                'provider_change', record=provider,
                payload={'provider': provider.provider})

    def _api_key(self):
        self.ensure_one()
        if not self.api_key_encrypted:
            return None
        return _fernet(self.env).decrypt(
            self.api_key_encrypted.encode()).decode()

    @api.model
    def get_default(self):
        provider = self.search([('is_default', '=', True)], limit=1)
        return provider or self.search([], limit=1)

    # ------------------------------------------------------------------
    # Completion contract: _complete(system, user, force_json) -> str
    # ------------------------------------------------------------------

    def _complete(self, system, user_message, force_json=True):
        self.ensure_one()
        handler = getattr(self, '_complete_%s' % self.provider)
        return handler(system, user_message, force_json)

    def _complete_anthropic(self, system, user_message, force_json):
        key = self._api_key()
        if not key:
            raise UserError(_("Provider %s has no API key.", self.name))
        response = requests.post(
            self.endpoint,
            headers={
                'x-api-key': key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': self.model_name,
                'max_tokens': self.max_tokens,
                'temperature': self.temperature,
                'system': system,
                'messages': [{'role': 'user', 'content': user_message}],
            },
            timeout=self.timeout_s)
        response.raise_for_status()
        return response.json()['content'][0]['text']

    def _complete_openai(self, system, user_message, force_json):
        key = self._api_key()
        if not key:
            raise UserError(_("Provider %s has no API key.", self.name))
        payload = {
            'model': self.model_name,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user_message},
            ],
        }
        if force_json:
            payload['response_format'] = {'type': 'json_object'}
        response = requests.post(
            self.endpoint,
            headers={'Authorization': 'Bearer %s' % key},
            json=payload, timeout=self.timeout_s)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

    def _complete_ollama(self, system, user_message, force_json):
        payload = {
            'model': self.model_name,
            'stream': False,
            'options': {'temperature': self.temperature},
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user_message},
            ],
        }
        if force_json:
            payload['format'] = 'json'
        response = requests.post(self.endpoint, json=payload,
                                 timeout=self.timeout_s)
        response.raise_for_status()
        return response.json()['message']['content']


CHART_SCHEMA_BLOCK = """The chart configuration schema (used below):
  "name": "<short chart title>",
  "chart_type": "<one of: bar, bar_stacked, bar_h, line, area, combo, donut,
                  kpi, table, scatter, heatmap, treemap, funnel, gauge>",
  "slots": {
    "x": [{"field_id": <ref>, "grain": "<year|quarter|month|week|day, dates only>"}],
    "values": [{"field_id": <ref>, "agg": "<sum|avg|min|max|count|count_distinct>"}],
    "series": [{"field_id": <ref>}]
  },
  "filters": [{"field_id": <ref>, "op": "<eq|neq|gt|gte|lt|lte|in|not_in|between|like_i|is_set|is_null|relative>", "value": <value>}]

Every slot entry and every filter MUST be a JSON object exactly as shown —
never a bare number or string.

Rules:
- field_id MUST be a "ref" integer from the dataset card. Never invent refs.
- "grain" may ONLY be set on fields whose type is date or datetime.
- NEVER use the same field in both x and series.
- Time series ("monthly", "over time", "trend"): x = the date field with the
  grain; the breakdown dimension ("by facility", "by status") goes in series.
- Titles: use the same language as the USER REQUEST text.
- Use "relative" op with values like: today, last_7_days, last_30_days,
  this_week, this_month, last_month, this_quarter, last_6_months,
  last_12_months, this_year, last_year.
- kpi charts: empty x and series, exactly one values entry. Example:
  {"name": "Total Revenue", "chart_type": "kpi",
   "slots": {"x": [], "series": [],
             "values": [{"field_id": 631, "agg": "sum"}]}, "filters": []}
- donut: exactly one x, one values.
- Prefer measures with role "measure"; counting rows: any field with agg "count".
"""

NLQ_SYSTEM_PROMPT = """You are a BI chart configuration generator inside an
Odoo analytics platform. You receive a DATASET CARD describing the available
fields, and a user request in English or Vietnamese.

You output ONLY a JSON object — no prose, no markdown fences — with the keys
"name", "chart_type", "slots", "filters".

""" + CHART_SCHEMA_BLOCK

REPORT_SYSTEM_PROMPT = """You are a BI report designer inside an Odoo
analytics platform. You receive a DATASET CARD and a user request describing
a report/dashboard they want.

You output ONLY a JSON object — no prose, no markdown fences:
{
  "title": "<dashboard title in the user request's language>",
  "widgets": [
    {"name": "...", "chart_type": "...", "slots": {...}, "filters": [...],
     "width": <3|4|6|12>, "height": <2|3|4|5>}
  ]
}

""" + CHART_SCHEMA_BLOCK + """
- Compose 4 to 7 widgets: start with 2-3 KPI cards (width 3, height 2), then
  trend and breakdown charts (width 6, height 5), optionally one full-width
  chart (width 12, height 5).
"""


class BiAi(models.AbstractModel):
    """AI features. The LLM only ever sees the dataset card and only ever
    produces chart-config JSON, validated through the exact same resolver as
    human-built charts. It never sees or produces SQL."""
    _name = 'bi.ai'
    _description = 'BI AI Services'

    @api.model
    def is_available(self):
        provider = self.env['bi.ai.provider'].get_default()
        return bool(provider and (provider.has_api_key
                                  or provider.provider == 'ollama'))

    @api.model
    def nlq_chart(self, dataset_id, prompt):
        """Natural-language → validated chart config proposal."""
        dataset = self.env['bi.dataset'].browse(int(dataset_id))
        dataset.check_access('read')
        config, error = self._complete_validated(
            dataset, NLQ_SYSTEM_PROMPT, prompt, kind='nlq',
            validate=lambda cfg: self._validate_chart_config(dataset, cfg))
        if error:
            return {'error': error}
        return {'config': config}

    @api.model
    def compose_report(self, dataset_id, prompt):
        """Natural-language → draft dashboard with validated widgets."""
        dataset = self.env['bi.dataset'].browse(int(dataset_id))
        dataset.check_access('read')

        attempts = {'count': 0}

        def validate(plan):
            attempts['count'] += 1
            if not isinstance(plan.get('widgets'), list) or not plan['widgets']:
                raise UserError(_("Plan has no widgets."))
            valid, dropped = [], []
            for widget in plan['widgets']:
                try:
                    self._validate_chart_config(dataset, widget)
                    valid.append(widget)
                except Exception as exc:  # noqa: BLE001 — collect, don't die
                    dropped.append('%s: %s' % (widget.get('name', '?'), exc))
            if not valid:
                raise UserError(_(
                    "No valid widgets in plan: %s", '; '.join(dropped)))
            if dropped and attempts['count'] == 1:
                # first round: give the model one chance to fix its own drops
                raise UserError(_(
                    "These widgets were invalid — fix them and return the "
                    "FULL corrected plan: %s", '; '.join(dropped)))
            plan['widgets'] = valid
            plan['dropped'] = dropped
            return plan

        plan, error = self._complete_validated(
            dataset, REPORT_SYSTEM_PROMPT, prompt, kind='report',
            validate=validate)
        if error:
            return {'error': error}

        dashboard = self.env['bi.dashboard'].create({
            'name': plan.get('title') or _("AI Report"),
            'workspace_id': dataset.workspace_id.id,
        })
        x = y = row_height = 0
        for widget_plan in plan['widgets']:
            chart = self.env['bi.chart'].create({
                'name': widget_plan.get('name') or _("Chart"),
                'dataset_id': dataset.id,
                'chart_type': widget_plan.get('chart_type') or 'bar',
                'config_json': {
                    'version': 1,
                    'chart_type': widget_plan.get('chart_type') or 'bar',
                    'slots': widget_plan.get('slots') or {},
                    'filters': widget_plan.get('filters') or [],
                    'limit': 500,
                    'display': {},
                },
            })
            width = int(widget_plan.get('width') or 6)
            height = int(widget_plan.get('height') or 5)
            if x + width > 12:
                x, y = 0, y + row_height
                row_height = 0
            self.env['bi.dashboard.widget'].create({
                'dashboard_id': dashboard.id, 'chart_id': chart.id,
                'grid_x': x, 'grid_y': y, 'grid_w': width, 'grid_h': height,
            })
            x += width
            row_height = max(row_height, height)
        return {'dashboard_id': dashboard.id,
                'dropped': plan.get('dropped') or []}

    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_config(config):
        """Normalize sloppy-but-recoverable LLM output: bare refs in slots
        become proper entry objects; non-dict filters are dropped."""
        slots = config.get('slots') or {}
        for slot_name in ('x', 'values', 'series'):
            entries = slots.get(slot_name) or []
            normalized = []
            for entry in entries:
                if isinstance(entry, dict):
                    normalized.append(entry)
                elif isinstance(entry, (int, str)) and str(entry).isdigit():
                    normalized.append({'field_id': int(entry)})
            slots[slot_name] = normalized
        config['slots'] = slots
        config['filters'] = [f for f in (config.get('filters') or [])
                             if isinstance(f, dict)]
        return config

    def _validate_chart_config(self, dataset, config):
        """Run an LLM-proposed config through the human trust boundary:
        chart config -> query request -> engine resolver (field ownership,
        masking, op/agg/grain enums). Raises on anything invalid."""
        config = self._coerce_config(config)
        chart = self.env['bi.chart'].new({
            'name': config.get('name') or 'proposal',
            'dataset_id': dataset.id,
            'chart_type': config.get('chart_type') or 'bar',
            'config_json': {
                'slots': config.get('slots') or {},
                'filters': config.get('filters') or [],
                'limit': 500,
            },
        })
        request = chart._to_query_request()
        self.env['bi.query.engine']._resolve_request(dataset, request)
        return config

    def _complete_validated(self, dataset, system, prompt, kind, validate):
        provider = self.env['bi.ai.provider'].get_default()
        if not provider:
            return None, _("No AI provider configured.")
        card = dataset.get_dataset_card()
        user_message = "DATASET CARD:\n%s\n\nUSER REQUEST:\n%s" % (
            json.dumps(card, ensure_ascii=False, default=str), prompt)
        started = fields.Datetime.now()
        last_error = None
        for attempt in range(2):
            try:
                raw = provider._complete(system, user_message)
                config = self._parse_json(raw)
                result = validate(config)
                self._log(provider, kind, prompt, result, started, True)
                return result, None
            except Exception as exc:  # noqa: BLE001 — retry once with error
                last_error = str(exc)
                user_message += (
                    "\n\nYour previous answer was invalid: %s\n"
                    "Return corrected JSON only." % last_error)
        self._log(provider, kind, prompt, {'error': last_error}, started, False)
        return None, _(
            "The AI could not build a valid chart: %s", last_error)

    @staticmethod
    def _parse_json(raw):
        text = (raw or '').strip()
        if text.startswith('```'):
            text = text.strip('`')
            if text.startswith('json'):
                text = text[4:]
        start, end = text.find('{'), text.rfind('}')
        if start == -1 or end == -1:
            raise ValueError("No JSON object in the response")
        return json.loads(text[start:end + 1])

    def _log(self, provider, kind, prompt, response, started, accepted):
        duration = int((fields.Datetime.now() - started).total_seconds() * 1000)
        self.env['bi.ai.log'].sudo().create({
            'provider_id': provider.id,
            'kind': kind,
            'request_json': {'prompt': prompt},
            'response_json': response,
            'accepted': accepted,
            'duration_ms': duration,
        })
        self.env['bi.audit.log'].sudo().log(
            'ai_request', payload={'kind': kind, 'accepted': accepted})


class BiAiLog(models.Model):
    _name = 'bi.ai.log'
    _description = 'BI AI Request Log'
    _order = 'id desc'
    _log_access = False

    provider_id = fields.Many2one('bi.ai.provider', ondelete='set null')
    user_id = fields.Many2one('res.users',
                              default=lambda self: self.env.user)
    thread_key = fields.Char(index=True)
    kind = fields.Selection([
        ('nlq', 'Natural Language Query'),
        ('report', 'Report Composer'),
        ('insight', 'Insight Narration'),
    ], required=True)
    request_json = fields.Json()
    response_json = fields.Json()
    accepted = fields.Boolean()
    duration_ms = fields.Integer()
    created_at = fields.Datetime(default=fields.Datetime.now)
