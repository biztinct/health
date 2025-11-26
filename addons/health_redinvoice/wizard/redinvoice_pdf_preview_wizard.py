# -*- coding: utf-8 -*-

from odoo import api, fields, models


class RedInvoicePdfPreviewWizard(models.TransientModel):
    _name = 'redinvoice.pdf.preview.wizard'
    _description = 'Red Invoice PDF Preview Wizard'

    move_id = fields.Many2one('account.move', string='Invoice', required=True, readonly=True)
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', required=True, readonly=True)
    pdf_binary = fields.Binary(string='Red Invoice PDF', compute='_compute_pdf_binary', readonly=True)
    filename = fields.Char(string='Filename', related='attachment_id.name', readonly=True)

    @api.depends('attachment_id')
    def _compute_pdf_binary(self):
        for wizard in self:
            wizard.pdf_binary = wizard.attachment_id.with_context(bin_size=False).datas if wizard.attachment_id else False
