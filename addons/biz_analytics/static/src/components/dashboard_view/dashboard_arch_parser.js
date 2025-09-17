/** @odoo-module **/

export class DashboardArchParser {
    
    parse(arch, fields) {
        const archInfo = {
            dashboardId: false,
            widgets: [],
            filters: {},
            layout: 'grid',
            columns: 4,
            theme: 'light'
        };

        // Parse arch XML if provided
        if (arch) {
            const dashboard = arch.querySelector('dashboard');
            if (dashboard) {
                archInfo.dashboardId = dashboard.getAttribute('dashboard_id');
                archInfo.layout = dashboard.getAttribute('layout') || 'grid';
                archInfo.columns = parseInt(dashboard.getAttribute('columns')) || 4;
                archInfo.theme = dashboard.getAttribute('theme') || 'light';
                
                // Parse widgets
                const widgetNodes = dashboard.querySelectorAll('widget');
                for (const widgetNode of widgetNodes) {
                    const widget = {
                        id: widgetNode.getAttribute('id'),
                        name: widgetNode.getAttribute('name'),
                        type: widgetNode.getAttribute('type') || 'chart',
                        chartType: widgetNode.getAttribute('chart_type') || 'bar',
                        datasetId: widgetNode.getAttribute('dataset_id'),
                        x: parseInt(widgetNode.getAttribute('x')) || 0,
                        y: parseInt(widgetNode.getAttribute('y')) || 0,
                        width: parseInt(widgetNode.getAttribute('width')) || 6,
                        height: parseInt(widgetNode.getAttribute('height')) || 4,
                    };
                    archInfo.widgets.push(widget);
                }
                
                // Parse filters
                const filterNodes = dashboard.querySelectorAll('filter');
                for (const filterNode of filterNodes) {
                    const filterName = filterNode.getAttribute('name');
                    archInfo.filters[filterName] = {
                        type: filterNode.getAttribute('type') || 'text',
                        field: filterNode.getAttribute('field'),
                        label: filterNode.getAttribute('string'),
                        domain: filterNode.getAttribute('domain') || '[]',
                    };
                }
            }
        }

        return archInfo;
    }
}