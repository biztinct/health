{
    'name': 'Health Telehealth (Video Visits)',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Tier 3: video visits for online/telemedicine bookings — a '
               'session per visit, a tokenized waiting-room page, a PWA/backend '
               'join action, and the EVV geofence exemption for online visits.',
    'author': 'Biztinct',
    'description': """
Telehealth v1 (health_telehealth)
=================================

Turns the already-modelled ``telemedicine`` service type (which sets
``service_location='online'``) into a joinable video visit:

* ``health.telehealth.session`` — one session per online FSO (room slug +
  patient token + lifecycle), created at booking confirm, opened at service
  start, closed at completion / cancellation.
* A tokenized, no-login **waiting-room page** ``/tele/visit/<token>`` that
  reveals the room URL ONLY while the visit is live (in_progress). The
  unguessable room slug is the v1 access control.
* A ``telehealth_join`` ZNS purpose riding the shipped ``health.outbound.
  message`` safety rails (honors ``health_messaging.enabled`` / ``dry_run``).
* A nurse/doctor "Vào video (Join video)" action in the PWA (shares the
  daystrip card reveal row) plus a backend "Join Video" button on the FSO.
* An EVV fix: online visits are geofence-exempt for verification (a real
  shipped defect — ``evv_verified`` could never be true for an online visit).

The room URL is a **capability URL**: it is never logged at info level and is
served only in the live state. Self-hosting Jitsi with signed JWT room tokens
is the documented v2 upgrade path (config already points at a base URL so ops
can self-host later without a code change).
""",
    'depends': [
        'health_pwa_daystrip',
        'health_evv',
        'health_messaging',
        'health_consent',
        'health_api_gateway',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/telehealth_security.xml',
        'data/telehealth_config_params.xml',
        'views/telehealth_templates.xml',
        'views/telehealth_session_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/pwa_shell_inherit.xml',
    ],
    # NB: static/src/js/telehealth.js + css are PWA/public-page assets loaded by
    # <script>/<link> tags, not by a bundle. These two are backend-only.
    'assets': {
        'web.assets_backend': [
            'health_telehealth/static/src/js/booking_telehealth_widget.js',
            'health_telehealth/static/src/xml/booking_telehealth_widget.xml',
        ],
    },
    'installable': True,
    'application': False,
    'sequence': 150,
    'license': 'LGPL-3',
}
