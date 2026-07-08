{
    'name': 'Health PWA Day-Strip + On My Way',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Day-strip timeline, swipe-to-reveal actions, and an '
               '"On my way" travel event that lights up the family page.',
    'author': 'Biztinct',
    # Two model inherits (EVV event types + family page context), one PWA
    # front-of-house layer (daystrip.js/css injected into the shell), and a
    # family-page template inherit. No new tables, crons, config params, or
    # ACLs — health.evv.event ACLs already cover the new event types.
    'depends': [
        'health_pwa',
        'health_evv',
        'health_family_link',
    ],
    'data': [
        'views/pwa_shell_inherit.xml',
        'views/family_templates_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'sequence': 148,
    'license': 'LGPL-3',
}
