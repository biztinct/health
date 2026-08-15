# -*- coding: utf-8 -*-
"""Fold the CRM lookups' `name_vietnamese` columns into the vi_VN translation.

`health.province`, `health.contact.reason` and `health.lead.reason` each kept
the Vietnamese name in a second varchar column. Nothing rendered it: every
place a user PICKS one of these is a many2one, and a many2one renders
`display_name`, which reads `name`. `name` is now translatable and
`name_vietnamese` mirrors its vi_VN value, so this rescues the existing text
out of the (now unstored) column before it becomes unreachable.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.vi_alias_migration import (
    fold_vi_column_into_translation,
)

TARGETS = [
    ('health.province', 'health_province', 'name_vietnamese'),
    ('health.contact.reason', 'health_contact_reason', 'name_vietnamese'),
    ('health.lead.reason', 'health_lead_reason', 'name_vietnamese'),
]


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model, table, column in TARGETS:
        fold_vi_column_into_translation(env, model, table, column)
