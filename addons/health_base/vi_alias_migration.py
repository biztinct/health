# -*- coding: utf-8 -*-
"""Shared helper for the one-off "fold the Vietnamese column into the
translation" migrations.

Each module that turned a parallel `name_vi` / `name_vietnamese` column into a
`health.vi.alias.mixin` mirror calls this from its own post-migrate. The
column itself is left in postgres: the field is no longer stored, so Odoo stops
writing it, but reading it once here is how the existing Vietnamese text is
rescued instead of silently disappearing behind the compute.

Idempotent — a row whose vi_VN translation already differs from en_US is left
alone, so re-running never clobbers text a user has since corrected.
"""
import logging

_logger = logging.getLogger(__name__)


def fold_vi_column_into_translation(env, model_name, table, column,
                                    target='name'):
    """Copy `table`.`column` into the vi_VN translation of `model.target`.

    Returns the number of records updated.
    """
    env.cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    if not env.cr.fetchone():
        _logger.info("vi-alias fold: %s.%s already gone, nothing to do",
                     table, column)
        return 0

    env.cr.execute(
        "SELECT id, %s FROM %s WHERE %s IS NOT NULL AND btrim(%s) <> ''" % (
            column, table, column, column))
    rows = env.cr.fetchall()
    if not rows:
        return 0

    Model = env[model_name].with_context(active_test=False)
    updated = 0
    for rec_id, vi_value in rows:
        record = Model.browse(rec_id).exists()
        if not record:
            continue
        english = record.with_context(lang='en_US')[target]
        current_vi = record.with_context(lang='vi_VN')[target]
        # An untranslated record reads back the English fallback; that (and an
        # empty value) is the only state we overwrite.
        if current_vi and current_vi != english:
            continue
        if vi_value == english:
            continue
        record.with_context(lang='vi_VN')[target] = vi_value
        updated += 1

    _logger.info("vi-alias fold: %s.%s -> %s vi_VN translations on %s rows",
                 table, column, target, updated)
    return updated
