# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Seed the default workspace so first-run users land somewhere useful."""
    Workspace = env['bi.workspace']
    if not Workspace.search_count([('is_default', '=', True)]):
        Workspace.create({
            'name': 'General Analytics',
            'code': 'general',
            'is_default': True,
            'color': 1,
        })
        _logger.info("biz_bi: created default workspace 'General Analytics'")
