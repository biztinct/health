# -*- coding: utf-8 -*-
{
    'name': 'Viet Uc Care — platform overlay',
    'summary': "Tells the generic platform modules what this product is: its "
               "name, its addresses, what a customer never receives, what a "
               "customer's use is measured in, and where its doors go",
    'description': """
The one module that knows this is a healthcare product, sitting between the two
generic platform modules and everything else.

WHY IT EXISTS. `biz_tenancy` and `biz_tenants` were written to be lifted into
the next product. They therefore know nothing about clinics, visits, patients or
Viet Uc Care, and they ship no vocabulary of their own. This module registers
the five things they need and nothing else:

  1. **Who we are and where we live** — the brand, the apex domain, the address
     the application is served under, and the name of the blank system every new
     customer is copied from. All four are DEFAULTS behind settings, because the
     platform's own address has already changed once mid-programme.
  2. **What a customer never receives** — the cockpit itself, the data-migration
     tools and the one-off catchment backfill, plus a name prefix reserved for
     anything the platform grows later.
  3. **What a customer's use is measured in** — people in care, visits
     completed, staff with a login, invoices issued. Every one of them is
     collected every time; which one a customer is SOLD on is a later decision,
     made out of numbers that were already gathered.
  4. **Who a customer's own administrator is** — the Owner role and the clinic
     administrator tier, named by their fixed ids so a rename cannot break this.
     Never the system administrator permission: that is the platform's, and a
     customer's administrator runs their own system and nothing of ours.
  5. **The doors.** "About Viet Uc Care" on every system's own left menu, and
     "Customers" on the platform's — the second switched OFF automatically on
     any system where the cockpit is not installed, because an entry that opens
     nothing is a dead end and a dead end is worse than an absence.

EVERYTHING HERE IS INERT WHERE THE COCKPIT IS ABSENT. The registrations are
wrapped so that a customer's system — which has this module and not the cockpit —
loads it, registers what it can, and carries on.
""",
    'version': '19.0.1.1.0',
    'category': 'Administration',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'website': 'https://www.biztinct.com',
    'depends': [
        'biz_tenancy',          # the platform link this overlay puts a door on
        'health_cms_sidebar',   # the left menu both doors live on
        'health_access',        # the roles the doors are gated to
    ],
    'data': [
        'data/cms_sidebar_items.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # One line of glue: the platform link says "which parts of the
            # product are switched on has changed", and this product's own
            # left menu is asked to draw itself again (ledger F48).
            'health_tenancy/static/src/js/tenancy_rail_bridge.js',
        ],
    },
    # Gates the two entries to the right roles and switches off any whose
    # action is not on this system. A hook rather than a `ref=` in the data
    # file, because the roles are created by another module's own hook and a
    # `ref()` can only point at a row that already exists when the file is read.
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
