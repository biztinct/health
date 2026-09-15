# -*- coding: utf-8 -*-
"""``google.ads.sync.run`` — the honesty log for campaign reporting.

Every attempt to read Google leaves a row here, including the ones that read
nothing and the ones that never started. That is the whole point: a screen that
shows a spend figure has to be able to say WHEN it was last true, and a figure
that is stale for a reason nobody recorded is indistinguishable from a figure
that is current.

The row is created BEFORE the fetch, so a worker that dies mid-run still leaves
an attempt behind rather than a silence.
"""
from odoo import api, fields, models

SYNC_KIND_SELECTION = [
    ('scheduled', 'Daily'),
    ('manual', 'Asked for'),
    ('initial', 'First read'),
    ('backfill', 'Older days'),
]

SYNC_STATE_SELECTION = [
    ('success', 'Read'),
    ('failed', 'Failed'),
    ('skipped_locked', 'Skipped — already running'),
    ('skipped_reconnect', 'Skipped — sign-in needed'),
]


class GoogleAdsSyncRun(models.Model):
    _name = 'google.ads.sync.run'
    _description = 'Google Ads Sync Run'
    _order = 'id desc'

    account_id = fields.Many2one(
        'google.ads.account', string='Advertising Account',
        required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Company', related='account_id.company_id',
        store=True, index=True)

    kind = fields.Selection(
        SYNC_KIND_SELECTION, string='Why', required=True,
        default='scheduled')
    state = fields.Selection(
        SYNC_STATE_SELECTION, string='Result', required=True,
        default='failed',
        help='Created as Failed on purpose: a run that stops halfway leaves '
             'the honest answer behind rather than nothing at all.')

    window_from = fields.Date(string='From')
    window_to = fields.Date(string='To')
    started_at = fields.Datetime(string='Started')
    finished_at = fields.Datetime(string='Finished')

    attempts = fields.Integer(string='Attempts', default=0)
    campaigns_seen = fields.Integer(string='Campaigns Seen', default=0)
    rows_written = fields.Integer(string='Days Written', default=0)
    rows_removed = fields.Integer(string='Days Removed', default=0)

    error_code = fields.Char(string='Error Code')
    detail_redacted = fields.Char(
        string='Detail',
        help='What went wrong, in plain words. Never a password or a token.')
    request_id = fields.Char(
        string='Google Request ID',
        help='Google\'s own reference for the request. It is the one raw '
             'value kept, so a support question can be answered.')

    @api.depends('kind', 'started_at')
    def _compute_display_name(self):
        """"First read — 15/09/2026 19:17", never "google.ads.sync.run,473".

        A model with no `name` field falls back to `<model>,<id>` in every
        breadcrumb and every link, and a table name on a clinic's screen is a
        word from the code, not a word from the product.
        """
        labels = dict(self._fields['kind']._description_selection(self.env))
        for run in self:
            # In the READER's time zone, so the title and the Started field
            # underneath it cannot disagree by seven hours.
            stamp = fields.Datetime.to_string(
                fields.Datetime.context_timestamp(run, run.started_at)) \
                if run.started_at else ''
            parts = [labels.get(run.kind) or '', stamp]
            run.display_name = ' — '.join(p for p in parts if p) or '-'
