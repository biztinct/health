# -*- coding: utf-8 -*-
"""Install-time twin of the CC-D migration.

``migrations/19.0.4.0.0/post-migrate.py`` covers databases where this module
was already installed (a migration script never runs on a fresh install); this
hook covers the fresh install. Both call the same idempotent model method, so
running one after the other changes nothing.
"""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    # §5.11: the post_init_hook signature is (env).
    if 'zalo.config' in env:
        result = env['zalo.config']._migrate_legacy_connections()
        # The Z1 cleanup belongs on BOTH paths (CC-D review): installing this
        # module onto a database that already ran the old health_zalo is
        # exactly the case where leaked app_secret tracking values exist, and
        # a migration script never runs on a fresh install.
        leaked = env['zalo.config']._drop_app_secret_tracking()
        _logger.info('channel_hub post_init: zalo migration %s, %s leaked '
                     'app_secret tracking value(s) removed', result, leaked)
    # CC-F: the same twin for the calls facade. Distinct log lines on both
    # branches — "health_voip24h absent" and "0 configs migrated" are
    # different facts and must not read the same in the log.
    if 'voip.config' in env:
        _logger.info('channel_hub post_init: calls facade %s',
                     env['voip.config']._migrate_legacy_connections())
    else:
        _logger.info('channel_hub post_init: health_voip24h is NOT in the '
                     'registry — no calls migration ran')
