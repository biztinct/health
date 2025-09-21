/** @odoo-module **/

import { registry } from '@web/core/registry';

export class PricingService {
    constructor(env, { orm, notification }) {
        this.env = env;
        this.orm = orm;
        this.notification = notification;
        this.cache = new Map();
    }

    async calculatePrice(productId, quantity, partnerId, contextData) {
        const cacheKey = JSON.stringify({ productId, quantity, partnerId, contextData });
        
        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }

        const config = await this.orm.call('advanced.pricing.config', 'get_config', []);
        
        if (!config.default_engine_id) {
            throw new Error('No default pricing engine configured');
        }

        const price = await this.orm.call(
            'advanced.pricing.engine',
            'calculate_price',
            [config.default_engine_id[0]],
            {
                product_id: productId,
                quantity: quantity,
                partner_id: partnerId,
                context_data: contextData,
            }
        );

        this.cache.set(cacheKey, price);
        return price;
    }

    clearCache() {
        this.cache.clear();
    }
}

registry.category('services').add('pricing', {
    dependencies: ['orm', 'notification'],
    start(env, dependencies) {
        return new PricingService(env, dependencies);
    },
});