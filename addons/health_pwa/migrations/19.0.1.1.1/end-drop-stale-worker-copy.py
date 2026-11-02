# -*- coding: utf-8 -*-
"""Nurse app 1.21.1 — the service-worker script has no language copies.

The whole script used to be one text node of `health_pwa.service_worker_js`,
so it was one translatable term, and the Vietnamese copy stored in `arch_db`
still held the 1.0.95 script: every Vietnamese-language user was served a
two-year-old offline helper whatever the version (ledger 5.288). The script is
now outside the translatable terms (`t-translation="off"`), and its stale
term is gone from `i18n/vi_VN.po`. A copy that survived in `arch_db` is
removed here, for THIS VIEW ONLY: every language key but the source.

Plain SQL on the one view found by its external identifier; nothing else is
read or written. `end-` so it runs after the view itself was reloaded.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'health_pwa' AND name = 'service_worker_js'
          AND model = 'ir.ui.view'
    """)
    row = cr.fetchone()
    if not row:
        _logger.info("health_pwa 1.21.1: no service-worker view, nothing to "
                     "clean")
        return
    cr.execute("""
        UPDATE ir_ui_view
           SET arch_db = jsonb_build_object('en_US', arch_db -> 'en_US')
         WHERE id = %s
           AND arch_db ? 'en_US'
           AND EXISTS (SELECT 1 FROM jsonb_object_keys(arch_db) k
                        WHERE k <> 'en_US')
     RETURNING id
    """, (row[0],))
    cleaned = cr.rowcount
    _logger.info("health_pwa 1.21.1: service-worker view %s — %d stale "
                 "language copy(ies) removed", row[0], cleaned)
