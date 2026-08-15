# -*- coding: utf-8 -*-
"""``care.contact.capture`` — the Unrouted queue. Nothing vanishes.

The client's requirement: *"Any contact through the care command center should
be autologged whether answered or not. None of the contacts should vanish in
thin air."*

Most inbound contacts already become a ``care.conversation`` and sit on the
wall until somebody handles them. This model exists for the ones that could
not, and there were eleven distinct ways for that to happen — a webhook for a
Facebook page we do not recognise, a connection still mid-setup, a call with
no ``voip.config`` behind it, an email from an address that matches no lead or
partner, a web-chat visitor who opened the widget and typed nothing. Every one
of those used to end in a log line at best.

**Why a queue and not just "create the conversation anyway".** Our webhooks
are public URLs. An event we cannot attribute to a known account is an event
anyone could have sent, and auto-creating work items from it would let a
stranger flood the wall — the exact failure the fail-closed webhook posture
(ledger §5.61) exists to prevent. So verified-but-unroutable traffic lands
HERE, visible and convertible in one click, and the wall keeps its meaning.

**Posture.** ``_capture`` clones ``care.channel.audit._log`` exactly: the
create runs inside ``cr.savepoint()`` *inside* the try (a bare try/except does
not protect the host transaction once PostgreSQL aborts — ledger §5.55), and
it never raises into the caller. Losing a customer message because the
bookkeeping row failed would be worse than losing the bookkeeping row.

Unlike ``care.channel.audit`` this model is NOT append-only: an operator queue
needs a resolve state. What is guarded instead is the evidence — the capture's
payload, channel and reason are set once at creation and only the resolution
fields may be written afterwards.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.redact import redact

_logger = logging.getLogger(__name__)

# Why this contact could not become a conversation by itself. Every value maps
# to exactly one drop point that existed in the code before this model did.
CAPTURE_REASONS = [
    ('unknown_resource', 'Unrecognised account'),
    ('not_ingestable', 'Channel not connected yet'),
    ('no_identity', 'No sender id in the message'),
    ('no_anchor', 'Nothing to follow up on'),
    ('no_voip_config', 'Calls not set up'),
    ('unmatched_call', 'Caller not recognised'),
    ('webchat_abandoned', 'Web chat opened, nothing sent'),
    ('spam_suspect', 'Rejected as spam'),
]

CAPTURE_STATES = [
    ('new', 'Unrouted'),
    ('converted', 'Converted'),
    ('dismissed', 'Dismissed'),
]

# The evidence, capped. `raw_payload` is behind an ACL and never logged; the
# preview is what a triaging operator reads without opening the record.
BODY_PREVIEW_CAP = 280
RAW_PAYLOAD_CAP = 8000

# Set once at creation. A capture is evidence of what arrived; letting anyone
# rewrite the channel or the reason afterwards would make the queue unusable
# as a record of what the system actually dropped.
IMMUTABLE_FIELDS = {
    'channel', 'reason', 'resource_external_id', 'body_preview',
    'raw_payload', 'occurred_at', 'external_event_id', 'company_id',
}


class CareContactCapture(models.Model):
    _name = 'care.contact.capture'
    _description = 'Unrouted Contact'
    _order = 'occurred_at desc, id desc'

    company_id = fields.Many2one(
        'res.company', string='Company', index=True, required=True,
        default=lambda self: self.env.company)
    channel = fields.Char(index=True, required=True)
    connection_id = fields.Many2one(
        'care.channel.connection', string='Channel Account', index=True,
        # NOT cascade: deleting a connection must not erase the evidence of
        # what it failed to receive (ledger §5.30/§5.19).
        ondelete='set null')
    resource_external_id = fields.Char(
        string='Account ID',
        help='The page / OA / mailbox the provider addressed, when we could '
             'read one. An id we do not recognise is exactly the interesting '
             'case.')

    reason_id = fields.Many2one(
        'health.lookup.value',
        string='Reason',
        domain="[('category_code', '=', 'unrouted_contact_reason'), ('active', '=', True)]",
        ondelete='restrict',
        required=True,
        index=True,
        help='Why this contact could not be routed to a conversation.')
    # Companion for view expressions and domains: an Odoo view attribute
    # (invisible=, decoration-, domain=) cannot traverse a many2one, and
    # this keeps every existing comparison a one-word change.
    reason_code = fields.Char(
        related='reason_id.code', string='Reason Code', readonly=True)

    # Whatever we could learn about who this was. All optional — the whole
    # point is that these contacts arrived without enough to anchor on.
    peer_hint = fields.Char(
        string='From',
        help='Name, phone or handle as the provider gave it. Never trusted as '
             'an identity — it is a hint for the operator, not an anchor.')
    phone_normalized = fields.Char(string='Phone', index=True)
    email_normalized = fields.Char(string='Email', index=True)
    body_preview = fields.Char(string='Message')
    raw_payload = fields.Text(
        string='Raw Event',
        help='The original event, capped and redacted. Behind ACLs; never '
             'logged.')

    occurred_at = fields.Datetime(
        string='Received', required=True, index=True,
        default=fields.Datetime.now)
    external_event_id = fields.Char(
        string='Event ID', copy=False, index=True,
        help="The provider's id for this event — the idempotency key, so a "
             'redelivered webhook does not stack up duplicate rows.')

    state = fields.Selection(
        CAPTURE_STATES, default='new', required=True, index=True,
        readonly=True)
    conversation_id = fields.Many2one(
        'care.conversation', string='Conversation', readonly=True,
        ondelete='set null')
    resolved_by_id = fields.Many2one(
        'res.users', string='Handled by', readonly=True)
    resolved_at = fields.Datetime(string='Handled at', readonly=True)
    dismiss_reason = fields.Char(string='Dismissed because', readonly=True)

    def init(self):
        # §5.1: _sql_constraints are not materialised on Odoo 19. Partial
        # unique, because most captures have no provider event id at all.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                care_contact_capture_event_uniq
            ON care_contact_capture (external_event_id)
            WHERE external_event_id IS NOT NULL
        """)

    # ------------------------------------------------------------------
    # Evidence guard
    # ------------------------------------------------------------------
    def write(self, vals):
        offending = sorted(IMMUTABLE_FIELDS & set(vals))
        if offending and not self.env.su:
            raise UserError(_(
                'An unrouted contact records what actually arrived and cannot '
                'be edited (%s). Convert it or dismiss it instead.',
                ', '.join(offending)))
        return super().write(vals)

    # ------------------------------------------------------------------
    # The ONE writer — never breaks the caller
    # ------------------------------------------------------------------
    @api.model
    def _capture(self, reason, channel, connection=None, company_id=None,
                 resource_external_id=None, peer_hint=None, phone=None,
                 email=None, body=None, raw=None, external_event_id=None,
                 occurred_at=None):
        """Record one contact we could not route. Returns the row, or empty.

        Named ``_capture`` (not ``capture``): it creates through ``sudo()``, so
        a public name would let any RPC caller forge queue entries.

        Idempotent on ``external_event_id`` — a provider that redelivers the
        same unroutable event for hours must not produce hours of rows.
        """
        if external_event_id:
            existing = self.sudo().search(
                [('external_event_id', '=', external_event_id)], limit=1)
            if existing:
                return existing
        try:
            with self.env.cr.savepoint():
                Care = self.env['care.conversation']
                vals = {
                    'reason': reason,
                    'channel': channel or (connection.channel if connection
                                           else 'unknown'),
                    'connection_id': connection.id if connection else False,
                    'company_id': (
                        company_id
                        or (connection.company_id.id if connection else False)
                        or self.env.company.id),
                    'resource_external_id': (resource_external_id or '')[:120]
                    or False,
                    'peer_hint': redact(peer_hint) or False,
                    'phone_normalized': Care._safe_phone(phone) or False,
                    'email_normalized': Care._safe_email(email) or False,
                    'body_preview': (body or '')[:BODY_PREVIEW_CAP] or False,
                    'raw_payload': redact(raw, max_len=RAW_PAYLOAD_CAP),
                    'external_event_id': (external_event_id or '')[:120] or False,
                    'occurred_at': occurred_at or fields.Datetime.now(),
                }
                return self.sudo().create(vals)
        except Exception:  # noqa: BLE001 — capturing must never break ingest
            _logger.exception(
                'Failed to write care.contact.capture row (%s/%s)',
                channel, reason)
            return self.browse()

    # ------------------------------------------------------------------
    # Operator actions
    # ------------------------------------------------------------------
    def action_convert(self):
        """Promote this capture into a real conversation on the wall.

        The anchors are whatever the capture managed to learn. A capture with
        none of them cannot become a conversation — ``_check_anchor`` would
        refuse it — and the honest answer is to say so rather than to create an
        unreachable record.
        """
        Care = self.env['care.conversation']
        for rec in self:
            if rec.state != 'new':
                raise UserError(_('This contact has already been handled.'))
            anchor = {'phone_normalized': rec.phone_normalized,
                      'email_normalized': rec.email_normalized}
            if not any(anchor.values()):
                raise UserError(_(
                    'There is no phone number or email on this contact, so '
                    'there is nothing to follow up on. Add one to the contact '
                    'record first, or dismiss it.'))
            conv = Care.sudo().with_company(rec.company_id)._find_or_create_for(
                anchor, {
                    'channel': rec.channel,
                    'inbound': True,
                    'event_at': rec.occurred_at,
                    'set_status': 'needs_reply',
                    'unread': 1,
                    'watch_hits': Care._match_watchlist(rec.body_preview),
                })
            rec.sudo().write({
                'state': 'converted',
                'conversation_id': conv.id,
                'resolved_by_id': self.env.uid,
                'resolved_at': fields.Datetime.now(),
            })
        return True

    def action_dismiss(self, reason=None):
        for rec in self:
            if rec.state != 'new':
                raise UserError(_('This contact has already been handled.'))
            rec.sudo().write({
                'state': 'dismissed',
                'dismiss_reason': (reason or '')[:200] or False,
                'resolved_by_id': self.env.uid,
                'resolved_at': fields.Datetime.now(),
            })
        return True

    @api.model
    def unrouted_count(self):
        """Badge count for the Care Command wall. Company-scoped, cheap."""
        return self.sudo().search_count([
            ('state', '=', 'new'),
            ('company_id', '=', self.env.company.id),
        ])
