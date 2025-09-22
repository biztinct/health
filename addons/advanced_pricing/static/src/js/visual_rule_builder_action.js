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
                const ruleIds = await this.orm.create('advanced.pricing.rule', [{
                    ...ruleData,
                    rule_type: 'visual',
                }]);
                
                console.log('Created rule IDs:', ruleIds);
                
                // Show success notification
                this.notification.add("Visual rule saved successfully! Returning to rules list...", {
                    type: "success",
                });
                
                // Auto-navigate to rules list for better UX
                setTimeout(() => {
                    this.backToRulesList();
                }, 1000); // Give user time to see the success message
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

    async viewRule(ruleId) {
        try {
            await this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Pricing Rule',
                res_model: 'advanced.pricing.rule',
                res_id: ruleId,
                view_mode: 'form',
                target: 'current',
            });
        } catch (error) {
            console.warn('Failed to view rule:', error);
            this.notification.add("Could not open rule form", { type: "warning" });
        }
    }

    async backToRulesList() {
        try {
            await this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Pricing Rules',
                res_model: 'advanced.pricing.rule',
                view_mode: 'list,form',
                target: 'current',
                domain: [],
                context: {},
            });
        } catch (error) {
            console.warn('Failed to navigate to rules list:', error);
            // Fallback: just close the visual builder
            this.onCancel();
        }
    }
}

// Register the client action
registry.category("actions").add("visual_rule_builder", VisualRuleBuilderAction);