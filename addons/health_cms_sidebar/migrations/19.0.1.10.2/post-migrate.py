# -*- coding: utf-8 -*-
"""Master Data highlights for the new Package Templates screen.

The sidebar item rows are noupdate=1, so the data file's new
match_action_xmlids entry does not reach an existing database: append it here.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE cms_sidebar_item i
           SET match_action_xmlids = match_action_xmlids || ',health_landing.action_admin_package_templates'
          FROM ir_model_data d
         WHERE d.model = 'cms.sidebar.item' AND d.res_id = i.id
           AND d.module = 'health_cms_sidebar'
           AND i.match_action_xmlids LIKE '%%health_landing.action_admin_service_categories%%'
           AND i.match_action_xmlids NOT LIKE '%%action_admin_package_templates%%'
    """)
