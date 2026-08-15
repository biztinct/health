# -*- coding: utf-8 -*-
"""Keep the CMS shell on the dropdown-vocabulary screens.

The per-category drill-in (health.lookup.category.action_open_values) builds
its act_window in python, so it has no xml_id for the shell allowlist to match.
The MODEL is the only stable handle, hence match_models here. Safe from the
"last-wins model index" trap that health_cms_coverage warns about: these two
models belong to exactly one leaf.

Written from a migration because the sidebar rows are noupdate="1".
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    item = env.ref('health_cms_sidebar.item_admin_master_data',
                   raise_if_not_found=False)
    if item:
        item.match_models = 'health.lookup.value,health.lookup.category'
