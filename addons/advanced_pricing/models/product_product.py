# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductCategory(models.Model):
    """Service categories are a CLIENT-FACING taxonomy here, not an accounting
    bucket: the price-list import builds them from the sheet's
    `service_type` / `service_category` columns, which ship in both languages,
    and they surface in the Services list and the product dropdowns.

    Core Odoo leaves `name` untranslated, which forced the importer to pick one
    language and store it as the whole name (see `_get_or_create_category`).
    Making it translatable lets both live on the same record and lets the CMS
    Master Data > Service Categories tab edit either side.
    """
    _inherit = 'product.category'

    name = fields.Char(translate=True)


class ProductTemplate(models.Model):
    """Price-list columns carried onto the service itself.

    The CRM price input sheets (``<Region>_Base_Clean``) describe every item
    with a four-level taxonomy, each level in English AND Vietnamese:
    service class → main service → marketing service line → item group.
    The first two become the product.category hierarchy (translatable, see
    ProductCategory above); the last two are plain translatable labels on the
    service, because nothing selects or prices by them — they exist for
    grouping in lists and for marketing reports.

    ``default_code`` stays ``<item_code>_<region suffix>`` (``bs_010_hanoi``):
    nine places parse that suffix (catalog catchment, pricing region, quick
    booking), so the bare code lives in ``price_item_code`` instead of
    changing the contract.
    """
    _inherit = 'product.template'

    rounding_rule = fields.Selection([
        ('round_1000', 'Round up to next 1,000'),
        ('round_5min', 'Round up to next 5 mins'),
        ('round_30min', 'Round up to next 30 mins'),
        ('round_half_hour', 'Round up to next half hour'),
        ('round_hour', 'Round up to next hour'),
        ('round_partial_hour', 'Round partial hour up to next 1 hour'),
        ('round_partial_30min', 'Round partial hour up to next 30 minutes'),
        ('round_as_documented', 'Round up partial time as documented'),
    ], string='Rounding Rule',
       help='Rounding rule applied to the calculated price for this product')

    price_item_code = fields.Char(
        'Price List Code', index=True,
        help='Item code as written in the price list (e.g. bs_010). The internal '
             'reference adds the region (bs_010_hanoi).')
    marketing_service_line = fields.Char(
        'Marketing Service Line', translate=True,
        help='Marketing grouping from the price list (English and Vietnamese).')
    item_group = fields.Char(
        'Item Group', translate=True,
        help='Item group from the price list, e.g. Doctor, Wound Care (English and Vietnamese).')
    price_is_fee = fields.Boolean(
        'Fee Item',
        help='A fee or surcharge (visit fee, after-hours, weekend, travel) rather than '
             'a service. Fee items do not count as "another service" in price conditions.')
    price_valid_from = fields.Date('Price Valid From')
    price_valid_to = fields.Date('Price Valid To')
    price_version = fields.Char('Price Version')
    price_updated_by = fields.Char('Price Updated By')
    price_updated_on = fields.Date('Price Updated On')
    price_change_reason = fields.Text('Reason for Price Change')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    catalog_catchment_area = fields.Selection([
        ('hanoi', 'Hanoi'),
        ('tphcm', 'Ho Chi Minh City'),
    ], string='Catchment Area', compute='_compute_catalog_catchment_area', store=True)

    @api.depends('default_code')
    def _compute_catalog_catchment_area(self):
        for product in self:
            code = (product.default_code or '').lower()
            if code.endswith('_hanoi') or '_hanoi_' in code:
                product.catalog_catchment_area = 'hanoi'
            elif code.endswith('_tphcm') or '_tphcm_' in code:
                product.catalog_catchment_area = 'tphcm'
            else:
                product.catalog_catchment_area = False
    
    def action_return_to_healthcare_quote(self):
        """Return to Healthcare Quote from product catalog"""
        context = self.env.context
        quote_order_id = context.get('quote_order_id') or context.get('order_id')
        
        if not quote_order_id:
            return False
            
        # Get the quote/sale order
        quote = self.env['sale.order'].browse(quote_order_id)
        
        if not quote.exists():
            return False
            
        # Return to Healthcare Quote form
        return {
            'type': 'ir.actions.act_window',
            'name': f'Healthcare Quote - {quote.name}',
            'res_model': 'sale.order',
            'res_id': quote.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_fieldservice.view_healthcare_quote_form_custom').id,
            'target': 'main',
            'context': {
                'healthcare_context': True,
                'from_catalog': True,
            }
        }
