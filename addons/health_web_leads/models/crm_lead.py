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

from .health_consent import WEB_FORM_METHOD
from .lead_touchpoint import CITY_SOURCE_SELECTION
from .web_lead_service import _safe_email, _safe_phone

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

# ---------------------------------------------------------------------------
# Consent bridge outcome (W3 §4.1b)
# ---------------------------------------------------------------------------
# Set exactly once per lead, by the hook below. It is BOTH the re-fire guard
# (the hook exits the moment it is set — `_get_or_create_patient` re-fires
# from create(), from write() and from every convert action) AND the
# reporting answer to "what happened to the checkbox this visitor ticked?".
WEB_CONSENT_BRIDGE_SELECTION = [
    ('created', 'Consent record created'),
    ('skipped_existing', 'Skipped — consent already on file'),
    ('skipped_identity', 'Skipped — submitter is not the client'),
    ('skipped_declined', 'Skipped — consent not given'),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # -- Campaign detail the stock utm.mixin does not model ---------------
    utm_content = fields.Char(
        string='UTM Content', help='Ad / creative variant (raw value).')
    utm_term = fields.Char(
        string='UTM Term', help='Paid keyword, where the platform supplies it.')

    # -- Click / browser identifiers (W4 offline-conversion export) -------
    gclid = fields.Char(string='Google Click ID')
    # Google's cookie-less click ids. Under consent mode / ITP an ad click
    # frequently arrives with wbraid (web) or gbraid (app) and NO gclid at
    # all, and the offline-conversion upload accepts any of the three — so a
    # schema that stores only gclid silently loses those conversions.
    wbraid = fields.Char(string='Google Click ID (wbraid)')
    gbraid = fields.Char(string='Google Click ID (gbraid)')
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
    web_consent_bridged = fields.Selection(
        WEB_CONSENT_BRIDGE_SELECTION, string='Consent Bridge',
        copy=False, readonly=True, tracking=True,
        help='What happened to the website consent claim when this lead '
             'became a client. Set once, on the first conversion: a real '
             'health.consent record was created, or the reason none was.')

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

    # ==================================================================
    # Consent bridge (W3 §4.1c) — the checkbox becomes a real record
    # ==================================================================
    def _get_or_create_patient(self, patient_name=None, patient_vals=None,
                               force_create=False):
        """THE conversion chokepoint (`health_crm/models/crm_lead.py:1343`).

        Every lead→client path funnels through here — the two
        `_process_contact_relationship` arms, `action_convert_to_client`,
        `action_convert_to_appointment`, `_resolve_booking_client`, the
        booking wizard and the client-selection wizard — which is why the
        bridge hangs off it rather than off any single button.

        It also RETURNS PRE-EXISTING patients and re-fires from both
        `create()` and `write()`, so the hook it calls has to be idempotent
        and re-fire-safe by design, not by luck. The patient is returned
        completely unchanged: the bridge is a side effect on the LEAD and on
        `health.consent`, never on the conversion's own result.
        """
        patient = super()._get_or_create_patient(
            patient_name=patient_name, patient_vals=patient_vals,
            force_create=force_create)
        self._web_leads_bridge_consent(patient)
        return patient

    def _web_leads_bridge_consent(self, patient):
        """Materialise the web consent claim, or record why we did not.

        **Rail B1 — this can never break a conversion.** The entire ladder
        runs inside `try/except Exception`: an ops user losing their booking
        flow because a marketing consent could not be written would be a far
        worse outcome than a missing consent record, and the claim itself is
        never lost — it stays on `web_consent_marketing` for a human.

        **Rail B2** — every value is derived from the LEAD record. Nothing is
        read from the context or from `request`: the same conversion may be
        driven by an ops user, a wizard or a cron, and the evidence must not
        depend on which.
        """
        if len(self) != 1:
            return False
        try:
            return self._web_leads_bridge_consent_impl(patient)
        except Exception:  # noqa: BLE001 — rail B1, see the docstring
            _logger.warning(
                'web_leads: consent bridge failed for lead %s — the '
                'conversion is unaffected and the claim stays on the lead',
                self.id, exc_info=True)
            return False

    def _web_leads_bridge_consent_impl(self, patient):
        """The decision ladder. Each step marks `web_consent_bridged` and
        stops; the marker is what makes the next re-fire a no-op."""
        # 1. Not ours to touch. A lead with no `external_submission_id` did
        #    not come from the website, and a marked lead has been decided.
        if not patient or self.web_consent_bridged \
                or not self.external_submission_id:
            return False

        # 2. The visitor did not tick the box. No record, no chatter: the
        #    ABSENCE of consent is not an event, and a note claiming
        #    otherwise would be noise on every non-consenting lead.
        if not self.web_consent_marketing:
            self.web_consent_bridged = 'skipped_declined'
            return False

        # 3. Rail B3 — identity. A self-granted consent may only be
        #    materialised when the submitter IS the client. Someone
        #    enquiring for a relative consented for THEMSELVES; guessing a
        #    `health.client.relation` from a contact form would be the
        #    identity anti-pattern this pipeline exists to avoid (W1 §2).
        if not self._web_leads_identity_matches(patient):
            self.web_consent_bridged = 'skipped_identity'
            self.message_post(body=Markup('<p>%s</p>') % _(
                'Website marketing consent was NOT materialised: the '
                'contact details on this lead do not match the client '
                '%(client)s, so the person who ticked the box is not the '
                'person the consent would cover. Capture consent from the '
                'client directly if it is needed.',
                client=patient.name or ''))
            return False

        Consent = self.env['health.consent'].sudo()
        if not Consent._web_form_method_available():
            _logger.warning(
                'web_leads: the health.consent `web_form` method is not in '
                'the registry — skipping the bridge for lead %s', self.id)
            return False

        # 4. Idempotency. `client_mutation_id` carries a UNIQUE index and is
        #    pre-checked in `health.consent.create()` — it is the designed
        #    key, so use it rather than inventing a second one.
        #    `active_test=False`: an ARCHIVED consent still occupies the
        #    index (ledger §5.27), and the core pre-check would miss it.
        mutation_id = self._web_leads_mutation_id()
        if Consent.with_context(active_test=False).search_count(
                [('client_mutation_id', '=', mutation_id)]):
            self.web_consent_bridged = 'created'
            return False

        # 5. Rail B4 — skip, never supersede. `action_grant()` withdraws any
        #    other active consent of the same (client, type); a checkbox
        #    claim must never do that to a record a staff member captured
        #    deliberately. Checked BEFORE granting, so the supersede branch
        #    is simply never reached. The search is deliberately the ORDINARY
        #    one: `check_consent` cannot see an archived row either, so an
        #    archived consent is not "already on file" for anybody.
        existing = Consent.search(
            [('client_id', '=', patient.id),
             ('consent_type', '=', 'marketing'),
             ('state', '=', 'active')], limit=1)
        if existing:
            self.web_consent_bridged = 'skipped_existing'
            self.message_post(body=Markup('<p>%s</p>') % _(
                'Website marketing consent was NOT materialised: %(client)s '
                'already holds an active marketing consent (%(ref)s), which '
                'an automated claim must never supersede.',
                client=patient.name or '', ref=existing.name or ''))
            return False

        # 6. Create + grant. Ledger §5.55: the savepoint (not the try) is
        #    what keeps the surrounding transaction usable if a constraint
        #    or the unique index refuses — a caught IntegrityError leaves
        #    PostgreSQL aborted without one, and the conversion would then
        #    fail on its own next statement.
        occurred_at = self._web_leads_submission_datetime()
        with self.env.cr.savepoint():
            consent = Consent.create({
                'client_id': patient.id,
                'consent_type': 'marketing',
                'method': WEB_FORM_METHOD,
                'self_granted': True,
                'effective_date': self._web_leads_effective_date(occurred_at),
                'scope_note': self._web_leads_scope_note(occurred_at),
                'client_mutation_id': mutation_id,
            })
            consent.action_grant()

        self.web_consent_bridged = 'created'
        consent.message_post(body=Markup('<p>%s</p>') % _(
            'Created from website lead %(ref)s — the visitor ticked the '
            'marketing consent box on submission %(submission)s.',
            ref=self.unique_contact_code or self.id,
            submission=self.external_submission_id))
        self.message_post(body=Markup('<p>%s</p>') % _(
            'Website marketing consent materialised as %(ref)s for '
            '%(client)s.', ref=consent.name or '', client=patient.name or ''))
        return True

    def _web_leads_mutation_id(self):
        """The idempotency key: one consent per (lead, submission)."""
        return 'web-lead-%d-%s' % (self.id, self.external_submission_id)

    def _web_leads_identity_matches(self, patient):
        """Is the person who submitted the form the client themselves?

        Phone comparison is on the last 9 digits of the NORMALIZED number
        (`_safe_phone`, ledger §5.15 — the raw helper raises on garbage), so
        `+84901234567`, `0901234567` and `84901234567` are one person. Email
        comparison is exact on the lowercased address. `crm.lead` has no
        `mobile` field (ledger §5.16) but `res.partner` has both, so both
        sides of the patient record are checked.
        """
        lead_phone = _safe_phone(self.phone)
        if lead_phone:
            tail = lead_phone[-9:]
            for value in (patient.phone, patient.mobile):
                normalized = _safe_phone(value)
                if normalized and normalized[-9:] == tail:
                    return True
        lead_email = _safe_email(self.email_from)
        if lead_email and _safe_email(patient.email) == lead_email:
            return True
        return False

    def _web_leads_submission_datetime(self):
        """When the visitor actually acted.

        The form_submit touchpoint that CREATED this lead carries the
        visitor's own timestamp (`occurred_at`, never `received_at` — a
        queued relay delivers late). Falls back to the lead's creation.
        """
        touch = self.env['health.lead.touchpoint'].sudo().search(
            [('lead_id', '=', self.id),
             ('touchpoint_type', '=', 'form_submit'),
             ('external_event_id', '=', self.external_submission_id)],
            order='occurred_at asc, id asc', limit=1)
        return touch.occurred_at or self.create_date \
            or fields.Datetime.now()

    def _web_leads_effective_date(self, occurred_at):
        """The submission date, but never in the future.

        `submitted_at` is sender-controlled: a broken (or malicious) relay
        that back-dates is harmless, but one that FORWARD-dates would write
        a consent `check_consent` refuses to see until that day arrives —
        a silently inert record. Clamp to today.
        """
        today = fields.Date.context_today(self)
        submitted = fields.Date.to_date(occurred_at) or today
        return min(submitted, today)

    def _web_leads_scope_note(self, occurred_at):
        """The evidence line — what was shown, for which submission, when.

        This is the only durable record of WHICH consent wording the visitor
        agreed to, and `health.consent` locks it the moment the consent
        leaves draft, so it is written once and correctly.
        """
        return _(
            'Website marketing consent checkbox (text version %(version)s), '
            'submission %(submission)s, submitted %(when)s UTC.',
            version=self.web_consent_text_version or _('unversioned'),
            submission=self.external_submission_id,
            when=fields.Datetime.to_string(occurred_at))

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
