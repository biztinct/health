# -*- coding: utf-8 -*-
"""The routing decision, as model code so a plain test can drive it.

The controller above this is a shell: it captures the request and hands the
decision here (the same posture the Meta relay already uses — logic in a model,
a few lines in the route, ledger §5.32).

Nothing from a call — no phone number, no hotline, no recording link — may reach
a log line or a stored error. Short names, addresses and counts, and nothing
else. A call-back address is the public half of a credential and is already in
every web-server log on this box, so it may be logged; the token beside it in
the path never is.
"""
import logging

from odoo import api, fields, models

from ..services import relay

_logger = logging.getLogger(__name__)


class VoipRelayRouter(models.AbstractModel):
    _name = 'voip.relay.router'
    _description = 'Phone relay router'

    # ------------------------------------------------------------------
    # The routing decision
    # ------------------------------------------------------------------
    @api.model
    def _classify(self, receiver_id, hotline=''):
        """Who does this call-back belong to? ``(kind, tenant)``.

        Resolution order, and the order is the design:

        1. **A customer's own call-back address.** Read out of that customer's
           system, unique across the whole platform. Nothing in the payload can
           override it — a call that arrived on a customer's address belongs to
           that customer, full stop.
        2. **This platform's own clinic**, when the address is one of ours. A
           shared account with the phone supplier can still put several
           customers on this one address, so the hotline is consulted here and
           only here: if a customer owns the hotline dialled, the call is
           theirs; otherwise it is ours.
        3. **Nobody.** Read the customers once more — throttled — and look
           again, because "a customer finished setting up a minute ago" is the
           ordinary shape of this. Still nobody, and the call is left to the
           route that was already there, which refuses it.
        """
        Route = self.env['voip.relay.route']
        tenant = Route._find('receiver', receiver_id)
        if tenant:
            return relay.TENANT, tenant

        if self._is_local_receiver(receiver_id):
            if hotline:
                owner = Route._find('hotline', hotline)
                if owner:
                    return relay.TENANT, owner
            return relay.LOCAL, None

        # Unknown on both counts. A customer whose system minted its address
        # since the last reconcile looks exactly like this.
        self.env['voip.relay.tenant']._maybe_resync(reason='unknown address')
        tenant = Route._find('receiver', receiver_id)
        if tenant:
            return relay.TENANT, tenant
        if self._is_local_receiver(receiver_id):
            return relay.LOCAL, None
        return relay.UNKNOWN, None

    @api.model
    def _is_local_receiver(self, receiver_id):
        """Does the platform's own clinic answer to this address?

        The token is NOT checked here and must not be: this only decides which
        system should be asked. Whoever ends up handling the call does the
        constant-time check against its own database, and refuses it if it is
        wrong — including this one.
        """
        if not receiver_id:
            return False
        return bool(self.env['voip.config'].sudo()
                    .with_context(active_test=False)
                    .search_count([('receiver_id', '=', receiver_id)]))

    # ------------------------------------------------------------------
    # The hand-off
    # ------------------------------------------------------------------
    @api.model
    def _hand_over(self, tenant, feed, delivery):
        """Give one call-back to one customer. ``(status, body)``.

        Never raises. A customer's system that answered — with anything, a
        refusal included — has given the verdict, and that verdict is what the
        phone supplier is told. A customer's system that could not be reached
        becomes a queued hand-off and the supplier is told it was accepted,
        because at that point it durably has been: the row is committed before
        this returns.
        """
        try:
            status, body = relay.forward(self.env, tenant.host, delivery)
        except Exception as exc:  # noqa: BLE001 — every failure is a queue
            reason = (str(exc) if isinstance(exc, relay.RelayError)
                      else type(exc).__name__)
            _logger.warning('voip relay: %s could not be reached (%s) — the '
                            'call is queued', tenant.slug, reason)
            self.env['voip.relay.delivery']._queue(tenant, feed, delivery,
                                                   reason)
            return 202, {'status': 'accepted'}
        tenant.sudo().write({
            'last_forward_at': fields.Datetime.now(),
            'last_error': False if 200 <= status < 300
            else 'answered HTTP %s' % status,
        })
        _logger.info('voip relay: %s call-back handed to %s (HTTP %s)',
                     feed, tenant.slug, status)
        return status, body
