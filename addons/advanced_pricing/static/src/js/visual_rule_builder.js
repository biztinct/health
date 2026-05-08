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

    t(text) {
        return _t(text);
    }

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
            console.log('🚀 Starting Blockly initialization...');
            
            // Wait for Blockly to be loaded
            await this.loadBlocklyLibrary();
            console.log('✅ Blockly library loaded');
            
            // Use setTimeout to ensure DOM is ready
            await new Promise(resolve => {
                setTimeout(resolve, 200); // Small delay for DOM rendering
            });
            
            console.log('✅ DOM should be ready, checking element...');
            console.log('blocklyDiv.el:', this.blocklyDiv.el);
            
            // Define custom blocks for pricing rules
            this.defineCustomBlocks();
            console.log('✅ Custom blocks defined');
            
            // Initialize workspace
            this.createWorkspace();
            console.log('✅ Workspace created');
            
            // Load existing rule if provided
            console.log('🔍 Checking for existing rule data:', this.props.ruleData);
            if (this.props.ruleData && this.props.ruleData.visual_config) {
                console.log('📥 Loading existing visual config:', this.props.ruleData.visual_config);
                this.loadExistingRule();
            } else {
                console.log('ℹ️ No existing rule data to load');
            }
            
            this.state.isLoading = false;
            console.log('✅ Blockly initialization complete!');
        } catch (error) {
            console.error("❌ Failed to initialize Blockly:", error);
            this.state.isLoading = false;
            this.notification.add(_t("Failed to load visual rule builder: " + error.message), {
                type: "danger",
            });
        }
    }

    async waitForElement() {
        // Wait for the DOM element to be available
        return new Promise((resolve, reject) => {
            let attempts = 0;
            const maxAttempts = 50; // 5 seconds max
            
            const checkElement = () => {
                attempts++;
                console.log(`Attempt ${attempts}: Checking for blocklyDiv.el`, this.blocklyDiv.el);
                
                if (this.blocklyDiv.el && document.contains(this.blocklyDiv.el)) {
                    console.log('✅ DOM element found and is in document');
                    resolve();
                } else if (attempts >= maxAttempts) {
                    console.error('❌ Timeout waiting for DOM element');
                    reject(new Error('Timeout waiting for DOM element'));
                } else {
                    setTimeout(checkElement, 100);
                }
            };
            checkElement();
        });
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

        // Define custom blocks using JavaScript API for better compatibility
        window.Blockly.Blocks['pricing_condition'] = {
            init: function() {
                this.appendDummyInput()
                    .appendField("If")
                    .appendField(new window.Blockly.FieldDropdown([
                        ["Order Total", "order_total"],
                        ["Quantity", "quantity"],
                        ["Customer Type", "customer_type"],
                        ["--- FSO Fields ---", "separator1"],
                        ["Distance (km)", "distance"],
                        ["Appointment Hour", "appointment_hour"],
                        ["Service Type", "service_type"],
                        ["Service Location", "service_location"],
                        ["Urgency Level", "urgency"],
                        ["Priority", "priority"],
                        ["Service Units", "service_units"],
                        ["Service City", "service_city"],
                        ["--- Time Conditions ---", "separator2"],
                        ["Is Weekend", "is_weekend"],
                        ["Is Holiday", "is_holiday"],
                        ["Is After Hours", "is_after_hours"]
                    ]), "FIELD")
                    .appendField(new window.Blockly.FieldDropdown([
                        ["equals", "=="],
                        ["greater than", ">"],
                        ["less than", "<"],
                        ["greater or equal", ">="],
                        ["less or equal", "<="],
                        ["not equal", "!="]
                    ]), "OPERATOR");
                this.appendValueInput("VALUE");
                this.setInputsInline(true);
                this.setOutput(true, "Boolean");
                this.setColour(210);
                this.setTooltip("Create a pricing condition");
                this.setMovable(true);
                this.setDeletable(true);
            }
        };

        window.Blockly.Blocks['pricing_action'] = {
            init: function() {
                this.appendDummyInput()
                    .appendField("Set price to")
                    .appendField(new window.Blockly.FieldDropdown([
                        ["Add Amount", "add"],
                        ["Multiply by Factor", "multiply"],
                        ["Apply Percentage", "percentage"],
                        ["Set Fixed Price", "fixed"],
                        ["Apply Formula", "formula"]
                    ]), "ACTION_TYPE");
                this.appendValueInput("VALUE");
                this.setInputsInline(true);
                this.setPreviousStatement(true, null);
                this.setNextStatement(true, null);
                this.setColour(160);
                this.setTooltip("Define a pricing action");
                this.setMovable(true);
                this.setDeletable(true);
            }
        };

        window.Blockly.Blocks['number_value'] = {
            init: function() {
                this.appendDummyInput()
                    .appendField(new window.Blockly.FieldNumber(0), "NUM");
                this.setOutput(true, "Number");
                this.setColour(230);
                this.setTooltip("A number value");
                this.setMovable(true);
                this.setDeletable(true);
            }
        };

        window.Blockly.Blocks['pricing_rule'] = {
            init: function() {
                this.appendDummyInput()
                    .appendField("Pricing Rule")
                    .appendField(new window.Blockly.FieldTextInput("New Rule"), "RULE_NAME");
                this.appendValueInput("CONDITION")
                    .setCheck("Boolean")
                    .appendField("When");
                this.appendStatementInput("ACTIONS")
                    .setCheck(null)
                    .appendField("Then");
                this.setColour(120);
                this.setTooltip("Create a complete pricing rule");
                this.setMovable(true);
                this.setDeletable(true);
            }
        };

        // Define JavaScript generators for the blocks
        const javascriptGenerator = window.Blockly.JavaScript || window.Blockly.generators?.javascript;
        
        if (javascriptGenerator) {
            javascriptGenerator.forBlock['pricing_condition'] = function(block) {
                const field = block.getFieldValue('FIELD');
                const operator = block.getFieldValue('OPERATOR');
                const value = javascriptGenerator.valueToCode(block, 'VALUE', javascriptGenerator.ORDER_ATOMIC);
                
                return [`${field} ${operator} ${value}`, javascriptGenerator.ORDER_RELATIONAL];
            };

            javascriptGenerator.forBlock['pricing_action'] = function(block) {
                const actionType = block.getFieldValue('ACTION_TYPE');
                const value = javascriptGenerator.valueToCode(block, 'VALUE', javascriptGenerator.ORDER_ATOMIC);
                
                return `apply_${actionType}(${value});\n`;
            };

            javascriptGenerator.forBlock['number_value'] = function(block) {
                const number = parseFloat(block.getFieldValue('NUM'));
                return [number, javascriptGenerator.ORDER_ATOMIC];
            };

            javascriptGenerator.forBlock['pricing_rule'] = function(block) {
                const ruleName = block.getFieldValue('RULE_NAME');
                const condition = javascriptGenerator.valueToCode(block, 'CONDITION', javascriptGenerator.ORDER_NONE);
                const actions = javascriptGenerator.statementToCode(block, 'ACTIONS');
                
                return `// Rule: ${ruleName}\nif (${condition}) {\n${actions}}\n`;
            };
        }
    }

    createWorkspace() {
        // Validate that element exists and is in DOM
        if (!this.blocklyDiv.el) {
            throw new Error('Blockly container element not found');
        }
        
        if (!document.contains(this.blocklyDiv.el)) {
            throw new Error('Blockly container is not in current document');
        }

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

        try {
            
            this.state.workspace = window.Blockly.inject(this.blocklyDiv.el, {
                toolbox: toolbox,
                collapse: true,
                comments: true,
                disable: false,
                maxBlocks: Infinity,
                trashcan: true,
                horizontalLayout: false,
                toolboxPosition: 'start',
                css: true,
                media: 'https://unpkg.com/blockly/media/',
                rtl: false,
                scrollbars: true,
                sounds: false,
                oneBasedIndex: true,
                move: {
                    scrollbars: true,
                    drag: true,
                    wheel: true
                },
                grid: {
                    spacing: 20,
                    length: 1,
                    colour: '#ccc',
                    snap: false
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
            
            // Workspace is ready for drag and drop
            
            console.log('Blockly workspace created successfully');
        } catch (error) {
            console.error('Failed to create Blockly workspace:', error);
            throw error;
        }
    }

    onWorkspaceChange() {
        if (!this.state.workspace) return;
        
        try {
            // Generate code from blocks using the correct generator
            const javascriptGenerator = window.Blockly.JavaScript || window.Blockly.generators?.javascript;
            const code = javascriptGenerator ? javascriptGenerator.workspaceToCode(this.state.workspace) : '';
            this.state.generatedCode = code;
            
            // Update preview
            this.updatePreview();
        } catch (error) {
            console.error("Error generating code from blocks:", error);
            this.state.generatedCode = '// Error generating code: ' + error.message;
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
        if (!this.props.ruleData?.visual_config || !this.state.workspace) {
            console.log('ℹ️ No existing rule data to load');
            return;
        }
        
        const config = this.props.ruleData.visual_config;
        console.log('🔧 Attempting to load existing rule...');
        
        // Clear workspace first
        this.state.workspace.clear();
        
        try {
            if (typeof config === 'string' && config.trim()) {
                if (config.trim().startsWith('{')) {
                    // JSON format - load directly (modern approach)
                    console.log('📦 Loading from JSON format');
                    this.loadFromJSON(config);
                } else {
                    // Legacy XML or other format - just skip loading to preserve drag-and-drop
                    console.log('⚠️ Legacy format detected - skipping load to preserve drag-and-drop functionality');
                    console.log('💡 Create a new rule and drag-and-drop will work perfectly!');
                }
            }
            
            // Update preview
            this.onWorkspaceChange();
            
        } catch (error) {
            console.error("❌ Failed to load existing rule:", error);
            // Don't call recovery methods that break drag-and-drop
            this.state.workspace.clear();
        }
    }


    loadFromJSON(jsonConfig) {
        try {
            const state = JSON.parse(jsonConfig);
            if (window.Blockly.serialization) {
                window.Blockly.serialization.workspaces.load(state, this.state.workspace);
                console.log('✅ Successfully loaded rule using JSON serialization');
            } else {
                throw new Error('JSON serialization not available');
            }
        } catch (error) {
            console.error('❌ JSON loading failed:', error);
            throw error;
        }
    }

    extractRuleInfoForPreview() {
        // Simple method to extract rule info from JSON workspace state
        try {
            const config = this.props.ruleData.visual_config;
            
            if (typeof config === 'string' && config.trim()) {
                if (config.startsWith('{')) {
                    // JSON format - parse the workspace state
                    const workspaceState = JSON.parse(config);
                    if (workspaceState.blocks && workspaceState.blocks.blocks) {
                        // Find the pricing rule block
                        const ruleBlock = workspaceState.blocks.blocks.find(block => block.type === 'pricing_rule');
                        if (ruleBlock && ruleBlock.fields) {
                            this.state.previewRule = {
                                name: ruleBlock.fields.RULE_NAME || 'Visual Rule',
                                generated_code: '// JSON format rule loaded successfully',
                                description: 'Modern JSON format - ready for editing'
                            };
                        }
                    }
                } else {
                    // Legacy format
                    this.state.previewRule = {
                        name: 'Legacy Rule',
                        generated_code: '// Legacy format - drag and drop will work for new rules',
                        description: 'Create a new rule to use visual builder'
                    };
                }
            }
        } catch (error) {
            console.log('Could not extract rule info, continuing with empty preview');
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
            // Use modern JSON serialization (Google's 2024 recommendation)
            let visualConfig;
            try {
                if (window.Blockly.serialization) {
                    // Save using JSON serialization
                    const state = window.Blockly.serialization.workspaces.save(this.state.workspace);
                    visualConfig = JSON.stringify(state);
                    console.log('✅ Saved using modern JSON serialization');
                } else {
                    throw new Error('JSON serialization not available');
                }
            } catch (jsonError) {
                console.warn('⚠️ JSON serialization failed, falling back to XML:', jsonError);
                // Fallback to XML serialization
                const workspaceXml = window.Blockly.Xml.workspaceToDom(this.state.workspace);
                visualConfig = new XMLSerializer().serializeToString(workspaceXml);
                console.log('📄 Saved using XML serialization (fallback)');
            }
            
            const extractedData = this.extractRuleDataFromBlocks();
            
            // Get default engine_id if not provided
            let engineId = this.props.ruleData?.engine_id;
            if (!engineId) {
                try {
                    const engines = await this.orm.searchRead('advanced.pricing.engine', [], ['id'], { limit: 1 });
                    engineId = engines.length > 0 ? engines[0].id : 1;
                } catch (error) {
                    console.warn('Could not fetch default engine, using ID 1:', error);
                    engineId = 1;
                }
            }
            
            const ruleData = {
                name: this.state.previewRule.name || 'Visual Rule',
                visual_config: visualConfig,
                generated_code: this.state.generatedCode,
                rule_type: 'visual',
                level: this.props.ruleData?.level || '1',
                active: true,
                condition_field: extractedData.condition_field,
                condition_operator: extractedData.condition_operator,
                condition_value: extractedData.condition_value,
                action_type: extractedData.action_type,
                action_value: extractedData.action_value,
                engine_id: engineId,
            };

            // Handle subtract action with negative value
            if (extractedData.action_type === 'add' && this.getOriginalActionType() === 'subtract') {
                ruleData.action_value = -Math.abs(extractedData.action_value);
            }
            
            await this.props.onSave(ruleData);
            
            // Success notification is handled by the parent component
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
            
            // Force workspace to resize after clearing
            setTimeout(() => {
                if (this.state.workspace) {
                    window.Blockly.svgResize(this.state.workspace);
                }
            }, 50);
        }
    }

    backToRulesList() {
        // Call the parent's back to rules list method
        if (this.props.onBackToRulesList) {
            this.props.onBackToRulesList();
        } else {
            // Fallback: use cancel
            this.props.onCancel();
        }
    }

    loadTemplate(templateName) {
        if (!this.state.workspace) return;

        try {
            // Clear workspace first
            this.state.workspace.clear();

            // Use Blockly's recommended approach: XML workspace state
            const templates = {
                distance_pricing: `
                    <xml xmlns="https://developers.google.com/blockly/xml">
                        <block type="pricing_rule" x="20" y="20">
                            <field name="RULE_NAME">Distance Surcharge</field>
                        </block>
                        <block type="pricing_condition" x="20" y="120">
                            <field name="FIELD">distance</field>
                            <field name="OPERATOR">&gt;</field>
                        </block>
                        <block type="number_value" x="300" y="120">
                            <field name="NUM">15</field>
                        </block>
                        <block type="pricing_action" x="20" y="220">
                            <field name="ACTION_TYPE">add</field>
                        </block>
                        <block type="number_value" x="300" y="220">
                            <field name="NUM">50</field>
                        </block>
                    </xml>
                `,
                bulk_discount: `
                    <xml xmlns="https://developers.google.com/blockly/xml">
                        <block type="pricing_rule" x="20" y="20">
                            <field name="RULE_NAME">Bulk Discount</field>
                        </block>
                        <block type="pricing_condition" x="20" y="120">
                            <field name="FIELD">quantity</field>
                            <field name="OPERATOR">&gt;=</field>
                        </block>
                        <block type="number_value" x="300" y="120">
                            <field name="NUM">10</field>
                        </block>
                        <block type="pricing_action" x="20" y="220">
                            <field name="ACTION_TYPE">percentage</field>
                        </block>
                        <block type="number_value" x="300" y="220">
                            <field name="NUM">-10</field>
                        </block>
                    </xml>
                `
            };

            if (templates[templateName]) {
                console.log(`🔧 DEBUG: Loading template ${templateName}`);
                console.log(`🔧 DEBUG: Template XML:`, templates[templateName]);
                
                // Use DOMParser to parse XML (browser native, no Blockly dependencies)
                const parser = new DOMParser();
                const xmlDoc = parser.parseFromString(templates[templateName], "text/xml");
                
                console.log(`🔧 DEBUG: Parsed XML document:`, xmlDoc);
                console.log(`🔧 DEBUG: XML documentElement:`, xmlDoc.documentElement);
                console.log(`🔧 DEBUG: Workspace before loading:`, this.state.workspace);
                console.log(`🔧 DEBUG: Number of blocks before loading:`, this.state.workspace.getAllBlocks().length);
                
                // Clear workspace first to avoid conflicts
                this.state.workspace.clear();
                
                // Load blocks one by one to maintain interactivity
                const blocks = xmlDoc.documentElement.children;
                for (let i = 0; i < blocks.length; i++) {
                    const blockElement = blocks[i];
                    if (blockElement.tagName === 'block') {
                        this.createInteractiveBlock(blockElement);
                    }
                }
                
                console.log(`🔧 DEBUG: Number of blocks after loading:`, this.state.workspace.getAllBlocks().length);
                console.log(`🔧 DEBUG: All blocks:`, this.state.workspace.getAllBlocks());
                
                // Force workspace to render and resize
                this.state.workspace.render();
                this.state.workspace.resizeContents();
                
                // Debug workspace visibility
                console.log(`🔧 DEBUG: Container width: ${this.blocklyDiv.el.offsetWidth}px`);
                console.log(`🔧 DEBUG: Container height: ${this.blocklyDiv.el.offsetHeight}px`);
                console.log(`🔧 DEBUG: Container visible: ${this.blocklyDiv.el.offsetParent !== null}`);
                
                // Debug SVG elements
                const svgElement = this.blocklyDiv.el.querySelector('svg');
                if (svgElement) {
                    console.log(`🔧 DEBUG: SVG width: ${svgElement.getAttribute('width')}`);
                    console.log(`🔧 DEBUG: SVG height: ${svgElement.getAttribute('height')}`);
                    console.log(`🔧 DEBUG: SVG viewBox: ${svgElement.getAttribute('viewBox')}`);
                } else {
                    console.log(`🔧 DEBUG: No SVG element found!`);
                }
                
                // Debug block positions and visibility
                this.state.workspace.getAllBlocks().forEach((block, index) => {
                    const position = block.getRelativeToSurfaceXY();
                    console.log(`🔧 DEBUG: Block ${index} (${block.type}): x=${position.x}, y=${position.y}, rendered=${block.rendered}`);
                });
                
                // Force a resize to make sure everything is visible
                setTimeout(() => {
                    // Force container to have proper height
                    this.blocklyDiv.el.style.height = '600px';
                    this.blocklyDiv.el.style.minHeight = '600px';
                    
                    // Just re-render blocks for proper interaction
                    this.state.workspace.getAllBlocks().forEach(block => {
                        // Only re-render, don't re-initialize to avoid conflicts
                        if (block.render) {
                            block.render();
                        }
                    });
                    
                    // Trigger Blockly resize
                    window.Blockly.svgResize(this.state.workspace);
                    this.state.workspace.resizeContents();
                    this.state.workspace.render();
                    
                    // Clear any focus issues
                    try {
                        this.state.workspace.getFlyout()?.hide();
                    } catch (e) {
                        console.log('No flyout to hide');
                    }
                    
                    console.log(`🔧 DEBUG: After forced resize - Container height: ${this.blocklyDiv.el.offsetHeight}px`);
                    console.log(`🔧 DEBUG: Blocks configured for dragging`);
                    
                    const svgElement = this.blocklyDiv.el.querySelector('svg');
                    if (svgElement) {
                        console.log(`🔧 DEBUG: After resize - SVG height: ${svgElement.getAttribute('height')}`);
                    }
                }, 100);
                
                console.log(`✅ Template ${templateName} loaded successfully`);
            }

        } catch (error) {
            console.error('Failed to load template:', error);
            this.notification.add(_t("Failed to load template: " + error.message), {
                type: "danger",
            });
        }
    }

    /**
     * Create a block from XML element while maintaining full interactivity
     * This method parses XML block elements and creates them using the JavaScript API
     * to ensure they maintain the same interactivity as blocks dragged from the toolbox
     */
    createInteractiveBlock(blockElement) {
        try {
            const blockType = blockElement.getAttribute('type');
            const x = parseInt(blockElement.getAttribute('x')) || 0;
            const y = parseInt(blockElement.getAttribute('y')) || 0;
            
            console.log(`🔧 Creating interactive block: ${blockType} at (${x}, ${y})`);
            
            // Create the block using the JavaScript API
            const block = this.state.workspace.newBlock(blockType);
            
            // Initialize SVG first before positioning
            block.initSvg();
            
            // Set position after SVG initialization but before render
            if (x !== 0 || y !== 0) {
                block.moveBy(x, y);
            }
            
            // Parse and set field values
            const fields = blockElement.querySelectorAll('field');
            fields.forEach(field => {
                const fieldName = field.getAttribute('name');
                const fieldValue = field.textContent;
                
                console.log(`🔧 Setting field ${fieldName} = ${fieldValue}`);
                
                if (block.getField(fieldName)) {
                    block.setFieldValue(fieldValue, fieldName);
                }
            });
            
            // Parse and set values for value inputs
            const values = blockElement.querySelectorAll('value');
            values.forEach(value => {
                const valueName = value.getAttribute('name');
                const childBlock = value.querySelector('block');
                
                if (childBlock) {
                    console.log(`🔧 Creating child block for value input: ${valueName}`);
                    
                    // Recursively create child blocks
                    const childBlockObj = this.createInteractiveBlock(childBlock);
                    if (childBlockObj && block.getInput(valueName)) {
                        block.getInput(valueName).connection.connect(childBlockObj.outputConnection);
                    }
                }
            });
            
            // Parse and set statement connections
            const statements = blockElement.querySelectorAll('statement');
            statements.forEach(statement => {
                const statementName = statement.getAttribute('name');
                const childBlock = statement.querySelector('block');
                
                if (childBlock) {
                    console.log(`🔧 Creating child block for statement: ${statementName}`);
                    
                    // Recursively create child blocks
                    const childBlockObj = this.createInteractiveBlock(childBlock);
                    if (childBlockObj && block.getInput(statementName)) {
                        block.getInput(statementName).connection.connect(childBlockObj.previousConnection);
                    }
                }
            });
            
            // Parse next blocks in sequence
            const nextBlock = blockElement.querySelector(':scope > next > block');
            if (nextBlock) {
                console.log(`🔧 Creating next block in sequence`);
                const nextBlockObj = this.createInteractiveBlock(nextBlock);
                if (nextBlockObj && block.nextConnection) {
                    block.nextConnection.connect(nextBlockObj.previousConnection);
                }
            }
            
            // Render the block after all connections are made
            block.render();
            
            // Ensure block is movable and deletable (should be default, but ensure)
            block.setMovable(true);
            block.setDeletable(true);
            block.setEditable(true);
            
            console.log(`✅ Successfully created interactive block: ${blockType}`);
            
            return block;
            
        } catch (error) {
            console.error(`❌ Failed to create interactive block:`, error);
            console.error(`Block element:`, blockElement);
            return null;
        }
    }


}

registry.category("components").add("VisualRuleBuilder", VisualRuleBuilder);
