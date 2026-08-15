# -*- coding: utf-8 -*-
"""Back-fill the Many2one that replaced this module's Selection fields.

Converted here:
  * health.careplan.category -> category_id  (vocabulary: careplan_category)
  * health.careplan.task.not_done_reason -> not_done_reason_id  (vocabulary: task_not_done_reason)

The old varchar column is deliberately NOT dropped — it is the only
record of what each row said before the conversion, and the back-fill
reads it. Anything whose value has no matching code is left empty and
logged as an error rather than guessed at.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.lookup_migration import (
    backfill_module,
    seed_lookup_values,
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Idempotent, and cheap insurance: this module can be upgraded on its
    # own, without health_base being in the same -u run.
    seed_lookup_values(env)
    backfill_module(env, 'health_careplan')
