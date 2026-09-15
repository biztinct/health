# -*- coding: utf-8 -*-
{
    'name': 'Health Google Ads',
    'summary': 'Google Ads acquisition: attribution and reporting',
    'description': """
Google Ads in the Channel Connection Center — Phase GA1
=======================================================

The clinic advertises on Google. Before this module a visitor who clicked a
Google ad and filled in the website contact form became a CRM enquiry that
looked exactly like an organic one: the click id was stored only when it was
the ``gclid`` kind, the two cookie-less kinds (``wbraid`` / ``gbraid``) were
dropped, and nothing recorded which advertising account, campaign or ad the
enquiry came from.

What GA1 ships:

* **A Google Ads card in the Channel Connection Center**, after Facebook, that
  tells the truth about three capabilities — *Website leads*, *Campaign
  reporting* (later phases make it real; GA1 shows "Not connected") and
  *Google lead forms* ("Unavailable for healthcare ads": Google's lead-form
  policy forbids healthcare advertisers, and a checkbox cannot override it).
  It is an ACQUISITION card, never a chat channel — no
  ``care.channel.connection`` row, no reply transport, ``sendable=False``.
* **Attribution that survives**: every Google-attributed website enquiry keeps
  all three click ids, the customer / campaign / ad-group / creative ids the
  ad's final-URL suffix carried, which configured advertising account it
  matched (or "unmatched"), and whether Google Ads was the FIRST source of the
  enquiry or only a later touch.
* **A server-side proof** — "Test the website pipeline" runs one synthetic
  Google-attributed submission through the real handler, inspects the result,
  rolls it back, and records the evidence with a timestamp. It creates
  nothing.
* Company-safe account matching, first-touch immutability, CRM filters
  ("First source Google Ads" / "Google Ads influenced"), English + Vietnamese.

Binding non-goals of this phase: no Google API call of any kind (no OAuth, no
developer token, no reporting fetch — ``reporting_state`` stays
``not_connected``), no Google-hosted lead-form ingestion and no public route
for one, no change to the website credential model, and no campaign
auto-create (``utm.campaign`` stays find-only).

Design: docs/strategy/google-ads-channel-design.md
Handover: docs/strategy/handovers/google-ads-phaseGA1.md
""",
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'author': 'Biztinct',
    'website': 'https://carejiox.com',
    'depends': [
        # The website pipeline this module hooks into: `web.lead.service`'s
        # two extension seams, `crm.lead`'s click-id columns and
        # `health.lead.touchpoint`. Brings health_base / health_crm /
        # health_cms_sidebar / health_landing in transitively.
        'health_web_leads',
        # The Channel Connection Center: `care.channel.connection.
        # _center_extra_cards()` is the seam the card rides on.
        'health_care_command_channels',
    ],
    'data': [
        'security/google_ads_security.xml',
        'security/ir.model.access.csv',
        'views/google_ads_account_views.xml',
        'views/crm_lead_views.xml',
        'views/lead_touchpoint_views.xml',
        # after the views: the sidebar item references the actions by xmlid
        'data/cms_sidebar_items_google_ads.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_google_ads/static/src/center/google_ads_center.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
