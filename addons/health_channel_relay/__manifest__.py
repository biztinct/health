# -*- coding: utf-8 -*-
{
    'name': 'Channel Relay (customer)',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/CRM',
    'summary': 'Messenger sign-in returns through the platform and finds its '
               'way home',
    'description': """
Channel Relay — R1 (the customer side)
======================================

Meta hands a completed sign-in back to one address and one address only. This
system's address is not that one — the platform's is — so a Messenger sign-in
started here would otherwise come back to the wrong place and stop.

This module writes this system's short name into the sign-in ticket, once, when
the ticket is created. The platform reads it, sends the browser straight back
here, and the sign-in finishes exactly as it always did. Nothing is stored, no
screen changes, and there is nothing to set up.

On the platform's own system it does nothing at all.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        # The sign-in engine whose ticket is being prefixed.
        'health_care_command_channels',
        # Where this system's own short name is kept.
        'biz_tenancy',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'sequence': 128,
}
