import logging
import re

_logger = logging.getLogger(__name__)

_AMP_PATTERN = re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;)')


def _sanitize_translation_column(cr, column):
    query = f"""
        SELECT id, {column}
          FROM ir_translation
         WHERE name LIKE %s
           AND {column} LIKE %s
    """
    cr.execute(query, ('ir.ui.view,arch_db,health_fieldservice%', '%&%'))
    rows = cr.fetchall()
    updated = 0
    for record_id, value in rows:
        if not value:
            continue
        cleaned = _AMP_PATTERN.sub('&amp;', value)
        if cleaned != value:
            cr.execute(
                f"UPDATE ir_translation SET {column}=%s WHERE id=%s",
                (cleaned, record_id),
            )
            updated += 1
    if updated:
        _logger.info(
            "Sanitized %s translations in column %s for health_fieldservice views",
            updated,
            column,
        )


def pre_init_hook(cr):
    """Ensure existing translations do not contain raw ampersands."""
    _sanitize_translation_column(cr, 'value')
    _sanitize_translation_column(cr, 'src')
