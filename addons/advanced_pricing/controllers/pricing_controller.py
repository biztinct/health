# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class PricingController(http.Controller):
    
    @http.route('/api/pricing/calculate', type='json', auth='user', methods=['POST'], csrf=False)
    def calculate_price(self, **kwargs):
        """REST API endpoint for price calculation"""
        try:
            data = request.jsonrequest
            
            config = request.env['advanced.pricing.config'].get_config()
            
            if not config.enable_api:
                return {'error': 'API access is disabled', 'status': 403}
            
            engine = config.default_engine_id
            if not engine:
                return {'error': 'No default pricing engine configured', 'status': 400}
            
            price = engine.calculate_price(
                data.get('product_id'),
                data.get('quantity', 1),
                data.get('partner_id', False),
                data.get('context', {})
            )
            
            return {
                'status': 200,
                'price': price,
                'currency': request.env.company.currency_id.name
            }
            
        except Exception as e:
            _logger.error(f"API pricing error: {e}")
            return {'error': str(e), 'status': 500}