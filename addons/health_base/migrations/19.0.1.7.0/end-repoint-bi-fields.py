# -*- coding: utf-8 -*-
"""Repoint biz_bi dataset columns at res.partner.gender_id / crm.lead.gender_id.

`end`, not `post`: crm.lead's converted field is contributed by health_crm,
which loads AFTER health_base — a post-migrate here would see a registry
without it and skip it silently. See lookup_migration.repoint_bi_fields.

No-op when biz_bi is not installed.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.lookup_migration import repoint_bi_fields


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    repoint_bi_fields(env)
