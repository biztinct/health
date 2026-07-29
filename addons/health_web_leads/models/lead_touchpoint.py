# -*- coding: utf-8 -*-
"""``health.lead.touchpoint`` — one row per interaction behind a lead.

Attribution model (design §4): the LEAD's own fields are the FIRST touch,
frozen at creation; every touch (the creating one included) is a touchpoint
row; the LAST touch is the newest row. No duplicated first_*/last_* pairs.

`occurred_at` is the moment the visitor acted (WordPress `submitted_at`),
never the moment we received it — the relay's retry queue delivers late by
design, and reconciliation needs the skew visible (`received_at`).
"""
from odoo import api, fields, models

# Shared by the touchpoint and by ``crm.lead.city_source`` — the two must not
# drift, so both read this one list.
CITY_SOURCE_SELECTION = [
    ('form_location', 'Form Location Field'),
    ('form_id', 'Form ID Map'),
    ('page_url', 'Page URL Map'),
    ('campaign_prefix', 'Campaign Prefix'),
    ('clicked_phone', 'Clicked Phone Number'),
    ('zalo_oa', 'Zalo Official Account'),
    ('facebook_page', 'Facebook Page'),
    ('manual', 'Set Manually'),
    ('unknown', 'Unknown'),
]

# `click_to_call` / `zalo_click` / `messenger_click` / `call_cdr` are DECLARED
# here and written by nothing in W1 — they are the reserved vocabulary for the
# channel phases (VoIP24h CDR, Zalo OA, Messenger) so those phases add rows,
# not a migration.
TOUCHPOINT_TYPE_SELECTION = [
    ('form_submit', 'Website Form Submission'),
    ('manual', 'Manual Entry'),
    ('click_to_call', 'Click to Call'),
    ('zalo_click', 'Zalo Click'),
    ('messenger_click', 'Messenger Click'),
    ('call_cdr', 'Call Record (CDR)'),
]

SOURCE_SYSTEM_SELECTION = [
    ('wordpress', 'WordPress Website'),
    ('manual', 'Manual Entry'),
]


class HealthLeadTouchpoint(models.Model):
    _name = 'health.lead.touchpoint'
    _description = 'Lead Touchpoint'
    _order = 'occurred_at desc, id desc'

    lead_id = fields.Many2one(
        'crm.lead', string='Lead', required=True, index=True,
        ondelete='cascade')

    occurred_at = fields.Datetime(
        string='Occurred At', required=True, index=True,
        help='When the visitor acted (the website submission time), never the '
             'time we received it — a queued relay delivers late.')
    received_at = fields.Datetime(
        string='Received At', default=fields.Datetime.now,
        help='When this system accepted the touch. The gap to Occurred At is '
             'the relay skew.')

    touchpoint_type = fields.Selection(
        TOUCHPOINT_TYPE_SELECTION, string='Touchpoint Type', required=True,
        index=True)
    source_system = fields.Selection(
        SOURCE_SYSTEM_SELECTION, string='Source System')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='City',
        help="This touch's own city verdict. It never overwrites the lead's "
             'stored city — a disagreement raises City Conflict instead.')
    city_source = fields.Selection(
        CITY_SOURCE_SELECTION, string='City Source')

    utm_source = fields.Char(string='UTM Source')
    utm_medium = fields.Char(string='UTM Medium')
    utm_campaign = fields.Char(string='UTM Campaign')
    utm_content = fields.Char(string='UTM Content')
    utm_term = fields.Char(string='UTM Term')

    gclid = fields.Char(string='Google Click ID')
    fbclid = fields.Char(string='Facebook Click ID')

    page_url = fields.Char(string='Page URL')
    referrer_url = fields.Char(string='Referrer URL')

    external_event_id = fields.Char(
        string='External Event ID', copy=False, index=True,
        help='The sending system\'s id for this event (the WordPress '
             'submission UUID for a form submit) — the idempotency key.')

    raw_payload = fields.Text(
        string='Raw Payload',
        help='The original submission, capped at 8 KB. Behind ACLs; never '
             'logged.')

    @api.depends('touchpoint_type', 'occurred_at')
    def _compute_display_name(self):
        """The model has no `name`, so without this every breadcrumb, m2o
        label and log line reads `health.lead.touchpoint,97`.

        The type label comes from `fields_get`, which returns the TRANSLATED
        selection — so the name follows the reader's language for free and
        costs the catalogue no new msgid.
        """
        labels = dict(self.fields_get(
            ['touchpoint_type'])['touchpoint_type']['selection'])
        for touch in self:
            parts = [labels.get(touch.touchpoint_type) or '']
            if touch.occurred_at:
                parts.append(fields.Datetime.to_string(touch.occurred_at))
            touch.display_name = ' · '.join(p for p in parts if p) \
                or str(touch.id or '')

    def init(self):
        # Ledger §5.1 — `_sql_constraints` are NOT materialized on Odoo 19.
        # Search-first is the normal dedupe path; this partial unique index is
        # the concurrency backstop for two relay deliveries racing.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_lead_touchpoint_ext_uidx
            ON health_lead_touchpoint (touchpoint_type, external_event_id)
            WHERE external_event_id IS NOT NULL
        """)
