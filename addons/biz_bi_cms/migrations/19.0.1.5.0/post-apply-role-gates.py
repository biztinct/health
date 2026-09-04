# -*- coding: utf-8 -*-
"""Re-write the Analytics gate on the roles that have fixed names now.

``post_init_hook`` runs on INSTALL only, and every entry in this module's data
file is a row an upgrade does not re-assert, so the gate has to be WRITTEN.

Two things changed under it since 1.1.0. The roles are no longer matched by
name — they have fixed names of their own — and the reporting permission is no
longer handed out by a sweep from here: it is an ability on four role bundles,
so it arrives the way every other permission does. The sweep and the per-record
hook that kept it current are gone, and this replaces both.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID
    from odoo.api import Environment
    from odoo.addons.biz_bi_cms.hooks import apply_role_gates

    env = Environment(cr, SUPERUSER_ID, {})
    _logger.info('biz_bi_cms 19.0.1.5.0: re-applying the Analytics gate by '
                 'fixed role name (from version %s)', version)
    gated = apply_role_gates(env)
    _logger.info('biz_bi_cms 19.0.1.5.0: %s left-menu entry(ies) gated', gated)
