# -*- coding: utf-8 -*-
"""Backfill bi.field.relation_model for columns scanned before the field
existed, so many2one dimensions render the record's name instead of its id.

`end-`, not `post-`: post-migrations run while only the module's own
dependency closure is in the registry, so account.move.catchment_province_id
(added by a health_* module that loads after biz_bi) would be invisible —
measured: 27 of ~250 columns filled at post-, all of them core models.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    filled = env['bi.field']._backfill_relation_models()
    _logger.info("biz_bi: backfilled relation_model on %s field(s)", filled)
