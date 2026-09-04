# -*- coding: utf-8 -*-
{
    # USER-VISIBLE, in the apps list, on every database this ships to. Plain
    # words and no framework name anywhere (rail R12): the product's own name
    # arrives at run time from a brand setting, so this module names nobody.
    'name': 'Platform Link',
    'summary': "Tells this system which release it is running, shows notices "
               "from the people who run it, and lists what changed each time.",
    'description': """
The link between one customer's system and the platform that runs it.

WHAT THIS MODULE IS. Until it is installed, a system has no idea it is one of
several. It cannot say which release of the product it is on, it cannot be told
"we are updating tonight", and after an update nobody in it can find out what
changed. The only channel was an email somebody remembered to send.

THE WHOLE CONTRACT IS TEN SETTINGS. The platform WRITES them, through this
system's own data layer; this system READS them and nothing else. There is no
callback, no queue, no agent process and no open port. If the platform were to
disappear tomorrow, every screen here would keep working with the last thing it
was told.

    biz_tenancy.release        the release name, e.g. "2026.09.04"
    biz_tenancy.release_notes  what changed, in the words somebody typed
    biz_tenancy.release_at     the day it was cut
    biz_tenancy.releases       the last ten releases, newest first (JSON)
    biz_tenancy.notice         the message to show at the top of every page
    biz_tenancy.notice_kind    "maintenance" or "info"
    biz_tenancy.notice_from    when the message starts  (stored UTC)
    biz_tenancy.notice_to      when it stops            (stored UTC)
    biz_tenancy.pushed_at      when the platform last wrote any of the above
    biz_tenancy.platform_url   where to reach the people who run the platform
    biz_tenancy.support_email  who to write to

WHAT IS ON THE SCREEN. A bar under the top of every page while there is
something to say — a planned window before an update, and a "this is happening
right now" state during one, both said in the READER's own clock. And one
screen, "About", carrying the release this system is on, what changed in it and
the ones before it, and who to contact.

IT SEEDS NOTHING AND NAMES NOBODY. No roles, no menu entries, no vocabulary of
its own. A product supplies its own brand name (`biz_debranding.brand_name`) and
puts the About screen on its own navigation; this module supplies the shape.
""",
    'version': '19.0.1.1.0',
    'category': 'Technical',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'website': 'https://www.biztinct.com',
    # `biz_kit` for the tokens, the primitives and the one `ic()` icon set.
    # Nothing else: this module is meant to be the cheapest thing on a
    # customer's system.
    'depends': ['web', 'biz_kit'],
    'data': [
        'security/ir.model.access.csv',
        'views/about_action.xml',
        'views/support_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_tenancy/static/src/scss/tenancy.scss',
            # the pure renderer first, then the service that uses it, then the
            # components that read the service.
            'biz_tenancy/static/src/js/tenancy_range.js',
            'biz_tenancy/static/src/js/tenancy_service.js',
            'biz_tenancy/static/src/js/tenancy_banner.js',
            'biz_tenancy/static/src/js/tenancy_support_bar.js',
            'biz_tenancy/static/src/js/tenancy_feature_off.js',
            'biz_tenancy/static/src/js/tenancy_about.js',
            'biz_tenancy/static/src/xml/tenancy_banner.xml',
            'biz_tenancy/static/src/xml/tenancy_support_bar.xml',
            'biz_tenancy/static/src/xml/tenancy_feature_off.xml',
            'biz_tenancy/static/src/xml/tenancy_about.xml',
            'biz_tenancy/static/src/xml/webclient_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
