# -*- coding: utf-8 -*-
"""CC-D migration: give every live zalo.config a framework connection.

It lives HERE and not in health_zalo for a load-order reason, not a taste one.
health_zalo loads *before* this module (health_care_command sits between them
and depends on health_zalo), so a migration script over there would run at a
point where ``care.channel.connection`` is not in the registry yet. By the time
this module's post-migrate runs, both sides exist.

Everything it does is idempotent, so a re-run — a second upgrade, a
restore-and-replay — creates nothing new (T116 asserts exactly that).

Nothing is deleted and nothing is invalidated: an existing Zalo setup keeps
working as it did, in ``state='legacy'``, until a human completes the new
sign-in in the Channel Center.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'zalo.config' not in env:
        _logger.info('CC-D post-migrate: health_zalo is not installed, '
                     'nothing to migrate')
        return
    result = env['zalo.config']._migrate_legacy_connections()
    leaked = env['zalo.config']._drop_app_secret_tracking()
    _logger.info('CC-D post-migrate: %s, %s leaked app_secret tracking '
                 'value(s) removed', result, leaked)
