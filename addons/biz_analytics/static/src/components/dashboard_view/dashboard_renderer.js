/** @odoo-module **/

import { Component, useRef, onMounted, onPatched, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class DashboardRenderer extends Component {
    
    setup() {
        this.containerRef = useRef("container");
        this.notification = useService("notification");
        
        this.state = useState({
            isChartLibLoaded: false,
            dragOver: false,
        });
        
        this.chartInstances = new Map();
        this.resizeObserver = null;
        
        onMounted(() => {
            this._loadChartLibrary();
            this._setupResizeObserver();
            this._setupDragDrop();
        });
        
        onPatched(() => {
            this._updateCharts();
        });
    }

    // ===================
    // Chart Library Management
    // ===================

    async _loadChartLibrary() {
        try {
            await loadBundle("web.chartjs_lib");
            this.state.isChartLibLoaded = true;
            this._renderAllCharts();
        } catch (error) {
            console.error("Error loading Chart.js:", error);
            this.notification.add(_t("Error loading chart library"), { type: 'danger' });
        }
    }

    _renderAllCharts() {
        if (!this.state.isChartLibLoaded) return;
        
        const widgets = this.props.model.getAllWidgets();
        for (const widget of widgets) {
            if (widget.widget_type === 'chart') {
                this._renderChart(widget);
            }
        }
    }

    _renderChart(widget) {
        if (!window.Chart || !this.containerRef.el) return;
        
        const canvasId = `chart_${widget.id}`;
        const canvas = this.containerRef.el.querySelector(`#${canvasId}`);
        
        if (!canvas) return;
        
        // Destroy existing chart instance
        if (this.chartInstances.has(widget.id)) {
            this.chartInstances.get(widget.id).destroy();
        }
        
        // Create new chart instance
        const ctx = canvas.getContext('2d');
        const config = this._prepareChartConfig(widget);
        
        try {
            const chartInstance = new window.Chart(ctx, config);
            this.chartInstances.set(widget.id, chartInstance);
            
            // Add click handler for interactivity
            if (widget.clickable) {
                canvas.onclick = (event) => {
                    const points = chartInstance.getElementsAtEventForMode(
                        event, 'nearest', { intersect: true }, true
                    );
                    if (points.length > 0) {
                        this.props.onWidgetClick(widget.id, {
                            point: points[0],
                            data: widget.data,
                            event: event
                        });
                    }
                };
            }
            
        } catch (error) {
            console.error(`Error creating chart for widget ${widget.id}:`, error);
        }
    }

    _prepareChartConfig(widget) {
        const baseConfig = widget.config || {};
        const data = widget.data || { labels: [], datasets: [] };
        
        // Apply theme-based styling
        const dashboardData = this.props.model.getDashboardData();
        const theme = dashboardData.theme || 'light';
        
        const config = {
            ...baseConfig,
            data: data,
            options: {
                ...baseConfig.options,
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    ...baseConfig.options?.plugins,
                    legend: {
                        display: widget.legend_display !== false,
                        position: 'top',
                        labels: {
                            color: theme === 'dark' ? '#ffffff' : '#333333',
                            font: {
                                size: 12
                            }
                        }
                    },
                    title: {
                        display: widget.title_display !== false,
                        text: widget.name,
                        color: theme === 'dark' ? '#ffffff' : '#333333',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    },
                    tooltip: {
                        backgroundColor: theme === 'dark' ? '#333333' : '#ffffff',
                        titleColor: theme === 'dark' ? '#ffffff' : '#333333',
                        bodyColor: theme === 'dark' ? '#ffffff' : '#333333',
                        borderColor: theme === 'dark' ? '#555555' : '#cccccc',
                        borderWidth: 1
                    }
                },
                scales: this._getScalesConfig(widget, theme),
                animation: {
                    duration: widget.animation_enabled !== false ? 1000 : 0
                }
            }
        };
        
        return config;
    }

    _getScalesConfig(widget, theme) {
        if (!['bar', 'line', 'area'].includes(widget.chart_type)) {
            return {};
        }
        
        const gridColor = theme === 'dark' ? '#444444' : '#e0e0e0';
        const tickColor = theme === 'dark' ? '#cccccc' : '#666666';
        
        return {
            x: {
                display: true,
                grid: {
                    display: widget.grid_display !== false,
                    color: gridColor
                },
                ticks: {
                    color: tickColor
                }
            },
            y: {
                display: true,
                grid: {
                    display: widget.grid_display !== false,
                    color: gridColor
                },
                ticks: {
                    color: tickColor
                }
            }
        };
    }

    _updateCharts() {
        if (!this.state.isChartLibLoaded) return;
        
        // Update existing charts with new data
        this.chartInstances.forEach((chart, widgetId) => {
            const widget = this.props.model.getWidgetData(widgetId);
            if (widget && widget.data) {
                chart.data = widget.data;
                chart.update('none'); // No animation for updates
            }
        });
    }

    // ===================
    // Layout Management
    // ===================

    _setupResizeObserver() {
        if (!window.ResizeObserver) return;
        
        this.resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const widgetId = entry.target.dataset.widgetId;
                if (widgetId && this.chartInstances.has(parseInt(widgetId))) {
                    // Resize chart when widget container resizes
                    setTimeout(() => {
                        const chart = this.chartInstances.get(parseInt(widgetId));
                        if (chart) {
                            chart.resize();
                        }
                    }, 100);
                }
            }
        });
        
        // Observe all widget containers
        if (this.containerRef.el) {
            const widgetElements = this.containerRef.el.querySelectorAll('.analytics-widget');
            widgetElements.forEach(element => {
                this.resizeObserver.observe(element);
            });
        }
    }

    // ===================
    // Drag and Drop
    // ===================

    _setupDragDrop() {
        if (!this.containerRef.el) return;
        
        const container = this.containerRef.el;
        
        // Allow dropping
        container.addEventListener('dragover', this._onDragOver.bind(this));
        container.addEventListener('dragenter', this._onDragEnter.bind(this));
        container.addEventListener('dragleave', this._onDragLeave.bind(this));
        container.addEventListener('drop', this._onDrop.bind(this));
        
        // Make widgets draggable in edit mode
        this._updateWidgetDraggability();
    }

    _updateWidgetDraggability() {
        if (!this.containerRef.el) return;
        
        const widgets = this.containerRef.el.querySelectorAll('.analytics-widget');
        widgets.forEach(widget => {
            widget.draggable = this.props.editMode;
            if (this.props.editMode) {
                widget.addEventListener('dragstart', this._onWidgetDragStart.bind(this));
                widget.addEventListener('dragend', this._onWidgetDragEnd.bind(this));
            }
        });
    }

    _onDragOver(event) {
        if (this.props.editMode) {
            event.preventDefault();
        }
    }

    _onDragEnter(event) {
        if (this.props.editMode) {
            event.preventDefault();
            this.state.dragOver = true;
        }
    }

    _onDragLeave(event) {
        if (event.target === this.containerRef.el) {
            this.state.dragOver = false;
        }
    }

    _onDrop(event) {
        if (!this.props.editMode) return;
        
        event.preventDefault();
        this.state.dragOver = false;
        
        // Calculate drop position
        const rect = this.containerRef.el.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        const draggedWidgetId = event.dataTransfer.getData('text/plain');
        if (draggedWidgetId) {
            // Calculate grid position
            const gridPosition = this._calculateGridPosition(x, y);
            this.props.onWidgetMove(
                parseInt(draggedWidgetId),
                gridPosition.x,
                gridPosition.y,
                null, // Keep existing width
                null  // Keep existing height
            );
        }
    }

    _onWidgetDragStart(event) {
        const widgetId = event.target.dataset.widgetId;
        event.dataTransfer.setData('text/plain', widgetId);
        event.target.style.opacity = '0.5';
    }

    _onWidgetDragEnd(event) {
        event.target.style.opacity = '1';
    }

    _calculateGridPosition(x, y) {
        const dashboardData = this.props.model.getDashboardData();
        const columns = dashboardData.columns || 4;
        const containerWidth = this.containerRef.el.offsetWidth;
        
        const columnWidth = containerWidth / columns;
        const rowHeight = 200; // Approximate row height
        
        return {
            x: Math.floor(x / columnWidth),
            y: Math.floor(y / rowHeight)
        };
    }

    // ===================
    // Widget Rendering
    // ===================

    getWidgetStyle(widget) {
        const dashboardData = this.props.model.getDashboardData();
        const columns = dashboardData.columns || 4;
        
        if (dashboardData.layout_type === 'grid') {
            const widthPercent = (widget.width / columns) * 100;
            
            return {
                position: 'absolute',
                left: `${(widget.position_x / columns) * 100}%`,
                top: `${widget.position_y * 200}px`,
                width: `${widthPercent}%`,
                height: `${widget.height * 200}px`,
                zIndex: this.props.selectedWidget === widget.id ? 10 : 1
            };
        }
        
        return {};
    }

    getWidgetClasses(widget) {
        const classes = ['analytics-widget', `widget-${widget.widget_type}`];
        
        if (this.props.selectedWidget === widget.id) {
            classes.push('selected');
        }
        
        if (this.props.editMode) {
            classes.push('edit-mode');
        }
        
        return classes.join(' ');
    }

    // ===================
    // Event Handlers
    // ===================

    onWidgetClick(widgetId, event) {
        if (this.props.editMode) {
            this.props.onWidgetSelect(widgetId);
        } else {
            this.props.onWidgetClick(widgetId, event);
        }
    }

    onWidgetDoubleClick(widgetId) {
        this.props.onWidgetDoubleClick(widgetId);
    }

    onWidgetDelete(widgetId, event) {
        event.stopPropagation();
        this.props.onWidgetDelete(widgetId);
    }

    onAddWidget() {
        this.props.onAddWidget();
    }

    // ===================
    // Cleanup
    // ===================

    willUnmount() {
        // Destroy all chart instances
        this.chartInstances.forEach(chart => chart.destroy());
        this.chartInstances.clear();
        
        // Disconnect resize observer
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
    }
}

DashboardRenderer.template = "biz_analytics.DashboardRenderer";