# -*- coding: utf-8 -*-
"""Restore the dedicated Relationships leaf and remove its stale alias."""

from odoo.addons.health_cms_coverage.hooks import consolidate_sidebar


def migrate(cr, version):
    from odoo import SUPERUSER_ID
    from odoo.api import Environment
    env = Environment(cr, SUPERUSER_ID, {})
    consolidate_sidebar(env)
