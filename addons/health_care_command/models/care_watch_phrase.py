# -*- coding: utf-8 -*-
"""Watchlist phrases — deterministic triage rule (Phase 3, deliverable 2).

A manager-typed list of phrases. At INGEST time only (inbound Zalo message /
inbound email), the message text is lowercased and each active phrase is tested
as a literal substring. On a hit the conversation is flagged (``watch_flag``)
and the matched phrases stored (``watch_terms``) — a small triage badge on the
wall, +15 urgency. NO regex, NO scoring, NO NLP, NO severity judgement: this is
a substring rule the manager owns, nothing more (Phase-3 non-goal: still no AI).
"""

from odoo import fields, models


class CareWatchPhrase(models.Model):
    _name = "care.watch.phrase"
    _inherit = ['health.lifecycle.mixin']
    _description = "Care Command Watchlist Phrase"
    _order = "phrase"

    phrase = fields.Char(string="Phrase", required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True,
        default=lambda self: self.env.company,
    )
