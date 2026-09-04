# -*- coding: utf-8 -*-
"""Re-write the nineteen gates now that the roles have fixed names.

The entries are ``noupdate="1"``, so nothing this module ships in XML reaches a
database that already has them: the gate is written, from the install hook and
from here. What changed is only WHICH list it is written on — the previous
access application's column has gone with it, and the same nineteen leaves are
now gated on the role bundles, by fixed name rather than by matching a word.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.health_cms_coverage.hooks import apply_role_gates

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    gated = apply_role_gates(env)
    _logger.info('health_cms_coverage 19.0.1.4.0: %s leaf(s) re-gated onto '
                 'the role bundles (from version %s)', gated, version)
