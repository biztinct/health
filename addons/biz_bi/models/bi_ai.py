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
