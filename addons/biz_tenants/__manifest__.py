# -*- coding: utf-8 -*-
{
    'name': 'Customers (platform cockpit)',
    'summary': "Create a customer's system from the blank one, keep every "
               "customer in step, watch their health and keep their copies",
    'description': """
The screen that creates and runs customer systems. IT IS NEVER INSTALLED ON A
CUSTOMER'S SYSTEM, and that is the first line of its own never-list: inside a
customer's system it would be the controls to everybody else's.

WHAT IS ON IT

  * **Six steps and one button.** Somebody types a customer's name, presses
    Create, and watches six steps complete with the log lines they produce:
    copy the blank system, set its address and its settings, create its
    administrator, secure the address, check everything answers, hand it over.
    It ends on a working address, an administrator's sign-in name and a
    one-time password. Every step has a dry run that writes nothing, and every
    step that can fail says what failed, what it left behind, and the one
    button that continues or undoes it.
  * **The fleet.** One row per customer: their address, their state, the
    release they are on, their health, their size, when they were last copied,
    and how many of their people can sign in. Read with plain queries and one
    request each — opening a whole system per customer to draw a read-only
    screen would make it the most expensive thing on the machine.
  * **In step with master.** What each system is missing or behind on, with the
    parts a customer never receives listed separately WITH THE REASON. Nothing
    ever installs on a schedule; a person presses the button, and the screen
    says so in those words.
  * **Copies, and putting one back.** A copy every night per customer, kept for
    a fortnight, plus copies taken by hand and the final one before a customer
    is closed. A copy is the database AND the attachments and both sizes are
    checked, because an archive with no attachments in it still says "done".
    Any copy can be put back into a practice system to prove it is good.
  * **Releases.** A named photograph of what the master runs, so that "in step"
    stops being a moving target — and, for every customer moved onto one, the
    note somebody wrote when they cut it, on their own About screen.
  * **Sending a release out, in rings.** A practice run on a throwaway copy
    first — always, and the copy is deleted whatever happens — then the blank
    system, then ONE customer on their own with a watch period, then the rest,
    each inside their own quiet window said in their own clock. It stops at
    the first thing that goes wrong, and Pause, Continue now, Try again, Leave
    behind and Call it off are always one press away.
  * **Alerts.** Everything the platform notices, every quarter of an hour,
    each one with a plain sentence and what to do next. Messages are built and
    are honest when there is no account to send them with: they say so on the
    screen rather than pretending, and nothing is lost.
  * **Room for another customer.** How many more this machine holds, said as a
    number rather than as free memory — and the same number refuses a new
    customer at the door, naming the setting and the resize guide.
  * **A public page.** Written by the platform, handed out by the web server
    off disk so it stays up when the application does not. It names no
    customer, ever, and it admits it when it has gone stale.

WHAT IT KNOWS ABOUT THE PRODUCT: NOTHING. The brand, the addresses, the
never-list, the numbers a customer is measured in, which role their
administrator holds and which screen they land on all arrive through
registrations made by an overlay module (`models/tenants_common.py`). With
nothing registered this still boots, still lists what is on the machine, and
says honestly on screen that nobody has told it what this product is.
""",
    'version': '19.0.1.1.0',
    'category': 'Administration',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'website': 'https://www.biztinct.com',
    # `biz_access` for the left-menu MINIATURE beside the feature matrix. It is
    # a component that already exists and already draws a rail the way this
    # product's own screens do; a second copy of it here would be a second
    # thing to keep in step (SAAS H4c §3.4).
    'depends': ['web', 'biz_kit', 'biz_tenancy', 'biz_access'],
    'data': [
        'security/ir.model.access.csv',
        'views/biz_tenants_action.xml',
        'data/biz_feature.xml',
        'data/ir_cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_tenants/static/src/scss/tenants.scss',
            'biz_tenants/static/src/js/tenants.js',
            'biz_tenants/static/src/xml/tenants.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
