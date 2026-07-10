# -*- coding: utf-8 -*-
{
    'name': 'Health — Schedule Canvas',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Draw-to-create bookings, off-hours compression and windowed '
               'fetch on the unified staff schedule timeline.',
    'description': """
Schedule Timeline v2 (health_schedule_canvas)
=============================================
Adds to the unified Staff Schedule (action 1536, web_timeline on
health.staff.assignment):

* **Draw-to-create** — double-click a staff lane to open a quick-booking dialog
  pre-filled with that staff + time; saving creates the FSO + assignment through
  the shipped builder and reloads the timeline. Ops-group gated.
* **Off-hours compression** — vis hiddenDates collapse empty night/weekend space
  in Day/Week, with a persistent toolbar toggle; windows that contain a booking
  stay visible.
* **Performance** — opt-in windowed fetch (web_timeline dynamic_range), month
  overlay thinning and clustering.
* **Retires the template-assignment side channel** in health_fieldservice
  (the create dialog now receives the action context natively).
""",
    'author': 'Biztinct',
    'license': 'LGPL-3',
    'depends': [
        'health_fieldservice',
        'health_schedule_drag',
    ],
    'data': [
        'views/staff_schedule_canvas_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_schedule_canvas/static/src/js/quick_create_dialog.esm.js',
            'health_schedule_canvas/static/src/xml/quick_create_dialog.xml',
            'health_schedule_canvas/static/src/js/schedule_canvas.esm.js',
            'health_schedule_canvas/static/src/scss/schedule_canvas.scss',
        ],
    },
    'post_init_hook': 'post_init_cleanup_templates',
    'installable': True,
    'application': False,
}
