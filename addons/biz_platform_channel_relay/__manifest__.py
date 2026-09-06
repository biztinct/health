# -*- coding: utf-8 -*-
{
    'name': 'Channel Relay (platform)',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/CRM',
    'summary': 'One Meta application serves every customer: the platform '
               'splits, re-signs and forwards; sign-ins bounce home',
    'description': """
Channel Relay — R1 (the hub)
============================

Meta allows exactly ONE webhook address per product per application, and its
sign-in return list is exact-match with no wildcard. This platform is one
database per customer on its own address. Without this module one Meta
application serves one customer, and every new customer costs another
application review.

This module makes the platform the single address Meta talks to:

* **Incoming messages.** The platform's webhook verifies Meta's signature,
  splits the batch by which Page or WhatsApp number each entry is for,
  re-signs each customer's share and posts it to that customer's own webhook.
  Nothing of one clinic's traffic ever reaches another clinic's system, and the
  customer's own code is untouched — it checks the signature exactly as if Meta
  had called it.
* **Sign-in.** Every customer's Messenger sign-in returns to the platform's one
  callback address, which reads the customer's short name out of the sign-in
  ticket and sends the browser on to that customer's own callback. The short
  name is routing, never trust: the destination comes from the customer list
  held here, and from nowhere else.
* **Credentials.** The Meta application id, secret and configuration ids are
  pushed into every serving customer's system every ten minutes, encrypted
  inside that system with that system's own key. Nobody pastes a secret twice.

**What the operator sees**: two screens under Care Command Setup — *Customer
relay*, one row per customer with whether they hold the same application as the
platform, how many Pages and numbers they own and when a message last reached
them; and *Relay deliveries*, the forwards that did not land and are waiting to
be tried again. No message text is ever shown, stored unencrypted, logged or
written into an audit line.

**Where it runs**: the platform's own system, and nowhere else. A customer
system can never receive it.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        # The customer list, the per-customer cursor and the sanctioned
        # cross-database environment (rail R5) all live here.
        'biz_tenants',
        # The webhook route being extended, the platform application row the
        # secret is read from, the audit log and the crypto helper.
        'health_care_command_channels',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/relay_views.xml',
        'views/menus.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'sequence': 127,
}
