{
    'name': 'Health PWA Family Messaging',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Field-nurse PWA: family-message panel on the visit screen + '
               'FB-047 one-tap post-visit family update; plus the proper '
               'family_message bell card (sanctioned PWA 1.10.0 edit).',
    'author': 'Biztinct',
    # A PWA front-of-house layer over health_family_messages: fammsg.js/css
    # injected into the app shell (visit-context messages panel + FB-047
    # update), three /health_pwa/api/fso/<id>/family_messages* endpoints
    # (nurse-scoped, sudo after the scope check), and a family_update ZNS
    # purpose. The bell card + the 1.10.0 bump are sanctioned health_pwa edits
    # (handover §2). No new tables, crons, or ACLs.
    'depends': [
        'health_family_messages',
        'health_pwa',
    ],
    'data': [
        'data/pwa_family_config_params.xml',
        'views/pwa_shell_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'sequence': 149,
    'license': 'LGPL-3',
}
