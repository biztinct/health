# -*- coding: utf-8 -*-
"""One row per problem, for as long as the problem lasts.

WHY A RECORD AND NOT A LOG LINE. The question somebody asks is never "what
happened at 14:02", it is "what is wrong right now, and have I already dealt
with it". A log answers the first; only a record with a state answers the
second. So a problem is created once, bumped while it lasts, and resolved when
it stops — and anything the platform says about it follows the RECORD, not the
reading, which is why the same missing copy does not shout every fifteen
minutes.

THE KEY IS THE IDENTITY. `backup_stale:hhh` is one problem however many times
it is measured. Uniqueness is deliberately NOT a database constraint, because a
resolved alert has to be allowed to sit in history beside a new one with the
same key — `reconcile()` next door is what keeps exactly one of them open.

⚠ `spoken_at` IS THE STAMP THAT SAYS "WE TOLD YOU", AND IT IS ONLY EVER WRITTEN
WHEN A MESSAGE ACTUALLY LEFT (ledger F40). While this platform has no outgoing
mail account, `channel_state` stays `dark` and `spoken_at` stays empty — which
is the truth, and which is the whole reason the Alerts screen exists.
"""
from odoo import api, fields, models

from .alert_rules import ALERT_KINDS, KIND_ICON, KIND_LABEL


class BizAlert(models.Model):
    _name = 'biz.alert'
    _description = 'Something the platform noticed'
    _order = 'severity, first_seen desc, id desc'

    key = fields.Char(required=True, index=True,
                      help="The identity of the problem, e.g. backup_stale:hhh. "
                           "One open alert per key.")
    kind = fields.Selection([(k, KIND_LABEL.get(k, k)) for k in ALERT_KINDS],
                            required=True, index=True)
    severity = fields.Selection([
        ('critical', 'Needs attention now'),
        ('warning', 'Worth a look'),
        ('info', 'For information'),
    ], default='warning', required=True, index=True)
    #: The one line somebody reads first.
    subject = fields.Char(required=True)
    #: What is wrong AND what to do next, in plain words. An alert that hands
    #: somebody a number and leaves them to work out the rest is an alert they
    #: learn to scroll past.
    body_text = fields.Text()
    tenant_id = fields.Many2one('biz.tenant', ondelete='set null', index=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('acknowledged', 'You know about it'),
        ('resolved', 'Over'),
    ], default='open', required=True, index=True)
    first_seen = fields.Datetime(default=fields.Datetime.now, required=True)
    last_seen = fields.Datetime(default=fields.Datetime.now)
    count = fields.Integer(default=1, help="How many checks have seen it.")

    # ------------------------------------------------------------- the channel
    #: ⚠ WRITTEN ONLY AFTER A MESSAGE ACTUALLY LEFT (F40). If a send fails and
    #: this is stamped anyway, the problem falls silent for two hours on the
    #: strength of a message nobody received.
    spoken_at = fields.Datetime(string="Told somebody at")
    #: How bad it was called when it was last spoken. Storing this is what lets
    #: a problem that gets WORSE speak again straight away.
    spoken_severity = fields.Char()
    channel_state = fields.Selection([
        ('dark', 'Nothing was sent'),
        ('sent', 'Sent'),
        ('failed', 'Could not be sent'),
    ], default='dark', required=True, index=True)
    channel_reason = fields.Char(
        help="Why nothing was sent, in the words the screen shows.")

    resolved_at = fields.Datetime()
    resolution = fields.Char(help="Why it was closed, when a person closed it.")
    acknowledged_by = fields.Many2one('res.users', ondelete='set null')
    acknowledged_at = fields.Datetime()

    def as_dict(self):
        """One alert as the rules and the screen both read it."""
        out = []
        for a in self:
            out.append({
                'id': a.id, 'key': a.key, 'kind': a.kind,
                'kind_label': KIND_LABEL.get(a.kind, a.kind),
                'icon': KIND_ICON.get(a.kind, 'alert'),
                'severity': a.severity, 'subject': a.subject,
                'title': a.subject,
                'text': a.body_text or '',
                'state': a.state,
                'tenant_id': a.tenant_id.id or None,
                'tenant': a.tenant_id.name or '',
                'tenant_slug': a.tenant_id.slug or '',
                'first_seen': a.first_seen, 'last_seen': a.last_seen,
                'count': a.count,
                'spoken_at': a.spoken_at,
                'spoken_severity': a.spoken_severity or '',
                'channel_state': a.channel_state,
                'channel_reason': a.channel_reason or '',
                'resolved_at': a.resolved_at,
                'resolution': a.resolution or '',
                'acknowledged_by': a.acknowledged_by.name or '',
            })
        return out

    @api.model
    def open_alerts(self):
        return self.sudo().search([('state', 'in', ('open', 'acknowledged'))])
