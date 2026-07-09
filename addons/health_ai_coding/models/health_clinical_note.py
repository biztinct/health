# -*- coding: utf-8 -*-
"""The ONLY clinical-note schema touch: sweep bookkeeping + a review
smart-button count (handover §2.2 / §2.6)."""
from odoo import _, api, fields, models


class HealthClinicalNote(models.Model):
    _inherit = 'health.clinical.note'

    ai_attempts = fields.Integer(
        string='AI Coding Attempts', default=0, copy=False,
        help='How many times the retro-coding sweep has tried this note '
             '(capped so un-codable notes are not retried forever).')
    ai_last_attempt = fields.Datetime(
        string='Last AI Coding Attempt', copy=False)
    ai_suggestion_ids = fields.One2many(
        'health.ai.code.suggestion', 'note_id', string='AI Code Suggestions')
    ai_pending_count = fields.Integer(
        string='Pending AI Codes', compute='_compute_ai_pending_count')

    @api.depends('ai_suggestion_ids.state')
    def _compute_ai_pending_count(self):
        for rec in self:
            rec.ai_pending_count = len(rec.ai_suggestion_ids.filtered(
                lambda s: s.state == 'suggested'))

    def _mark_ai_attempt(self):
        """Increment the attempt counter (own cursor-safe write from the
        sweep's per-note savepoint)."""
        for rec in self:
            rec.sudo().write({
                'ai_attempts': rec.ai_attempts + 1,
                'ai_last_attempt': fields.Datetime.now(),
            })

    def action_open_ai_suggestions(self):
        """Smart-button target: this note's AI code suggestions."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('AI Code Suggestions'),
            'res_model': 'health.ai.code.suggestion',
            'view_mode': 'list,form',
            'domain': [('note_id', '=', self.id)],
            'context': {'search_default_suggested': 1},
        }
