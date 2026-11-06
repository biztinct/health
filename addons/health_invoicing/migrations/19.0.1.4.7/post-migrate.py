# -*- coding: utf-8 -*-
"""UAT round 11, item 3 — cash taken at the office is not "pending delivery".

A PAY record in "Cash Pending Delivery" moves to "Reconciled in AR" only when
(a) the round-10 rule says the cash was NOT taken by a nurse/doctor in the
field (`_cash_taken_in_field`), and (b) its accounting payment already exists
and is posted (paid / in process) — the same state an office payment gets
today. Office cash WITHOUT a payment yet (prepaid packages, whose payment is
only made at the hand-in) is left as it is and listed: changing its state
would leave its invoice with nothing to pay it. Custody state only: never
journal entries, payments, invoices or AR log rows.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Txn = env['health.payment.transaction'].with_context(active_test=False)
    pending = Txn.search([('status', '=', 'pending_delivery'),
                          ('payment_method', '=', 'cash')])
    office = pending.filtered(lambda t: not t._cash_taken_in_field())
    fix = office.filtered(lambda t: t.payment_id and t.payment_id.state in ('paid', 'in_process'))
    left = office - fix
    if fix:
        cr.execute("UPDATE health_payment_transaction SET status = 'reconciled' "
                   "WHERE id IN %s", (tuple(fix.ids),))
    _logger.info('health_invoicing 19.0.1.4.7: %s office cash record(s) -> reconciled: %s; '
                 'office cash without a payment left pending: %s; field cash pending: %s',
                 len(fix), fix.mapped('name'), left.mapped('name'),
                 (pending - office).mapped('name'))
