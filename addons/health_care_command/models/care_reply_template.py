# -*- coding: utf-8 -*-
"""Reply templates — plain internal model (Phase 3, deliverable 1).

Deliberately NOT a ``mail.template``: it renders no expressions, ships no
subject/body render-check, and touches no ZNS/health_messaging plumbing (which
would trip the install-render gotcha §5.14). A template is a plain text snippet
a CRM manager types; clicking a chip in the composer INSERTS the body — the
only send path stays the existing composer send. No AI, no variables.
"""

from odoo import fields, models


class CareReplyTemplate(models.Model):
    _name = "care.reply.template"
    _inherit = ['health.lifecycle.mixin']
    _description = "Care Command Reply Template"
    _order = "sequence, id"

    name = fields.Char(string="Name", required=True)
    body = fields.Text(string="Body", required=True)
    # Optional channel scope: mirrors care.conversation.channel_primary + "any".
    # A conversation shows templates whose channel is "any" OR matches its
    # own last-inbound channel.
    channel = fields.Selection(
        [
            ("any", "Any channel"),
            ("zalo", "Zalo"),
            ("call", "Calls"),
            ("email", "Email"),
            ("zns", "ZNS"),
        ],
        string="Channel",
        default="any",
        required=True,
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", required=True, index=True,
        default=lambda self: self.env.company,
    )
