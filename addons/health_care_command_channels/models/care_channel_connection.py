# -*- coding: utf-8 -*-
"""Plane 2 — the tenant's authorization for one channel (architecture §5.2).

This is the record the Channel Connection Center manages: what the tenant
granted by signing in with the provider (tokens, the selected Page/WABA/OA/
mailbox/bot, granted scopes, expiry, webhook state) plus the derived health of
that grant.

Three rules shape the whole file:

1. **``ready`` is DERIVED, never asserted.** A connection is not Ready because
   a row exists — it is Ready when every readiness check its adapter declares
   as *required* has status ``pass`` (:meth:`_recompute_ready`). This is the
   anti-"configured ≠ connected" rule from the architecture.
2. **``state`` has exactly one writer**, :meth:`_transition`, which validates
   against an explicit transition table and audits every move. Direct writes of
   ``state`` (or of any credential/resource field) are refused for callers that
   did not come through a server path — see :meth:`_check_guarded_vals`. The
   gate is keyed on an internal *context flag*, not on ``self.env.su``, because
   uid 1 always runs as su and an su-based guard is dead code in tests and for
   admin (ledger §5.4).
3. **Secrets are write-only from outside.** ``*_enc`` columns carry
   ``groups='base.group_system'`` and appear in no view; the only writer is
   :meth:`action_set_secret` and the only reader is ``_get_secret()``, whose
   leading underscore keeps it off the RPC surface.
"""
import json
import logging
from datetime import timedelta

import psycopg2

from odoo import SUPERUSER_ID, _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.modules.registry import Registry

from odoo.addons.health_care_command.models.care_conversation import (
    CHANNEL_SELECTION, CONNECTABLE_SELECTION,
)

from ..services import channel_crypto
from ..services.adapters import get_adapter
from ..services.redact import redact

_logger = logging.getLogger(__name__)

# Context flag that marks a write as coming from a sanctioned server path.
INTERNAL_CTX = 'channel_hub_internal'

STATES = [
    ('not_connected', 'Not connected'),
    ('authorizing', 'Signing in'),
    ('select_resource', 'Choosing what to connect'),
    ('configuring', 'Setting things up'),
    ('testing', 'Testing'),
    ('ready', 'Connected'),
    ('action_required', 'Action required'),
    ('expiring', 'Expiring soon'),
    ('error', 'Error'),
    ('disabled', 'Disabled'),
    ('legacy', 'Legacy (not migrated)'),
]

# Explicit transition table. Anything not listed is refused — a state machine
# that accepts everything is not a state machine.
TRANSITIONS = {
    'not_connected': {'authorizing', 'legacy', 'disabled'},
    # CC-C review (MED-1): `disabled` is the tenant's off switch and must be
    # reachable from every in-flight state — a tenant who registered a webhook
    # for the wrong bot cannot be forced to finish proving it before turning
    # it off. `authorizing` from the mid-setup states is the matching restart.
    'authorizing': {'select_resource', 'configuring', 'testing', 'ready',
                    'action_required', 'error', 'not_connected', 'disabled'},
    'select_resource': {'configuring', 'testing', 'ready', 'action_required',
                        'error', 'not_connected', 'authorizing', 'disabled'},
    'configuring': {'testing', 'ready', 'action_required', 'error',
                    'not_connected', 'authorizing', 'disabled'},
    'testing': {'ready', 'action_required', 'error', 'not_connected',
                'authorizing', 'disabled'},
    'ready': {'expiring', 'action_required', 'error', 'disabled',
              'authorizing', 'not_connected'},
    'action_required': {'authorizing', 'select_resource', 'configuring',
                        'testing', 'ready', 'expiring', 'error', 'disabled',
                        'not_connected'},
    'expiring': {'ready', 'action_required', 'authorizing', 'error',
                 'disabled', 'not_connected'},
    'error': {'authorizing', 'action_required', 'disabled', 'not_connected'},
    'disabled': {'not_connected', 'authorizing'},
    'legacy': {'authorizing', 'not_connected', 'disabled'},
}

# States in which readiness derivation may move the record. A connection that
# was never authorized can never become Ready by seeding check rows.
RECOMPUTE_STATES = {'testing', 'ready', 'action_required', 'expiring'}

# CC-B §2.1 — the ONE definition of "this channel may send". `expiring` is
# included deliberately: a grant that dies in six days still works today, and
# refusing to reply would be a worse failure than the warning already raised.
SENDABLE_STATES = {'ready', 'expiring'}

# ...and the ONE definition of "this channel may still receive". A connection
# mid-setup should collect the traffic that proves it works; a disabled or
# errored one must NOT keep filling the inbox (CC-B §2.3, declared behaviour).
INGESTABLE_STATES = SENDABLE_STATES | {'testing', 'configuring'}

WEBHOOK_STATES = [
    ('none', 'None'),
    ('pending', 'Pending'),
    ('subscribed', 'Subscribed'),
    ('verified', 'Verified'),
    ('failing', 'Failing'),
]

HEALTH_STATUSES = [
    ('healthy', 'Healthy'),
    ('action_required', 'Action required'),
    ('expiring', 'Expiring'),
    ('permission_lost', 'Permission lost'),
    ('webhook_failing', 'Webhook failing'),
    ('provider_down', 'Provider unavailable'),
]

SECRET_FIELDS = {
    'access_token': 'access_token_enc',
    'refresh_token': 'refresh_token_enc',
    'provider_secret': 'provider_secret_enc',
}

