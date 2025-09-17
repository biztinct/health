/** @odoo-module **/

import { KeepLast } from "@web/core/utils/concurrency";
import { Model } from "@web/model/model";

export class DashboardModel extends Model {
    
    setup(params, { orm, user, dialog, notification }) {
        this.orm = orm;
        this.user = user;
        this.dialog = dialog;
        this.notification = notification;
        this.keepLast = new KeepLast();
        
        // Dashboard configuration
        this.dashboardId = params.dashboardId;
        this.resModel = params.resModel || 'analytics.dashboard';
        this.fields = params.fields;
        
        // Dashboard state
        this.dashboardData = {};
        this.widgetData = {};
        this.datasets = {};
        this.filters = {};
        
        // UI state
        this.isLoading = false;
        this.editMode = false;
        this.selectedWidget = null;
    }

    async load(params = {}) {
        this.isLoading = true;
        
        try {
            // Load dashboard configuration
            if (this.dashboardId) {
                await this._loadDashboard(this.dashboardId);
            } else {
                await this._loadDefaultDashboard();
            }
            
            // Load widget data
            await this._loadWidgetData();
            
            // Load available datasets
            await this._loadDatasets();
            
        } catch (error) {
            console.error('Error loading dashboard:', error);
            this.notification.add('Error loading dashboard', { type: 'danger' });
        } finally {
            this.isLoading = false;
        }
    }

    async _loadDashboard(dashboardId) {
        const result = await this.orm.read('analytics.dashboard', [dashboardId], [
            'name', 'description', 'layout_type', 'columns', 'theme',
            'background_color', 'accent_color', 'dashboard_data',
            'filter_data', 'auto_refresh', 'refresh_interval'
        ]);
        
        if (result.length > 0) {
            this.dashboardData = result[0];
            this.filters = JSON.parse(this.dashboardData.filter_data || '{}');
        }
    }

    async _loadDefaultDashboard() {
        // Load user's default dashboard or create sample
        const result = await this.orm.call('analytics.dashboard', 'get_user_dashboards', []);
        
        if (result.length > 0) {
            this.dashboardId = result[0].id;
            await this._loadDashboard(this.dashboardId);
        } else {
            // Create default dashboard structure
            this.dashboardData = {
                name: 'My Dashboard',
                layout_type: 'grid',
                columns: 4,
                theme: 'light',
                background_color: '#ffffff',
                accent_color: '#875A7B'
            };
        }
    }

    async _loadWidgetData() {
        if (!this.dashboardId) return;
        
        const widgets = await this.orm.search_read('analytics.widget', 
            [['dashboard_id', '=', this.dashboardId], ['active', '=', true]], 
            ['name', 'widget_type', 'chart_type', 'position_x', 'position_y', 
             'width', 'height', 'dataset_id', 'widget_data', 'chart_config']
        );
        
        this.widgetData = {};
        for (const widget of widgets) {
            this.widgetData[widget.id] = {
                ...widget,
                data: JSON.parse(widget.widget_data || '{"labels": [], "datasets": []}'),
                config: JSON.parse(widget.chart_config || '{}')
            };
        }
    }

    async _loadDatasets() {
        const datasets = await this.orm.search_read('analytics.dataset',
            [['active', '=', true]],
            ['name', 'description', 'model_name', 'dataset_metadata']
        );
        
        this.datasets = {};
        for (const dataset of datasets) {
            this.datasets[dataset.id] = {
                ...dataset,
                metadata: JSON.parse(dataset.dataset_metadata || '{}')
            };
        }
    }

    async refreshWidget(widgetId) {
        try {
            // Call widget refresh method
            await this.orm.call('analytics.widget', 'action_refresh_data', [[widgetId]]);
            
            // Reload widget data
            const widget = await this.orm.read('analytics.widget', [widgetId], 
                ['widget_data', 'chart_config']);
                
            if (widget.length > 0) {
                this.widgetData[widgetId].data = JSON.parse(widget[0].widget_data || '{}');
                this.widgetData[widgetId].config = JSON.parse(widget[0].chart_config || '{}');
            }
            
            this.notify();
        } catch (error) {
            console.error('Error refreshing widget:', error);
            this.notification.add('Error refreshing widget', { type: 'danger' });
        }
    }

    async refreshDashboard() {
        await this.load();
    }

    async updateWidgetPosition(widgetId, x, y, width, height) {
        try {
            await this.orm.write('analytics.widget', [widgetId], {
                position_x: x,
                position_y: y,
                width: width,
                height: height
            });
            
            // Update local data
            if (this.widgetData[widgetId]) {
                this.widgetData[widgetId].position_x = x;
                this.widgetData[widgetId].position_y = y;
                this.widgetData[widgetId].width = width;
                this.widgetData[widgetId].height = height;
            }
            
        } catch (error) {
            console.error('Error updating widget position:', error);
        }
    }

    async createWidget(widgetConfig) {
        try {
            const result = await this.orm.create('analytics.widget', [{
                name: widgetConfig.name || 'New Widget',
                dashboard_id: this.dashboardId,
                dataset_id: widgetConfig.datasetId,
                widget_type: widgetConfig.type || 'chart',
                chart_type: widgetConfig.chartType || 'bar',
                position_x: widgetConfig.x || 0,
                position_y: widgetConfig.y || 0,
                width: widgetConfig.width || 6,
                height: widgetConfig.height || 4,
            }]);
            
            // Reload widget data
            await this._loadWidgetData();
            this.notify();
            
            return result;
        } catch (error) {
            console.error('Error creating widget:', error);
            this.notification.add('Error creating widget', { type: 'danger' });
        }
    }

    async deleteWidget(widgetId) {
        try {
            await this.orm.unlink('analytics.widget', [widgetId]);
            delete this.widgetData[widgetId];
            this.notify();
        } catch (error) {
            console.error('Error deleting widget:', error);
            this.notification.add('Error deleting widget', { type: 'danger' });
        }
    }

    async updateFilter(filterName, value) {
        this.filters[filterName] = value;
        
        // Apply filters to all widgets
        for (const widgetId in this.widgetData) {
            await this.refreshWidget(widgetId);
        }
    }

    getDashboardData() {
        return this.dashboardData;
    }

    getWidgetData(widgetId) {
        return this.widgetData[widgetId] || null;
    }

    getAllWidgets() {
        return Object.values(this.widgetData);
    }

    getDatasets() {
        return this.datasets;
    }

    getFilters() {
        return this.filters;
    }

    setEditMode(enabled) {
        this.editMode = enabled;
        this.notify();
    }

    isEditModeEnabled() {
        return this.editMode;
    }

    selectWidget(widgetId) {
        this.selectedWidget = widgetId;
        this.notify();
    }

    getSelectedWidget() {
        return this.selectedWidget;
    }
}