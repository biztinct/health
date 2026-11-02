# -*- coding: utf-8 -*-
"""FS-H5 — rebuild the SQL layer so it carries only analytics material.

The clean view of a pipeline used to be `SELECT *` over the raw table and the
silver view listed every stored field of the dataset, so both carried columns
a product marked non-exportable (encrypted values, search indexes) and fields
marked sensitive. The code now leaves them out; existing views keep their old
column list until they are made again. This re-applies every active pipeline
and re-creates every silver view and gold copy that EXISTS on this database
(a missing one is made by the engine on first use, as before), and prints the
counts.

`end-` on purpose: the product's "not exportable" marks live on fields of
OTHER modules, which must all be loaded with their new code first.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _exists(cr, relname, kind):
    cr.execute("SELECT 1 FROM pg_class WHERE relname = %s AND relkind = %s",
               (relname, kind))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    pipelines = silvers = golds = failed = 0
    for pipeline in env['bi.pipeline'].search([('is_active', '=', True)]):
        try:
            with cr.savepoint():
                pipeline.action_apply()
            pipelines += 1
        except Exception:  # noqa: BLE001 — one bad pipeline must not stop the upgrade
            failed += 1
            _logger.warning("biz_bi FS-H5: pipeline %s could not be "
                            "re-applied", pipeline.id, exc_info=True)
    Gold = env['bi.refresh.job']
    for dataset in env['bi.dataset'].search([]):
        if _exists(cr, dataset._silver_view_name(), 'v'):
            try:
                with cr.savepoint():
                    dataset._recreate_silver_view()
                silvers += 1
            except Exception:  # noqa: BLE001
                failed += 1
                _logger.warning("biz_bi FS-H5: silver view of dataset %s "
                                "could not be re-created", dataset.id,
                                exc_info=True)
        if _exists(cr, dataset._gold_matview_name(), 'm'):
            try:
                with cr.savepoint():
                    Gold._publish_gold_for(dataset)
                golds += 1
            except Exception:  # noqa: BLE001
                failed += 1
                _logger.warning("biz_bi FS-H5: gold copy of dataset %s could "
                                "not be re-published", dataset.id,
                                exc_info=True)
    _logger.info("biz_bi FS-H5: SQL layer rebuilt — %d pipeline(s) re-applied, "
                 "%d silver view(s) and %d gold copy(ies) re-created, %d "
                 "failed", pipelines, silvers, golds, failed)
