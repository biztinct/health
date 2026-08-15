# -*- coding: utf-8 -*-
"""Fold health.medication.notgiven.reason.name_vi into the vi_VN translation.

See health_base/vi_alias_migration.py. The eMAR reason buttons keep reading
`name_vi`; it is now a mirror of the translation.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.vi_alias_migration import (
    fold_vi_column_into_translation,
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    fold_vi_column_into_translation(
        env, 'health.medication.notgiven.reason',
        'health_medication_notgiven_reason', 'name_vi')
