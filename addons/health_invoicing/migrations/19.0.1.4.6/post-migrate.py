# -*- coding: utf-8 -*-
"""UAT round 10, item 7 — AR log cash rows the office recorded.

Every cash payment was logged as NURSE_CASH. A row is changed to OFFICE_CASH
only when the payment itself shows the cash was NOT taken by a nurse/doctor:
its PAY record's collector is not visit staff, or (no collector recorded) the
user who recorded the payment is not visit staff
(`health.ar.transaction.log._cash_taken_by_field_staff`). Log rows only —
never journal entries, payments or PAY records.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Log = env['health.ar.transaction.log']
    rows = Log.search([('posting_path', '=', 'NURSE_CASH'),
                       ('event_type', 'in', ('payment', 'refund')),
                       ('payment_id', '!=', False)])
    office = rows.filtered(lambda r: not Log._cash_taken_by_field_staff(r.payment_id))
    if office:
        cr.execute("UPDATE health_ar_transaction_log SET posting_path = 'OFFICE_CASH' "
                   "WHERE id IN %s", (tuple(office.ids),))
    _logger.info('health_invoicing 19.0.1.4.6: %s of %s NURSE_CASH row(s) were '
                 'recorded at the office -> OFFICE_CASH: %s', len(office),
                 len(rows), sorted(office.ids))
