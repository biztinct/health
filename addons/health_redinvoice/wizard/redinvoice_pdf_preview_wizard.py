# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class RedInvoicePdfPreviewWizard(models.TransientModel):
    _name = 'redinvoice.pdf.preview.wizard'
    _description = 'Red Invoice PDF Preview Wizard'

    move_id = fields.Many2one('account.move', string='Invoice', required=True, readonly=True)
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', required=True, readonly=True)
    filename = fields.Char(string='Filename', related='attachment_id.name', readonly=True)
    pdf_url = fields.Char(string='PDF URL', compute='_compute_pdf_url', readonly=True)

    @api.depends('attachment_id')
    def _compute_pdf_url(self):
        for wizard in self:
            wizard.pdf_url = (
                f'/web/content/{wizard.attachment_id.id}?download=0#toolbar=1&navpanes=0&zoom=page-width'
                if wizard.attachment_id else False
            )

    def action_download(self):
        """Download the Red Invoice PDF."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=1',
            'target': 'self',
        }

    def action_print(self):
        """Open the PDF inline in a new tab (browser print dialog available)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=0#toolbar=1',
            'target': 'new',
        }

    def action_email_client(self):
        """Compose an email to the client with the Red Invoice PDF attached."""
        self.ensure_one()
        move = self.move_id
        partner = move.partner_id
        subject = _('Red Invoice %s') % (move.red_invoice_no or move.name or '')
        body = _(
            '<p>Dear %s,</p><p>Please find attached your VAT (Red) invoice.</p>'
            '<p>Best regards,<br/>%s</p>'
        ) % (partner.name or _('Customer'), move.company_id.name or '')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Email Red Invoice'),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_composition_mode': 'comment',
                'default_model': 'account.move',
                'active_model': 'account.move',
                'active_id': move.id,
                'active_ids': move.ids,
                'default_partner_ids': partner.ids,
                'default_attachment_ids': [(6, 0, [self.attachment_id.id])],
                'default_subject': subject,
                'default_body': body,
            },
        }
