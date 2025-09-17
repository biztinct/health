/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class FieldSelector extends Component {
    
    setup() {
        this.notification = useService("notification");
        this.containerRef = useRef("container");
        
        this.state = useState({
            selectedDataset: null,
            selectedFields: {
                x_axis: null,
                y_axis: null,
                color: null
            },
            chartType: 'bar',
            widgetName: '',
            widgetPosition: { x: 0, y: 0, width: 6, height: 4 }
        });
        
        this._setupDragDrop();
    }

    // ===================
    // Dataset Management
    // ===================

    getDatasets() {
        return Object.values(this.props.model.getDatasets());
    }

    onDatasetChange(datasetId) {
        this.state.selectedDataset = parseInt(datasetId);
        // Reset field selections when dataset changes
        this.state.selectedFields = {
            x_axis: null,
            y_axis: null,
            color: null
        };
    }

    getSelectedDataset() {
        if (!this.state.selectedDataset) return null;
        const datasets = this.props.model.getDatasets();
        return datasets[this.state.selectedDataset] || null;
    }

    // ===================
    // Field Management
    // ===================

    getFieldsByType(fieldType) {
        const dataset = this.getSelectedDataset();
        if (!dataset || !dataset.metadata.fields) return [];
        
        return dataset.metadata.fields[fieldType] || [];
    }

    getDimensionFields() {
        return this.getFieldsByType('dimensions');
    }

    getMeasureFields() {
        return this.getFieldsByType('measures');
    }

    getDateFields() {
        return this.getFieldsByType('dates');
    }

    onFieldSelect(fieldType, fieldId) {
        this.state.selectedFields[fieldType] = parseInt(fieldId);
        this._updateWidgetName();
    }

    getSelectedField(fieldType) {
        const fieldId = this.state.selectedFields[fieldType];
        if (!fieldId) return null;
        
        const dataset = this.getSelectedDataset();
        if (!dataset) return null;
        
        // Search in all field types
        for (const type of ['dimensions', 'measures', 'dates']) {
            const field = dataset.metadata.fields[type].find(f => f.id === fieldId);
            if (field) return field;
        }
        
        return null;
    }

    // ===================
    // Chart Configuration
    // ===================

    onChartTypeChange(chartType) {
        this.state.chartType = chartType;
        this._updateWidgetName();
    }

    getChartTypes() {
        return [
            { value: 'bar', label: _t('Bar Chart'), icon: 'fa-bar-chart' },
            { value: 'line', label: _t('Line Chart'), icon: 'fa-line-chart' },
            { value: 'pie', label: _t('Pie Chart'), icon: 'fa-pie-chart' },
            { value: 'doughnut', label: _t('Doughnut Chart'), icon: 'fa-circle-o' },
            { value: 'area', label: _t('Area Chart'), icon: 'fa-area-chart' },
            { value: 'scatter', label: _t('Scatter Plot'), icon: 'fa-scatter-chart' },
            { value: 'radar', label: _t('Radar Chart'), icon: 'fa-star' },
            { value: 'gauge', label: _t('Gauge Chart'), icon: 'fa-tachometer' }
        ];
    }

    getCompatibleChartTypes() {
        const xField = this.getSelectedField('x_axis');
        const yField = this.getSelectedField('y_axis');
        
        if (!xField || !yField) {
            return this.getChartTypes();
        }
        
        const chartTypes = this.getChartTypes();
        
        // Filter chart types based on field types
        if (xField.type === 'date') {
            // Time series charts
            return chartTypes.filter(ct => ['line', 'area', 'bar'].includes(ct.value));
        } else if (xField.type === 'dimension' && yField.type === 'measure') {
            // Standard categorical charts
            return chartTypes.filter(ct => !['gauge', 'scatter'].includes(ct.value));
        }
        
        return chartTypes;
    }

    // ===================
    // Widget Creation
    // ===================

    canCreateWidget() {
        return (
            this.state.selectedDataset &&
            this.state.selectedFields.x_axis &&
            this.state.selectedFields.y_axis &&
            this.state.chartType &&
            this.state.widgetName.trim()
        );
    }

    async createWidget() {
        if (!this.canCreateWidget()) {
            this.notification.add(_t("Please complete all required fields"), { type: 'warning' });
            return;
        }
        
        const dataset = this.getSelectedDataset();
        const xField = this.getSelectedField('x_axis');
        const yField = this.getSelectedField('y_axis');
        const colorField = this.getSelectedField('color');
        
        const widgetConfig = {
            name: this.state.widgetName.trim(),
            type: 'chart',
            chartType: this.state.chartType,
            datasetId: this.state.selectedDataset,
            x: this.state.widgetPosition.x,
            y: this.state.widgetPosition.y,
            width: this.state.widgetPosition.width,
            height: this.state.widgetPosition.height,
            fields: {
                x_axis: xField.id,
                y_axis: yField.id,
                color: colorField ? colorField.id : null
            }
        };
        
        try {
            await this.props.onCreateWidget(widgetConfig);
            this._resetForm();
        } catch (error) {
            console.error('Error creating widget:', error);
        }
    }

    _resetForm() {
        this.state.selectedDataset = null;
        this.state.selectedFields = {
            x_axis: null,
            y_axis: null,
            color: null
        };
        this.state.chartType = 'bar';
        this.state.widgetName = '';
        this.state.widgetPosition = { x: 0, y: 0, width: 6, height: 4 };
    }

    _updateWidgetName() {
        if (!this.state.widgetName.trim()) {
            const xField = this.getSelectedField('x_axis');
            const yField = this.getSelectedField('y_axis');
            const chartType = this.state.chartType;
            
            if (xField && yField && chartType) {
                const chartLabel = this.getChartTypes().find(ct => ct.value === chartType)?.label || chartType;
                this.state.widgetName = `${yField.label} by ${xField.label} (${chartLabel})`;
            }
        }
    }

    // ===================
    // Drag and Drop
    // ===================

    _setupDragDrop() {
        // This will be called after component is mounted
        // We'll set up drag and drop for field items
    }

    onFieldDragStart(event, field, fieldType) {
        const dragData = {
            field: field,
            fieldType: fieldType,
            source: 'field_selector'
        };
        
        event.dataTransfer.setData('text/plain', JSON.stringify(dragData));
        event.dataTransfer.effectAllowed = 'copy';
        
        // Visual feedback
        event.target.style.opacity = '0.5';
    }

    onFieldDragEnd(event) {
        event.target.style.opacity = '1';
    }

    onDropZoneDragOver(event, dropZone) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'copy';
        
        // Visual feedback for drop zone
        event.currentTarget.classList.add('drag-over');
    }

    onDropZoneDragLeave(event) {
        event.currentTarget.classList.remove('drag-over');
    }

    onDropZoneDrop(event, fieldType) {
        event.preventDefault();
        event.currentTarget.classList.remove('drag-over');
        
        try {
            const dragData = JSON.parse(event.dataTransfer.getData('text/plain'));
            if (dragData.source === 'field_selector') {
                this.onFieldSelect(fieldType, dragData.field.id);
                this.notification.add(
                    _t("Field added to %s", fieldType.replace('_', ' ')), 
                    { type: 'success' }
                );
            }
        } catch (error) {
            console.error('Error handling drop:', error);
        }
    }

    // ===================
    // UI Helpers
    // ===================

    getFieldTypeIcon(fieldType) {
        const icons = {
            dimension: 'fa-tags',
            measure: 'fa-calculator',
            date: 'fa-calendar'
        };
        return icons[fieldType] || 'fa-question';
    }

    getDropZoneLabel(fieldType) {
        const labels = {
            x_axis: _t('X-Axis (Categories)'),
            y_axis: _t('Y-Axis (Values)'),
            color: _t('Color Grouping (Optional)')
        };
        return labels[fieldType] || fieldType;
    }

    getDropZoneIcon(fieldType) {
        const icons = {
            x_axis: 'fa-arrows-h',
            y_axis: 'fa-arrows-v',
            color: 'fa-palette'
        };
        return icons[fieldType] || 'fa-question';
    }

    close() {
        this.props.onClose();
    }
}

FieldSelector.template = "biz_analytics.FieldSelector";
FieldSelector.props = {
    model: Object,
    onCreateWidget: Function,
    onClose: Function,
};