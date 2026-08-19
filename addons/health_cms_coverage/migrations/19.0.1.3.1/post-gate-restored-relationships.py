# -*- coding: utf-8 -*-
"""Reapply role gates after restoring the Relationships workspace."""

from odoo.addons.health_cms_coverage.hooks import apply_role_gates


def migrate(cr, version):
    from odoo import SUPERUSER_ID
    from odoo.api import Environment
    env = Environment(cr, SUPERUSER_ID, {})
    apply_role_gates(env)
