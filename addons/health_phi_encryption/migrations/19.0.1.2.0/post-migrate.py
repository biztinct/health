# -*- coding: utf-8 -*-
"""Drop the plain columns the move to encrypted storage left behind.

When the clinic's health fields became computed over their encrypted columns,
the framework kept each field's old physical column (ledger §5.302). Every one
of them is empty on every database (checked 2026-11-03), nothing reads or
writes them any more, and anything that selects the whole table still carried
them. Owner decision 2026-11-03: drop them.

Each column goes only when ALL of this holds: it exists; its field is now a
non-stored field (so the framework will not want it back); and it holds no
value at all. A column with a value in it is kept and named in the log.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import SQL

from odoo.addons.health_phi_encryption.hooks import TABLE_MAPS, _existing_columns

_logger = logging.getLogger(__name__)

MODELS = {'res_partner': 'res.partner', 'health_clinical_note': 'health.clinical.note'}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    dropped, kept = [], []
    for table, mapping in TABLE_MAPS:
        model_name = MODELS.get(table)
        if not model_name or model_name not in env:
            continue
        model = env[model_name]
        existing = _existing_columns(cr, table)
        for exposed in mapping:
            if exposed not in existing:
                continue
            field = model._fields.get(exposed)
            if field is None or field.store:
                kept.append(f'{table}.{exposed} (still a stored field)')
                continue
            cr.execute(SQL(
                "SELECT count(*) FROM %s WHERE %s IS NOT NULL AND %s::text <> ''",
                SQL.identifier(table), SQL.identifier(exposed),
                SQL.identifier(exposed)))
            values = cr.fetchone()[0]
            if values:
                kept.append(f'{table}.{exposed} ({values} value(s))')
                continue
            cr.execute(SQL("ALTER TABLE %s DROP COLUMN %s",
                           SQL.identifier(table), SQL.identifier(exposed)))
            dropped.append(f'{table}.{exposed}')
    _logger.info(
        'health_phi_encryption 19.0.1.2.0: %s empty plain column(s) dropped '
        '(%s); %s kept (%s)', len(dropped), ', '.join(dropped) or 'none',
        len(kept), ', '.join(kept) or 'none')
