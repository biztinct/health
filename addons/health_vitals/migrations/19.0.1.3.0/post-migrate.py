# -*- coding: utf-8 -*-
"""Fold health.vitals.type.name_vi into the vi_VN translation of `name`.

See health_base/vi_alias_migration.py. The PWA keeps reading `name_vi` — it is
now a mirror of the translation rather than a second column.
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
        env, 'health.vitals.type', 'health_vitals_type', 'name_vi')
