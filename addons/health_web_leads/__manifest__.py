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

Phase W2.5 turns provisioning into a screen (`web.leads.connector`):

* one button issues (or adopts) the service account and the OAuth client and
  shows the secret once — no SSH, no psql, no developer,
* a ready-to-paste `wp-config.php` block that carries the client id and the
  endpoint URLs but never secret material,
* the two city maps editable on screen, validated before they are saved back
  to the `ir.config_parameter` rows that stay the single source of truth,
* a pipeline test that runs a synthetic submission through the real handler
  inside a savepoint that always rolls back,
* a delivery-health strip plus the heartbeat switch and its watcher,
* disconnect / reconnect by archiving the OAuth client, never deleting it.

Design: docs/strategy/website-crm-integration.md
Handovers: docs/strategy/handovers/web-leads-phaseW1.md, …-phaseW2.md,
…-phaseW2_5.md
""",
    'version': '19.0.3.0.0',
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
        # W2.5: the connector's ACL rows and its header-button `groups=`
        # reference `health_user_admin.group_health_user_admin`. Already a
        # TRANSITIVE dependency (health_landing → health_user_admin), so this
        # edge closes no loop (§5.71 walked: health_user_admin depends on
        # health_base / health_fieldservice / access_roles / hr, and nothing
        # in the tree depends on health_web_leads).
        'health_user_admin',
    ],
    'data': [
        'security/web_leads_security.xml',
        'security/ir.model.access.csv',
        'data/web_leads_scopes.xml',
        'data/web_leads_params.xml',
        'data/web_leads_cron.xml',
        'views/lead_touchpoint_views.xml',
        'views/crm_lead_views.xml',
        'views/web_leads_connector_views.xml',
        # after the views: the sidebar items reference the actions by xmlid
        'data/cms_sidebar_items_web_leads.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
