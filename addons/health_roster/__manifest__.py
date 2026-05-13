{
    'name': 'Healthcare Roster Planning',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Operations',
    'summary': 'Nursing roster planning board with weekly grid view and drag-drop assignment',
    'description': """
        Healthcare Roster Planning
        ==========================

        Weekly planning board for nursing staff scheduling:
        - Nurses x Days grid with assignment cards
        - Drag-and-drop from unassigned bookings to assign staff
        - Conflict detection for overlapping assignments
        - Leave overlay and utilization tracking
        - Filters by facility, catchment area, and availability

        Integrates into the Operations Center sidebar.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'health_fieldservice',
        'health_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/roster_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_roster/static/src/scss/roster_planning.scss',
            'health_roster/static/src/js/roster_planning.js',
            'health_roster/static/src/xml/roster_planning.xml',
            'health_roster/static/src/xml/sidebar_inherit.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'sequence': 115,
}
