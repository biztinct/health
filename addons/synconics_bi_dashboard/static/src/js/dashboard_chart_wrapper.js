/** @odoo-module **/

import { Component, useState, onWillUpdateProps, onWillUnmount, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AreaChart } from "../components/AreaChart/AreaChart";
import { BarChart } from "../components/BarChart/BarChart";
import { ColumnChart } from "../components/ColumnChart/ColumnChart";
import { DoughnutChart } from "../components/DoughnutChart/DoughnutChart";
import { FunnelChart } from "../components/FunnelChart/FunnelChart";
import { PyramidChart } from "../components/PyramidChart/PyramidChart";
import { LineChart } from "../components/LineChart/LineChart";
import { PieChart } from "../components/PieChart/PieChart";
import { RadarChart } from "../components/RadarChart/RadarChart";
import { StackedColumnChart } from "../components/StackedColumnChart/StackedColumnChart";
import { RadialChart } from "../components/RadialChart/RadialChart";
import { ScatterChart } from "../components/ScatterChart/ScatterChart";
import { MapChart } from "../components/MapChart/MapChart";
import { MeterChart } from "../components/MeterChart/MeterChart";
import { SankeyChart } from "../components/SankeyChart/SankeyChart";
import { ChordChart } from "../components/ChordChart/ChordChart";
import { TreemapChart } from "../components/TreemapChart/TreemapChart";
import { HeatmapChart } from "../components/HeatmapChart/HeatmapChart";
import { WaterfallChart } from "../components/WaterfallChart/WaterfallChart";
import { CandlestickChart } from "../components/CandlestickChart/CandlestickChart";
import { BoxPlotChart } from "../components/BoxPlotChart/BoxPlotChart";
import { NetworkChart } from "../components/NetworkChart/NetworkChart";
import { ListView } from "../components/ListView/ListView";
import { TileView } from "../components/TileView/TileView";
import { KPIView } from "../components/KPIView/KPIView";
import { TodoView } from "../components/TodoView/TodoView";
import { OdooEmbeddedView } from "../components/OdooEmbeddedView/OdooEmbeddedView";
import { WarningDialog } from "@web/core/errors/error_dialogs";
import { _t } from "@web/core/l10n/translation";
import { Domain } from "@web/core/domain";

export class DashboardChartWrapper extends Component {
  static props = {
    chartId: String,
    name: String,
    theme: String,
    chart_type: String,
    editChart: Function,
    recordSets: Object,
    background_color: String,
    reloadKey: Number,
    onUpdateExport: { optional: true, type: Function },
    action_id: { optional: true, type: [Number, Boolean] },
    show_data_value_type: { optional: true, type: String },
  };

