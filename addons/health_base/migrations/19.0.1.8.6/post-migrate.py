"""UAT round 6, item 2: a client's driving distance that was written by a
person or an import (no lookup method recorded) is a value set on purpose —
including 0 — and is marked 'manual' so bookings use it as is. Only rows that
HAVE a stored value are marked; NULL (never set) stays unknown."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE res_partner
           SET clinic_distance_method = 'manual'
         WHERE clinic_distance_method IS NULL
           AND clinic_drive_distance_km IS NOT NULL
        RETURNING id
    """)
    ids = [r[0] for r in cr.fetchall()]
    _logger.info('health_base 19.0.1.8.6: %d client distance(s) marked as set on purpose: %s',
                 len(ids), ids)
