# -*- coding: utf-8 -*-
"""The other half of the A2 pair: the top-bar decision, on an UPGRADE.

A `post_init_hook` does not fire on an upgrade and a migration does not fire on
an install, so a decision written in only one of them reaches only half the
databases this product runs on. `data/config.xml` writes both settings on a
fresh install and — being `noupdate="1"`, deliberately — writes nothing at all
on an upgrade of a database that predates it. This is the upgrade path.

It only ever writes a setting that is MISSING. A clinic that has changed its
mind keeps its decision, which is the whole reason the data file is
`noupdate="1"`.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.health_access.hooks import ensure_topbar_settings

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    written = ensure_topbar_settings(env)
    _logger.info('health_access 19.0.1.2.1: top-bar settings written on '
                 'upgrade: %s', ', '.join(written) or 'none were missing')