  setup() {
    this.state = useState({
      chartId: this.props.chartId,
      name: this.props.name,
      chart_type: this.props.chart_type,
      theme: this.props.theme,
      breadcrump_ids: [],
      prev_domains: [],
      current_group_by: false,
      isKpiError: false,
      recordSets: this.props.recordSets,
      exporting: false,
      background_color: this.props.background_color,
      show_data_value_type: this.props.show_data_value_type || 'value',
    });
    if (
      ["kpi", "tile"].includes(this.props.chart_type) &&
      typeof this.props.recordSets === "object" &&
      this.props.recordSets !== null &&
      !Array.isArray(this.props.recordSets) &&
      "type" in this.props.recordSets
    ) {
      this.state.isKpiError = true;
    } else {
      this.state.isKpiError = false;
    }

    this.orm = useService("orm");
    this.action = useService("action");
    this.dialog = useService("dialog");
    this.filterService = useService("dashboardFilterService");

    // Track cross-filter subscription
    this.filterUnsubscribe = null;

    // Subscribe to cross-filter changes
    onWillStart(() => {
      this.filterUnsubscribe = this.filterService.subscribe((filterData) => {
        console.log('[ChartWrapper] Cross-filter changed for chart:', this.state.chartId);
        // Refresh chart data with new filters
        this.update_record_sets(
          this.state.chartId,
          this.state.chart_type,
          false,
          this.state.name,
          Object,
          filterData.domain  // Pass cross-filter domain
        );
      });
    });

    // Cleanup subscription on unmount
    onWillUnmount(() => {
      if (this.filterUnsubscribe) {
        this.filterUnsubscribe();
      }
    });

    onWillUpdateProps((nextprops) => {
      this.update_record_sets(
        nextprops.chartId,
        nextprops.chart_type,
        false,
        nextprops.name,
        Object,
      );
    });

    this.onEditChart = (ev, chartId) => {
      this.props.editChart(chartId, this.state.name, this.onHandleEdit);
    };

    this.onOpenExternalWindow = async (ev) => {
      // Open embedded view in new browser tab/window
      if (['odoo_list_view', 'odoo_kanban_view', 'odoo_pivot_view', 'odoo_calendar_view'].includes(this.state.chart_type)) {
        try {
          // Call backend to get proper action URL
          const result = await this.orm.call(
            'dashboard.chart',
            'get_action_url_for_embedded_view',
            [parseInt(this.state.chartId)]
          );

          if (result && result.url_hash) {
            // Construct full URL with /web as base path
            const baseUrl = window.location.origin + '/web';
            const fullUrl = baseUrl + result.url_hash;

            // Open in new tab
            window.open(fullUrl, '_blank');
          }
        } catch (error) {
          console.error('Error opening view in new window:', error);
        }
      }
    };

    this.onMaximizeView = (ev) => {
      // Open embedded view as modal window for embedded Odoo views
      if (['odoo_list_view', 'odoo_kanban_view', 'odoo_pivot_view', 'odoo_calendar_view'].includes(this.state.chart_type)) {
        const viewConfig = this.state.recordSets;
        if (viewConfig && viewConfig.type === 'embedded_view') {
          const { model, view_type, domain, context, view_id } = viewConfig;
          this.action.doAction({
            type: "ir.actions.act_window",
            name: this.state.name,
            res_model: model,
            views: [[view_id || false, view_type]],
            domain: domain || [],
            context: context || {},
            target: "new",  // Opens as modal dialog overlay
          });
        }
      }
    };

    this.setExporting = (exporting) => {
      this.state.exporting = exporting;
      if (this.props.onUpdateExport) {
        this.props.onUpdateExport(parseInt(this.state.chartId), {
          name: this.state.name,
          exporting: exporting,
          chart_type: this.state.chart_type,
        });
      }
    };

    /**
     * Apply cross-filter from chart click
     * Called by child chart components when user clicks a data point
     */
    this.onApplyCrossFilter = (field, label, values, model) => {
      console.log('[ChartWrapper] Applying cross-filter:', {
        chartId: this.state.chartId,
        field,
        label,
        values,
        model
      });

      // Apply filter through the filter service
      this.filterService.applyFilter(
        this.state.chartId,
        field,
        label,
        values,
        model,
        this.state.chart_type
      );
    };

    this.onDownloadCSV = (ev) => {
      return this.orm
        .call("dashboard.chart", "export_csv", [
          parseInt(this.state.chartId),
          this.state.name,
          this.state.chart_type,
          {
            breadcrump_ids: this.state.breadcrump_ids,
            prev_domains: this.state.prev_domains,
          },
        ])
        .then((response) => {
          if (response.error) {
            return this.dialog.add(WarningDialog, {
              title: _t("Warning"),
              message:
                _t(
                  "No data is available for downloading the CSV file at this time!",
                ) || "",
            });
          }
          const base64Content = response.file_content;
          const fileName = response.file_name || "download.csv";

          const byteCharacters = atob(base64Content);
          const byteArray = new Uint8Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteArray[i] = byteCharacters.charCodeAt(i);
          }

          const blob = new Blob([byteArray], {
            type: "text/csv;charset=utf-8;",
          });

          const link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = fileName;
          link.click();
        })
        .catch((error) => {
          console.error("Error downloading CSV:", error);
        });
    };

