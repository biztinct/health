# -*- coding: utf-8 -*-
"""ACCESS AR-3 — Vietnamese for the roles, and sign-in lands on Home.

  * C: the Vietnamese name and sentence of every seeded role and ability
    (`catalogue_vi.apply_catalogue_vi`), written as translated field values —
    English untouched, a row somebody has reworded left alone.
  * G3: a person whose home screen is the old provisioning default (the admin
    dashboard) lands on Home instead (`hooks.move_provisioned_home`).

The doctor's Bookings tab and the Google Ads application (G1/G2) are written by
`health_cms_ia`'s own migration, which loads after this module.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.health_access.catalogue_vi import apply_catalogue_vi
from odoo.addons.health_access.hooks import move_provisioned_home

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    rows = apply_catalogue_vi(env)
    homes = move_provisioned_home(env)
    _logger.info('health_access 19.0.1.7.0: %s role/ability row(s) in '
                 'Vietnamese, %s home screen(s) moved to Home', rows, homes)
