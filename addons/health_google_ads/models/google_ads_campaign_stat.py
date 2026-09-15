# -*- coding: utf-8 -*-
"""``google.ads.campaign.stat`` — one reporting row per campaign and day.

This is the ONE place the reporting definitions of design §8 are written down,
and everything else reads them from here: the pivot, the list, the graph and
the 30-day rollups the account page shows. Two numbers that mean different
things sit side by side on purpose:

* **Google conversions** come from Google, on Google's attribution rules.
* **New enquiries** and **Submissions** come from this system's own enquiry
  book. A submission counts every accepted Google-attributed touch; a NEW
  enquiry counts only the touch that CREATED an enquiry — one merged into an
  older enquiry is a submission and not a new enquiry (the same rule
  `health_web_leads`' own daily reconciliation uses: the creating touch is the
  one whose event id is the enquiry's own submission id).

The two are not expected to agree, and no screen pretends they do.

Days come from the ADVERTISING ACCOUNT's own time zone, not the server's: a
touch at 17:30 UTC on the 14th is the 15th in `Asia/Ho_Chi_Minh`, and Google's
spend for that click is on the 15th too. The zone lives in a column, so the
conversion is `(ts AT TIME ZONE 'UTC') AT TIME ZONE <column>` — a per-row
conversion PostgreSQL happily does, unlike a literal-only cast.

`_auto = False`: the model is a SQL view, precedent
`health_base/models/health_audit_log.py`. `id` is a row number and means
nothing outside one query — never store a reference to it.
"""
from odoo import fields, models, tools

# The view kernel, as specified in the GA3 handover §4.4. It is quoted in the
# phase report; if you change it, change it there too.
VIEW_SQL = """
  WITH tz AS (
    SELECT a.id AS account_id, COALESCE(NULLIF(a.account_timezone, ''), 'UTC') AS zone
    FROM google_ads_account a
  ),
  touches AS (
    SELECT t.google_ads_account_id AS account_id,
           c.id AS campaign_id,
           ((t.occurred_at AT TIME ZONE 'UTC') AT TIME ZONE tz.zone)::date AS day,
           COUNT(*) AS submissions,
           COUNT(*) FILTER (WHERE l.id IS NOT NULL
                              AND l.external_submission_id = t.external_event_id
                              AND l.google_ads_origin IS NOT NULL) AS new_enquiries
    FROM health_lead_touchpoint t
    JOIN tz ON tz.account_id = t.google_ads_account_id
    JOIN google_ads_campaign c
      ON c.account_id = t.google_ads_account_id
     AND c.external_campaign_id = t.google_ads_campaign_id
    LEFT JOIN crm_lead l ON l.id = t.lead_id
    WHERE t.google_ads_origin IS NOT NULL
    GROUP BY 1, 2, 3
  ),
  keys AS (
    SELECT account_id, campaign_id, date AS day FROM google_ads_campaign_day
    UNION
    SELECT account_id, campaign_id, day FROM touches
  )
  SELECT row_number() OVER (ORDER BY k.account_id, k.campaign_id, k.day) AS id,
         k.account_id,
         a.company_id,
         k.campaign_id,
         k.day AS date,
         COALESCE(d.currency_id, a.currency_id) AS currency_id,
         COALESCE(d.impressions, 0) AS impressions,
         COALESCE(d.clicks, 0) AS clicks,
         COALESCE(d.spend, 0.0) AS spend,
         COALESCE(d.google_conversions, 0.0) AS google_conversions,
         COALESCE(t.new_enquiries, 0) AS new_enquiries,
         COALESCE(t.submissions, 0) AS submissions,
         (d.id IS NOT NULL) AS has_metrics
  FROM keys k
  JOIN google_ads_account a ON a.id = k.account_id
  LEFT JOIN google_ads_campaign_day d
    ON d.account_id = k.account_id AND d.campaign_id = k.campaign_id AND d.date = k.day
  LEFT JOIN touches t
    ON t.account_id = k.account_id AND t.campaign_id = k.campaign_id AND t.day = k.day
"""


class GoogleAdsCampaignStat(models.Model):
    _name = 'google.ads.campaign.stat'
    _description = 'Google Ads Report'
    _auto = False
    _order = 'date desc, campaign_id'
    _rec_name = 'campaign_id'

    account_id = fields.Many2one(
        'google.ads.account', string='Advertising Account', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', readonly=True)
    campaign_id = fields.Many2one(
        'google.ads.campaign', string='Campaign', readonly=True)
    date = fields.Date(
        string='Day', readonly=True,
        help='The day as the advertising account counts it, in its own time '
             'zone.')
    currency_id = fields.Many2one(
        'res.currency', string='Currency', readonly=True)

    impressions = fields.Integer(string='Impressions', readonly=True)
    clicks = fields.Integer(string='Clicks', readonly=True)
    spend = fields.Monetary(
        string='Spend', currency_field='currency_id', readonly=True)
    google_conversions = fields.Float(
        string='Google Conversions', readonly=True,
        help='What Google counts. It uses different rules from the enquiry '
             'count beside it and need not agree.')
    new_enquiries = fields.Integer(
        string='New Enquiries', readonly=True,
        help='Enquiries this system opened because of a Google ad. A '
             'submission added to an enquiry that already existed is not '
             'counted here.')
    submissions = fields.Integer(
        string='Form Submissions', readonly=True,
        help='Every accepted form submission that came from a Google ad, '
             'including the ones added to an enquiry that already existed.')
    has_metrics = fields.Boolean(
        string='Figures from Google', readonly=True,
        help='Whether Google has reported figures for this campaign on this '
             'day. When it has not, spend and clicks are shown as zero '
             'because nothing has been read, not because nothing was spent.')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            'CREATE OR REPLACE VIEW %s AS (%s)' % (self._table, VIEW_SQL))