    this.onDownloadExcel = (ev) => {
      return this.orm
        .call("dashboard.chart", "export_excel", [
          parseInt(this.state.chartId),
          this.state.name,
          this.state.chart_type,
          {
            breadcrump_ids: this.state.breadcrump_ids,
            prev_domains: this.state.prev_domains,
          },
        ])
        .then((response) => {
          if (response.error) {
            return this.dialog.add(WarningDialog, {
              title: _t("Warning"),
              message:
                _t(
                  "No data is available for downloading the Excel file at this time!",
                ) || "",
            });
          }
          const base64Content = response.file_content;
          const fileName = response.file_name || "download.xlsx";
          const byteCharacters = atob(base64Content);
          const byteArray = new Uint8Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteArray[i] = byteCharacters.charCodeAt(i);
          }
          const blob = new Blob([byteArray], {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          });
          const link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = fileName;
          link.click();
        })
        .catch((error) => {
          console.error("Error downloading Excel:", error);
        });
    };

    this.onDownloadImage = async (ev) => {
      var self = this;
      if (["kpi", "tile"].includes(this.state.chart_type)) {
        var close_grid = ev.target.closest(".grid-stack-item-content");
        var child_date_range = close_grid.querySelectorAll(
          ".o_bottom .o_date_range",
        );
        var client_width = close_grid.clientWidth;
        if (child_date_range.length > 0) {
          if (client_width < 301) {
            child_date_range.forEach((el) => {
              el.style.fontSize = "9px";
            });
          } else if (client_width > 300 && client_width < 601) {
            child_date_range.forEach((el) => {
              el.style.fontSize = "11px";
            });
          } else {
            child_date_range.forEach((el) => {
              el.style.fontSize = "13px";
            });
          }
        }
        html2canvas(close_grid, {
          useCORS: true,
          scale: 2, // higher quality capture
          windowWidth: "100%",
          windowHeight: close_grid.clientHeight,
        })
          .then((canvas) => {
            const imgData = canvas.toDataURL("image/jpeg");
            function dataUrlToBlob(dataUrl) {
              const arr = dataUrl.split(",");
              const mime = arr[0].match(/:(.*?);/)[1];
              const bstr = atob(arr[1]);
              let n = bstr.length;
              const u8arr = new Uint8Array(n);
              while (n--) {
                u8arr[n] = bstr.charCodeAt(n);
              }
              return new Blob([u8arr], { type: mime });
            }
            const blob = dataUrlToBlob(imgData);
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download =
              (this?.state?.name || "download").replaceAll(" ", "_") + ".jpeg";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            child_date_range.forEach((el, i) => {
              el.style.fontSize = "1vh";
            });
          })
          .catch((error) => {
            console.error("Image generation failed:", error);
            child_date_range.forEach((el, i) => {
              el.style.fontSize = "1vh";
            });
          });
      } else if (["list", "to_do"].includes(this.state.chart_type)) {
        let image = await this.orm.call("dashboard.chart", "html_to_image", [
          parseInt(this.state.chartId),
        ]);
        const blob = this.dataUrlToBlob(image);
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = this.state.name.replaceAll(" ", "_") + ".jpeg";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      } else {
        if (!this.state.exporting) {
          return this.dialog.add(WarningDialog, {
            title: _t("Warning"),
            message:
              _t(
                "No data is available for downloading the Image at this time!",
              ) || "",
          });
        }
        let image = await this.state.exporting.export("png");
        const blob = this.dataUrlToBlob(image);
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = this.state.name.replaceAll(" ", "_") + ".png";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    };

    this.onHandleEdit = async () => {
      const updatedDetails = await this.orm.call(
        "dashboard.chart",
        "search_fetch",
        [],
        {
          domain: [["id", "=", this.props.chartId]],
          fields: ["name", "chart_type", "theme"],
        },
      );
      if (updatedDetails.length) {
        this.state.chart_type = updatedDetails[0].chart_type;
        this.state.name = updatedDetails[0].name;
        this.state.theme = updatedDetails[0].theme;
        this.update_record_sets(
          this.props.chartId,
          updatedDetails[0].chart_type,
          false,
          updatedDetails[0].name,
          Object,
        );
      }
    };

    this.update_chart = async (chartId, chartType, domain) => {
      let chart_data = await this.orm.call(
        "dashboard.chart",
        "get_chart_data",
        [chartId],
        {
          chart_type: chartType,
          name: this.state.name,
          isDirty: false,
          data: Object,
          extra_action: {
            breadcrump_ids: this.state.breadcrump_ids,
            prev_domains: this.state.prev_domains,
            domain,
            current_group_by: this.state.current_group_by,
          },
        },
      );
      if (chart_data.type && chart_data.type == "action") {
        this.action.doAction(chart_data.action);
      }
      if (!chart_data.prepared_data || !chart_data.prepared_data.length) {
        return;
      }
      this.state.recordSets = chart_data.prepared_data;
      this.state.prev_domains = chart_data.current_domain;
      this.state.breadcrump_ids.push(chart_data.breadcrump_ids);
      this.state.current_group_by = chart_data.current_group_by;
      this.state.chart_type = chart_data.chart_type;
    };
  }

  dataUrlToBlob(dataUrl) {
    const parts = dataUrl.split(",");
    const mimeMatch = parts[0].match(/:(.*?);/);
    const mime = mimeMatch ? mimeMatch[1] : "image/png";
    const binary = atob(parts[1]);
    const array = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      array[i] = binary.charCodeAt(i);
    }
    return new Blob([array], { type: mime });
  }

  async update_record_sets(recordId, chart_type, isDirty, name, data, cross_filter_domain = null) {
    // Get cross-filter domain if not provided
    if (cross_filter_domain === null && this.filterService) {
      cross_filter_domain = this.filterService.getActiveDomain();
    }

    // Get date filter state
    let date_filter = null;
    if (this.filterService && this.filterService.hasActiveDateFilter()) {
      date_filter = this.filterService.getDateFilterState();
      console.log('[ChartWrapper] Date filter active for chart', recordId, ':', date_filter);
    }

    console.log('[ChartWrapper] Calling get_chart_data for chart', recordId, 'with:', {
      chart_type,
      cross_filter_domain: cross_filter_domain || [],
      dashboard_date_filter: date_filter,
    });

    let recordSets = await this.orm.call(
      "dashboard.chart",
      "get_chart_data",
      [parseInt(recordId)],
      {
        chart_type,
        name,
        isDirty,
        data,
        cross_filter_domain: cross_filter_domain || [],  // Pass cross-filter domain
        dashboard_date_filter: date_filter,  // Pass dashboard-level date filter
      },
    );
    if (
      ["kpi", "tile"].includes(chart_type) &&
      typeof recordSets === "object" &&
      recordSets !== null &&
      !Array.isArray(recordSets) &&
      "type" in recordSets
    ) {
      this.state.isKpiError = true;
    } else {
      this.state.isKpiError = false;
    }
    this.state.recordSets = recordSets;
    let chart_color_id = await this.orm.searchRead(
      "dashboard.chart",
      [["id", "=", parseInt(recordId)]],
      ["background_color"],
    );
    if (chart_color_id.length) {
      this.state.background_color = chart_color_id[0].background_color;
    }
  }

  /**
   * Handle click on Tile or KPI chart
   * Executes the configured window action if action_id is set
   */
  async onChartClick() {
    if (!this.props.action_id || !['kpi', 'tile'].includes(this.props.chart_type)) {
      return;
    }

    console.log('[ChartWrapper] Executing action', this.props.action_id, 'for chart', this.props.chartId);

    try {
      // Read the chart configuration to get its domain
      const charts = await this.orm.read("dashboard.chart", [parseInt(this.props.chartId)], [
        "domain",
        "model_id",
      ]);

      // Read the action configuration
      const actions = await this.orm.read("ir.actions.act_window", [this.props.action_id], [
        "name",
        "type",
        "res_model",
        "view_mode",
        "views",
        "domain",
        "context",
        "limit",
      ]);

      if (actions.length > 0 && charts.length > 0) {
        const actionData = actions[0];
        const chartData = charts[0];

        console.log('[ChartWrapper] Opening action:', actionData.name);
        console.log('[ChartWrapper] Chart domain:', chartData.domain);

        // Parse the chart's domain (it's stored as a Python-formatted string)
        let chartDomain = [];
        if (chartData.domain) {
          try {
            chartDomain = new Domain(chartData.domain).toList();
            console.log('[ChartWrapper] Parsed chart domain:', chartDomain);
          } catch (e) {
            console.warn('[ChartWrapper] Failed to parse chart domain:', e);
          }
        }

        // Parse the action's default domain (also Python-formatted)
        let actionDomain = [];
        if (actionData.domain) {
          try {
            actionDomain = typeof actionData.domain === 'string'
              ? new Domain(actionData.domain).toList()
              : actionData.domain;
            console.log('[ChartWrapper] Parsed action domain:', actionDomain);
          } catch (e) {
            console.warn('[ChartWrapper] Failed to parse action domain:', e);
          }
        }

        // Merge domains: combine chart domain with action domain using Domain.and()
        let combinedDomain;
        if (chartDomain.length > 0 && actionDomain.length > 0) {
          combinedDomain = Domain.and([chartDomain, actionDomain]).toList();
        } else if (chartDomain.length > 0) {
          combinedDomain = chartDomain;
        } else if (actionDomain.length > 0) {
          combinedDomain = actionDomain;
        } else {
          combinedDomain = [];
        }
        console.log('[ChartWrapper] Combined domain:', combinedDomain);

        // Execute the action with the combined domain
        // Only pass specific fields to avoid format issues
        this.action.doAction({
          name: actionData.name,
          type: actionData.type || 'ir.actions.act_window',
          res_model: actionData.res_model,
          view_mode: actionData.view_mode,
          views: actionData.views || [],
          domain: combinedDomain,
          context: actionData.context || {},
          limit: actionData.limit,
        });
      } else {
        console.error('[ChartWrapper] Missing action or chart data');
        this.dialog.add(WarningDialog, {
          title: _t("Action Error"),
          message: _t("Chart or action configuration not found."),
        });
      }
    } catch (error) {
      console.error('[ChartWrapper] Error executing action:', error);
      console.error('[ChartWrapper] Error details:', error.message, error.stack);
      this.dialog.add(WarningDialog, {
        title: _t("Action Error"),
        message: _t("Failed to execute the configured action: ") + (error.message || "Unknown error"),
      });
    }
  }
}

DashboardChartWrapper.template = "synconics_bi_dashboard.DashboardChartWrapper";

DashboardChartWrapper.components = {
  AreaChart,
  BarChart,
  ColumnChart,
  DoughnutChart,
  FunnelChart,
  PyramidChart,
  LineChart,
  PieChart,
  RadarChart,
  StackedColumnChart,
  RadialChart,
  ScatterChart,
  MapChart,
  MeterChart,
  SankeyChart,
  ChordChart,
  TreemapChart,
  HeatmapChart,
  WaterfallChart,
  CandlestickChart,
  BoxPlotChart,
  NetworkChart,
  ListView,
  TileView,
  KPIView,
  TodoView,
  OdooEmbeddedView,
};
