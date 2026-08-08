{
    'name': 'Health Family Visit Link',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Tier 3a: tokenized no-login family visit page + post-visit '
               'snapshot ZNS through the shipped messaging rails',
    'author': 'Biztinct',
    'description': """
Family Visit Link + Post-Visit Snapshot (FA-066 / UX-093 v1)
============================================================

A tokenized, no-login, phone-friendly public page per (visit, family
relation) that follows the visit lifecycle: upcoming -> nurse arrived ->
completed (with a sanitized snapshot). One link covers the whole visit; the
completion ZNS points at the same URL.

Two family ZNS purposes ride the shipped ``health.outbound.message`` rails
(``family_visit_link`` at booking confirmation, ``family_snapshot`` at
completion), honoring ``health_messaging.enabled`` / ``dry_run`` exactly.

Consent: sends are gated by three ANDed conditions per recipient — the
relation's ``receives_visit_updates`` opt-in (default False, so installing
changes nothing), ``can_receive_medical_info`` (snapshot only), and the
shipped ``health.consent`` ``data_sharing`` check. Consent withdrawal is
enforced at render time: a completed-state page re-checks ``data_sharing``
on every view and falls back to the neutral page when consent is gone — no
write hooks into health_consent are needed.
""",
    'depends': [
        'health_fieldservice',
        'health_messaging',
        'health_consent',
        'health_crm',
        'health_api_gateway',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/health_family_link_security.xml',
        'data/family_link_config_params.xml',
        'views/family_templates.xml',
        'views/family_link_views.xml',
        'views/health_client_relation_views.xml',
        'views/ops_booking_family_tab.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_family_link/static/src/js/booking_family_widget.js',
            'health_family_link/static/src/xml/booking_family_widget.xml',
        ],
    },
    'installable': True,
    'application': False,
    'sequence': 146,
    'license': 'LGPL-3',
}
