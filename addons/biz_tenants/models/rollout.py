# -*- coding: utf-8 -*-
"""A rollout: one release, reaching every system in rings.

WHY THIS IS A RECORD AND NOT A SCRIPT. Bringing one customer in step is a
button and a minute. Bringing them all in step is hours — a practice run, the
blank system, one clinic, a day of watching, then the rest, each inside their
own night — and nobody is going to sit at a screen for it. So the intention is
written down once, when a person presses Start, and a background worker spends
the next two days doing exactly what was written down and nothing else.

That is also the whole of rail R1 in this phase. THE WORKER NEVER DECIDES TO
UPDATE ANYBODY. It reads the list a person made, and it stops at the first
thing that goes wrong.
"""
import json

from odoo import api, fields, models

from .rollout_rules import (
    CUSTOMER_RINGS, DEFAULT_HOURS, DEFAULT_START_HOUR, RING_LABEL, RING_MEANING,
    RING_ORDER,
)

RING_SELECTION = [(r, RING_LABEL[r]) for r in CUSTOMER_RINGS]
ALL_RING_SELECTION = [(r, RING_LABEL[r]) for r in RING_ORDER]


class BizTenantRollout(models.Model):
    """Which ring a customer is in, and when their night is."""
    _inherit = 'biz.tenant'

    #: EVERYBODY STARTS LAST. A customer becomes the first to get a release
    #: because somebody decided they should be, never because they happened to
    #: be created first.
    ring = fields.Selection(
        RING_SELECTION, default='everyone', required=True, index=True,
        string="Update ring",
        help="Which ring of a rollout this customer is updated in.")
    #: The hour their quiet window opens, IN THEIR TIME ZONE, and how long it
    #: lasts. Stored as an hour rather than as a moment, because "22:00 where
    #: they are" survives daylight saving and a stored moment does not.
    maintenance_start = fields.Integer(
        default=DEFAULT_START_HOUR, string="Quiet window opens",
        help="The hour their quiet window opens, on their own clock (0–23).")
    maintenance_hours = fields.Integer(
        default=DEFAULT_HOURS, string="Quiet window lasts",
        help="How many hours the quiet window stays open.")
    #: Read once off their own company record — plain read-only SQL, no
    #: registry opened — and then kept here, so the worker never has to open a
    #: customer's whole system to answer "what time is it where they are".
    tz = fields.Char(string="Their time zone",
                     help="Read from their own company record.")
    rollout_task_ids = fields.One2many('biz.rollout.task', 'tenant_id')

    def ring_meaning(self):
        self.ensure_one()
        return RING_MEANING.get(self.ring, '')


class BizRollout(models.Model):
    _name = 'biz.rollout'
    _description = 'One release walking the fleet'
    _order = 'create_date desc, id desc'

    release_id = fields.Many2one('biz.release', required=True,
                                 ondelete='restrict', index=True)
    name = fields.Char(compute='_compute_name')
    state = fields.Selection([
        ('draft', 'Not started'),
        ('rehearsing', 'Practising on a copy'),
        ('running', 'Running'),
        ('waiting', 'Waiting'),
        ('paused', 'Stopped'),
        ('done', 'Finished'),
        ('aborted', 'Called off'),
    ], default='draft', required=True, index=True)
    #: The ring it is on now.
    ring = fields.Selection(ALL_RING_SELECTION, default='rehearsal',
                            string="Ring")
    watch_hours_canary = fields.Integer(default=24)
    watch_hours_early = fields.Integer(default=48)
    #: Set when somebody presses "Continue now" — the watch period for the
    #: CURRENT ring is over early. Cleared the moment the next ring starts, so
    #: it can never quietly shorten a ring nobody meant to shorten.
    watch_skipped = fields.Boolean()
    ring_started_at = fields.Datetime()
    ring_done_at = fields.Datetime()
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    #: Why it stopped, in words somebody can act on. NEVER a traceback.
    note = fields.Text(string="Why it stopped")
    started_by = fields.Many2one('res.users', ondelete='set null')
    #: Everything the worker did, newest last: one line per act, the same trail
    #: a provisioning run leaves on a customer.
    log = fields.Text(default='[]')
    task_ids = fields.One2many('biz.rollout.task', 'rollout_id')

    task_count = fields.Integer(compute='_compute_counts')
    done_count = fields.Integer(compute='_compute_counts')
    failed_count = fields.Integer(compute='_compute_counts')
    queued_count = fields.Integer(compute='_compute_counts')
    customer_total = fields.Integer(compute='_compute_counts')
    customer_done = fields.Integer(compute='_compute_counts')

    @api.depends('release_id.name')
    def _compute_name(self):
        for r in self:
            r.name = r.release_id.name or 'Rollout'

    @api.depends('task_ids.state', 'task_ids.ring')
    def _compute_counts(self):
        for r in self:
            tasks = r.task_ids
            r.task_count = len(tasks)
            r.done_count = len(tasks.filtered(lambda t: t.state == 'done'))
            r.failed_count = len(tasks.filtered(lambda t: t.state == 'failed'))
            r.queued_count = len(tasks.filtered(
                lambda t: t.state in ('waiting', 'due')))
            cust = tasks.filtered(lambda t: t.ring in CUSTOMER_RINGS)
            r.customer_total = len(cust)
            r.customer_done = len(cust.filtered(lambda t: t.state == 'done'))

    def log_line(self, line, level='info'):
        """One line in the rollout's own trail. NEVER RAISES — a trail that can
        break the thing it is recording is worse than no trail."""
        self.ensure_one()
        try:
            rows = json.loads(self.log or '[]')
        except ValueError:
            rows = []
        rows.append({'line': line, 'level': level,
                     'ts': fields.Datetime.now().isoformat(timespec='seconds')})
        self.sudo().write({'log': json.dumps(rows[-400:])})
        return line

    def log_rows(self):
        self.ensure_one()
        try:
            rows = json.loads(self.log or '[]')
        except ValueError:
            return []
        return rows if isinstance(rows, list) else []


