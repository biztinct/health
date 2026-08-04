# -*- coding: utf-8 -*-
"""``health.lead.touchpoint`` — one row per interaction behind a lead.

Attribution model (design §4): the LEAD's own fields are the FIRST touch,
frozen at creation; every touch (the creating one included) is a touchpoint
row; the LAST touch is the newest row. No duplicated first_*/last_* pairs.

`occurred_at` is the moment the visitor acted (WordPress `submitted_at`),
never the moment we received it — the relay's retry queue delivers late by
design, and reconciliation needs the skew visible (`received_at`).
"""
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

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

# ---------------------------------------------------------------------------
# Unmatched-campaign review (W3 §4.2)
# ---------------------------------------------------------------------------
# The find-only campaign policy (design §9.3) deliberately leaves a raw
# `utm_campaign` string on the touchpoint when no `utm.campaign` matched —
# blanket auto-create from attacker-controllable URL input is a
# record-explosion vector. This domain is the review queue that policy
# implies, and the merge path never calls `_utm_ids` at all
# (`web_lead_service.py:540-558`), so a campaign seeded LATER never
# back-fills by itself. Hence the action below.
# `lead_id != False` is load-bearing since touchpoints became lead-optional:
# without it a chat touch with no lead reads `lead_id.campaign_id = False` as
# TRUE and floods the review queue with rows that have no lead to link a
# campaign onto.
UNMATCHED_CAMPAIGN_DOMAIN = [('utm_campaign', '!=', False),
                             ('lead_id', '!=', False),
                             ('lead_id.campaign_id', '=', False)]

# Who may retro-link a campaign onto a lead. The W2.5 operator trio plus the
# stock sales administrator, which is the group the live ops persona (uid 40)
# actually carries — verified on vietuat rather than assumed.
LINK_CAMPAIGN_GROUPS = (
    'base.group_system',
    'health_user_admin.group_health_user_admin',
    'health_crm.group_health_crm_manager',
    'sales_team.group_sale_manager',
)

# An unselected sweep is bounded. Past the cap the action reports what it
# left behind rather than pretending it finished (no silent truncation).
LINK_CAMPAIGN_SWEEP_CAP = 500


