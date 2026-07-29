# -*- coding: utf-8 -*-
{
    'name': 'Health Web Leads',
    'summary': 'Website contact-form capture: attribution fields, touchpoints '
               'and POST /api/v1/web/leads on the API-gateway rails',
    'description': """
Website → CRM lead integration, Phases W1 + W2.

Turns pkgdvietuc.com contact-form submissions into `crm.lead` records with
city (catchment) and marketing attribution, over the existing
`health_api_gateway` OAuth2 rails:

* attribution fields on `crm.lead` (UTM content/term, click ids, URLs,
  the WordPress submission id, city derivation provenance),
* `health.lead.touchpoint` — one row per interaction (first touch = the
  lead's own fields, last touch = the newest touchpoint),
* `POST /api/v1/web/leads` (scope `web_lead.write`) — idempotent,
  spam-gated, city-resolving, lead-to-lead deduplicating.

Phase W2 makes that pipeline operable:

* `POST /api/v1/web/leads/reconcile` (scope `web_lead.read`) — the relay's
  daily known/missing check plus per-day created/merged counts,
* a daily heartbeat cron that raises ONE activity when the relay goes quiet
  (ships active, gated off by `web_leads.heartbeat_enabled`),
* the Web Attribution tab, the Lead Hub Source-modal fields, the touchpoint
  list and the `Needs review (web)` / `City conflict` / `Web leads` filters,
* a `crm.lead.message_new` guard so a marked CF7 notification email files
  onto the lead its webhook already created instead of making a second one,
* a service account narrowed to its own ACL rows — no salesman group, so no
  `res.partner` writes and no accounting reads.

Design: docs/strategy/website-crm-integration.md
Handovers: docs/strategy/handovers/web-leads-phaseW1.md, …-phaseW2.md
""",
    'version': '19.0.2.0.0',
    'category': 'Healthcare',
    'author': 'Biztinct',
    'website': 'https://carejiox.com',
    'depends': [
        'health_base',
        'health_crm',
        'health_api_gateway',
        # W2: the ops-facing lead UI is the Lead Hub, and its Source spoke
        # modal lives here — an inheritance record cannot ref a view from a
        # module that is not a dependency. No loop: nothing depends on
        # health_web_leads (ledger §5.71).
        'health_landing',
        # W2: the CMS shell is where the ops persona actually lives, so the
        # touchpoint list needs a `cms.sidebar.item` seed (ledger §5.69).
        'health_cms_sidebar',
    ],
    'data': [
        'security/web_leads_security.xml',
        'security/ir.model.access.csv',
        'data/web_leads_scopes.xml',
        'data/web_leads_params.xml',
        'data/web_leads_cron.xml',
        'views/lead_touchpoint_views.xml',
        'views/crm_lead_views.xml',
        # after the views: the sidebar item references the action by xmlid
        'data/cms_sidebar_items_web_leads.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
