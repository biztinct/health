# -*- coding: utf-8 -*-
"""``google.ads.backfill.wizard`` — "fetch older days", bounded.

The rolling window is 30 days. An operator who wants more asks for it here, and
the request is a QUEUE rather than a fetch: the scheduled job walks backwards
in batches of 30, at most three batches per run. Asking Google for a year of
history in one request is how an integration gets rate-limited on the day it is
switched on.

The number of days is clamped to :data:`BACKFILL_MAX_DAYS`, and the
notification says so when it had to clamp — a silently shortened request would
read as missing data later.
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .google_ads_sync import BACKFILL_MAX_DAYS


class GoogleAdsBackfillWizard(models.TransientModel):
    _name = 'google.ads.backfill.wizard'
    _description = 'Google Ads: Fetch Older Days'

    account_id = fields.Many2one(
        'google.ads.account', string='Advertising Account', required=True,
        ondelete='cascade')
    days = fields.Integer(
        string='How many days back', default=90,
        help='Older days are fetched in batches of 30 over the next scheduled '
             'runs, so nothing is asked of Google all at once.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            account = self.env['google.ads.account'].browse(
                vals.get('account_id') or [])
            if account:
                account._check_operator()
        return super().create(vals_list)

    def action_apply(self):
        self.ensure_one()
        account = self.account_id
        if not account:
            raise UserError(_('Choose an advertising account first.'))
        account._check_operator()
        account._check_company_scope()
        asked = int(self.days or 0)
        days = max(1, min(asked, BACKFILL_MAX_DAYS))
        today = account.sudo()._sync_today()
        window_from = account.sudo()._sync_window(today)[0]
        oldest = today - timedelta(days=days)
        account._internal().write({
            'backfill_until': oldest,
            'backfill_cursor': window_from,
        })
        cron = account.sudo()._sync_cron()
        if cron:
            cron.sudo()._trigger()
        message = _(
            'Older days will be fetched in batches of 30 over the next runs, '
            'back to %s.', fields.Date.to_string(oldest))
        if days != asked:
            message = '%s\n\n%s' % (message, _(
                'This system holds at most %s days of history, so that is '
                'what was asked for.', BACKFILL_MAX_DAYS))
        return account._with_reload(account._notify(
            _('Google Ads: older days queued'), message))
