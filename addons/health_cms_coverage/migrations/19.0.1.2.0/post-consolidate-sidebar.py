# -*- coding: utf-8 -*-
"""Apply the menu consolidation to a copy installed before 19.0.1.2.0.

`post_init_hook` runs on install only, so without this an already-installed
database would keep the un-consolidated sidebar: menus whose records are now
tabs on the client/booking record, config leaves sitting in the daily-work
sections, and expanders wrapping a single child.

The logic itself lives in ``hooks.consolidate_sidebar`` so a fresh install and
an upgrade converge on exactly the same sidebar — same split as
``apply_role_gates`` / ``post-apply-role-gates.py``.

Idempotent: every write is guarded on the current value, so re-running is a
no-op rather than a second retirement pass.
"""
from odoo.addons.health_cms_coverage.hooks import consolidate_sidebar


def migrate(cr, version):
    from odoo import SUPERUSER_ID
    from odoo.api import Environment
    env = Environment(cr, SUPERUSER_ID, {})
    consolidate_sidebar(env)
