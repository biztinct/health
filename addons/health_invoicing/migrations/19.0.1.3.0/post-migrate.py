# -*- coding: utf-8 -*-
"""Back-fill the Many2one that replaced this module's Selection fields.

Converted here:
  * product.template.healthcare_package_type -> healthcare_package_type_id  (vocabulary: package_service_type)
  * product.template.healthcare_service_location -> healthcare_service_location_id  (vocabulary: service_location)

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
    backfill_module(env, 'health_invoicing')
