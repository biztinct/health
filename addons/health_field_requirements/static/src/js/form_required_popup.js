/** @odoo-module **/
/**
 * Missing Fields Popup + Visual Required Markers
 *
 *   A) Visual Markers — on form load, marks BOTH native required and
 *      admin-configured (Field Requirements) field labels red/bold.
 *
 *   B) Save Interceptor — on save, shows a popup dialog listing ALL
 *      unfilled mandatory fields before blocking the save.
 */
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { Record } from "@web/model/relational_model/record";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, onMounted, onPatched } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

// =========================================================================
// Dialog Component — shows the list of missing fields
// =========================================================================
export class MissingFieldsDialog extends Component {
    static template = "health_field_requirements.MissingFieldsDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        missingFields: Array,
        nativeCount: Number,
        configuredCount: Number,
    };
}

// =========================================================================
// Patch Record to suppress default notification when we handle it
// =========================================================================
patch(Record.prototype, {
    _displayInvalidFieldNotification() {
        if (this._suppressedByFieldReqDialog) {
            this._suppressedByFieldReqDialog = false;
            return () => {};
        }
        return super._displayInvalidFieldNotification(...arguments);
    },
});

// =========================================================================
// FormController patch
// =========================================================================
patch(FormController.prototype, {

    // -----------------------------------------------------------------
    // Setup — add lifecycle hooks for visual marking
    // -----------------------------------------------------------------
    setup() {
        super.setup(...arguments);

        // Cache for configured required fields
        this._configuredRequiredFields = [];
        this._configuredFieldsCacheKey = null;

        onMounted(async () => {
            await this._loadConfiguredRequiredFields();
            this._applyRequiredFieldStyles();
        });

        onPatched(async () => {
            // Re-fetch if model or state changed
            const record = this.model.root;
            if (record) {
                const stateVal = record.data?.state;
                const stateArg = (stateVal && typeof stateVal !== 'object') ? stateVal : '';
                const key = `${record.resModel}|${stateArg}`;
                if (key !== this._configuredFieldsCacheKey) {
                    await this._loadConfiguredRequiredFields();
                }
            }
            this._applyRequiredFieldStyles();
        });
    },

    // -----------------------------------------------------------------
    // Load configured required fields from the server (cached)
    // -----------------------------------------------------------------
    async _loadConfiguredRequiredFields() {
        const record = this.model.root;
        if (!record) return;

        const stateVal = record.data?.state;
        const stateArg = (stateVal && typeof stateVal !== 'object') ? stateVal : null;
        this._configuredFieldsCacheKey = `${record.resModel}|${stateArg || ''}`;

        try {
            this._configuredRequiredFields = await this.orm.call(
                'field.requirement.rule',
                'get_required_fields',
                [record.resModel, stateArg],
            );
        } catch {
            this._configuredRequiredFields = [];
        }
    },

    // -----------------------------------------------------------------
    // Visual Marking — apply red label + required border to fields
    // -----------------------------------------------------------------
    _applyRequiredFieldStyles() {
        const root = this.rootRef?.el;
        if (!root) return;

        const record = this.model.root;
        if (!record) return;

        // When NOT in edit mode, remove borders/input markers but KEEP labels red
        if (!record.isInEdition) {
            root.querySelectorAll('.o_fr_required_field').forEach(el =>
                el.classList.remove('o_fr_required_field', 'o_fr_admin_field'));
            root.querySelectorAll('.o_fr_required_input').forEach(el =>
                el.classList.remove('o_fr_required_input'));
            // Labels stay red in readonly — user confirmed this is desired
            return;
        }

        const configuredFields = new Set(this._configuredRequiredFields || []);

        // Process all field widgets in the form
        const allFieldWidgets = root.querySelectorAll('.o_field_widget[name]');
        for (const widget of allFieldWidgets) {
            const fieldName = widget.getAttribute('name');
            if (!fieldName) continue;

            const label = this._findLabelForField(root, fieldName, widget);
            const isNativeRequired = widget.classList.contains('o_required_modifier');
            const isConfiguredRequired = configuredFields.has(fieldName);

            if (isNativeRequired || isConfiguredRequired) {
                // Labels stay red ALWAYS for required fields
                if (label) {
                    label.classList.add('o_fr_required_label');
                    if (isConfiguredRequired && !isNativeRequired) {
                        label.classList.add('o_fr_admin_required');
                    }
                }

                // Check if field is empty — border only on empty fields
                const fieldDef = record.fields[fieldName];
                const isEmpty = fieldDef
                    ? this._isFieldEmptyForDialog(record, fieldName, fieldDef)
                    : false;

                if (isEmpty) {
                    // Empty required field — show red/purple left border
                    widget.classList.add('o_fr_required_field');
                    if (isConfiguredRequired && !isNativeRequired) {
                        widget.classList.add('o_required_modifier');
                        widget.classList.add('o_fr_admin_field');
                    }
                    // For header fields without labels, also color placeholder
                    if (!label) {
                        const input = widget.querySelector('input, select, textarea');
                        if (input) {
                            input.classList.add('o_fr_required_input');
                        }
                    }
                } else {
                    // Filled required field — remove border markers
                    widget.classList.remove('o_fr_required_field', 'o_fr_admin_field');
                    const input = widget.querySelector('input, select, textarea');
                    if (input) {
                        input.classList.remove('o_fr_required_input');
                    }
                }
            } else {
                // Field is not required — clean up everything
                if (label) {
                    label.classList.remove('o_fr_required_label', 'o_fr_admin_required');
                }
                widget.classList.remove('o_fr_required_field', 'o_fr_admin_field');
                const input = widget.querySelector('input, select, textarea');
                if (input) {
                    input.classList.remove('o_fr_required_input');
                }
            }
        }
    },

    // -----------------------------------------------------------------
    // Find the <label> element associated with a field widget
    // -----------------------------------------------------------------
    _findLabelForField(root, fieldName, fieldWidget) {
        // Strategy 1: Match label via input ID
        const input = fieldWidget.querySelector('input, select, textarea');
        if (input && input.id) {
            const label = root.querySelector(`label.o_form_label[for="${CSS.escape(input.id)}"]`);
            if (label) return label;
        }

        // Strategy 2: Parent container (inner_group grid layout)
        const wrapInput = fieldWidget.closest('.o_wrap_input');
        if (wrapInput) {
            const container = wrapInput.parentElement;
            if (container) {
                const wrapLabel = container.querySelector('.o_wrap_label');
                if (wrapLabel) {
                    const label = wrapLabel.querySelector('label.o_form_label');
                    if (label) return label;
                }
            }
        }

        // Strategy 3: Table-based layout (legacy)
        const td = fieldWidget.closest('td');
        if (td) {
            const tr = td.closest('tr');
            if (tr) {
                const labelTd = tr.querySelector('.o_td_label, td:first-child');
                if (labelTd) {
                    const label = labelTd.querySelector('label.o_form_label');
                    if (label) return label;
                }
            }
        }

        // Strategy 4: Adjacent sibling
        const cell = fieldWidget.closest('.o_cell');
        if (cell && cell.previousElementSibling) {
            const label = cell.previousElementSibling.querySelector('label.o_form_label');
            if (label) return label;
        }

        return null;
    },

    // -----------------------------------------------------------------
    // Save Interceptor — show popup for all missing required fields
    // -----------------------------------------------------------------
    async saveButtonClicked(params = {}) {
        const record = this.model.root;

        // Ensure configured fields are loaded
        if (!this._configuredFieldsCacheKey) {
            await this._loadConfiguredRequiredFields();
        }
        const configuredRequired = this._configuredRequiredFields || [];

        const missingFields = [];
        const seen = new Set();

        // ── Native required fields ──
        const activeFields = record.activeFields || {};
        for (const fieldName of Object.keys(activeFields)) {
            const fieldDef = record.fields[fieldName];
            if (!fieldDef) continue;

            try {
                if (record._isInvisible(fieldName)) continue;
                if (!record._isRequired(fieldName)) continue;
            } catch {
                continue;
            }

            if (this._isFieldEmptyForDialog(record, fieldName, fieldDef)) {
                missingFields.push({
                    name: fieldName,
                    label: fieldDef.string || fieldName,
                    type: fieldDef.type || '',
                    source: 'native',
                });
                seen.add(fieldName);
            }
        }

        // ── Configured required fields ──
        for (const fieldName of configuredRequired) {
            if (seen.has(fieldName)) continue;
            const fieldDef = record.fields[fieldName];
            if (!fieldDef) continue;

            try {
                if (fieldName in activeFields && record._isInvisible(fieldName)) continue;
            } catch { /* skip */ }

            if (this._isFieldEmptyForDialog(record, fieldName, fieldDef)) {
                missingFields.push({
                    name: fieldName,
                    label: fieldDef.string || fieldName,
                    type: fieldDef.type || '',
                    source: 'configured',
                });
            }
        }

        if (missingFields.length > 0) {
            const nativeCount = missingFields.filter(f => f.source === 'native').length;
            const configuredCount = missingFields.filter(f => f.source === 'configured').length;

            record._suppressedByFieldReqDialog = true;

            this.dialogService.add(MissingFieldsDialog, {
                missingFields,
                nativeCount,
                configuredCount,
            });

            return; // Block save
        }

        return super.saveButtonClicked(params);
    },

    // -----------------------------------------------------------------
    // Empty-value check
    // -----------------------------------------------------------------
    _isFieldEmptyForDialog(record, fieldName, fieldDef) {
        const value = record.data[fieldName];
        const type = fieldDef.type;

        if (type === 'boolean') return false;
        if (type === 'char' || type === 'text') {
            return !value || (typeof value === 'string' && !value.trim());
        }
        if (type === 'html') {
            if (!value) return true;
            return value.length === 0;
        }
        if (type === 'many2one') return !value;
        if (type === 'many2many' || type === 'one2many') {
            if (!value) return true;
            if (value.count !== undefined) return value.count === 0;
            if (value.records && Array.isArray(value.records)) return value.records.length === 0;
            if (Array.isArray(value)) return value.length === 0;
            return !value;
        }
        if (type === 'integer' || type === 'float' || type === 'monetary') return false;
        if (type === 'date' || type === 'datetime') return !value;
        if (type === 'selection') return !value && value !== 0;
        return !value;
    },
});
