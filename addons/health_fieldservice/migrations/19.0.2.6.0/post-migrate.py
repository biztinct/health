# -*- coding: utf-8 -*-
"""Back-fill the Many2one that replaced this module's Selection fields.

Converted here:
  * health.portable.equipment.equipment_type -> equipment_type_id  (vocabulary: equipment_type)
  * health.portable.equipment.power_source -> power_source_id  (vocabulary: equipment_power_source)
  * health.staff.skill.skill_category -> skill_category_id  (vocabulary: staff_skill_category)
  * hr.employee.preferred_shift -> preferred_shift_id  (vocabulary: preferred_shift)

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
    backfill_module(env, 'health_fieldservice')
