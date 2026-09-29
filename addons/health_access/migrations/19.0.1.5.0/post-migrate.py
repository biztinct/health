# -*- coding: utf-8 -*-
"""MENU M1 — the Training heading and its five screens move from ADMIN to the
new Learn rail entry.

The seed file is noupdate, so the upgrade alone does not move rows that already
exist; `hooks.rehome_training` does, once, and keeps the ADMIN block's gate on
the heading so the people who opened it there still do.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.health_access.hooks import rehome_training

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    moved = rehome_training(env)
    _logger.info('health_access 19.0.1.5.0: %s Training row(s) re-homed to '
                 'Learn', moved)
