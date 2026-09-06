# -*- coding: utf-8 -*-
"""Channel Relay — the hub half. Master database only.

WHY THIS MODULE EXISTS
======================

Meta allows exactly ONE webhook address per product per app (one for WhatsApp,
one for Messenger) and its sign-in return list is exact-match with no wildcard
(ledger §5.171). This platform is one database per customer on its own
subdomain, and each of them expects Meta to call *its own* address. Without a
relay, one Meta app serves exactly one customer and every new customer costs a
second App Review — weeks — or an operator editing the Meta console by hand.

So the master takes everything and hands each customer only their own share:

1. **Incoming messages.** Meta calls the master's existing webhook address.
   ``RelayMetaWebhookController`` verifies the signature exactly as the
   customer-side route does, then ``channel.relay.router._route_meta`` looks at
   which Page / WhatsApp number each entry is for, SPLITS the batch so nothing
   of one clinic's traffic reaches another's server, RE-SIGNS each share with
   the app secret and posts it to that customer's own webhook route. The
   customer's code is unchanged: it verifies the signature as if Meta had
   called it directly.
2. **Sign-in.** Every customer's Messenger sign-in returns to the master's
   single callback address. ``RelayOauthController`` reads the customer's short
   name out of the ``<slug>~`` prefix the customer's own ``_mint_state`` put in
   front of the opaque state (ledger §5.173), checks it against the allowlist
   of active ``channel.relay.tenant`` rows — never against the string itself —
   and bounces the browser to that customer's callback, which finishes the
   sign-in as it always did.
3. **Credentials.** ``channel.relay.tenant._reconcile`` pushes the Meta app id,
   secret and configuration ids into every serving customer's database,
   encrypted INSIDE that database's own environment because the key is derived
   per database (ledger §5.172). Nobody ever pastes a secret twice.

THE RULES THIS MODULE IS BUILT ON
=================================

* **Signature first, then 200.** The relay verifies with the master's secret
  before it does anything, and answers Meta 200 from that point on whatever a
  customer does — a non-2xx makes Meta retry the whole batch for every customer
  and, sustained, gets the app's Messenger webhook disabled for all of them.
  The retry queue is therefore OURS (``channel.relay.delivery``).
* **Only a customer's own entries leave the master.** ``services.relay
  .split_payload`` is that boundary and it is a pure function so it can be
  tested in isolation.
* **The redirect allowlist is the route table**, not the state string. An open
  redirect on an OAuth callback is a phishing primitive.
* **No message body on the master except encrypted, in the retry queue, for a
  delivery that failed** — cleared on delivery, purged after seven days.
* **Every audit detail is a short name, a channel and a count.** No phone
  number, no page id, no sender, no text, no code, no state, no token.
* **Cross-database writes go through ``biz.tenants._tenant_env`` only** (rail
  R5) and reads through ``_pg_cursor``. A public route never opens a registry.

It ships to the master and to nothing else: the ``biz_platform`` prefix is on
``health_tenancy``'s never-list, so no customer system can ever receive it.
"""
from . import models
from . import services
from . import controllers
