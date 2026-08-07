# -*- coding: utf-8 -*-
"""Re-apply the sidebar gate and the BI group grant on upgrade.

``post_init_hook`` runs on INSTALL only. Roles get renamed, users get created
and re-roled, and a leaf whose gate was written once drifts out of date — so
the same two idempotent functions run again from here, and an upgraded
database converges on exactly what a fresh install produces.
"""
from odoo.addons.biz_bi_cms.hooks import apply_role_gates, grant_creator_group


def migrate(cr, version):
    from odoo import SUPERUSER_ID
    from odoo.api import Environment

    env = Environment(cr, SUPERUSER_ID, {})
    apply_role_gates(env)
    grant_creator_group(env)
