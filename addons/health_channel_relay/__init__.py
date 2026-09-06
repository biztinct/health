# -*- coding: utf-8 -*-
"""Channel Relay — the customer half. One override, and that is the module.

Meta hands a sign-in back to exactly ONE address per login configuration and
matches it character for character, so every customer's Messenger sign-in has
to come back through the platform. The only thing the platform's callback can
use to work out whose sign-in it is holding is the ``state`` ticket Meta echoes
back untouched — and that string is opaque to everything except the customer's
own ``_consume`` (ledger §5.173).

So this module puts the customer's own short name in front of it, once, at the
moment the ticket is minted:

    ``<slug>~<the ordinary random ticket>``

The hash that is stored is the hash of the WHOLE string, ``_consume`` hashes
whatever comes back, and the platform passes the string on untouched — so
nothing about the sign-in itself changes. ``~`` is outside the alphabet the
ticket is generated from, which is what makes the split unambiguous.

On the platform's own system ``biz_tenancy.slug`` is never set, so the ticket
carries no prefix and the platform handles its own sign-ins itself. Nothing
else in this module: the return address is a parameter the platform writes, and
the credentials arrive the same way.
"""
from . import models
