# -*- coding: utf-8 -*-
"""``google.ads.campaign.day`` — the daily campaign cache.

One row per (advertising account, campaign, ACCOUNT-LOCAL day). It is written
by the sync engine and by nothing else: the ACL gives create/write/unlink to
``base.group_system`` only and the sync runs elevated.

Two numeric postures are load-bearing:

* **`cost_micros` is a string.** Google sends an int64 in micros; a
  nineteen-digit value is past ``2**53`` and past int4, so the exact figure is
  kept as text and ``spend`` is DERIVED from it through ``decimal.Decimal``
  (rail R3). ``spend`` is a float column and is exact for any spend below
  roughly 9×10¹⁵ micros — the field help says so rather than implying more.
* **`impressions` / `clicks` are int4** (ledger §5.80 — an Odoo
  ``fields.Integer`` is an int4 and a value past ``2**31`` raises
  ``NumericValueOutOfRange`` at flush time, which then poisons every later
  statement in the transaction and errors tests that name none of it). A value
  that would not fit is stored at the ceiling and ``overflow`` is set, so the
  screen can say the number is a floor rather than quietly lying.
"""
import logging
import re
from decimal import Decimal, InvalidOperation

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# int4. Not a "big number" — the exact PostgreSQL ceiling (§5.80).
INT4_MAX = 2 ** 31 - 1

# What a valid `cost_micros` looks like: unsigned digits, int64-shaped.
MICROS_RE = re.compile(r'^\d{1,20}$')

_MICRO = Decimal(10) ** 6


def micros_to_amount(raw):
    """``'1230000'`` → ``1.23``. Anything malformed reads 0.0.

    Through ``Decimal`` rather than ``int(raw) / 1e6``: the division is the
    only place precision can be lost, and a nineteen-digit micro value divided
    as a float loses the last digits before anyone can see it.
    """
    text = str(raw or '').strip()
    if not MICROS_RE.match(text):
        return 0.0
    try:
        return float(Decimal(text) / _MICRO)
    except (InvalidOperation, ValueError):
        return 0.0


class GoogleAdsCampaignDay(models.Model):
    _name = 'google.ads.campaign.day'
    _description = 'Google Ads Campaign Day'
    _order = 'account_id, date desc, campaign_id, id'
    _rec_names_search = ['campaign_id']

    account_id = fields.Many2one(
        'google.ads.account', string='Advertising Account',
        required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Company', related='account_id.company_id',
        store=True, index=True)
    campaign_id = fields.Many2one(
        'google.ads.campaign', string='Campaign',
        required=True, index=True, ondelete='cascade')
    date = fields.Date(
        string='Day', required=True, index=True,
        help='The day as the advertising account itself counts it, in its own '
             'time zone — not this system\'s.')

    currency_id = fields.Many2one(
        'res.currency', string='Currency', readonly=True,
        help='Copied from the advertising account when the figures were read. '
             'Amounts are never added up across currencies.')

    impressions = fields.Integer(string='Impressions', default=0)
    clicks = fields.Integer(string='Clicks', default=0)
    overflow = fields.Boolean(
        string='Counted at the ceiling', default=False,
        help='Set when a count from Google was larger than this system can '
             'hold, so the number shown is a floor rather than the exact '
             'figure.')

    cost_micros = fields.Char(
        string='Spend (millionths)', default='0',
        help='The exact figure Google sent, in millionths of the account '
             'currency, kept as text so no digit is lost.')
    spend = fields.Monetary(
        string='Spend', currency_field='currency_id',
        compute='_compute_spend', store=True, readonly=True,
        help='Worked out from the exact figure Google sent. It is exact for '
             'any spend below about 9 thousand million in the account '
             'currency.')
    google_conversions = fields.Float(
        string='Google Conversions', default=0.0,
        help='What Google counts as a conversion. It uses different rules '
             'from this system\'s own enquiry count and need not agree.')

    synced_at = fields.Datetime(string='Read from Google at', readonly=True)

    # ==================================================================
    @api.depends('campaign_id', 'date')
    def _compute_display_name(self):
        """"Hà Nội — Search — 2026-09-15", never "google.ads.campaign.day,12".

        A model with no `name` field falls back to `<model>,<id>` wherever it
        is referenced, and a table name is a word from the code, not a word a
        clinic should ever read.
        """
        for row in self:
            parts = [row.campaign_id.name or '',
                     fields.Date.to_string(row.date) if row.date else '']
            row.display_name = ' — '.join(p for p in parts if p) or '-'

    @api.depends('cost_micros')
    def _compute_spend(self):
        for row in self:
            row.spend = micros_to_amount(row.cost_micros)

    # ==================================================================
    @api.model
    def _clamp_counters(self, vals):
        """int4 ceiling, in the model rather than in the caller (§5.80).

        `overflow` is only ever set True here — never cleared — so a caller
        that writes one clamped value and one ordinary one cannot accidentally
        un-flag the row.
        """
        for name in ('impressions', 'clicks'):
            if name not in vals:
                continue
            try:
                value = int(vals[name] or 0)
            except (TypeError, ValueError):
                value = 0
            if value > INT4_MAX or value < -INT4_MAX:
                vals[name] = INT4_MAX
                vals['overflow'] = True
                _logger.warning(
                    'google_ads: %s of %s exceeds int4 — stored at the '
                    'ceiling', name, value)
            else:
                vals[name] = value
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._clamp_counters(vals)
        return super().create(vals_list)

    def write(self, values):
        return super().write(self._clamp_counters(dict(values)))

    def init(self):
        init = getattr(super(), 'init', None)
        if callable(init):
            init()
        # Ledger §5.1 — `_sql_constraints` are NOT materialized on Odoo 19,
        # and this uniqueness is the contract the sync's upsert depends on.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS google_ads_campaign_day_uidx
            ON google_ads_campaign_day (account_id, campaign_id, date)
        """)
