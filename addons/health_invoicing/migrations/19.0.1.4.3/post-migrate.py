# -*- coding: utf-8 -*-
""""Invoiced" on a booking now follows its invoice (UAT 2026-11-04, BK4056).
The flag became a stored computed field; existing rows keep their old value
until recomputed, so recompute every booking that has an invoice."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    fsos = env['health.fieldservice.order'].with_context(active_test=False).search(
        [('invoice_id', '!=', False)])
    before = {f.id: f.is_invoiced for f in fsos}
    env.add_to_compute(fsos._fields['is_invoiced'], fsos)
    fsos.flush_recordset(['is_invoiced'])
    changed = [f.name for f in fsos if f.is_invoiced != before[f.id]]
    _logger.info('health_invoicing 19.0.1.4.3: "Invoiced" recomputed on %s booking(s), '
                 'changed on %s: %s', len(fsos), len(changed), ', '.join(changed[:20]))