# The whole user-editable surface (handover §4.2). Everything else on this
# model — state, every *_enc column, granted_scopes, every resource_*, the
# webhook and health fields — is maintained by server paths only. Expressed as
# a whitelist rather than a denylist so a field added in a later phase is
# guarded by default.
# (message_main_attachment_id is mail.thread plumbing: _message_post_after_hook
# writes it on the record when a chatter message carries an attachment.)
# account_label is deliberately in both: with several accounts per channel the
# tenant needs to be able to name them ("Zalo OA — HCM"), and a label is inert
# display text, not a credential or a state.
# The attribution defaults join account_label: they are marketing metadata a
# tenant owns, not credentials or state.
USER_WRITABLE = {'active', 'account_label', 'utm_source_id', 'utm_medium_id',
                 'campaign_id', 'message_main_attachment_id'}
USER_CREATABLE = {'channel', 'company_id', 'active', 'account_label'}

# Who may operate a connection through the Channel Connection Center: the
# platform operator, the Care Command manager, and — from CC-C — the tenant
# administrator, who is the persona the Center was designed for. Membership is
# checked EXPLICITLY in every method that writes through sudo(): a model ACL
# cannot gate a method whose writes bypass it (ledger §5.37 corollary).
CENTER_GROUPS = (
    'base.group_system',
    'health_crm.group_health_crm_manager',
    'health_user_admin.group_health_user_admin',
)

# Advisory-lock class key for refresh serialisation (CC-D review). Any stable
# int32 does; this one spells "chnl" so it is recognisable in `pg_locks`.
REFRESH_LOCK_CLASS = 0x63686E6C

# Failure backoff for the health cron (handover §7): 30 m → 2 h → 8 h.
BACKOFF_MINUTES = (30, 120, 480)
HEALTH_INTERVAL_MINUTES = 30
EXPIRY_WARNING_DAYS = 7


