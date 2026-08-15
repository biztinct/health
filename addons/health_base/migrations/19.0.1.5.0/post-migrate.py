# -*- coding: utf-8 -*-
"""Back-fill the Many2one that replaced this module's Selection fields.

Converted here:
  * health.facility.facility_type -> facility_type_id  (vocabulary: facility_type)
  * health.referral.source.source_type -> source_type_id  (vocabulary: referral_source_type)
  * health.symptom.category -> category_id  (vocabulary: symptom_category)
  * health.vietnamese.district.region -> region_id  (vocabulary: vn_region)
  * health.vietnamese.district.travel_zone -> travel_zone_id  (vocabulary: travel_zone)
  * health.booking.cancellation.reason.reason_type -> reason_type_id  (vocabulary: cancellation_reason_type)

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
    backfill_module(env, 'health_base')
