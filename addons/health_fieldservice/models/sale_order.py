from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    """Extend sale.order to add healthcare quote validation and invoice creation"""
    _inherit = 'sale.order'
    
    def action_confirm(self):
        """Override confirm to validate quote lines"""
        for order in self:
            if order.origin and 'FSO' in order.origin:
                order._validate_healthcare_quote_lines()
        return super().action_confirm()
    
    def action_create_invoice_from_healthcare_quote(self):
        """Create invoice from healthcare quote (proper sale.order workflow)"""
        self.ensure_one()
        
        # Validate quote has items
        if not self.order_line:
            raise UserError(_(
                'Cannot create invoice from empty quote.\n'
                'Please add at least one service or product to this quote.'
            ))
        
        # Get the related FSO
        fso = self.env['health.fieldservice.order'].search([('sale_order_id', '=', self.id)], limit=1)
        if not fso:
            raise UserError(_('No FSO found for this quote.'))
        
        # Validate FSO is completed before invoicing
        if fso.state != 'completed':
            raise UserError(_(
                'Cannot create invoice: FSO must be completed first.\n'
                'Current FSO state: %s\n'
                'Please complete the field service order before creating the invoice.'
            ) % fso.state)
        
        # Confirm the quote first if not already confirmed
        if self.state == 'draft':
            self.action_confirm()
        
        # For healthcare services, mark all order lines as delivered
        # since healthcare services are delivered when the FSO is completed
        for line in self.order_line:
            if line.product_id.type == 'service':
                # Mark services as fully delivered
                line.qty_delivered = line.product_uom_qty
            else:
                # For other products, also mark as delivered (consumables used during service)
                line.qty_delivered = line.product_uom_qty
        
        # Create invoice from quote using standard sale.order workflow
        # This respects the quote items and creates invoice lines accordingly
        invoice_ids = self._create_invoices()
        
        if not invoice_ids:
            raise UserError(_(
                'No invoice could be created from this quote.\n'
                'Please check that:\n'
                '• All items have been marked as delivered\n'
                '• Product invoicing policies are correct\n'
                '• Quote is in confirmed state'
            ))
        
        # Get the created invoice
        invoice = invoice_ids[0] if invoice_ids else None
        if invoice:
            # Update FSO with invoice link
            fso.invoice_id = invoice.id
            
            # Set invoice origin to FSO reference
            invoice.write({
                'invoice_origin': f'FSO: {fso.name}',
                'ref': fso.name,
            })
            
            # Post a message in FSO chatter
            fso.message_post(
                body=_('Invoice %s created from healthcare quote %s') % (invoice.name, self.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        
        # Close the quote popup and return to FSO
        return {
            'type': 'ir.actions.act_window_close',
        }
    
    def _validate_healthcare_quote_lines(self):
        """Validate that healthcare quotes have at least one order line"""
        self.ensure_one()
        if not self.order_line:
            raise UserError(_(
                'Healthcare quotes must have at least one order line before confirmation.\n'
                'Please add at least one service or product to this quote.'
            ))
    
    def action_save_and_return_to_fso(self):
        """Save quote and return to parent FSO regardless of workflow path"""
        self.ensure_one()
        
        # Find the related FSO
        fso = self.env['health.fieldservice.order'].search([('sale_order_id', '=', self.id)], limit=1)
        
        # Show notification to debug what's happening
        if fso:
            message = f'FSO Found: {fso.name} (ID: {fso.id}). Attempting redirect...'
        else:
            message = f'No FSO found for quote {self.name}. Closing modal...'
            
        # Show notification first
        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Debug Info',
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }
        
        # If this is an FSO quote, try to return to the FSO
        if fso:
            # Return multiple actions - notification then navigation
            return {
                'type': 'ir.actions.act_multi',
                'actions': [
                    notification,
                    {
                        'type': 'ir.actions.act_window',
                        'name': f'Field Service Order - {fso.name}',
                        'res_model': 'health.fieldservice.order',
                        'res_id': fso.id,
                        'view_mode': 'form',
                        'target': 'main',  # Try 'main' to replace everything
                    }
                ]
            }
        
        # For regular quotes, show notification and close modal
        return notification
    
    def get_healthcare_quote_view_id(self):
        """Get the correct view ID for healthcare quotes"""
        self.ensure_one()
        # Always return the healthcare quote form view for FSO quotes
        return self.env.ref('health_fieldservice.view_healthcare_quote_form_custom').id