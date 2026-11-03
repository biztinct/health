# -*- coding: utf-8 -*-
"""Area-less contacts take their client's area (see crm.lead._catchment_from_client).

On carejiox one active contact ("WA Demo Lead", no area, Hà Nội client) made
Contacts > All Dates raise an AccessError for every user who can read
area-less contacts but not Hà Nội clients (HCMC Operations Manager, the
area-less CRM account). Archived contacts are filled too so un-archiving one
cannot bring the error back. Contacts that already carry an area are left alone.
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
         WHERE p.id = l.partner_id
           AND l.catchment_province_id IS NULL
           AND p.catchment_province_id IS NOT NULL
     RETURNING l.id
    """)
    _logger.info("health_crm: contact area filled from the client on %s", [r[0] for r in cr.fetchall()])
