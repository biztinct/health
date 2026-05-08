/** @odoo-module **/

import { Component, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { _t } from "@web/core/l10n/translation";

export class PricingRuleBuilder extends Component {
    static template = 'advanced_pricing.RuleBuilder';
    static props = {
        rule: { type: Object, optional: true },
        onSave: { type: Function },
        onClose: { type: Function },
    };

    t(text) {
        return _t(text);
    }

    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        
        this.state = useState({
            ruleName: this.props.rule?.name || 'New Rule',
            level: this.props.rule?.level || '1',
            generatedCode: '',
        });
    }

    async saveRule() {
        const ruleData = {
            name: this.state.ruleName,
            level: this.state.level,
            rule_type: 'custom',
            engine_id: this.props.rule?.engine_id?.[0],
        };

        try {
            let ruleId;
            if (this.props.rule?.id) {
                await this.orm.write('advanced.pricing.rule', [this.props.rule.id], ruleData);
                ruleId = this.props.rule.id;
            } else {
                ruleId = await this.orm.create('advanced.pricing.rule', ruleData);
            }

            this.notification.add('Rule saved successfully', { type: 'success' });

            if (this.props.onSave) {
                this.props.onSave(ruleId);
            }
        } catch (error) {
            console.error('Error saving rule:', error);
            this.notification.add('Error saving rule', { type: 'danger' });
        }
    }
}

registry.category('components').add('pricing_rule_builder', PricingRuleBuilder);
