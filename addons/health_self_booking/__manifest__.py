{
    'name': 'Health Client Self-Booking',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Tier 3: tokenized no-login client rebook page — pick a slot, '
               'book your next visit in two taps',
    'author': 'Biztinct',
    'description': """
Client Self-Booking (rebook) — health_self_booking
===================================================

A tokenized, no-login, phone-friendly public **rebook page** where an
existing client books their own next visit in two taps: pick a proposed
slot, done. It attacks phone-call rebooking load with plumbing that already
exists end-to-end — slot proposal, the quick-booking builder, packages,
the shipped messaging rails, and public token pages.

- ``health.selfbook.invite`` — one active tokenized invite per patient.
  GET ``/booking/self/<token>`` renders proposed slots; a POST accept books
  the visit (row-locked, race-safe, idempotent on double-POST).
- What "book again" offers is resolved and snapshotted at INVITE time
  (A3 precedence: active prepaid package -> last completed visit's quoted
  service -> config fallback product), so the page is stable.
- ZNS purpose ``selfbook_invite`` rides the shipped
  ``health.outbound.message`` rails (honoring ``health_messaging.enabled`` /
  ``dry_run`` exactly). Manual "Send booking link" button on the patient
  form; optional auto-invite after visit completion (config, default OFF).

No portal accounts, Zalo-first, no PWA change. The page is server QWeb like
the first-visit offer / family-link pages, not part of the nurse PWA.
""",
    'depends': [
        'health_fieldservice',
        'health_invoicing',
        'health_workflow_auto',
        'health_messaging',
        'health_api_gateway',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/health_self_booking_security.xml',
        'data/self_booking_config_params.xml',
        'views/selfbook_templates.xml',
        'views/selfbook_invite_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'sequence': 147,
    'license': 'LGPL-3',
}
