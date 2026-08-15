# -*- coding: utf-8 -*-
"""Repoint biz_bi dataset columns at the converted Many2one fields.

`end`, not `post`: the converted fields on hr.employee and crm.lead come from
health_fieldservice / health_crm, which load AFTER health_base. A post-migrate
here sees a registry where those fields do not exist yet and silently skips
them — which is exactly what happened on the first attempt (2 of 13 repointed).
The `end` phase runs once every module is loaded.

No-op when biz_bi is not installed.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.lookup_migration import repoint_bi_fields


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    repoint_bi_fields(env)
