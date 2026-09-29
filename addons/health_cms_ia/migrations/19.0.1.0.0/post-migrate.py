# -*- coding: utf-8 -*-
"""The upgrade path of the consolidation.

A `post_init_hook` does not fire on an upgrade (ledger A2), so a database that
already has this module converges through here — the SAME function the install
hook calls, never a copy written to agree with it. Every writer compares before
it writes and the gates are decided once per entry, so running it on a database
that is already consolidated changes nothing.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.health_cms_ia.hooks import consolidate_ia

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    log = consolidate_ia(env)
    _logger.info('health_cms_ia %s: consolidation re-run from %s — %s',
                 '19.0.1.0.0', version,
                 ', '.join('%s %s' % (len(v), k) for k, v in log.items()))
