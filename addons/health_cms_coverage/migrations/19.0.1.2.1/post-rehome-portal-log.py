# -*- coding: utf-8 -*-
"""Re-run the consolidation to pick up a missed match target.

19.0.1.2.0 retired ``item_clin_patient_portal`` but re-homed only its
``action_xmlid``. That leaf ALSO answered for
``health_portal.action_portal_access_log`` via ``match_action_xmlids``, and
``get_match_keys()`` filters ``active = True`` — so the access-log screen fell
out of the shell allowlist and would have opened outside the CMS chrome.

``consolidate_sidebar`` is idempotent (every write is guarded on the current
value), so re-running it is the whole fix: it only adds the missing target.
"""
from odoo.addons.health_cms_coverage.hooks import consolidate_sidebar


def migrate(cr, version):
    from odoo import SUPERUSER_ID
    from odoo.api import Environment
    env = Environment(cr, SUPERUSER_ID, {})
    consolidate_sidebar(env)
