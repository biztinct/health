/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { VisualRuleBuilder } from "./visual_rule_builder";

/**
 * Client Action for Visual Rule Builder
 * Provides full-screen interface for building pricing rules
 */
export class VisualRuleBuilderAction extends Component {
    static template = "advanced_pricing.VisualRuleBuilderActionTemplate";
    static components = { VisualRuleBuilder };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        
        this.state = useState({
            ruleData: this.props.action?.context?.rule_data || {},
            wizardId: this.props.action?.context?.wizard_id,
        });
    }

    async onSaveRule(ruleData) {
        try {
            if (this.state.wizardId) {
                // Save through wizard
                const result = await this.orm.call(
                    'advanced.pricing.visual.wizard',
                    'save_visual_rule_data',
                    [this.state.wizardId, ruleData]
                );
                
                if (result && result.res_id) {
                    // Close current action and show the created rule
                    this.action.doAction(result);
                } else {
                    // Just close the visual builder
                    this.onCancel();
                }
            } else {
                // Direct save to pricing rule model
                const rule = await this.orm.create('advanced.pricing.rule', {
                    ...ruleData,
                    rule_type: 'visual',
                });
                
                // Show success and navigate to rule
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: 'Pricing Rule',
                    res_model: 'advanced.pricing.rule',
                    res_id: rule,
                    view_mode: 'form',
                    target: 'current',
                });
            }
        } catch (error) {
            console.error("Failed to save visual rule:", error);
            this.notification.add("Failed to save rule: " + (error.message || 'Unknown error'), {
                type: "danger",
            });
        }
    }

    onCancel() {
        // Close the action and return to previous view
        this.action.doAction({ type: 'ir.actions.act_window_close' });
    }
}

// Register the client action
registry.category("actions").add("visual_rule_builder", VisualRuleBuilderAction);