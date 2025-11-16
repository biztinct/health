# -*- coding: utf-8 -*-

import json
import logging
import uuid
import datetime
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    red_invoice_state = fields.Selection([
        ('not_required', 'Not Required'),
        ('pending', 'Pending'),
        ('issuing', 'Issuing'),
        ('issued', 'Issued'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Red Invoice State', default='pending', copy=False, tracking=True)
    red_invoice_no = fields.Char(string='Red Invoice No', copy=False, readonly=True)
    red_invoice_series = fields.Char(string='Red Invoice Series', copy=False)
    red_invoice_template_code = fields.Char(string='Red Invoice Template', copy=False)
    red_invoice_reservation_code = fields.Char(string='Reservation Code', copy=False)
    red_invoice_transaction_uuid = fields.Char(string='Transaction UUID', copy=False, default=lambda self: str(uuid.uuid4()))
    red_invoice_transaction_id = fields.Char(string='Transaction ID', copy=False)
    red_invoice_code_of_tax = fields.Char(string='Tax Office Code', copy=False)
    red_invoice_last_error = fields.Text(string='Red Invoice Error', copy=False)
    red_invoice_last_sync = fields.Datetime(string='Red Invoice Sync Date', copy=False)
    red_invoice_download_attachment_id = fields.Many2one('ir.attachment', string='Red Invoice File', copy=False)
    red_invoice_pdf_attachment_id = fields.Many2one('ir.attachment', string='Red Invoice PDF', copy=False)
    red_invoice_hash_string = fields.Char(string='Hash String', copy=False)
    red_invoice_secret_mode = fields.Boolean(string='Use Secret Code Mode', default=False)
    red_invoice_payment_method = fields.Selection([
        ('1', 'Cash'),
        ('2', 'Bank Transfer'),
        ('3', 'Cash/Bank Transfer'),
        ('4', 'Credit'),
        ('5', 'Other'),
        ('6', 'Cash (TT78)'),
        ('7', 'Bank Transfer (TT78)'),
        ('8', 'Cash/Bank Transfer (TT78)'),
    ], string='Red Invoice Payment Method', copy=False)
    red_invoice_payment_method_name = fields.Char(string='Payment Method Name', copy=False)
    red_invoice_lookup_url = fields.Char(string='Lookup URL', copy=False, readonly=True)

    def action_post(self):
        res = super().action_post()
        auto_issue = self.env['ir.config_parameter'].sudo().get_param('health_redinvoice.auto_issue', 'True') == 'True'
        if auto_issue:
            for move in self:
                try:
                    move._redinvoice_maybe_issue()
                except Exception as exc:  # do not block posting
                    _logger.warning("Red Invoice auto-issue skipped for %s: %s", move.name, exc)
        return res

    def action_redinvoice_generate(self):
        for move in self:
            move._redinvoice_issue()
        return True

    def action_redinvoice_download_zip(self):
        for move in self:
            move._redinvoice_download(file_type='ZIP')
        return True

    def action_redinvoice_download_pdf(self):
        for move in self:
            move._redinvoice_download(file_type='PDF')
        return True

    def action_redinvoice_cancel(self):
        for move in self:
            move._redinvoice_cancel_remote()
        return True

    # -------------------------------------------------------------------------
    # Core helpers
    # -------------------------------------------------------------------------
    def _redinvoice_maybe_issue(self):
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'out_refund'):
            return
        if self.amount_total <= 0:
            self.red_invoice_state = 'not_required'
            return
        if self.red_invoice_state in ('issued', 'issuing'):
            return
        self._redinvoice_issue()

    def _redinvoice_issue(self):
        self.ensure_one()
        company = self.company_id
        if not company.red_supplier_tax_code or not company.red_invoice_api_base:
            self.write({
                'red_invoice_state': 'failed',
                'red_invoice_last_error': _('Missing Red Invoice configuration on company.'),
            })
            return

        payload = self._prepare_redinvoice_payload()
        endpoint = f"{company.red_invoice_api_base.rstrip('/')}/InvoiceAPI/InvoiceWS/createInvoice/{company.red_supplier_tax_code}"
        request_log = self.env['redinvoice.request'].create({
            'name': f"Red Invoice for {self.name}",
            'move_id': self.id,
            'company_id': company.id,
            'endpoint': endpoint,
            'payload': json.dumps(payload, ensure_ascii=False, indent=2),
        })

        headers = {
            'Content-Type': 'application/json',
        }
        cookies = self._redinvoice_auth_cookies()
        self.write({'red_invoice_state': 'issuing'})

        try:
            response = requests.post(endpoint, json=payload, headers=headers, cookies=cookies, timeout=60)
            request_log.mark_sent(code=str(response.status_code), body=response.text)
        except Exception as exc:
            self.write({
                'red_invoice_state': 'failed',
                'red_invoice_last_error': str(exc),
            })
            request_log.mark_failed(message=str(exc))
            return

        if response.status_code != 200:
            self.write({
                'red_invoice_state': 'failed',
                'red_invoice_last_error': f"HTTP {response.status_code}: {response.text}",
            })
            request_log.mark_failed(message=response.text, code=str(response.status_code), body=response.text)
            return

        result = {}
        try:
            result = response.json() if response.text else {}
        except Exception:
            pass

        if result.get('errorCode'):
            message = result.get('description') or result.get('errorCode')
            self.write({
                'red_invoice_state': 'failed',
                'red_invoice_last_error': message,
            })
            request_log.mark_failed(message=message, code=str(response.status_code), body=response.text)
            return

        info = result.get('result', {})
        vals = {
            'red_invoice_state': 'issued',
            'red_invoice_no': info.get('invoiceNo'),
            'red_invoice_series': info.get('invoiceNo', '')[:7] if info.get('invoiceNo') else self.red_invoice_series,
            'red_invoice_reservation_code': info.get('reservationCode'),
            'red_invoice_transaction_id': info.get('transactionID'),
            'red_invoice_code_of_tax': info.get('codeOfTax'),
            'red_invoice_last_error': False,
            'red_invoice_last_sync': fields.Datetime.now(),
        }
        if info.get('supplierTaxCode'):
            vals.setdefault('red_invoice_template_code', self.red_invoice_template_code or company.red_invoice_template_code)
        self.write(vals)
        request_log.mark_success(code=str(response.status_code), body=response.text)

        # Optional immediate download of representation file
        download_pdf = self.env['ir.config_parameter'].sudo().get_param('health_redinvoice.download_pdf', 'True') == 'True'
        self._redinvoice_download(file_type='ZIP')
        if download_pdf:
            self._redinvoice_download(file_type='PDF')

    def _redinvoice_download(self, file_type='ZIP'):
        self.ensure_one()
        if not self.red_invoice_no or not self.red_invoice_template_code:
            return
        company = self.company_id
        base = company.red_invoice_api_base
        if not base:
            return
        path = '/InvoiceAPI/InvoiceUtilsWS/getInvoiceRepresentationFile'
        if file_type.upper() == 'PDF':
            path = '/InvoiceAPI/InvoiceWS/createExchangeInvoiceFile'
        endpoint = f"{base.rstrip('/')}{path}"
        payload = {
            'supplierTaxCode': company.red_supplier_tax_code,
            'invoiceNo': self.red_invoice_no,
            'templateCode': self.red_invoice_template_code,
            'transactionUuid': self.red_invoice_transaction_uuid,
        }
        if file_type.upper() == 'PDF':
            payload['strIssueDate'] = fields.Date.to_string(self.invoice_date or fields.Date.context_today(self))
            payload['exchangeUser'] = company.red_invoice_exchange_user or company.name
        headers = {'Content-Type': 'application/json' if file_type.upper() == 'ZIP' else 'application/x-www-form-urlencoded'}
        cookies = self._redinvoice_auth_cookies()
        try:
            resp = requests.post(endpoint, json=payload if headers['Content-Type'] == 'application/json' else None,
                                  data=None if headers['Content-Type'] == 'application/json' else payload,
                                  headers=headers, cookies=cookies, timeout=60)
            if resp.status_code != 200:
                _logger.warning("Red Invoice download failed %s: %s", self.name, resp.text)
                return
            data = resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else {}
            file_bytes = data.get('fileToBytes')
            filename = data.get('fileName') or f"{self.name}.{file_type.lower()}"
            if not file_bytes:
                return
            attachment = self._redinvoice_attach_file(filename, file_bytes, file_type)
            if file_type.upper() == 'ZIP':
                self.red_invoice_download_attachment_id = attachment.id
            else:
                self.red_invoice_pdf_attachment_id = attachment.id
        except Exception as exc:
            _logger.warning("Red Invoice download error for %s: %s", self.name, exc)

    def _redinvoice_attach_file(self, filename, file_bytes, file_type):
        """Create attachment from base64 string."""
        return self.env['ir.attachment'].create({
            'name': filename,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'datas': file_bytes,
            'mimetype': 'application/zip' if file_type.upper() == 'ZIP' else 'application/pdf',
        })

    def _redinvoice_cancel_remote(self):
        self.ensure_one()
        company = self.company_id
        if not self.red_invoice_no:
            raise UserError(_('No Red Invoice was issued for this document.'))
        endpoint = f"{company.red_invoice_api_base.rstrip('/')}/InvoiceAPI/InvoiceWS/cancelTransactionInvoice"
        payload = {
            'supplierTaxCode': company.red_supplier_tax_code,
            'invoiceNo': self.red_invoice_no,
            'templateCode': self.red_invoice_template_code,
            'strIssueDate': fields.Date.to_string(self.invoice_date or fields.Date.context_today(self)),
            'additionalReferenceDesc': _('Cancellation requested from Odoo'),
            'additionalReferenceDate': int(datetime.datetime.now().timestamp() * 1000),
            'reasonDelete': _('Cancelled from Odoo'),
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        cookies = self._redinvoice_auth_cookies()
        try:
            resp = requests.post(endpoint, data=payload, headers=headers, cookies=cookies, timeout=60)
            if resp.status_code == 200:
                result = resp.json() if resp.text else {}
                if result.get('errorCode'):
                    raise UserError(result.get('description') or result.get('errorCode'))
                self.write({'red_invoice_state': 'cancelled'})
            else:
                raise UserError(_("Cancellation failed: %s") % resp.text)
        except Exception as exc:
            raise UserError(str(exc))

    def _redinvoice_auth_cookies(self):
        company = self.company_id
        if not company.red_invoice_username or not company.red_invoice_password:
            return {}
        login_endpoint = f"{company.red_invoice_api_base.rstrip('/')}/auth/login"
        payload = {
            'username': company.red_invoice_username,
            'password': company.red_invoice_password,
        }
        try:
            resp = requests.post(login_endpoint, json=payload, timeout=30)
            if resp.status_code != 200:
                _logger.warning("Red Invoice auth failed: %s", resp.text)
                return {}
            data = resp.json()
            token = data.get('access_token')
            if token:
                return {'access_token': token}
        except Exception as exc:
            _logger.warning("Red Invoice auth error: %s", exc)
        return {}

    def _prepare_redinvoice_payload(self):
        self.ensure_one()
        company = self.company_id
        partner = self.partner_id
        template_code = self.red_invoice_template_code or company.red_invoice_template_code
        series = self.red_invoice_series or company.red_invoice_series
        if not template_code or not series:
            raise UserError(_('Red Invoice template code/series not configured.'))

        issue_dt = self.invoice_date or fields.Date.context_today(self)
        issue_ms = int(datetime.datetime.combine(issue_dt, datetime.time.min).timestamp() * 1000)
        payment_status = self.payment_state in ('paid', 'in_payment')
        currency_code = self.currency_id.name or 'VND'

        payments = [{
            'paymentMethod': self.red_invoice_payment_method or '5',
            'paymentMethodName': self.red_invoice_payment_method_name or 'Other',
        }]

        item_info = []
        line_number = 1
        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            tax_percentage = self._redinvoice_tax_percentage(line)
            item = {
                'lineNumber': line_number,
                'itemCode': line.product_id.default_code or '',
                'itemName': line.name or line.product_id.name,
                'unitName': line.product_uom_id.name if line.product_uom_id else '',
                'unitPrice': line.price_unit,
                'quantity': line.quantity,
                'itemTotalAmountWithoutTax': line.price_subtotal,
                'itemTotalAmountWithTax': line.price_total,
                'itemTotalAmountAfterDiscount': line.price_subtotal,
                'taxPercentage': tax_percentage,
                'taxAmount': line.price_total - line.price_subtotal,
                'discount': line.discount or 0,
                'itemDiscount': 0,
                'isIncreaseItem': True,
            }
            item_info.append(item)
            line_number += 1

        summarize = {
            'sumOfTotalLineAmountWithoutTax': sum(item['itemTotalAmountWithoutTax'] for item in item_info),
            'totalAmountWithoutTax': self.amount_untaxed,
            'totalTaxAmount': self.amount_tax,
            'totalAmountWithTax': self.amount_total,
            'totalAmountAfterDiscount': self.amount_total,
            'totalAmountWithTaxInWords': self.currency_id.amount_to_text(self.amount_total) if hasattr(self.currency_id, 'amount_to_text') else '',
        }

        tax_breakdowns = self._redinvoice_tax_breakdowns(item_info)

        payload = {
            'generalInvoiceInfo': {
                'transactionUuid': self.red_invoice_transaction_uuid,
                'invoiceType': '',  # optional depending on template
                'templateCode': template_code,
                'invoiceSeries': series,
                'invoiceIssuedDate': issue_ms,
                'currencyCode': currency_code,
                'adjustmentType': '1',
                'paymentStatus': payment_status,
                'cusGetInvoiceRight': True,
                'reservationCode': self.red_invoice_reservation_code or '',
            },
            'sellerInfo': {
                'sellerLegalName': company.name,
                'sellerTaxCode': company.red_supplier_tax_code,
                'sellerAddressLine': company.street or '',
                'sellerPhoneNumber': company.phone or '',
                'sellerEmail': company.email or '',
                'sellerBankName': company.red_invoice_bank_name or '',
                'sellerBankAccount': company.red_invoice_bank_account or '',
                'sellerDistrictName': company.red_invoice_district_name or '',
                'sellerCityName': company.city or '',
                'sellerCountryCode': company.red_invoice_country_code or '',
                'merchantCode': company.red_invoice_merchant_code or '',
                'merchantName': company.red_invoice_merchant_name or '',
                'merchantCity': company.red_invoice_merchant_city or '',
            },
            'buyerInfo': {
                'buyerName': partner.name,
                'buyerLegalName': partner.buyer_legal_name or partner.name,
                'buyerTaxCode': partner.vat or '',
                'buyerAddressLine': partner.street or '',
                'buyerPostalCode': partner.buyer_postal_code or '',
                'buyerDistrictName': partner.buyer_district_name or '',
                'buyerCityName': partner.city or '',
                'buyerCountryCode': partner.buyer_country_code or '',
                'buyerPhoneNumber': partner.phone or '',
                'buyerEmail': partner.email or '',
                'buyerBankName': partner.buyer_bank_name or '',
                'buyerBankAccount': partner.buyer_bank_account or '',
                'buyerIdType': partner.buyer_id_type or '',
                'buyerIdNo': partner.vat or '',
                'buyerNotGetInvoice': 1 if partner.buyer_not_get_invoice else 0,
            },
            'payments': payments,
            'itemInfo': item_info,
            'taxBreakdowns': tax_breakdowns,
            'summarizeInfo': summarize,
        }

        metadata = self._redinvoice_metadata()
        if metadata:
            payload['metadata'] = metadata

        return payload

    def _redinvoice_tax_percentage(self, line):
        if not line.tax_ids:
            return -1
        tax = line.tax_ids[0]
        return tax.amount or 0

    def _redinvoice_tax_breakdowns(self, item_info):
        buckets = {}
        for item in item_info:
            rate = item.get('taxPercentage')
            bucket = buckets.setdefault(rate, {'taxPercentage': rate, 'taxableAmount': 0, 'taxAmount': 0})
            bucket['taxableAmount'] += item.get('itemTotalAmountWithoutTax', 0)
            bucket['taxAmount'] += item.get('taxAmount', 0)
        return list(buckets.values())

    def _redinvoice_metadata(self):
        # Placeholder for dynamic metadata (custom fields)
        return []
