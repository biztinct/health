/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Visual Rule Builder using Google Blockly
 * Drag-and-drop interface for creating pricing rules
 */
export class VisualRuleBuilder extends Component {
    static template = "advanced_pricing.VisualRuleBuilderTemplate";
    static props = {
        ruleData: { type: Object, optional: true },
        onSave: Function,
        onCancel: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            isLoading: true,
            workspace: null,
            generatedCode: "",
            previewRule: {},
        });
        
        this.blocklyDiv = useRef("blocklyDiv");
        this.toolboxRef = useRef("toolbox");
        
        onMounted(this.initializeBlockly);
        onWillUnmount(this.destroyBlockly);
    }

    async initializeBlockly() {
        try {
            // Wait for Blockly to be loaded
            await this.loadBlocklyLibrary();
            
            // Define custom blocks for pricing rules
            this.defineCustomBlocks();
            
            // Initialize workspace
            this.createWorkspace();
            
            // Load existing rule if provided
            if (this.props.ruleData && this.props.ruleData.visual_config) {
                this.loadExistingRule();
            }
            
            this.state.isLoading = false;
        } catch (error) {
            console.error("Failed to initialize Blockly:", error);
            this.notification.add(_t("Failed to load visual rule builder"), {
                type: "danger",
            });
        }
    }

    async loadBlocklyLibrary() {
        // Check if Blockly is already loaded
        if (window.Blockly) {
            return;
        }

        // Load from official CDN as recommended by Blockly
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/blockly/blockly.min.js';
        
        return new Promise((resolve, reject) => {
            script.onload = () => {
                // Blockly should be immediately available from the minified version
                if (window.Blockly) {
                    resolve();
                } else {
                    // Retry after a short delay
                    setTimeout(() => {
                        if (window.Blockly) {
                            resolve();
                        } else {
                            reject(new Error('Blockly failed to load from CDN'));
                        }
                    }, 1000);
                }
            };
            script.onerror = () => reject(new Error('Failed to load Blockly from CDN'));
            document.head.appendChild(script);
        });
    }

    async loadBlocklyDependencies() {
        // The minified version includes everything, so no additional dependencies needed
        return Promise.resolve();
    }

    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    defineCustomBlocks() {
        if (!window.Blockly) return;

        // Define pricing condition block
        window.Blockly.defineBlocksWithJsonArray([
            {
                "type": "pricing_condition",
                "message0": "If %1 %2 %3",
                "args0": [
                    {
                        "type": "field_dropdown",
                        "name": "FIELD",
                        "options": [
                            ["Order Total", "order_total"],
                            ["Quantity", "quantity"],
                            ["Customer Type", "customer_type"],
                            ["Distance", "distance"],
                            ["Time", "time"],
                            ["Service Type", "service_type"]
                        ]
                    },
                    {
                        "type": "field_dropdown",
                        "name": "OPERATOR",
                        "options": [
                            ["equals", "=="],
                            ["greater than", ">"],
                            ["less than", "<"],
                            ["greater or equal", ">="],
                            ["less or equal", "<="],
                            ["not equal", "!="]
                        ]
                    },
                    {
                        "type": "input_value",
                        "name": "VALUE"
                    }
                ],
                "inputsInline": true,
                "output": "Boolean",
                "colour": 210,
                "tooltip": "Create a pricing condition",
                "helpUrl": ""
            },
            {
                "type": "pricing_action",
                "message0": "Set price to %1 %2",
                "args0": [
                    {
                        "type": "field_dropdown",
                        "name": "ACTION_TYPE",
                        "options": [
                            ["Add", "add"],
                            ["Subtract", "subtract"],
                            ["Multiply by", "multiply"],
                            ["Set to", "set"],
                            ["Percentage", "percentage"]
                        ]
                    },
                    {
                        "type": "input_value",
                        "name": "VALUE"
                    }
                ],
                "inputsInline": true,
                "previousStatement": null,
                "nextStatement": null,
                "colour": 160,
                "tooltip": "Define a pricing action",
                "helpUrl": ""
            },
            {
                "type": "number_value",
                "message0": "%1",
                "args0": [
                    {
                        "type": "field_number",
                        "name": "NUM",
                        "value": 0
                    }
                ],
                "output": "Number",
                "colour": 230,
                "tooltip": "A number value",
                "helpUrl": ""
            },
            {
                "type": "pricing_rule",
                "message0": "Pricing Rule %1 %2 Then %3",
                "args0": [
                    {
                        "type": "field_input",
                        "name": "RULE_NAME",
                        "text": "New Rule"
                    },
                    {
                        "type": "input_value",
                        "name": "CONDITION",
                        "check": "Boolean"
                    },
                    {
                        "type": "input_statement",
                        "name": "ACTIONS"
                    }
                ],
                "colour": 120,
                "tooltip": "Create a complete pricing rule",
                "helpUrl": ""
            }
        ]);

        // Define JavaScript generators for the blocks
        window.Blockly.JavaScript['pricing_condition'] = function(block) {
            const field = block.getFieldValue('FIELD');
            const operator = block.getFieldValue('OPERATOR');
            const value = window.Blockly.JavaScript.valueToCode(block, 'VALUE', window.Blockly.JavaScript.ORDER_ATOMIC);
            
            return [`${field} ${operator} ${value}`, window.Blockly.JavaScript.ORDER_RELATIONAL];
        };

        window.Blockly.JavaScript['pricing_action'] = function(block) {
            const actionType = block.getFieldValue('ACTION_TYPE');
            const value = window.Blockly.JavaScript.valueToCode(block, 'VALUE', window.Blockly.JavaScript.ORDER_ATOMIC);
            
            return `apply_${actionType}(${value});\n`;
        };

        window.Blockly.JavaScript['number_value'] = function(block) {
            const number = parseFloat(block.getFieldValue('NUM'));
            return [number, window.Blockly.JavaScript.ORDER_ATOMIC];
        };

        window.Blockly.JavaScript['pricing_rule'] = function(block) {
            const ruleName = block.getFieldValue('RULE_NAME');
            const condition = window.Blockly.JavaScript.valueToCode(block, 'CONDITION', window.Blockly.JavaScript.ORDER_NONE);
            const actions = window.Blockly.JavaScript.statementToCode(block, 'ACTIONS');
            
            return `// Rule: ${ruleName}\nif (${condition}) {\n${actions}}\n`;
        };
    }

    createWorkspace() {
        const toolbox = `
        <xml xmlns="https://developers.google.com/blockly/xml" id="toolbox" style="display: none">
            <category name="Conditions" colour="210">
                <block type="pricing_condition"></block>
                <block type="logic_boolean"></block>
                <block type="logic_operation"></block>
                <block type="logic_negate"></block>
            </category>
            <category name="Actions" colour="160">
                <block type="pricing_action"></block>
            </category>
            <category name="Values" colour="230">
                <block type="number_value"></block>
                <block type="text"></block>
            </category>
            <category name="Rules" colour="120">
                <block type="pricing_rule"></block>
            </category>
            <category name="Logic" colour="210">
                <block type="controls_if"></block>
                <block type="logic_compare"></block>
                <block type="math_arithmetic"></block>
            </category>
        </xml>`;

        this.state.workspace = window.Blockly.inject(this.blocklyDiv.el, {
            toolbox: toolbox,
            collapse: true,
            comments: true,
            disable: true,
            maxBlocks: Infinity,
            trashcan: true,
            horizontalLayout: false,
            toolboxPosition: 'start',
            css: true,
            media: 'https://unpkg.com/blockly/media/',
            rtl: false,
            scrollbars: true,
            sounds: true,
            oneBasedIndex: true,
            grid: {
                spacing: 20,
                length: 1,
                colour: '#888',
                snap: true
            },
            zoom: {
                controls: true,
                wheel: true,
                startScale: 1.0,
                maxScale: 3,
                minScale: 0.3,
                scaleSpeed: 1.2
            }
        });

        // Listen for changes
        this.state.workspace.addChangeListener(this.onWorkspaceChange.bind(this));
    }

    onWorkspaceChange() {
        if (!this.state.workspace) return;
        
        try {
            // Generate code from blocks
            const code = window.Blockly.JavaScript.workspaceToCode(this.state.workspace);
            this.state.generatedCode = code;
            
            // Update preview
            this.updatePreview();
        } catch (error) {
            console.error("Error generating code from blocks:", error);
        }
    }

    updatePreview() {
        // Convert Blockly workspace to rule data
        const blocks = this.state.workspace.getAllBlocks();
        const ruleBlocks = blocks.filter(block => block.type === 'pricing_rule');
        
        if (ruleBlocks.length > 0) {
            const ruleBlock = ruleBlocks[0];
            const ruleData = this.extractRuleDataFromBlocks();
            
            this.state.previewRule = {
                name: ruleBlock.getFieldValue('RULE_NAME') || 'Untitled Rule',
                visual_config: window.Blockly.Xml.workspaceToDom(this.state.workspace),
                generated_code: this.state.generatedCode,
                condition_field: ruleData.condition_field,
                condition_operator: ruleData.condition_operator,
                condition_value: ruleData.condition_value,
                action_type: ruleData.action_type,
                action_value: ruleData.action_value,
            };
        }
    }

    extractRuleDataFromBlocks() {
        const blocks = this.state.workspace.getAllBlocks();
        const ruleBlocks = blocks.filter(block => block.type === 'pricing_rule');
        
        const ruleData = {
            condition_field: 'visual_condition',
            condition_operator: 'custom',
            condition_value: 'visual_rule',
            action_type: 'custom',
            action_value: 0,
        };

        if (ruleBlocks.length > 0) {
            const ruleBlock = ruleBlocks[0];
            
            // Extract condition from the rule block
            const conditionBlock = ruleBlock.getInputTargetBlock('CONDITION');
            if (conditionBlock && conditionBlock.type === 'pricing_condition') {
                ruleData.condition_field = conditionBlock.getFieldValue('FIELD') || 'visual_condition';
                ruleData.condition_operator = this.mapOperator(conditionBlock.getFieldValue('OPERATOR'));
                
                const valueBlock = conditionBlock.getInputTargetBlock('VALUE');
                if (valueBlock && valueBlock.type === 'number_value') {
                    ruleData.condition_value = valueBlock.getFieldValue('NUM') || '0';
                }
            }
            
            // Extract action from the rule block
            const actionBlock = ruleBlock.getInputTargetBlock('ACTIONS');
            if (actionBlock && actionBlock.type === 'pricing_action') {
                ruleData.action_type = this.mapActionType(actionBlock.getFieldValue('ACTION_TYPE'));
                
                const valueBlock = actionBlock.getInputTargetBlock('VALUE');
                if (valueBlock && valueBlock.type === 'number_value') {
                    ruleData.action_value = parseFloat(valueBlock.getFieldValue('NUM')) || 0;
                }
            }
        }

        return ruleData;
    }

    mapOperator(blocklyOperator) {
        const operatorMap = {
            '==': '=',
            '>': '>',
            '<': '<',
            '>=': '>=',
            '<=': '<=',
            '!=': '!='
        };
        return operatorMap[blocklyOperator] || '=';
    }

    mapActionType(blocklyAction) {
        const actionMap = {
            'add': 'add',
            'subtract': 'add', // Use negative value
            'multiply': 'multiply',
            'set': 'fixed',
            'percentage': 'percentage'
        };
        return actionMap[blocklyAction] || 'add';
    }

    loadExistingRule() {
        if (!this.props.ruleData.visual_config || !this.state.workspace) return;
        
        try {
            const xml = this.props.ruleData.visual_config;
            window.Blockly.Xml.domToWorkspace(xml, this.state.workspace);
        } catch (error) {
            console.error("Failed to load existing rule:", error);
        }
    }

    destroyBlockly() {
        if (this.state.workspace) {
            this.state.workspace.dispose();
            this.state.workspace = null;
        }
    }

    async saveRule() {
        if (!this.state.workspace) return;
        
        try {
            const workspaceXml = window.Blockly.Xml.workspaceToDom(this.state.workspace);
            const extractedData = this.extractRuleDataFromBlocks();
            
            const ruleData = {
                name: this.state.previewRule.name || 'Visual Rule',
                visual_config: new XMLSerializer().serializeToString(workspaceXml),
                generated_code: this.state.generatedCode,
                rule_type: 'visual',
                level: this.props.ruleData?.level || '1',
                active: true,
                condition_field: extractedData.condition_field,
                condition_operator: extractedData.condition_operator,
                condition_value: extractedData.condition_value,
                action_type: extractedData.action_type,
                action_value: extractedData.action_value,
            };

            // Handle subtract action with negative value
            if (extractedData.action_type === 'add' && this.getOriginalActionType() === 'subtract') {
                ruleData.action_value = -Math.abs(extractedData.action_value);
            }
            
            await this.props.onSave(ruleData);
            
            this.notification.add(_t("Visual rule saved successfully"), {
                type: "success",
            });
        } catch (error) {
            console.error("Failed to save rule:", error);
            this.notification.add(_t("Failed to save rule"), {
                type: "danger",
            });
        }
    }

    getOriginalActionType() {
        const blocks = this.state.workspace.getAllBlocks();
        const ruleBlocks = blocks.filter(block => block.type === 'pricing_rule');
        
        if (ruleBlocks.length > 0) {
            const actionBlock = ruleBlocks[0].getInputTargetBlock('ACTIONS');
            if (actionBlock && actionBlock.type === 'pricing_action') {
                return actionBlock.getFieldValue('ACTION_TYPE');
            }
        }
        return 'add';
    }

    clearWorkspace() {
        if (this.state.workspace) {
            this.state.workspace.clear();
        }
    }

    loadTemplate(templateName) {
        // Load predefined templates
        const templates = {
            distance_pricing: `
                <xml xmlns="https://developers.google.com/blockly/xml">
                    <block type="pricing_rule" x="20" y="20">
                        <field name="RULE_NAME">Distance Surcharge</field>
                        <value name="CONDITION">
                            <block type="pricing_condition">
                                <field name="FIELD">distance</field>
                                <field name="OPERATOR">&gt;</field>
                                <value name="VALUE">
                                    <block type="number_value">
                                        <field name="NUM">15</field>
                                    </block>
                                </value>
                            </block>
                        </value>
                        <statement name="ACTIONS">
                            <block type="pricing_action">
                                <field name="ACTION_TYPE">add</field>
                                <value name="VALUE">
                                    <block type="number_value">
                                        <field name="NUM">50</field>
                                    </block>
                                </value>
                            </block>
                        </statement>
                    </block>
                </xml>
            `,
            bulk_discount: `
                <xml xmlns="https://developers.google.com/blockly/xml">
                    <block type="pricing_rule" x="20" y="20">
                        <field name="RULE_NAME">Bulk Discount</field>
                        <value name="CONDITION">
                            <block type="pricing_condition">
                                <field name="FIELD">quantity</field>
                                <field name="OPERATOR">&gt;=</field>
                                <value name="VALUE">
                                    <block type="number_value">
                                        <field name="NUM">10</field>
                                    </block>
                                </value>
                            </block>
                        </value>
                        <statement name="ACTIONS">
                            <block type="pricing_action">
                                <field name="ACTION_TYPE">percentage</field>
                                <value name="VALUE">
                                    <block type="number_value">
                                        <field name="NUM">-10</field>
                                    </block>
                                </value>
                            </block>
                        </statement>
                    </block>
                </xml>
            `
        };

        if (templates[templateName] && this.state.workspace) {
            const xml = window.Blockly.Xml.textToDom(templates[templateName]);
            this.state.workspace.clear();
            window.Blockly.Xml.domToWorkspace(xml, this.state.workspace);
        }
    }
}

registry.category("components").add("VisualRuleBuilder", VisualRuleBuilder);