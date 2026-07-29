# -*- coding: utf-8 -*-
"""`crm.lead` web-attribution extension (design §4.1).

Everything here is ADDITIVE. The existing healthcare fields the pipeline
writes — `mode_of_contact`, `contact_source`, `healthcare_lead_source`,
`vietnamese_channel`, `catchment_province_id`, `contact_status`,
`is_spam_caller`, `description` — and the stock `utm.mixin` m2o fields
(`source_id`/`medium_id`/`campaign_id`) are REUSED, never recreated.
"""
import logging
import re

from markupsafe import Markup

from odoo import _, api, fields, models

from .lead_touchpoint import CITY_SOURCE_SELECTION

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# The web-lead email marker (design §11 / W2 §4.4)
# ---------------------------------------------------------------------------
# THE CONTRACT, verbatim, as the WordPress plugin must implement it:
#
#   * the CF7 notification email carries, as its FINAL body line,
#         [web-lead:<submission_id>]
#   * and, where the mail transport allows it, the header
#         X-Web-Lead-Submission: <submission_id>
#   * `<submission_id>` is the SAME uuid the webhook payload carries. The
#     plugin generates it once at `wpcf7_before_send_mail` so both the email
#     and the webhook see it.
#
# Without this, connecting an inbound mailbox to the `crm.lead` aliases would
# create a SECOND lead for every submission that also produced a webhook —
# the notification email and the API call describe the same enquiry.
MARKER_HEADER = 'X-Web-Lead-Submission'
MARKER_RE = re.compile(r'\[web-lead:([A-Za-z0-9-]{8,64})\]')
MARKER_VALUE_RE = re.compile(r'^[A-Za-z0-9-]{8,64}$')


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

    # ------------------------------------------------------------------
    # Inbound email: never a second lead for a submission we already have
    # ------------------------------------------------------------------
    def message_new(self, msg_dict, custom_values=None):
        """Route a marked CF7 notification email onto its existing lead.

        Core `mail.thread.message_new` CREATES the record for alias mail;
        returning an EXISTING record instead makes `message_process` post the
        email onto that record and create nothing (mail_thread.py:1496).

        This is the guard that makes connecting an inbound mailbox SAFE. It
        is deliberately live before any mailbox is connected — on vietuat
        there is no `mail.alias.domain` and no fetchmail server today, so
        nothing reaches the five `crm.lead` aliases yet, and the day someone
        wires one up the duplicate door is already shut.

        An unknown or absent marker falls through to `super()`: this is a
        narrow de-duplicator, not a replacement gateway.
        """
        marker = self._web_lead_marker(msg_dict)
        if marker:
            lead = self.sudo().search(
                [('external_submission_id', '=', marker)], limit=1)
            if lead:
                lead.sudo().message_post(body=Markup('<p>%s</p>') % _(
                    'Notification email for website submission %s matched '
                    'this lead by its marker — the email was filed here '
                    'instead of creating a second lead.', marker))
                return self.browse(lead.id)
        return super().message_new(msg_dict, custom_values=custom_values)

    @api.model
    def _web_lead_marker(self, msg_dict):
        """Extract the submission id from an inbound message, or False.

        NEVER raises: a malformed marker is the same thing as no marker, and
        an exception here would break the whole mail gateway for every model
        sharing this create path.

        The header is checked first, but note that Odoo's stock
        `message_parse` does NOT copy custom headers into `msg_dict`
        (mail_thread.py:1765-1874 builds a fixed key set) — so on an
        unmodified deployment the BODY line is the path that actually fires.
        The header branch costs nothing and is what makes the contract work
        if a future parser hook does keep headers.
        """
        try:
            if not isinstance(msg_dict, dict):
                return False
            wanted = MARKER_HEADER.lower()
            for key, value in msg_dict.items():
                if isinstance(key, str) and key.lower() == wanted:
                    candidate = str(value or '').strip()
                    if MARKER_VALUE_RE.match(candidate):
                        return candidate
            for key in ('body', 'subject'):
                match = MARKER_RE.search(str(msg_dict.get(key) or ''))
                if match:
                    return match.group(1)
        except Exception:  # noqa: BLE001 — a bad marker must never break mail
            _logger.warning('web_leads: marker extraction failed',
                            exc_info=True)
        return False

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
