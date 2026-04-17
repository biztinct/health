/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Field Requirements Dashboard — 4-Layer Drill-down
 *
 * Phase 1 (nodes):   Primary circles (CRM, Bookings, Finance, Admin)
 * Phase 2 (tiles):   Tiles within the selected node
 * Phase 3 (models):  Models used by the selected tile
 * Phase 4 (fields):  Form view fields of the selected model
 */
class FieldRequirementsDashboard extends Component {
    static template = "health_field_requirements.Dashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            phase: 'nodes',      // nodes | tiles | models | fields
            loading: true,

            // Hierarchy data
            hierarchy: [],

            // Navigation state
            selectedNode: null,
            selectedTile: null,
            selectedModel: null,

            // Field detail state
            fieldsData: [],
            availableRoles: [],
            fieldsLoading: false,
            searchQuery: '',
            savingField: null,
        });

        onWillStart(async () => {
            await this.loadHierarchy();
        });
    }

    // =========================================================================
    // DATA
    // =========================================================================

    async loadHierarchy() {
        this.state.loading = true;
        try {
            this.state.hierarchy = await this.orm.call(
                'field.requirement.rule', 'get_hierarchy', []
            );
        } catch (error) {
            console.error('[FieldReq] Failed to load hierarchy:', error);
            this.notification.add(_t("Failed to load hierarchy"), { type: 'danger' });
        }
        this.state.loading = false;
    }

    async loadFieldsForModel(modelData) {
        this.state.fieldsLoading = true;
        this.state.selectedModel = modelData;
        this.state.phase = 'fields';
        this.state.searchQuery = '';
        try {
            const result = await this.orm.call(
                'field.requirement.rule', 'get_model_fields_config', [modelData.model]
            );
            this.state.fieldsData = result.fields || [];
            this.state.availableRoles = result.roles || [];
        } catch (error) {
            console.error('[FieldReq] Failed to load fields:', error);
            this.notification.add(_t("Failed to load fields"), { type: 'danger' });
        }
        this.state.fieldsLoading = false;
    }

    // =========================================================================
    // NAVIGATION
    // =========================================================================

    /** Breadcrumb: all the way back */
    goToNodes() {
        this.state.phase = 'nodes';
        this.state.selectedNode = null;
        this.state.selectedTile = null;
        this.state.selectedModel = null;
        this.state.fieldsData = [];
        this.state.searchQuery = '';
        this.loadHierarchy();
    }

    /** Breadcrumb: back to tiles for current node */
    goToTiles() {
        this.state.phase = 'tiles';
        this.state.selectedTile = null;
        this.state.selectedModel = null;
        this.state.fieldsData = [];
        this.state.searchQuery = '';
    }

    /** Breadcrumb: back to models for current tile */
    goToModels() {
        this.state.phase = 'models';
        this.state.selectedModel = null;
        this.state.fieldsData = [];
        this.state.searchQuery = '';
    }

    // =========================================================================
    // CLICK HANDLERS
    // =========================================================================

    onNodeClick(node) {
        this.state.selectedNode = node;
        this.state.phase = 'tiles';
    }

    onTileClick(tile) {
        this.state.selectedTile = tile;
        // If tile has exactly 1 model, skip to fields directly
        if (tile.models && tile.models.length === 1) {
            this.loadFieldsForModel(tile.models[0]);
        } else {
            this.state.phase = 'models';
        }
    }

    onModelClick(model) {
        this.loadFieldsForModel(model);
    }

    // =========================================================================
    // BREADCRUMB
    // =========================================================================

    get breadcrumbs() {
        const crumbs = [];
        crumbs.push({ label: 'Field Requirements', phase: 'nodes' });
        if (this.state.selectedNode) {
            crumbs.push({
                label: this.state.selectedNode.name,
                phase: 'tiles',
                color: this.state.selectedNode.color,
            });
        }
        if (this.state.selectedTile) {
            crumbs.push({ label: this.state.selectedTile.name, phase: 'models' });
        }
        if (this.state.selectedModel) {
            crumbs.push({ label: this.state.selectedModel.name, phase: 'fields' });
        }
        return crumbs;
    }

    onBreadcrumbClick(crumb) {
        if (crumb.phase === 'nodes') this.goToNodes();
        else if (crumb.phase === 'tiles') this.goToTiles();
        else if (crumb.phase === 'models') this.goToModels();
    }

    // =========================================================================
    // FIELD ACTIONS (same as before)
    // =========================================================================

    get filteredFields() {
        const query = (this.state.searchQuery || '').toLowerCase();
        if (!query) return this.state.fieldsData;
        return this.state.fieldsData.filter(f =>
            (f.field_label || '').toLowerCase().includes(query) ||
            (f.field_name || '').toLowerCase().includes(query)
        );
    }

    onSearchInput(ev) { this.state.searchQuery = ev.target.value; }

    async onToggleActive(field) {
        field.active = !field.active;
        if (field.active && !field.has_rule) {
            await this.saveFieldRule(field);
        } else if (field.has_rule) {
            await this.saveFieldRule(field);
        }
    }

    async onToggleGlobal(field) {
        field.is_global = !field.is_global;
        if (field.is_global) { field.role_ids = []; field.role_names = ''; }
        if (field.has_rule || field.active) await this.saveFieldRule(field);
    }

    async onStateValuesChange(field, ev) { field.state_values = ev.target.value; }
    async onStateValuesBlur(field) {
        if (field.has_rule || field.active) await this.saveFieldRule(field);
    }

    async onRoleToggle(field, roleId) {
        const idx = field.role_ids.indexOf(roleId);
        if (idx > -1) field.role_ids.splice(idx, 1);
        else field.role_ids.push(roleId);
        const selectedRoles = this.state.availableRoles.filter(r => field.role_ids.includes(r.id));
        field.role_names = selectedRoles.map(r => r.name).join(', ');
        if (field.has_rule || field.active) await this.saveFieldRule(field);
    }

    isRoleSelected(field, roleId) { return (field.role_ids || []).includes(roleId); }

    async saveFieldRule(field) {
        this.state.savingField = field.field_name;
        try {
            const result = await this.orm.call('field.requirement.rule', 'save_field_rule', [{
                rule_id: field.rule_id || false,
                model_id: field.model_id,
                field_id: field.field_id,
                is_global: field.is_global,
                role_ids: field.role_ids || [],
                state_values: field.state_values || '',
                active: field.active,
            }]);
            field.rule_id = result.rule_id;
            field.has_rule = true;
        } catch (error) {
            console.error('[FieldReq] Failed to save rule:', error);
            this.notification.add(_t("Failed to save rule"), { type: 'danger' });
        }
        this.state.savingField = null;
    }

    async onDeleteRule(field) {
        if (!field.rule_id) return;
        try {
            await this.orm.call('field.requirement.rule', 'delete_field_rule', [field.rule_id]);
            field.rule_id = false; field.has_rule = false; field.active = false;
            field.is_global = true; field.role_ids = []; field.role_names = '';
            field.state_values = '';
            this.notification.add(_t("Rule removed"), { type: 'success' });
        } catch (error) {
            console.error('[FieldReq] Failed to delete rule:', error);
            this.notification.add(_t("Failed to delete rule"), { type: 'danger' });
        }
    }

    getActiveRuleCount() { return this.state.fieldsData.filter(f => f.active).length; }
    getTotalFieldCount() { return this.state.fieldsData.length; }
}

registry.category("actions").add("field_requirements_dashboard", FieldRequirementsDashboard);
