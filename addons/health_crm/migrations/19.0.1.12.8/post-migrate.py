# -*- coding: utf-8 -*-
"""Area-less contacts take their client's area — the patient link this time.

19.0.1.12.7 filled the area from `partner_id` only. The Client Name column
resolves `patient_id` first, and a Quick Booking conversion sets `patient_id`
without `partner_id` (carejiox contact 4002 → Hà Nội client 37955), so those
contacts were still area-less. Contacts that already carry an area are left alone.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE crm_lead l
           SET catchment_province_id = p.catchment_province_id
          FROM res_partner p
         WHERE p.id = l.patient_id
           AND l.catchment_province_id IS NULL
           AND p.catchment_province_id IS NOT NULL
     RETURNING l.id
    """)
    _logger.info("health_crm: contact area filled from the patient on %s", [r[0] for r in cr.fetchall()])
