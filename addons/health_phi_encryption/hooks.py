# -*- coding: utf-8 -*-
"""Post-install migration: encrypt legacy plaintext and drop the old columns.

When this module converts a stored field to a computed one, the ORM stops
using the original column but leaves it (and its plaintext) in the table.
This hook copies every legacy value into the ``*_enc`` column as an
AES-GCM token (+ blind index where applicable), then drops the plaintext
column so no PHI remains readable at rest.

Idempotent: on re-run the legacy columns no longer exist and nothing happens.
"""
import logging

from .models import phi_crypto
from .models.res_partner import PARTNER_PHI_MAP
from .models.health_clinical_note import NOTE_PHI_MAP

_logger = logging.getLogger(__name__)

BATCH = 500

TABLE_MAPS = [
    ('res_partner', PARTNER_PHI_MAP),
    ('health_clinical_note', NOTE_PHI_MAP),
]


def _existing_columns(cr, table):
    cr.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table,))
    return {row[0] for row in cr.fetchall()}


def _migrate_column(env, table, exposed, enc, bidx):
    cr = env.cr
    cr.execute(
        f'SELECT id, "{exposed}" FROM "{table}" '
        f'WHERE "{exposed}" IS NOT NULL AND "{exposed}" != \'\'')
    rows = cr.fetchall()
    for i in range(0, len(rows), BATCH):
        for rec_id, plaintext in rows[i:i + BATCH]:
            token = phi_crypto.encrypt(env, plaintext)
            if bidx:
                cr.execute(
                    f'UPDATE "{table}" SET "{enc}" = %s, "{bidx}" = %s WHERE id = %s',
                    (token, phi_crypto.blind_index(env, plaintext), rec_id))
            else:
                cr.execute(
                    f'UPDATE "{table}" SET "{enc}" = %s WHERE id = %s',
                    (token, rec_id))
    # Drop the plaintext column; if other DB objects depend on it (e.g. the
    # biz_bi silver SQL views), null it out instead — plaintext is still
    # removed at rest and the dependent views keep working (they now read
    # NULL, which is correct: PHI must not leak through raw BI views).
    cr.execute('SAVEPOINT phi_drop')
    try:
        cr.execute(f'ALTER TABLE "{table}" DROP COLUMN "{exposed}"')
        cr.execute('RELEASE SAVEPOINT phi_drop')
        outcome = 'plaintext column dropped'
    except Exception:
        cr.execute('ROLLBACK TO SAVEPOINT phi_drop')
        cr.execute(f'UPDATE "{table}" SET "{exposed}" = NULL '
                   f'WHERE "{exposed}" IS NOT NULL')
        outcome = ('plaintext column NULLED (dependent objects such as BI '
                   'views prevent dropping it — remove the field from those '
                   'views, then drop the column manually)')
    _logger.info('PHI migration: %s.%s -> %s (%d rows), %s',
                 table, exposed, enc, len(rows), outcome)


def post_init_hook(env):
    for table, phi_map in TABLE_MAPS:
        columns = _existing_columns(env.cr, table)
        for exposed, (enc, bidx) in phi_map.items():
            if exposed in columns and enc in columns:
                _migrate_column(env, table, exposed, enc, bidx)
            elif exposed in columns and enc not in columns:
                _logger.error(
                    'PHI migration skipped %s.%s: %s column missing',
                    table, exposed, enc)
    env.registry.clear_cache()
    _logger.info('PHI encryption post-init migration complete')
