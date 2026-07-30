# -*- coding: utf-8 -*-
"""Apply the role gating to a copy installed before 19.0.1.1.0.

`post_init_hook` runs on install only. The first install of this module shipped
all nineteen leaves ungated, which served a FINANCE section to the CRM role
(and an AccessError on click); this brings an upgraded database to the same
state a fresh install now produces.
"""
from odoo.addons.health_cms_coverage.hooks import apply_role_gates


def migrate(cr, version):
    from odoo.api import Environment
    from odoo import SUPERUSER_ID
    env = Environment(cr, SUPERUSER_ID, {})
    apply_role_gates(env)
