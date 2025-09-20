/** @odoo-module **/

import { Component, useState } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';

export class PricingCalculator extends Component {
    static template = 'advanced_pricing.Calculator';
    
    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        
        this.state = useState({
            calculating: false,
            result: null,
            error: null,
        });
    }

    async calculate() {
        this.state.calculating = true;
        this.state.error = null;
        
        try {
            const config = await this.orm.call(
                'advanced.pricing.config',
                'get_config',
                []
            );

            if (!config.default_engine_id) {
                throw new Error('No default pricing engine configured');
            }

            const result = await this.orm.call(
                'advanced.pricing.engine',
                'calculate_price',
                [config.default_engine_id[0]],
                {
                    product_id: this.props.productId,
                    quantity: this.props.quantity || 1,
                    partner_id: this.props.partnerId,
                    context_data: {},
                }
            );

            this.state.result = result;
        } catch (error) {
            this.state.error = error.message || 'Calculation failed';
        } finally {
            this.state.calculating = false;
        }
    }
}