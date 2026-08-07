# -*- coding: utf-8 -*-
"""Re-apply the sidebar gate and the BI group grant on upgrade to 1.1.0.

``post_init_hook`` runs on INSTALL only, and Odoo runs a migration script only
when the INSTALLED version is below the module version — so the identical
script under ``19.0.1.0.0/`` never executed on this deployment: the module was
installed AT 1.0.0 and nothing ever moved past it (Phase-1 report §6). This
directory is the first one that actually runs, and it is why the manifest
moved to ``19.0.1.1.0``.

The two functions are idempotent by construction, so an upgraded database
converges on exactly what a fresh install produces.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID
    from odoo.api import Environment
    from odoo.addons.biz_bi_cms.hooks import (
        apply_role_gates,
        grant_creator_group,
    )

    env = Environment(cr, SUPERUSER_ID, {})
    _logger.info('biz_bi_cms 19.0.1.1.0: re-applying role gates and the '
                 'creator-group grant (from version %s)', version)
    gated = apply_role_gates(env)
    granted = grant_creator_group(env)
    _logger.info('biz_bi_cms 19.0.1.1.0: %s leaf(s) gated, %s user(s) granted '
                 'the BI creator group', gated, granted)
