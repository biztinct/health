# -*- coding: utf-8 -*-
"""Owner decisions of 2026-11-03, taken at the end of the Form Studio work.

  * Owners may export lists: the "Export lists" ability is written down
    (`hooks._ensure_abilities`, create-only) and given to the Owner role
    (`hooks.grant_export`), additively — nobody loses anything.
  * The role called "Admin" is "Office Admin" from now on, in English and in
    Vietnamese, where nobody has reworded it (`hooks.rename_admin_role`).
  * The `demo` login the demonstration data left behind is switched off where
    it exists, is still on and has never signed in (`hooks.retire_demo_login`).
  * The new ability gets its Vietnamese words (`catalogue_vi.apply_catalogue_vi`).
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.health_access.catalogue_vi import apply_catalogue_vi
from odoo.addons.health_access.hooks import (
    _ensure_abilities, grant_export, rename_admin_role, retire_demo_login)

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    made = _ensure_abilities(env)
    roles = grant_export(env)
    renamed = rename_admin_role(env)
    rows = apply_catalogue_vi(env)
    demo = retire_demo_login(env)
    _logger.info(
        'health_access 19.0.1.9.0: %s ability(ies) added, %s role(s) given '
        '"export lists", admin role renamed=%s, %s row(s) in Vietnamese, demo '
        'login switched off=%s', made, roles, renamed, rows, demo)
