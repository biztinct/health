# -*- coding: utf-8 -*-
{
    'name': 'Phone Relay (platform)',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Telephony',
    'summary': 'One call-back address serves every customer: the platform '
               'reads who a call belongs to and hands it on',
    'description': """
Phone Relay — one address for every customer's phone system
===========================================================

This platform is one database per customer on its own address. Without this
module every customer's phone supplier has to be pointed at that customer's own
address, and the address the supplier is given is different for each of them.

This module makes the platform's own address the single one the phone supplier
ever calls. A call record arrives there, the platform reads which customer it
belongs to, and hands it to that customer's own system over this machine's
internal loopback — never over the internet, never through DNS, never through a
certificate. The customer's own code is untouched: it checks the call-back
address exactly as if the supplier had called it directly.

**The platform does not keep a customer's call-back password.** The address the
supplier calls already carries it, and it is passed through byte for byte. All
this platform stores is the public half of that address — the part that is
already visible in any web-server log — and the short name of the customer it
belongs to. The one exception is a call that could not be delivered because the
customer's system was unreachable: that is held encrypted so it can be tried
again, is never shown on any screen, and is erased the moment it lands.

Who a call belongs to
---------------------

* **By call-back address** — the ordinary case, and the only one that needs no
  setting up. Each customer's system mints its own call-back address; the
  platform reads the public half out of that customer's system every ten
  minutes and routes on it. A customer added five minutes ago is being served
  inside ten without anybody pressing anything.
* **By hotline number** — for the case where several customers share ONE
  account with the phone supplier, so every call arrives on the same address.
  An operator enters which customer owns which hotline number. This covers
  completed call records, which carry the hotline; live ringing events do not
  carry it and are never guessed at.

What the operator sees
----------------------

Two screens under Phone System → Setup: *Customer phone relay*, one row per
customer with the addresses read from their system, the hotlines they own and
when a call last reached them; and *Relay deliveries*, the hand-offs that did
not land and are waiting to be tried again. No phone number from a call is ever
shown on these screens, logged, or kept unencrypted.

Where it runs
-------------

The platform's own system, and nowhere else. On a customer system the customer
list does not exist, the routing table stays empty and every call is handled
locally exactly as before — so installing it there changes nothing, and it is
not meant to be installed there.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        # The customer list, the read-only per-customer cursor and the
        # sanctioned cross-database environment (rail R5) all live here.
        'biz_tenants',
        # The two call-back routes being extended, the encryption helper the
        # queued hand-offs are stored with, and the menu they sit under.
        'health_voip24h',
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
    'sequence': 128,
}
