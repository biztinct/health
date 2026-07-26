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
    if 'zalo.config' not in env:
        return
    result = env['zalo.config']._migrate_legacy_connections()
    _logger.info('channel_hub post_init: zalo migration %s', result)
