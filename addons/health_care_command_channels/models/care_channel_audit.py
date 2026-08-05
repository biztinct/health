# -*- coding: utf-8 -*-
"""Append-only channel operations audit (architecture §5.5).

Posture cloned verbatim from ``health.consent.check.log``: ``write()`` and
``unlink()`` raise UNCONDITIONALLY — no ``self.env.su`` escape, because uid 1
always runs as su and any su bypass voids the guarantee (ledger §5.4).

``connection_id`` uses ``ondelete='set null'``, NOT cascade: a cascade is
executed by PostgreSQL and never fires the Python ``unlink()`` guard, so
deleting a connection would silently erase its whole audit history
(ledger §5.30/§5.19).

Nothing here is ever written raw: ``detail`` flows through
``services/redact.py`` on the way in, so no token, secret, URL query string or
provider payload can land in the table.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.redact import redact

_logger = logging.getLogger(__name__)

# Known event tags (architecture §5.5). ``event`` is a Char (not a Selection)
# so a later phase's adapter can add one without a schema change; an unknown
# tag is logged but never refused — losing the audit row would be worse.
KNOWN_EVENTS = {
    'connect_start', 'callback_ok', 'callback_denied', 'callback_error',
    'resource_selected', 'webhook_subscribed', 'test_ok', 'test_fail',
    'reconnect', 'disconnect', 'secret_rotated', 'refresh_ok', 'refresh_fail',
    'health_transition', 'health_check',
    # CC-B (message spine): a webhook we verified but deliberately dropped
    # because the connection is not in an ingestable state, and a send that
    # the provider refused.
    'webhook_ignored', 'send_failed',
    # CC-E (Meta): a subscribed_apps call the provider refused, and a re-read
    # of where Meta's human reviews stand.
    'webhook_failed', 'approvals_refreshed',
    # CC-G (platform go-live): the operator minted a Meta webhook verify token,
    # and the outcome of a platform-application preflight. Both are plane-1
    # operator events — no connection, no tenant.
    'verify_token_generated', 'preflight',
    # GL-1 (Go-Live Studio): a provider's own dashboard completed the webhook
    # handshake against this deployment — the only honest proof that the
    # operator pasted our URL and our verify token correctly.
    'webhook_handshake',
    # GL-3 (delegation): a go-live step was emailed to somebody outside
    # Health19, that link was opened, or it was withdrawn. NEVER the token —
    # the detail carries the provider/step and a masked address, nothing more.
    'golive_invite_sent', 'golive_invite_viewed', 'golive_invite_revoked',
}


class CareChannelAudit(models.Model):
    _name = 'care.channel.audit'
    _description = 'Channel Connection Audit'
    _order = 'id desc'

    company_id = fields.Many2one(
        'res.company', string='Company', index=True, required=True,
        default=lambda self: self.env.company)
    connection_id = fields.Many2one(
        'care.channel.connection', string='Connection', index=True,
        ondelete='set null')
    channel = fields.Char(index=True)
    user_id = fields.Many2one(
        'res.users', string='User', default=lambda self: self.env.uid)
    event = fields.Char(required=True, index=True)
    detail_redacted = fields.Char(string='Detail')
    ts = fields.Datetime(
        string='Timestamp', required=True, default=fields.Datetime.now)

    # ------------------------------------------------------------------
    # Append-only guards (unconditional — ledger §5.4)
    # ------------------------------------------------------------------
    @api.model
    def _blocked(self):
        raise UserError(_(
            'Channel audit entries are append-only operational evidence '
            'and can never be modified or deleted.'))

    def write(self, vals):
        self._blocked()

    def unlink(self):
        self._blocked()

    # ------------------------------------------------------------------
    # The ONE writer
    # ------------------------------------------------------------------
    @api.model
    def _log(self, event, connection=None, company_id=None, user=None,
             detail=None, channel=None):
        """Append one audit row. NEVER breaks the caller.

        The create runs inside ``cr.savepoint()`` *inside* the try: a bare
        try/except does not protect the host transaction from a database-level
        error — once PostgreSQL aborts, every later statement in the caller's
        flow fails too (ledger §5.55).

        Named ``_log`` (not ``log``): it creates through ``sudo()``, so a
        public name would let any RPC caller forge operational evidence.
        """
        if event not in KNOWN_EVENTS:
            _logger.info('care.channel.audit: unknown event tag %r', event)
        try:
            with self.env.cr.savepoint():
                vals = {
                    'event': event,
                    'company_id': (company_id
                                   or (connection.company_id.id if connection else False)
                                   or self.env.company.id),
                    'connection_id': connection.id if connection else False,
                    'channel': channel or (connection.channel if connection else False),
                    'user_id': (user.id if user else self.env.uid),
                    'detail_redacted': redact(detail),
                    'ts': fields.Datetime.now(),
                }
                return self.sudo().create(vals)
        except Exception:  # noqa: BLE001 — auditing must never break the flow
            _logger.exception('Failed to write care.channel.audit row (%s)', event)
            return self.browse()

    @api.model
    def _redact(self, text):
        """Model-level handle on the shared redaction helper (tests + views)."""
        return redact(text)
