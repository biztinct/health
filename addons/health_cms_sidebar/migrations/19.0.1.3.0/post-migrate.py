# -*- coding: utf-8 -*-
"""Re-point the ADMIN sidebar's Pricing and Master Data leaves.

WHY A MIGRATION AND NOT JUST THE XML
------------------------------------
`data/cms_sidebar_items_admin.xml` is `<odoo noupdate="1">`, so the edited
`action_xmlid` / `match_action_xmlids` on `item_admin_pricing` and
`item_admin_master_data` are dropped on upgrade for any database where those
rows already exist — the XML change only reaches fresh installs. (Ledger: the
noupdate seed-cutover gotcha.) This script writes the same values to the DB,
idempotently, so existing databases converge.

WHAT CHANGES
------------
* Pricing now lands on the new **Services** list (`product.template`,
  `type='service'` — what "Import Price List" populates) instead of the
  single-row pricing-ENGINE list, which is no longer a tab.
* Master Data matches the eleven new lookup-table actions, so opening any of
  them keeps the CMS shell AND keeps "Master Data" highlighted. The xml-id
  index wins over `match_models` in `_resolveActiveItem`, which is what stops
  the new Deletion Reasons tab from lighting up "Data Lifecycle" instead.
"""

MASTER_DATA_ACTIONS = [
    'health_landing.action_admin_facilities',
    'health_landing.action_admin_catchments',
    'health_landing.action_admin_service_types',
    'health_landing.action_admin_symptoms',
    'health_landing.action_admin_referral_sources',
    'health_landing.action_admin_insurance',
    'health_landing.action_admin_urgency',
    'health_landing.action_admin_categories',
    'health_landing.action_admin_specialties',
    'health_landing.action_admin_districts',
    'health_landing.action_admin_provinces',
    'health_landing.action_admin_contact_reasons',
    'health_landing.action_admin_lead_reasons',
    'health_landing.action_admin_lost_reasons',
    'health_landing.action_admin_service_categories',
    'health_landing.action_admin_protocols',
    'health_cms_sidebar.action_admin_medications',
    'health_landing.action_admin_booking_stages',
    'health_landing.action_admin_fs_teams',
    'health_landing.action_admin_cancel_reasons',
    'health_landing.action_admin_deletion_reasons',
    'health_cms_sidebar.action_admin_observation_types',
    'health_cms_sidebar.action_admin_notgiven_reasons',
    'health_landing.action_admin_lookup_values',
    'health_landing.action_admin_lookup_categories',
]

PRICING_ACTIONS = [
    'health_landing.action_admin_services',
    'health_landing.action_admin_pricelists',
    'health_landing.action_admin_pricing_rules',
    'health_landing.action_admin_quick_edit_rules',
    'health_landing.action_admin_packages',
]


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    master = env.ref('health_cms_sidebar.item_admin_master_data',
                     raise_if_not_found=False)
    if master:
        master.match_action_xmlids = ','.join(MASTER_DATA_ACTIONS)

    pricing = env.ref('health_cms_sidebar.item_admin_pricing',
                      raise_if_not_found=False)
    if pricing:
        pricing.write({
            'action_xmlid': 'health_landing.action_admin_services',
            'match_action_xmlids': ','.join(PRICING_ACTIONS),
        })
