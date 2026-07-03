import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Normalize stale res_partner.patient_status values.

    An old migration (18.0.4.0.1) created the patient_status column with
    DEFAULT 'new'. The Selection was later narrowed to only 'active'/'inactive',
    leaving some partners with the invalid value 'new' (and possibly other
    legacy codes). Any invalid value breaks ORM operations that read the field
    — e.g. copying a res.users record fails with:
        ValueError: Wrong value for res.partner.patient_status: 'new'

    Map every value that is not a current selection option to 'active'.
    """
    cr.execute("""
        UPDATE res_partner
        SET patient_status = 'active'
        WHERE patient_status IS NOT NULL
          AND patient_status NOT IN ('active', 'inactive')
    """)
    _logger.info("Normalized %d res_partner.patient_status values to 'active'", cr.rowcount)
