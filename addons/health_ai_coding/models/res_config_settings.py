# -*- coding: utf-8 -*-
"""Settings for the AI retro-coding sweep (handover §2.4 / §3).

Sovereignty defaults ship OFF: ``enabled`` and ``allow_cloud`` are both
False, so installing the module changes nothing until ops flips them, and a
non-Ollama provider is refused unless cloud is explicitly allowed.
"""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ai_coding_enabled = fields.Boolean(
        string='Enable AI Retro-Coding',
        config_parameter='health_ai_coding.enabled')
    ai_coding_allow_cloud = fields.Boolean(
        string='Allow Cloud AI Providers',
        config_parameter='health_ai_coding.allow_cloud',
        help='When off (default) only an Ollama (local) provider is called; a '
             'cloud provider is refused. Data-sovereignty control.')
    ai_coding_provider_id = fields.Many2one(
        'bi.ai.provider', string='AI Provider',
        config_parameter='health_ai_coding.provider_id')
    ai_coding_batch_cap = fields.Integer(
        string='Notes per Sweep',
        config_parameter='health_ai_coding.batch_cap', default=25)
    ai_coding_max_prompt_chars = fields.Integer(
        string='Max Prompt Characters',
        config_parameter='health_ai_coding.max_prompt_chars', default=4000)
    ai_coding_max_attempts = fields.Integer(
        string='Max Attempts per Note',
        config_parameter='health_ai_coding.max_attempts', default=3)