class BizRolloutTask(models.Model):
    """One system, one release, one attempt at a time."""
    _name = 'biz.rollout.task'
    _description = 'One system in a rollout'
    _order = 'sequence, id'

    rollout_id = fields.Many2one('biz.rollout', required=True,
                                 ondelete='cascade', index=True)
    sequence = fields.Integer(default=10, index=True)
    ring = fields.Selection(ALL_RING_SELECTION, required=True, index=True)
    #: Empty for the practice run and the blank system — neither is a customer.
    tenant_id = fields.Many2one('biz.tenant', ondelete='cascade', index=True)
    #: Whose copy the practice run is restored from. DELIBERATELY NOT
    #: `tenant_id`: a practice run on a copy of somebody's data is not an update
    #: that customer received, and it must never appear on their own trail as
    #: though it were.
    source_tenant_id = fields.Many2one('biz.tenant', ondelete='set null')
    label = fields.Char(required=True)
    #: The system actually acted on: `hhh-staging`, `carejiox_template`, `hhh`.
    target_db = fields.Char(required=True)
    state = fields.Selection([
        ('waiting', 'Waiting for their window'),
        ('due', 'Their window is open'),
        ('running', 'Being updated'),
        ('done', 'Done'),
        ('failed', 'Failed'),
        ('skipped', 'Left behind'),
    ], default='waiting', required=True, index=True)
    #: Somebody pressed "Run now": ignore the window FOR THIS ONE STEP.
    run_now = fields.Boolean()
    run_now_by = fields.Many2one('res.users', ondelete='set null')
    notified_at = fields.Datetime(
        help="When this customer's own people were told it was coming.")
    #: ⚠ STORED AS UTC AND RENDERED IN THEIR CLOCK (ledger F32). The number in
    #: this column is never the number on the screen, and the screen names the
    #: zone beside it so the two cannot be confused.
    window_start = fields.Datetime(help="When their window next opens (UTC).")
    window_end = fields.Datetime(help="When it closes (UTC).")
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    duration_s = fields.Integer()
    attempts = fields.Integer()
    result = fields.Text(help="What the update did, as it was reported.")
    error = fields.Text()
    health_verdict = fields.Text(help="What the checks found afterwards.")
    #: The lines the health gate found, and the ones it was told to ignore.
    #: ⚠ IGNORED LINES ARE RECORDED, NEVER DROPPED (ledger F25): a gate that
    #: hides what it ignored cannot be checked by anybody.
    error_lines = fields.Text()
    ignored_count = fields.Integer(default=0)

    def _json(self, field):
        self.ensure_one()
        try:
            return json.loads(getattr(self, field) or '{}')
        except ValueError:
            return {}

    def result_dict(self):
        return self._json('result')

    def health_dict(self):
        return self._json('health_verdict')

    def error_line_list(self):
        self.ensure_one()
        try:
            rows = json.loads(self.error_lines or '[]')
        except ValueError:
            return []
        return rows if isinstance(rows, list) else []
