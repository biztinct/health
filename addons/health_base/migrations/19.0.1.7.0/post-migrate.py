# -*- coding: utf-8 -*-
"""Gender joins the client-editable dropdown vocabularies.

It was left out of Tiers 1 and 2 because it has more non-view readers than any
other Selection in the system — the FHIR Patient facade, /api/v1, the PWA sync
payload and the MoH report all emit it. Those all now read `gender_code`, which
returns the same string the Selection did, so nothing on the wire changed and
the codes here are a contract: `male`, `female`, `other`, `prefer_not_to_say`
(the last one is what health_fhir_core maps to FHIR "unknown").

Seeds the vocabulary, then points res.partner.gender_id at the row whose code
matches the retired Selection value. Values with no matching code are left NULL
and logged — recoverable from health_lookup_conversion_audit.
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
    seed_lookup_values(env)
    backfill_module(env, 'health_base')
