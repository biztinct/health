"""UAT round 9, item 1: payment/refund rows of the AR transaction log that a
"client's latest invoice" fallback filed on the wrong booking are moved to the
payment's own booking — only where that booking is unambiguous from the
payment itself (its booking, its PAY record, the PAY record's invoice, or the
one booking of the invoices it paid). A booking nothing on the payment
confirms is cleared (lead ruling: row 1465)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Log = env['health.ar.transaction.log'].with_context(active_test=False)
    rows = Log.search([('payment_id', '!=', False), ('event_type', 'in', ('payment', 'refund'))])
    for row in rows:
        own = Log._payment_own_booking(row.payment_id)
        if not own:
            if row.booking_id:
                # Lead ruling (round 9): nothing on the payment confirms it -> empty.
                _logger.info('AR log row %s (%s): unconfirmed booking %s cleared', row.id,
                             row.payment_id.name, row.booking_id.name)
                row.write({'booking_id': False, 'crm_event_id': False, 'facility_id': False})
            continue
        if own != row.booking_id:
            _logger.info('AR log row %s (%s): booking %s -> %s', row.id, row.payment_id.name,
                         row.booking_id.name, own.name)
            row.write({
                'booking_id': own.id,
                'crm_event_id': own.crm_lead_id.id if 'crm_lead_id' in own._fields else row.crm_event_id.id,
                'facility_id': own.facility_id.id,
            })
