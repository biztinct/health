# -*- coding: utf-8 -*-
{
    'name': 'Health Web Leads',
    'summary': 'Website contact-form capture: attribution fields, touchpoints '
               'and POST /api/v1/web/leads on the API-gateway rails',
    'description': """
Website → CRM lead integration, Phase W1.

Turns pkgdvietuc.com contact-form submissions into `crm.lead` records with
city (catchment) and marketing attribution, over the existing
`health_api_gateway` OAuth2 rails:

* attribution fields on `crm.lead` (UTM content/term, click ids, URLs,
  the WordPress submission id, city derivation provenance),
* `health.lead.touchpoint` — one row per interaction (first touch = the
  lead's own fields, last touch = the newest touchpoint),
* `POST /api/v1/web/leads` (scope `web_lead.write`) — idempotent,
  spam-gated, city-resolving, lead-to-lead deduplicating.

Design: docs/strategy/website-crm-integration.md
Handover: docs/strategy/handovers/web-leads-phaseW1.md
""",
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'author': 'Biztinct',
    'website': 'https://carejiox.com',
    'depends': [
        'health_base',
        'health_crm',
        'health_api_gateway',
    ],
    'data': [
        'security/web_leads_security.xml',
        'security/ir.model.access.csv',
        'data/web_leads_scopes.xml',
        'data/web_leads_params.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
