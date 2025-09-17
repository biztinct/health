/** @odoo-module alias=biz_analytics.DashboardController **/

import { Component, useRef, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { Layout } from "@web/search/layout";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { _t } from "@web/core/l10n/translation";
import { standardViewProps } from "@web/views/standard_view_props";
import { useModel } from "@web/model/model";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";

export class DashboardController extends Component {
    
    setup() {
        this.rootRef = useRef("root");
        this.model = useModel(this.props.Model, this.props.modelParams);
        useSetupAction({ rootRef: this.rootRef });
        
        // Services
        this.dialogService = useService("dialog");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        
        // Component state
        this.state = useState({
            editMode: false,
            selectedWidget: null,
            draggedWidget: null,
            showFieldSelector: false,
            showFilterPanel: false,
            autoRefreshEnabled: true,
        });
        
        // Auto-refresh setup
        this.refreshInterval = null;
        
        onMounted(() => {
            this._setupAutoRefresh();
            this._setupKeyboardShortcuts();
        });
        
        onWillUnmount(() => {
            this._clearAutoRefresh();
            this._removeKeyboardShortcuts();
        });
    }

    get rendererProps() {
        return {
            model: this.model,
            editMode: this.state.editMode,
            selectedWidget: this.state.selectedWidget,
            onWidgetSelect: this._onWidgetSelect.bind(this),
            onWidgetMove: this._onWidgetMove.bind(this),
            onWidgetResize: this._onWidgetResize.bind(this),
            onWidgetClick: this._onWidgetClick.bind(this),
            onWidgetDoubleClick: this._onWidgetDoubleClick.bind(this),
            onWidgetDelete: this._onWidgetDelete.bind(this),
            onAddWidget: this._onAddWidget.bind(this),
            onFilterChange: this._onFilterChange.bind(this),
        };
    }

    // ===================
    // Dashboard Actions
    // ===================

    async toggleEditMode() {
        this.state.editMode = !this.state.editMode;
        this.model.setEditMode(this.state.editMode);
        
        if (this.state.editMode) {
            this.notification.add(_t("Edit mode enabled"), { type: 'info' });
        } else {
            this.notification.add(_t("Edit mode disabled"), { type: 'info' });
        }
    }

    async refreshDashboard() {
        try {
            await this.model.refreshDashboard();
            this.notification.add(_t("Dashboard refreshed"), { type: 'success' });
        } catch (error) {
            this.notification.add(_t("Error refreshing dashboard"), { type: 'danger' });
        }
    }

    async exportDashboard() {
        // TODO: Implement dashboard export
        this.notification.add(_t("Export feature coming soon"), { type: 'info' });
    }

    async shareDashboard() {
        // TODO: Implement dashboard sharing
        this.notification.add(_t("Sharing feature coming soon"), { type: 'info' });
    }

    async openDashboardSettings() {
        const dashboardData = this.model.getDashboardData();
        
        this.dialogService.add(FormViewDialog, {
            resModel: 'analytics.dashboard',
            resId: dashboardData.id,
            title: _t("Dashboard Settings"),
            onRecordSaved: async () => {
                await this.model.refreshDashboard();
                this.render();
            }
        });
    }

    // ===================
    // Widget Actions
    // ===================

    _onWidgetSelect(widgetId) {
        this.state.selectedWidget = widgetId;
        this.model.selectWidget(widgetId);
    }

    async _onWidgetMove(widgetId, x, y, width, height) {
        await this.model.updateWidgetPosition(widgetId, x, y, width, height);
    }

    async _onWidgetResize(widgetId, width, height) {
        const widget = this.model.getWidgetData(widgetId);
        if (widget) {
            await this.model.updateWidgetPosition(widgetId, widget.position_x, widget.position_y, width, height);
        }
    }

    _onWidgetClick(widgetId, event) {
        if (!this.state.editMode) {
            // Handle chart interactions (drill-down, etc.)
            this._handleChartInteraction(widgetId, event);
        }
    }

    _onWidgetDoubleClick(widgetId) {
        if (this.state.editMode) {
            this._openWidgetEditor(widgetId);
        }
    }

    async _onWidgetDelete(widgetId) {
        this.dialogService.add(ConfirmationDialog, {
            title: _t("Delete Widget"),
            body: _t("Are you sure you want to delete this widget?"),
            confirmLabel: _t("Delete"),
            cancelLabel: _t("Cancel"),
            confirm: async () => {
                await this.model.deleteWidget(widgetId);
                this.notification.add(_t("Widget deleted"), { type: 'success' });
            }
        });
    }

    _onAddWidget() {
        if (!this.state.editMode) {
            this.toggleEditMode();
        }
        this.state.showFieldSelector = true;
    }

    async _onFilterChange(filterName, value) {
        await this.model.updateFilter(filterName, value);
    }

    // ===================
    // Widget Management
    // ===================

    _openWidgetEditor(widgetId) {
        this.dialogService.add(FormViewDialog, {
            resModel: 'analytics.widget',
            resId: widgetId,
            title: _t("Edit Widget"),
            onRecordSaved: async () => {
                await this.model.refreshWidget(widgetId);
                this.render();
            }
        });
    }

    async createWidget(widgetConfig) {
        try {
            const result = await this.model.createWidget(widgetConfig);
            if (result) {
                this.notification.add(_t("Widget created successfully"), { type: 'success' });
                this.state.showFieldSelector = false;
            }
        } catch (error) {
            this.notification.add(_t("Error creating widget"), { type: 'danger' });
        }
    }

    _handleChartInteraction(widgetId, event) {
        const widget = this.model.getWidgetData(widgetId);
        if (!widget || !widget.clickable) return;
        
        // Handle drill-down or navigation based on chart data
        console.log('Chart interaction:', widgetId, event);
        // TODO: Implement chart interaction logic
    }

    // ===================
    // Field Selector
    // ===================

    toggleFieldSelector() {
        this.state.showFieldSelector = !this.state.showFieldSelector;
    }

    closeFieldSelector() {
        this.state.showFieldSelector = false;
    }

    // ===================
    // Filter Panel
    // ===================

    toggleFilterPanel() {
        this.state.showFilterPanel = !this.state.showFilterPanel;
    }

    closeFilterPanel() {
        this.state.showFilterPanel = false;
    }

    // ===================
    // Auto Refresh
    // ===================

    _setupAutoRefresh() {
        const dashboardData = this.model.getDashboardData();
        if (dashboardData.auto_refresh && dashboardData.refresh_interval) {
            this.refreshInterval = setInterval(() => {
                if (this.state.autoRefreshEnabled) {
                    this.model.refreshDashboard();
                }
            }, dashboardData.refresh_interval * 60 * 1000);
        }
    }

    _clearAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    toggleAutoRefresh() {
        this.state.autoRefreshEnabled = !this.state.autoRefreshEnabled;
        
        if (this.state.autoRefreshEnabled) {
            this._setupAutoRefresh();
            this.notification.add(_t("Auto-refresh enabled"), { type: 'info' });
        } else {
            this._clearAutoRefresh();
            this.notification.add(_t("Auto-refresh disabled"), { type: 'info' });
        }
    }

    // ===================
    // Keyboard Shortcuts
    // ===================

    _setupKeyboardShortcuts() {
        document.addEventListener('keydown', this._handleKeydown.bind(this));
    }

    _removeKeyboardShortcuts() {
        document.removeEventListener('keydown', this._handleKeydown.bind(this));
    }

    _handleKeydown(event) {
        if (event.ctrlKey || event.metaKey) {
            switch (event.key) {
                case 'e':
                    event.preventDefault();
                    this.toggleEditMode();
                    break;
                case 'r':
                    event.preventDefault();
                    this.refreshDashboard();
                    break;
                case 'f':
                    event.preventDefault();
                    this.toggleFilterPanel();
                    break;
                case 'n':
                    if (this.state.editMode) {
                        event.preventDefault();
                        this._onAddWidget();
                    }
                    break;
            }
        }
        
        if (event.key === 'Escape') {
            if (this.state.showFieldSelector) {
                this.closeFieldSelector();
            } else if (this.state.showFilterPanel) {
                this.closeFilterPanel();
            } else if (this.state.selectedWidget) {
                this.state.selectedWidget = null;
            }
        }
    }

    // ===================
    // Utility Methods
    // ===================

    getDashboardTitle() {
        const dashboardData = this.model.getDashboardData();
        return dashboardData.name || _t("Analytics Dashboard");
    }

    getWidgetCount() {
        return this.model.getAllWidgets().length;
    }

    canAddWidget() {
        return this.state.editMode && Object.keys(this.model.getDatasets()).length > 0;
    }
}

DashboardController.template = "biz_analytics.DashboardView";
DashboardController.components = { Layout, SearchBar };
DashboardController.props = {
    ...standardViewProps,
    Model: Function,
    modelParams: Object,
    Renderer: Function,
};