# -*- coding: utf-8 -*-
"""Clear the raw program error every customer invoice carried (UAT 2026-11-04).

`account.move` has no `patient_id`; the tax-authority and MISA steps read it on
posting and stored "'account.move' object has no attribute 'patient_id'" as the
submission / sync error, so the invoice tab and Finance > VAT Log showed an
error on every invoice. Nothing was ever sent (the step failed before any
call). Put those invoices back to "not submitted" / "not synced" with no error
text. Only rows carrying exactly that error are touched.

Also (owner, same day): "Receive Payment" pre-filled the demonstration bank
account "BANK134567890 - BNP Paribas". It is detached from every journal and
archived — not deleted: posted invoices and payments still point at it.
"""
import logging

_logger = logging.getLogger(__name__)

NEEDLE = "%object has no attribute 'patient_id'%"


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE account_move
           SET tax_submission_error = NULL,
               tax_authority_submission_status = 'draft'
         WHERE tax_submission_error LIKE %s
           AND COALESCE(tax_authority_submission_status, 'error') IN ('error', 'pending')
    """, (NEEDLE,))
    tax = cr.rowcount
    cr.execute("""
        UPDATE account_move
           SET misa_sync_error = NULL,
               misa_sync_status = 'not_synced'
         WHERE misa_sync_error LIKE %s
           AND COALESCE(misa_sync_status, 'sync_error') IN ('sync_error', 'syncing')
    """, (NEEDLE,))
    misa = cr.rowcount
    _logger.info('health_invoicing 19.0.1.4.2: cleared the patient_id program error on '
                 '%s tax and %s MISA rows', tax, misa)

    from odoo import SUPERUSER_ID, api
    env = api.Environment(cr, SUPERUSER_ID, {})
    demo = env['res.partner.bank'].with_context(active_test=False).search([
        ('acc_number', '=', 'BANK134567890'),
        ('partner_id', 'in', env['res.company'].search([]).mapped('partner_id').ids),
    ])
    journals = env['account.journal']
    if demo:
        try:
            with cr.savepoint():
                journals = env['account.journal'].with_context(active_test=False).search(
                    [('bank_account_id', 'in', demo.ids)])
                journals.write({'bank_account_id': False})
                demo.write({'active': False})
        except Exception as e:  # never block the upgrade on demo data
            _logger.warning('health_invoicing 19.0.1.4.2: demo bank account left as is: %s', e)
            return
    _logger.info('health_invoicing 19.0.1.4.2: demo bank account archived=%s, '
                 'detached from %s journal(s)', bool(demo), len(journals))
