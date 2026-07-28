# -*- coding: utf-8 -*-
"""`crm.lead` web-attribution extension (design §4.1).

Everything here is ADDITIVE. The existing healthcare fields the pipeline
writes — `mode_of_contact`, `contact_source`, `healthcare_lead_source`,
`vietnamese_channel`, `catchment_province_id`, `contact_status`,
`is_spam_caller`, `description` — and the stock `utm.mixin` m2o fields
(`source_id`/`medium_id`/`campaign_id`) are REUSED, never recreated.
"""
from odoo import fields, models

from .lead_touchpoint import CITY_SOURCE_SELECTION


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # -- Campaign detail the stock utm.mixin does not model ---------------
    utm_content = fields.Char(
        string='UTM Content', help='Ad / creative variant (raw value).')
    utm_term = fields.Char(
        string='UTM Term', help='Paid keyword, where the platform supplies it.')

    # -- Click / browser identifiers (W4 offline-conversion export) -------
    gclid = fields.Char(string='Google Click ID')
    fbclid = fields.Char(string='Facebook Click ID')
    fbc = fields.Char(string='Meta Click Cookie (_fbc)')
    fbp = fields.Char(string='Meta Browser Cookie (_fbp)')
    ga_client_id = fields.Char(string='GA Client ID')

    # -- Where the visit happened -----------------------------------------
    web_landing_url = fields.Char(string='Landing URL')
    web_submit_page_url = fields.Char(string='Submit Page URL')
    web_referrer_url = fields.Char(string='Referrer URL')
    web_form_id = fields.Char(
        string='Web Form ID', help='Contact Form 7 form id, e.g. 15838.')

    external_submission_id = fields.Char(
        string='External Submission ID', copy=False, readonly=True,
        index=True,
        help='The sending system\'s submission UUID. Idempotency key: a '
             'replayed delivery finds this lead instead of creating a second.')

    # -- City derivation provenance ---------------------------------------
    city_source = fields.Selection(
        CITY_SOURCE_SELECTION, string='City Source',
        help='How the city on this lead was derived.')
    city_conflict = fields.Boolean(
        string='City Conflict',
        help='A later touchpoint disagreed with the stored city. The stored '
             'city is never auto-changed — a human decides.')
    web_needs_review = fields.Boolean(
        string='Needs Web Review', index=True,
        help='Ops review flag: unusable phone, unknown city, city conflict, '
             'a shared phone number or a possible existing client.')

    # -- Consent claim carried by the form --------------------------------
    web_consent_marketing = fields.Boolean(
        string='Marketing Consent (Web)',
        help='The consent checkbox claim as submitted. Materialised as a '
             'health.consent record on conversion (Phase W3).')
    web_consent_text_version = fields.Char(
        string='Consent Text Version',
        help='Which consent wording the visitor was shown.')

    web_touchpoint_ids = fields.One2many(
        'health.lead.touchpoint', 'lead_id', string='Web Touchpoints')

    def init(self):
        # `crm.lead` ships no `init()` of its own today (verified), but this is
        # an inherited model — chain anyway so a future base implementation is
        # not silently dropped.
        init = getattr(super(), 'init', None)
        if callable(init):
            init()
        # Ledger §5.1. The partial unique index is the concurrency backstop
        # behind the handler's search-first idempotency check; the two btree
        # indexes serve the dedup lookups, which are exact `=` matches on the
        # normalized values.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS crm_lead_external_submission_uidx
            ON crm_lead (external_submission_id)
            WHERE external_submission_id IS NOT NULL
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS crm_lead_phone_idx ON crm_lead (phone)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS crm_lead_email_from_idx
            ON crm_lead (email_from)
        """)
