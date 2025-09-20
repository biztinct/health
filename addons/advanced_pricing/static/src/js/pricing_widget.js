/** @odoo-module **/

import { Component, useState, onWillStart } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

export class AdvancedPricingWidget extends Component {
    static template = 'advanced_pricing.PricingWidget';
    static props = {
        record: { type: Object, optional: true },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        
        this.state = useState({
            rules: [],
            selectedRule: null,
            isLoading: false,
        });

        onWillStart(async () => {
            await this.loadRules();
        });
    }

    async loadRules() {
        this.state.isLoading = true;
        try {
            const engineId = this.props.record?.data?.advanced_engine_id?.[0];
            if (engineId) {
                const rules = await this.orm.searchRead(
                    'advanced.pricing.rule',
                    [['engine_id', '=', engineId]],
                    ['name', 'sequence', 'level', 'rule_type', 'active']
                );
                this.state.rules = rules;
            }
        } catch (error) {
            console.error('Error loading rules:', error);
            this.notification.add('Error loading pricing rules', {
                type: 'danger',
            });
        } finally {
            this.state.isLoading = false;
        }
    }
}

registry.category('fields').add('advanced_pricing_widget', {
    component: AdvancedPricingWidget,
});