class HealthLeadTouchpoint(models.Model):
    _name = 'health.lead.touchpoint'
    _description = 'Lead Touchpoint'
    _order = 'occurred_at desc, id desc'

    # OPTIONAL since the channel-attribution work (client requirement 3).
    # A Messenger or Zalo contact carries a click id and an ad id from the
    # first message, which is long before anyone decides it is a lead. Forcing
    # a lead here would have meant either creating speculative leads or
    # throwing the attribution away — and the click id is exactly what cannot
    # be recovered later. Exactly one of lead_id / conversation_id is required;
    # see `_check_attached`.
    lead_id = fields.Many2one(
        'crm.lead', string='Lead', index=True, ondelete='cascade')
    conversation_id = fields.Many2one(
        'care.conversation', string='Conversation', index=True,
        ondelete='cascade',
        help='The Care Command conversation this touch belongs to, when it '
             'arrived on a chat or call channel rather than a web form.')

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
    # Google's cookie-less click ids. Since consent-mode/ITP, an ad click
    # frequently arrives with wbraid (web) or gbraid (app) INSTEAD of gclid,
    # and the offline-conversion upload accepts any of the three — so storing
    # only gclid loses those conversions outright.
    wbraid = fields.Char(string='Google Click ID (wbraid)')
    gbraid = fields.Char(string='Google Click ID (gbraid)')

    # Chat-channel attribution (client requirement 3). Messenger and Zalo have
    # no click id at all: a Click-to-Messenger ad delivers a `ref` payload and
    # an ad id on the conversation's FIRST event, and that is the only moment
    # it is ever available.
    ad_id = fields.Char(string='Ad ID')
    ad_account_id = fields.Char(string='Ad Account ID')
    referral_ref = fields.Char(
        string='Referral Ref',
        help='The provider\'s own tracking payload for how this conversation '
             'started — the m.me/ad `ref` string, or Zalo\'s equivalent.')
    referral_source = fields.Char(
        string='Referral Source',
        help='How the provider says the conversation started (ADS, SHORTLINK, '
             'CUSTOMER_CHAT_PLUGIN, …).')
    entry_point = fields.Char(string='Entry Point')

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

    @api.constrains('lead_id', 'conversation_id')
    def _check_attached(self):
        """A touchpoint must belong to something.

        `lead_id` stopped being `required` so chat channels can record
        attribution before a lead exists, but an orphan touch is unreachable
        from every surface in the system and would silently accumulate.
        """
        for touch in self:
            if not touch.lead_id and not touch.conversation_id:
                raise ValidationError(_(
                    'A touchpoint must belong to a lead or a conversation.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # `@api.constrains` only fires for fields PRESENT in the create vals,
        # so a create that mentions neither anchor slipped past it entirely —
        # which is exactly the orphan the constraint exists to stop. Re-run it
        # unconditionally on create; this replaces the `required=True` that
        # used to make the case impossible.
        records._check_attached()
        return records

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

    # ------------------------------------------------------------------
    # Campaign back-fill (W3 §4.2)
    # ------------------------------------------------------------------
    def _check_link_campaigns_allowed(self):
        """Defense in depth: the button carries `groups=`, the method checks.

        A view attribute hides the button; it does not stop an RPC. Since
        the body runs `sudo()` (below), the gate here is the only thing
        between a plain internal user and a write on somebody else's lead.
        """
        user = self.env.user
        if self.env.su or user._is_admin():
            return
        for group in LINK_CAMPAIGN_GROUPS:
            if user.has_group(group):
                return
        raise AccessError(_(
            'Only CRM managers and administrators may link campaigns '
            'retroactively.'))

    def action_link_seeded_campaigns(self):
        """Link leads to campaigns marketing has SINCE seeded. FIND-ONLY.

        Never creates a `utm.campaign` — that is the whole point of the
        find-only policy this action serves. `=ilike` gives the
        case-insensitive match the capture path uses, and the result is then
        re-checked for exact casefolded equality: `=ilike` is a SQL pattern,
        so a raw campaign string containing `%` would otherwise match an
        unrelated campaign and mislabel a lead.

        Runs on the selected rows; called with none (a server action, a
        shell) it sweeps the unmatched queue up to `LINK_CAMPAIGN_SWEEP_CAP`.
        Reads and writes go through `sudo()` AFTER the group gate (the §5.24
        pattern): a user-admin operator has no `crm.lead` ACL of their own,
        and the selection they are acting on already passed their own record
        rules.
        """
        self._check_link_campaigns_allowed()
        rows = self
        swept = False
        if not rows:
            swept = True
            rows = self.search(UNMATCHED_CAMPAIGN_DOMAIN,
                               limit=LINK_CAMPAIGN_SWEEP_CAP)
        Campaign = self.env['utm.campaign'].sudo()
        resolved = {}
        linked, unmatched = 0, set()
        for touch in rows.sudo():
            raw = (touch.utm_campaign or '').strip()
            lead = touch.lead_id
            if not raw or not lead or lead.campaign_id:
                continue
            key = raw.casefold()
            if key not in resolved:
                found = Campaign.search([('name', '=ilike', raw)], limit=1)
                # `=ilike` is a PATTERN: '%' and '_' in the raw string are
                # wildcards. Accept the hit only on exact casefolded equality.
                if found and (found.name or '').strip().casefold() != key:
                    found = Campaign.browse()
                resolved[key] = found
            campaign = resolved[key]
            if not campaign:
                unmatched.add(raw)
                continue
            lead.write({'campaign_id': campaign.id})
            lead.message_post(body=Markup('<p>%s</p>') % _(
                'Campaign %(campaign)s linked retroactively from touchpoint '
                '%(touchpoint)s (raw value "%(raw)s").',
                campaign=campaign.name, touchpoint=touch.id, raw=raw))
            linked += 1
        _logger.info('web_leads: campaign back-fill linked %s lead(s); '
                     '%s raw value(s) still unseeded', linked, len(unmatched))

        if linked:
            title = _('Campaigns linked')
            message = _('%s lead(s) linked to a seeded campaign.', linked)
            kind = 'success'
        else:
            title = _('Nothing to link')
            message = _(
                'No lead was linked: none of the selected raw campaign '
                'values matches a seeded utm.campaign. Seed the campaign '
                'first — this action never creates one.')
            kind = 'warning'
        if swept and len(rows) == LINK_CAMPAIGN_SWEEP_CAP:
            message = '%s %s' % (message, _(
                'Only the first %s rows were examined — run it again to '
                'continue.', LINK_CAMPAIGN_SWEEP_CAP))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind,
                       'sticky': False,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }

    def init(self):
        # Ledger §5.1 — `_sql_constraints` are NOT materialized on Odoo 19.
        # Search-first is the normal dedupe path; this partial unique index is
        # the concurrency backstop for two relay deliveries racing.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_lead_touchpoint_ext_uidx
            ON health_lead_touchpoint (touchpoint_type, external_event_id)
            WHERE external_event_id IS NOT NULL
        """)
