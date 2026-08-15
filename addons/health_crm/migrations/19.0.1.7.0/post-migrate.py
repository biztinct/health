# -*- coding: utf-8 -*-
"""Back-fill the Many2one that replaced this module's Selection fields.

Converted here:
  * health.contact.reason.category -> category_id  (vocabulary: contact_reason_category)
  * health.lead.reason.category -> category_id  (vocabulary: lead_reason_category)
  * health.lead.reason.lead_type -> lead_type_id  (vocabulary: lead_reason_applies_to)
  * health.province.region -> region_id  (vocabulary: vn_region)
  * crm.lead.service_interest -> service_interest_id  (vocabulary: service_interest)

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
    backfill_module(env, 'health_crm')