class CareChannelConnection(models.Model):
    _name = 'care.channel.connection'
    _description = 'Care Channel Connection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'channel'

    # mail.thread is inherited for ONE reason: the expiry warning is a
    # mail.activity, and mail.activity.action_notify() calls
    # record.message_notify() on the assigned record — which only exists on a
    # mail.thread model. NOT ONE FIELD ON THIS MODEL CARRIES tracking=True:
    # that is defect Z1 in health_zalo (a tracked app_secret copies plaintext
    # secrets into mail.tracking.value, bypassing field groups entirely).

    # CONNECTABLE_SELECTION, not CHANNEL_SELECTION: walk_in is a conversation
    # channel with no provider behind it, so it can never be a connection.
    channel = fields.Selection(
        CONNECTABLE_SELECTION, required=True, index=True,
        help='The Care Command channel key this connection powers.')
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    # The channel ACCOUNT owns the catchment area, not the conversation: each
    # area runs its own Zalo OA and its own Facebook page, so a message's area
    # is decided the moment it arrives, before anyone knows who sent it. This
    # is the root of catchment truth for everything in Care Command —
    # identities, messages and conversations all read it from here.
    #
    # Editable and optional. A connection with no area is a national one and
    # its traffic falls back to the contact's or lead's area.
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area', index=True,
        help='The area this channel account serves. Conversations arriving on '
             'it are scoped to this area, so staff only see their own area\'s '
             'chats. Leave empty for an account shared across all areas.')
    active = fields.Boolean(default=True)

    state = fields.Selection(
        STATES, default='not_connected', required=True, index=True,
        readonly=True,
        help='Lifecycle of the tenant authorization. Only server paths write '
             'it; "Connected" is derived from the readiness checks.')

    # The tenant's own name for this account. With two Facebook pages and two
    # Zalo accounts, `resource_display_name` (what the PROVIDER calls it) is
    # often the same or unhelpful, and a page id is not something an operator
    # should have to recognise. This is the only free-text field a tenant owns.
    account_label = fields.Char(
        string='Account Name',
        help='Your name for this account, e.g. "Zalo OA — HCM". Shown wherever '
             'you have to pick between accounts on the same channel.')

    # --- attribution defaults (client requirement 3) --------------------
    # What a contact arriving on THIS account should be attributed to when the
    # provider tells us nothing more specific. This is what makes multi-account
    # pay off for marketing: "Messenger — HCM" and "Messenger — Hanoi" become
    # different sources with no per-message work, and a phone call — which can
    # never carry a click id — is attributed by the number that was dialled.
    #
    # A per-event ref/click id from the provider always WINS over these; they
    # are the floor, not the answer.
    utm_source_id = fields.Many2one(
        'utm.source', string='Default Source',
        help='Attributed to contacts arriving on this account when the '
             'provider sends no campaign information of its own.')
    utm_medium_id = fields.Many2one('utm.medium', string='Default Medium')
    campaign_id = fields.Many2one('utm.campaign', string='Default Campaign')

    # -- what is connected ---------------------------------------------
    resource_external_id = fields.Char(
        string='Resource ID', readonly=True,
        help='Page id / phone_number_id / oa_id / bot id / mailbox / PBX account.')
    resource_secondary_id = fields.Char(
        string='Secondary ID', readonly=True, help='WABA id, where applicable.')
    resource_display_name = fields.Char(string='Connected as', readonly=True)

    # -- credentials (never in a view, never returned over RPC) ---------
    access_token_enc = fields.Text(groups='base.group_system')
    refresh_token_enc = fields.Text(groups='base.group_system')
    provider_secret_enc = fields.Text(groups='base.group_system')
    webhook_path_secret = fields.Char(groups='base.group_system')
    secret_hint = fields.Char(string='Credential', readonly=True)
    has_credentials = fields.Boolean(
        compute='_compute_has_credentials', string='Credentials stored')

    granted_scopes = fields.Char(readonly=True)
    token_expires_at = fields.Datetime(
        readonly=True, help='UTC, as every fields.Datetime is.')

    # -- non-secret per-channel settings (CC-B §2.1) ---------------------
    # json.dumps dict: webchat allowed_origins / greeting, and whatever a later
    # adapter needs that is configuration rather than credential. Server-
    # maintained like every other field here (NOT in USER_WRITABLE): the CC-C
    # Center writes it through an action, never through a form.
    settings_json = fields.Text(string='Channel settings (JSON)', readonly=True)
    api_base_override = fields.Char(
        string='API base override', readonly=True,
        help='Test/staging provider endpoint. Empty = the provider default.')

    # -- webhook --------------------------------------------------------
    webhook_state = fields.Selection(
        WEBHOOK_STATES, default='none', required=True, readonly=True)
    last_webhook_at = fields.Datetime(readonly=True)

    # -- health ---------------------------------------------------------
    last_inbound_at = fields.Datetime(readonly=True)
    last_outbound_at = fields.Datetime(readonly=True)
    health_status = fields.Selection(HEALTH_STATUSES, readonly=True)
    next_health_check_at = fields.Datetime(readonly=True, index=True)
    consecutive_failures = fields.Integer(default=0, readonly=True)
    last_error_redacted = fields.Char(string='Last error', readonly=True)

    readiness_check_ids = fields.One2many(
        'care.channel.readiness.check', 'connection_id', string='Readiness')
    audit_ids = fields.One2many(
        'care.channel.audit', 'connection_id', string='Audit trail')

    # ------------------------------------------------------------------
    # DB constraints
    # ------------------------------------------------------------------
    def init(self):
        # §5.1: _sql_constraints are not materialised on Odoo 19.
        #
        # MULTI-ACCOUNT (client requirement 1). The old index was
        # (channel, company_id) WHERE active — one Facebook page, one Zalo OA
        # per tenant, full stop. The client runs two of each, so the rule moves
        # from "one connection per channel" to "one connection per provider
        # RESOURCE": two Facebook pages are two page ids and coexist; the same
        # page id twice is still a mistake.
        #
        # A CREATE ... IF NOT EXISTS will not remove the old index, so it is
        # dropped explicitly. This is idempotent and safe to re-run.
        self.env.cr.execute("""
            DROP INDEX IF EXISTS care_channel_connection_channel_company_uniq
        """)
        # Rows still in the stepper carry no resource id yet and are left
        # unconstrained on purpose — otherwise a tenant could not begin setting
        # up their second account while the first is mid-flow.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                care_channel_connection_channel_company_resource_uniq
            ON care_channel_connection (channel, company_id, resource_external_id)
            WHERE active AND resource_external_id IS NOT NULL
        """)
        # One owner per provider resource platform-wide. `_find_for_resource`
        # routes inbound webhooks by resource id alone and is company-agnostic
        # by design, so two tenants claiming the same page id makes routing a
        # coin flip. CC-F found this for `call` and fixed it in Python for that
        # one channel; with several accounts per tenant now legal, it becomes a
        # database rule for every channel.
        #
        # webchat is excluded: it uses the literal 'default' as its resource id
        # for EVERY company, so this index would let exactly one tenant have a
        # web chat widget.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                care_channel_connection_channel_resource_uniq
            ON care_channel_connection (channel, resource_external_id)
            WHERE active AND resource_external_id IS NOT NULL
              AND channel <> 'webchat'
        """)

    @api.depends('access_token_enc', 'refresh_token_enc', 'provider_secret_enc')
    def _compute_has_credentials(self):
        for rec in self:
            # The sources are group-restricted; read them as su so a crm_user
            # can still see the boolean without tripping the field ACL.
            su = rec.sudo()
            rec.has_credentials = bool(
                su.access_token_enc or su.refresh_token_enc
                or su.provider_secret_enc)

    @api.depends('channel', 'account_label', 'resource_display_name')
    def _compute_display_name(self):
        labels = dict(CHANNEL_SELECTION)
        for rec in self:
            label = labels.get(rec.channel, rec.channel or '')
            # The tenant's own label wins: with two Messenger pages connected,
            # "Messenger — Viet UC HCM" is the only thing that distinguishes
            # them in a picker, and the provider's own name often does not.
            suffix = rec.account_label or rec.resource_display_name
            rec.display_name = '%s — %s' % (label, suffix) if suffix else label

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    @api.model
    def _is_internal(self):
        # The context flag alone is NOT sufficient: RPC callers control their
        # own context (call_kw merges the client's dict), so a published flag
        # would be a forgeable key to the guard. Require the flag AND an
        # escalated environment — su covers every sanctioned server path
        # (sudo()/_internal() chains, crons, uid 1), group_system covers an
        # administrator in a debug shell. (CC-A review finding #1.)
        if not self.env.context.get(INTERNAL_CTX):
            return False
        return self.env.su or self.env.user.has_group('base.group_system')

    def _internal(self):
        """Recordset flagged as a sanctioned server write path."""
        return self.with_context(**{INTERNAL_CTX: True})

    @api.model
    def _check_guarded_vals(self, vals, creating=False):
        if self._is_internal():
            return
        allowed = USER_CREATABLE if creating else USER_WRITABLE
        offending = sorted(set(vals) - allowed)
        if offending:
            raise UserError(_(
                'Channel connection fields are maintained by the Channel '
                'Center, not by direct edits (%s). Use the connect, test and '
                'disconnect actions.', ', '.join(offending)))

    @api.model
    def _check_resource_unique(self, channel, company_id, resource_external_id,
                               active, exclude_id=None):
        """Pre-check both partial unique indexes (ledger §5.3): raise a clean
        ValidationError instead of letting the IntegrityError poison the tx.

        Mirrors ``init()`` exactly. A connection with no resource id yet is
        mid-stepper and is not constrained by either index, so it short-circuits
        here too — the two must not drift.
        """
        if not channel or not active or not resource_external_id:
            return
        base = [('channel', '=', channel), ('active', '=', True),
                ('resource_external_id', '=', resource_external_id)]
        if exclude_id:
            base.append(('id', '!=', exclude_id))

        if company_id and self.sudo().search_count(
                base + [('company_id', '=', company_id)]):
            raise ValidationError(_(
                'This account is already connected for this company. Each '
                'Facebook page, Zalo account or mailbox can be connected once.'))

        # Cross-company: webchat legitimately shares the literal 'default'.
        if channel != 'webchat' and self.sudo().search_count(base):
            raise ValidationError(_(
                'This account is already connected by another company. An '
                'account can only belong to one company at a time.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_guarded_vals(vals, creating=True)
            self._check_resource_unique(
                vals.get('channel'),
                vals.get('company_id') or self.env.company.id,
                vals.get('resource_external_id'),
                vals.get('active', True))
        return super().create(vals_list)

    def write(self, vals):
        self._check_guarded_vals(vals)
        # resource_external_id joins the trigger set: adopting a resource id is
        # exactly the moment a row becomes constrained.
        if {'active', 'channel', 'company_id',
                'resource_external_id'} & set(vals):
            for rec in self:
                self._check_resource_unique(
                    vals.get('channel', rec.channel),
                    vals.get('company_id', rec.company_id.id),
                    vals.get('resource_external_id', rec.resource_external_id),
                    vals.get('active', rec.active),
                    exclude_id=rec.id)
        return super().write(vals)

    # ------------------------------------------------------------------
    # State machine — the ONLY writer of `state`
    # ------------------------------------------------------------------
    def _transition(self, new_state, reason=None):
        """Move to ``new_state`` if the transition table allows it, audit it.

        Raises UserError on a disallowed move: an illegal transition is a bug
        in a calling adapter, and silently absorbing it would let a channel
        claim readiness it never proved.
        """
        self.ensure_one()
        if new_state not in dict(STATES):
            raise UserError(_('Unknown channel connection state.'))
        old = self.state
        if old == new_state:
            return False
        if new_state not in TRANSITIONS.get(old, set()):
            raise UserError(_(
                'A channel connection cannot move from "%(old)s" to "%(new)s".',
                old=old, new=new_state))
        self._internal().write({'state': new_state})
        self.env['care.channel.audit']._log(
            'health_transition', connection=self,
            detail='%s -> %s%s' % (old, new_state,
                                   (': %s' % reason) if reason else ''))
        return True

    # ------------------------------------------------------------------
    # Adapter
    # ------------------------------------------------------------------
    def _get_adapter(self):
        self.ensure_one()
        return get_adapter(self.env, self)

    def _capabilities(self):
        self.ensure_one()
        return self._get_adapter().authorization_capabilities()

    def _required_checks(self):
        """The readiness checks this channel's adapter declares as required."""
        self.ensure_one()
        try:
            return list(self._capabilities().get('required_checks') or [])
        except (ValueError, NotImplementedError):
            return []

    # ------------------------------------------------------------------
    # Readiness derivation
    # ------------------------------------------------------------------
    def _recompute_ready(self):
        """Derive ``ready`` / ``action_required`` from the readiness checks.

        A *required* check must be ``pass``. ``n_a`` satisfies nothing that is
        required — it is only meaningful for checks outside the required set
        (architecture §5.4). Failure never falls to ``error``: ``error`` means
        the framework broke, ``action_required`` means the tenant must act.

        **CC-C amendment F1 (ledger §5.66).** A required check that merely has
        not happened YET is not the same claim as one that FAILED, and the
        difference decides whether a channel can finish proving itself:

        * any required check ``fail`` ⇒ ``action_required``, from every
          recompute state — a broken grant must stop the traffic;
        * every required check ``pass`` ⇒ ``ready``;
        * otherwise (some required check missing / pending / ``n_a``) a
          connection in ``testing`` STAYS in ``testing`` — still ingestable,
          still not sendable — because ``testing`` is precisely the state in
          which those checks are being proven, and demoting on the FIRST
          proving inbound locked the channel out of the traffic that would
          finish the job. From ``ready``/``expiring`` the demotion stands: a
          required check cannot go missing there except by deletion.
        """
        for rec in self:
            if rec.state not in RECOMPUTE_STATES:
                continue
            required = rec._required_checks()
            statuses = {c.check_key: c.status for c in rec.readiness_check_ids}
            failed = [k for k in required if statuses.get(k) == 'fail']
            unmet = [k for k in required if statuses.get(k) != 'pass']
            if failed:
                target = 'action_required'
                reason = 'failed: %s' % ','.join(failed)
            elif not unmet:
                target = 'ready'
                reason = 'all checks pass'
            elif rec.state == 'testing':
                # Still proving itself — no move, no audit noise.
                target = 'testing'
                reason = None
            else:
                target = 'action_required'
                reason = 'unmet: %s' % ','.join(unmet)
            if target != rec.state:
                rec._transition(target, reason=reason)
            if not unmet and rec.health_status in (False, 'action_required'):
                rec._internal().write({'health_status': 'healthy'})
        return True

    def readiness_summary(self):
        """JSON-safe readiness for the (future) Center UI.

        Carries no secret, no raw provider text: every ``detail`` was redacted
        on the way into the database and is re-redacted here for good measure.
        """
        self.ensure_one()
        required = set(self._required_checks())
        rows = []
        seen = set()
        for check in self.readiness_check_ids:
            seen.add(check.check_key)
            rows.append({
                'check_key': check.check_key,
                'status': check.status,
                'required': check.check_key in required,
                'detail': redact(check.detail_redacted) or '',
                'checked_at': fields.Datetime.to_string(check.checked_at) or '',
            })
        for key in required - seen:
            rows.append({'check_key': key, 'status': 'pending',
                         'required': True, 'detail': '', 'checked_at': ''})
        return {
            'channel': self.channel,
            'state': self.state,
            'health_status': self.health_status or '',
            'resource_display_name': self.resource_display_name or '',
            'has_credentials': self.has_credentials,
            'secret_hint': self.secret_hint or '',
            'checks': rows,
        }

    # ------------------------------------------------------------------
    # Secrets (architecture §7.2)
    # ------------------------------------------------------------------
    @api.model
    def _center_group_ok(self, user=None):
        """True when ``user`` may operate connections (CENTER_GROUPS)."""
        user = user or self.env.user
        return any(user.has_group(xmlid) for xmlid in CENTER_GROUPS)

    def _check_center_access(self):
        """Group + company gate for every Center action and credential write.

        Raises rather than returns: these methods all write through ``sudo()``,
        so there is no ACL underneath them to fall back on.
        """
        user = self.env.user
        if not self._center_group_ok(user):
            raise UserError(_(
                'Only a Care Command manager or a tenant administrator can '
                'set up channels.'))
        for rec in self:
            if rec.company_id not in user.company_ids and not user.has_group(
                    'base.group_system'):
                raise UserError(_('This connection belongs to another company.'))
        return True

    def action_set_secret(self, field_key, secret):
        """Encrypt and store one credential. Group- and company-gated."""
        self.ensure_one()
        column = SECRET_FIELDS.get(field_key)
        if not column:
            raise UserError(_('Unknown credential field.'))
        self._check_center_access()
        if not secret or not isinstance(secret, str) or not secret.strip():
            raise UserError(_('The credential cannot be empty.'))
        secret = secret.strip()
        self.sudo()._internal().write({
            column: channel_crypto.encrypt(self.env, secret),
            # No tail for short secrets (CC-A review finding #6).
            'secret_hint': '••••' + (secret[-4:] if len(secret) >= 8 else ''),
        })
        self.env['care.channel.audit']._log(
            'secret_rotated', connection=self, detail='field %s' % field_key)
        return True

    def _get_secret(self, field_key):
        """Server-side only (leading underscore ⇒ not RPC-callable)."""
        self.ensure_one()
        column = SECRET_FIELDS.get(field_key)
        if not column:
            raise UserError(_('Unknown credential field.'))
        return channel_crypto.decrypt(self.env, self.sudo()[column] or '')

    # ------------------------------------------------------------------
    # Non-secret settings + resolution helpers (CC-B)
    # ------------------------------------------------------------------
    def get_setting(self, key, default=None):
        """One non-secret per-channel setting out of ``settings_json``."""
        self.ensure_one()
        try:
            data = json.loads(self.settings_json or '{}') or {}
        except ValueError:
            _logger.warning('Connection %s has unparsable settings_json', self.id)
            return default
        if not isinstance(data, dict):
            return default
        return data.get(key, default)

    def set_settings(self, values):
        """Merge ``values`` into ``settings_json`` (server path, never a form).

        Refuses anything credential-shaped: this column is readable by any CRM
        manager, so a secret must never be routed here by a later adapter.

        Group-gated like every other public writer on this model (CC-C): the
        write goes through ``sudo()._internal()``, so without an explicit gate
        any logged-in user who can read a connection could re-point the web
        chat's allowed origins by RPC.
        """
        self.ensure_one()
        self._check_center_access()
        if not isinstance(values, dict):
            raise UserError(_('Channel settings must be a mapping.'))
        for key in values:
            low = str(key).lower()
            if any(bad in low for bad in ('token', 'secret', 'password', 'key')):
                raise UserError(_(
                    'Credentials belong in the encrypted columns, not in the '
                    'channel settings.'))
        try:
            current = json.loads(self.settings_json or '{}') or {}
        except ValueError:
            current = {}
        if not isinstance(current, dict):
            current = {}
        current.update(values)
        self.sudo()._internal().write({'settings_json': json.dumps(current)})
        return True

    @api.model
    def _find_sendable(self, channel, company_id):
        """*Some* connection that may SEND on ``channel`` for ``company_id``.

        Empty recordset when the channel is not connected, is still being set
        up, or was disabled — the composer then degrades honestly instead of
        offering a send that would fail at the provider.

        With several accounts per channel this is now the FALLBACK, not the
        answer: prefer ``_sendable_for_conversation`` wherever a conversation
        is in hand, because replying to a Facebook thread from the wrong page
        reaches nobody.
        """
        if not channel or not company_id:
            return self.browse()
        return self.sudo().search([
            ('channel', '=', channel),
            ('company_id', '=', company_id),
            ('state', 'in', sorted(SENDABLE_STATES)),
        ], order='id asc', limit=1)

    @api.model
    def _find_sendable_for_resource(self, channel, company_id,
                                    resource_external_id):
        """A sendable connection for THIS provider resource specifically.

        The reconnect case: disconnecting and re-authorising a Facebook page
        leaves the old row archived and creates a new one, so identities that
        arrived on the old row must be able to follow the page to its new
        connection. Matching on the resource id does exactly that — and,
        unlike a channel-wide search, it cannot silently hand the thread to a
        DIFFERENT page that happens to be connected too.
        """
        if not channel or not company_id or not resource_external_id:
            return self.browse()
        return self.sudo().search([
            ('channel', '=', channel),
            ('company_id', '=', company_id),
            ('resource_external_id', '=', resource_external_id),
            ('state', 'in', sorted(SENDABLE_STATES)),
        ], order='id desc', limit=1)

    @api.model
    def _find_for_resource(self, channel, resource_external_id):
        """Route an inbound webhook to its tenant (CC-B §2.3).

        Company-AGNOSTIC on purpose: the provider addresses us by a resource id
        (phone_number_id / page id), and which company owns it is exactly what
        we are resolving. Every caller re-enters the tenant's company with
        ``with_company`` before touching a conversation.
        """
        if not channel or not resource_external_id:
            return self.browse()
        return self.sudo().search([
            ('channel', '=', channel),
            ('resource_external_id', '=', resource_external_id),
        ], limit=1)

    def _may_ingest(self):
        self.ensure_one()
        return self.state in INGESTABLE_STATES

    # ------------------------------------------------------------------
    # Traffic → truth (CC-B §2.4). Real traffic is the only honest proof that
    # a webhook works, so ingest and send feed the readiness model directly.
    # None of these may EVER raise into the caller: an ingest that dies over a
    # bookkeeping write would drop a real customer message.
    # ------------------------------------------------------------------
    def _safe(self, func, what):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                return func()
        except Exception:  # noqa: BLE001 — bookkeeping never breaks messaging
            _logger.exception('Channel connection %s: %s failed', self.id, what)
            return False

    def _note_inbound(self, when=None, webhook=True):
        """An inbound event arrived: the webhook is verified, inbound proven.

        ``webhook=False`` is CC-F's email path: a mailbox is polled over IMAP,
        there is no webhook to call verified, and claiming one would be a
        state the tenant could never act on. Everything else is identical —
        and note that both branches only ever PROMOTE a check (ledger §5.78):
        real traffic is evidence, and evidence is never withdrawn by silence.
        """
        self.ensure_one()
        now = when or fields.Datetime.now()

        def _run():
            vals = {'last_inbound_at': now}
            if webhook:
                vals.update({'last_webhook_at': now,
                             'webhook_state': 'verified'})
            self.sudo()._internal().write(vals)
            Check = self.env['care.channel.readiness.check']
            if webhook:
                Check.upsert_check(self.sudo(), 'webhook_verified', 'pass')
            Check.upsert_check(self.sudo(), 'inbound_ok', 'pass')
            return True

        return self._safe(_run, 'inbound health wiring')

    def _note_outbound(self, when=None):
        """A message went out and the provider accepted it."""
        self.ensure_one()
        now = when or fields.Datetime.now()

        def _run():
            self.sudo()._internal().write({'last_outbound_at': now})
            self.env['care.channel.readiness.check'].upsert_check(
                self.sudo(), 'outbound_ok', 'pass')
            return True

        return self._safe(_run, 'outbound health wiring')

    def _persist_send_failure(self, identity, text, error, auth_failure=False,
                              conversation=None):
        """Record a failed send in an INDEPENDENT cursor, so the evidence
        survives the ``UserError`` the composer raises.

        An RPC method that raises rolls its whole transaction back — so a
        failed message row, the redacted reason and (for a 401) the lost
        ``authorization_valid`` check would all vanish exactly when they matter
        most. Same idiom as health_emar ``_persist_interaction_result``
        (ledger §5.12): fresh cursor FIRST, before any same-transaction write
        to this row, with a bounded ``lock_timeout`` so best-effort bookkeeping
        can never hang a request.

        Returns True when the evidence was committed. Under ``--test-enable``
        it returns False without writing: a second cursor cannot see records
        the test transaction created (ledger §5.63), and the caller then writes
        the same evidence in-transaction, which is what the suites assert on.
        """
        self.ensure_one()
        if tools.config.get('test_enable') or tools.config.get('test_file'):
            return False
        record_id, dbname = self.id, self.env.cr.dbname
        identity_id = identity.id if identity else False
        conversation_id = conversation.id if conversation else False
        detail = redact(error) or _('Send failed')
        try:
            with Registry(dbname).cursor() as cr:
                cr.execute("SET LOCAL lock_timeout = '2s'")
                env = api.Environment(cr, SUPERUSER_ID, {INTERNAL_CTX: True})
                conn = env['care.channel.connection'].browse(record_id)
                if identity_id:
                    env['care.channel.message'].create({
                        'connection_id': record_id,
                        'identity_id': identity_id,
                        'conversation_id': conversation_id,
                        'direction': 'outgoing',
                        'message_type': 'text',
                        'body': (text or '')[:4000] or False,
                        'state': 'failed',
                        'error_message': detail,
                        'event_at': fields.Datetime.now(),
                    })
                conn.write({'last_error_redacted': detail})
                if auth_failure:
                    env['care.channel.readiness.check'].upsert_check(
                        conn, 'authorization_valid', 'fail', detail=error)
                    conn.write({'health_status': 'permission_lost'})
                env['care.channel.audit']._log(
                    'send_failed', connection=conn, detail=error)
        except Exception:  # noqa: BLE001 — evidence is best effort, never fatal
            _logger.exception('Failed to persist send failure for connection %s',
                              record_id)
            return False
        self.invalidate_recordset(['last_error_redacted', 'health_status',
                                   'state'])
        return True

    def _note_send_failure(self, error, auth_failure=False):
        """Record a send failure; an authorization failure costs readiness.

        A transient provider error must not tear a working channel down, so
        only a 401/190-class failure flips ``authorization_valid`` (and through
        ``_recompute_ready`` the connection into ``action_required``).
        """
        self.ensure_one()
        detail = redact(error)

        def _run():
            self.sudo()._internal().write({
                'last_error_redacted': detail or _('Send failed')})
            if auth_failure:
                self.env['care.channel.readiness.check'].upsert_check(
                    self.sudo(), 'authorization_valid', 'fail', detail=error)
                self.sudo()._internal().write({'health_status': 'permission_lost'})
            return True

        return self._safe(_run, 'send failure wiring')

    # ------------------------------------------------------------------
    # Refresh locking (architecture §7.4) — used for real in CC-D
    # ------------------------------------------------------------------
    def _with_refresh_lock(self, func):
        """Run ``func()`` under an ADVISORY lock on this connection.

        Returns ``'locked'`` (never raises) when another worker already holds
        it — Zalo's single-use refresh-token rotation means two concurrent
        refreshes would burn the 3-month grant.

        **Advisory, deliberately NOT ``SELECT … FOR UPDATE`` (CC-D review).**
        A row lock lives until the transaction ends — releasing the savepoint
        does not release it — and the rotation this guards is persisted by
        ``_persist_refreshed_tokens`` through an INDEPENDENT cursor, whose
        ``UPDATE`` of this very row would then block on our own row lock.
        Forever: PostgreSQL sees no cycle to break (this session is merely
        idle-in-transaction while Python waits on the other cursor) and
        ``lock_timeout`` is 0 on the deployment. The first real rotation would
        hang a worker *after* Zalo had already invalidated the old refresh
        token — destroying the grant the lock exists to protect.

        An advisory key gives the same mutual exclusion between refreshers,
        conflicts with no row write at all, and — because the key is just an
        integer — is finally stageable in a TransactionCase: a second cursor
        needs no visibility of the row to contend for it (ledger §5.63 does
        not bite here, T125).
        """
        self.ensure_one()
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                            (REFRESH_LOCK_CLASS, self.id))
        if not self.env.cr.fetchone()[0]:
            _logger.info('Channel connection %s already locked for refresh', self.id)
            return 'locked'
        return func()

    def _committed_secret(self, field_key):
        """The COMMITTED value of a secret, read on an independent cursor.

        The refresh lock is advisory, so PostgreSQL no longer fails a
        transaction whose snapshot predates another worker's rotation (a row
        lock did, with a serialisation error). Odoo opens every connection at
        REPEATABLE READ, so an in-snapshot read could hand back a refresh
        token that has already been spent — and a single-use token spent twice
        is a dead grant. Reading what is actually committed is what closes it.

        Falls back to the in-transaction value when the fresh cursor cannot
        see the row: under ``--test-enable`` the record was created inside the
        test transaction (ledger §5.63), and on any read failure a possibly
        stale token still beats no token at all.
        """
        self.ensure_one()
        # Whitelisted by construction: `column` can only be a value of the
        # SECRET_FIELDS constant, never anything a caller supplies.
        column = SECRET_FIELDS.get(field_key)
        if not column:
            raise UserError(_('Unknown credential field.'))
        if tools.config.get('test_enable') or tools.config.get('test_file'):
            return self._get_secret(field_key)
        blob = None
        try:
            with Registry(self.env.cr.dbname).cursor() as cr:
                cr.execute(
                    'SELECT %s FROM care_channel_connection WHERE id = %%s'
                    % column, (self.id,))
                row = cr.fetchone()
                blob = row[0] if row else None
        except Exception:  # noqa: BLE001 — never take the refresh down with us
            _logger.exception('Could not read the committed %s for connection '
                              '%s; falling back to this transaction',
                              field_key, self.id)
            return self._get_secret(field_key)
        if not blob:
            return self._get_secret(field_key)
        return channel_crypto.decrypt(self.env, blob)

    def _persist_refreshed_tokens(self, access_token=None, refresh_token=None,
                                  token_expires_at=None, granted_scopes=None):
        """Persist rotated credentials through a FRESH cursor that commits
        immediately.

        Providers with single-use refresh tokens (Zalo) invalidate the old
        token the moment they issue the new one. If we only wrote it into the
        request transaction and that transaction later rolled back, the grant
        would be lost for good. Same fresh-cursor idiom as the gateway audit
        writer (health_api_gateway/controllers/gateway.py:240-249).
        """
        self.ensure_one()
        vals = {}
        if access_token is not None:
            vals['access_token_enc'] = channel_crypto.encrypt(self.env, access_token)
        if refresh_token is not None:
            vals['refresh_token_enc'] = channel_crypto.encrypt(self.env, refresh_token)
        if token_expires_at is not None:
            vals['token_expires_at'] = token_expires_at
        if granted_scopes is not None:
            vals['granted_scopes'] = granted_scopes
        if not vals:
            return False
        record_id, dbname = self.id, self.env.cr.dbname
        try:
            with Registry(dbname).cursor() as cr:
                # Bounded, like the send-failure writer: even if some future
                # caller does hold a row lock on this record, persisting must
                # fail fast so the caller can fall back to an in-transaction
                # write — never hang a worker holding a rotated token
                # (CC-D review).
                cr.execute("SET LOCAL lock_timeout = '2s'")
                env = api.Environment(cr, SUPERUSER_ID, {INTERNAL_CTX: True})
                env['care.channel.connection'].browse(record_id).write(vals)
        except Exception:  # noqa: BLE001 — never take the caller down with us
            _logger.exception('Failed to persist refreshed tokens for '
                              'connection %s', record_id)
            return False
        self.invalidate_recordset(list(vals))
        return True

    # ------------------------------------------------------------------
    # Health cron (architecture §8)
    # ------------------------------------------------------------------
    def _schedule_next_health_check(self, minutes=None):
        self.ensure_one()
        if minutes is None:
            idx = min(max(self.consecutive_failures - 1, 0),
                      len(BACKOFF_MINUTES) - 1)
            minutes = (BACKOFF_MINUTES[idx] if self.consecutive_failures
                       else HEALTH_INTERVAL_MINUTES)
        self._internal().write({
            'next_health_check_at': fields.Datetime.now() + timedelta(minutes=minutes)})

    @api.model
    def _cron_channel_health(self):
        now = fields.Datetime.now()
        due = self.sudo().search([
            ('next_health_check_at', '<=', now),
            ('state', 'not in', ('not_connected', 'disabled', 'legacy')),
        ])
        for conn in due:
            # Per-record savepoint: one broken provider must never abort the
            # whole sweep (ledger §5.55).
            try:
                with self.env.cr.savepoint():
                    conn._run_health_check()
            except Exception:  # noqa: BLE001
                _logger.exception('Channel health check crashed for connection %s',
                                  conn.id)
        self.sudo()._sweep_token_expiry()
        return True

    def _run_health_check(self):
        self.ensure_one()
        try:
            result = self._get_adapter().health_check()
        except NotImplementedError:
            # Declaration-only adapter (this phase): nothing to check yet.
            self._schedule_next_health_check(HEALTH_INTERVAL_MINUTES)
            return False
        except Exception as exc:  # noqa: BLE001 — provider/network failure
            self._register_health_failure(exc)
            return False
        if isinstance(result, dict) and result.get('ok') is False:
            self._register_health_failure(result.get('error'))
            return False
        self._internal().write({
            'consecutive_failures': 0,
            'last_error_redacted': False,
            'health_status': 'healthy',
        })
        self._schedule_next_health_check(HEALTH_INTERVAL_MINUTES)
        return True

    def _register_health_failure(self, error):
        """Count the failure, back off, and record a REDACTED reason.

        A provider being down is not the tenant being broken: ``state`` is left
        alone and only ``health_status`` says ``provider_down`` (architecture §8).
        """
        self.ensure_one()
        failures = self.consecutive_failures + 1
        self._internal().write({
            'consecutive_failures': failures,
            'last_error_redacted': redact(error) or _('Health check failed'),
            'health_status': 'provider_down',
        })
        self._schedule_next_health_check()
        self.env['care.channel.audit']._log(
            'health_check', connection=self,
            detail='failure #%s: %s' % (failures, error))
        return True

    @api.model
    def _sweep_token_expiry(self):
        """Warn once, ``EXPIRY_WARNING_DAYS`` ahead, and flag past-due grants."""
        now = fields.Datetime.now()
        horizon = now + timedelta(days=EXPIRY_WARNING_DAYS)
        soon = self.sudo().search([
            ('token_expires_at', '!=', False),
            ('token_expires_at', '<=', horizon),
            ('state', 'in', ('ready', 'expiring', 'action_required', 'testing')),
        ])
        for conn in soon:
            expired = conn.token_expires_at <= now
            if expired:
                conn._internal().write({'health_status': 'action_required'})
                if conn.state != 'action_required':
                    conn._transition('action_required', reason='token expired')
            else:
                conn._internal().write({'health_status': 'expiring'})
                if conn.state == 'ready':
                    conn._transition('expiring', reason='token expiring')
                conn._ensure_expiry_activity()
        return True

    def _expiry_activity_summary(self):
        # Fixed string: the summary is the idempotency key AND is visible in
        # the activity list — no channel-specific text, and never credentials.
        return _('Channel connection expiring — reconnect needed')

    def _ensure_expiry_activity(self):
        """One open activity per connection, for the company's Care Command
        managers. Idempotent: a second cron pass creates nothing."""
        self.ensure_one()
        Activity = self.env['mail.activity'].sudo()
        model_id = self.env['ir.model']._get_id(self._name)
        summary = self._expiry_activity_summary()
        # Idempotency keys on automated=True, NOT on the summary text: the
        # summary is translated, so a server language change between cron runs
        # would duplicate the warning (CC-A review finding #7). This cron is
        # the only automated-activity creator on this model.
        existing = Activity.search_count([
            ('res_model_id', '=', model_id), ('res_id', '=', self.id),
            ('automated', '=', True),
        ])
        if existing:
            return False
        activity_type = self.env.ref('mail.mail_activity_data_todo',
                                     raise_if_not_found=False)
        user = self._expiry_activity_user()
        if not user:
            _logger.info('No manager to warn about connection %s expiry', self.id)
            return False
        days = max(0, (self.token_expires_at - fields.Datetime.now()).days)
        note = _('The %(channel)s connection stops working in %(days)s day(s). '
                 'Open Care Command → Channels and reconnect it.',
                 channel=dict(CHANNEL_SELECTION).get(self.channel, self.channel),
                 days=days)
        Activity.create({
            'res_model_id': model_id,
            'res_id': self.id,
            'activity_type_id': activity_type.id if activity_type else False,
            'summary': summary,
            'note': note,
            'user_id': user.id,
            'date_deadline': fields.Date.context_today(self),
            'automated': True,  # the idempotency key above
        })
        return True

    def _expiry_activity_user(self):
        """ONE Care Command manager of this connection's company.

        Deliberately one activity, not one per manager: an expiry warning
        fanned out to every manager is a notification storm, and the record it
        hangs on is shared anyway. Which manager gets it is stable (lowest id).

        health_user_admin is NOT a dependency in CC-A (handover §4.2 deferral),
        so the tenant-admin group is not addressable yet; the crm manager group
        is the same desk in practice. CC-F polishes admin notification routing.
        """
        self.ensure_one()
        group = self.env.ref('health_crm.group_health_crm_manager',
                             raise_if_not_found=False)
        users = self.env['res.users'].browse()
        if group:
            users = group.sudo().user_ids.filtered(
                lambda u: u.active and self.company_id in u.company_ids)
        if not users:
            admin = self.env.ref('base.user_admin', raise_if_not_found=False)
            return admin if admin and admin.active else users
        return users.sorted('id')[0]
