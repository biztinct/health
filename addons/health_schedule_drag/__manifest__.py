# -*- coding: utf-8 -*-
{
    'name': 'Health Schedule Reschedule-by-Drag',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Dragging an assignment on the staff schedule actually '
               'reschedules the booking — validated, ops-gated, matrix-'
               'consistent, multi-staff-coherent, notified.',
    'description': """
Reschedule-by-Drag (health_schedule_drag)
=========================================

On the unified staff schedule (action 1536, web_timeline on
health.staff.assignment), dragging an assignment block to a new time / day /
staff lane RESCHEDULES the whole booking through a single server gate
``reschedule_from_drag``:

* **Ops-only, state-gated**: operations_manager / head_nurse / manager+ only;
  the FSO must be ``confirmed`` or ``assigned`` — anything else (draft /
  in_progress / completed / cancelled) is refused with a snap-back.
* **Drag MOVES, never resizes**: the end is recomputed from the booking's
  scheduled_duration; the client's end is ignored, so a resize can never
  smuggle a duration change.
* **Multi-staff coherent**: the reschedule writes the FSO's scheduled_datetime,
  and the shipped FSO write path resyncs every sibling assignment, fires the
  staff push notification, and records a chatter entry — all for free.
* **Matrix-consistent**: the stale booked/buffer availability rows are released
  and the new slot is re-booked (best-effort).
* **Patient-notified**: a ``booking_rescheduled`` ZNS on the messaging rails
  (empty template default → no send), dedup-keyed on the new datetime.

Refusals and unvalidated overlaps snap the block back; warnings ask for
confirmation first. Backend timeline only — no PWA change.
""",
    'author': 'Biztinct',
    'website': 'https://biztinct.com',
    'license': 'LGPL-3',
    'sequence': 168,
    'depends': [
        'health_fieldservice',
        'health_messaging',
    ],
    'data': [
        'data/schedule_drag_config_params.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_schedule_drag/static/src/js/schedule_drag.esm.js',
        ],
    },
    'installable': True,
    'application': False,
}
