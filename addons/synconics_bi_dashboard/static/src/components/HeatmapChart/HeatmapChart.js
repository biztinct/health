/** @odoo-module **/

import { Component, onMounted, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class HeatmapChart extends Component {
  static template = "synconics_bi_dashboard.HeatmapChart";
  static props = {
    chartId: String,
    name: String,
    isDirty: { optional: true, type: Boolean },
    data: { optional: true, type: Object },
    update_chart: { optional: true, type: Function },
    apply_cross_filter: { optional: true, type: Function },
    theme: String,
    recordSets: Object,
    export: { optional: true, type: Function },
  };

  setup() {
    this.orm = useService("orm");
    this.root = null;
    this.themeMap = {
      animated: am5themes_Animated,
      frozen: am5themes_Frozen,
      kelly: am5themes_Kelly,
      material: am5themes_Material,
      moonrise: am5themes_Moonrise,
      spirited: am5themes_Spirited,
    };
    this.state = useState({ isError: false, errorMessage: false });
    useEffect(
      () => {
        this.render_heatmap_chart();
      },
      () => [this.props.chartId, this.props.recordSets, this.props.data],
    );
    onMounted(() => {
      this.render_heatmap_chart();
    });
  }

  render_heatmap_chart() {
    var data = this.props.recordSets;
    if (this.root) {
      this.root.dispose();
    }
    if (typeof data == "object" && !Array.isArray(data)) {
      this.state.isError = true;
      this.state.errorMessage = data.message;
      return;
    }

    this.state.isError = false;
    this.state.errorMessage = false;

    if (!data || !data.length) {
      this.state.isError = true;
      this.state.errorMessage = "No Data to display!";
      return;
    }

    this.root = am5.Root.new("heatmap_chart__" + this.props.chartId);
    // Remove amCharts branding/logo
    if (this.root._logo) {
      this.root._logo.dispose();
    }
    const theme = this.themeMap[this.props.theme];
    this.root.setThemes([theme.new(this.root)]);

    // Create chart with simple heatmap using column series
    var chart = this.root.container.children.push(
      am5xy.XYChart.new(this.root, {
        panX: false,
        panY: false,
        wheelX: "none",
        wheelY: "none",
        layout: this.root.verticalLayout,
      })
    );

    // Create Y axis (categories)
    var yAxis = chart.yAxes.push(
      am5xy.CategoryAxis.new(this.root, {
        categoryField: "category",
        renderer: am5xy.AxisRendererY.new(this.root, {
          minGridDistance: 20,
        }),
      })
    );

    yAxis.data.setAll(data);
    yAxis.get("renderer").labels.template.setAll({
      fontSize: 11,
    });

    // Create X axis (simple numeric)
    var xAxis = chart.xAxes.push(
      am5xy.ValueAxis.new(this.root, {
        renderer: am5xy.AxisRendererX.new(this.root, {}),
      })
    );

    // Create series with heat colors
    var series = chart.series.push(
      am5xy.ColumnSeries.new(this.root, {
        name: "Heatmap",
        xAxis: xAxis,
        yAxis: yAxis,
        valueXField: "value",
        categoryYField: "category",
      })
    );

    series.columns.template.setAll({
      tooltipText: "{categoryY}: [bold]{valueX}[/]",
      width: am5.percent(90),
      strokeOpacity: 0,
    });

    // Apply heat colors
    var maxValue = Math.max(...data.map(d => d.value || 0));
    series.columns.template.adapters.add("fill", function (fill, target) {
      if (target.dataItem) {
        var value = target.dataItem.get("valueX");
        var intensity = maxValue > 0 ? value / maxValue : 0;

        if (intensity < 0.33) {
          return am5.Color.interpolate(intensity * 3, am5.color(0x3366CC), am5.color(0x66B3FF));
        } else if (intensity < 0.66) {
          return am5.Color.interpolate((intensity - 0.33) * 3, am5.color(0x66B3FF), am5.color(0xFFCC66));
        } else {
          return am5.Color.interpolate((intensity - 0.66) * 3, am5.color(0xFFCC66), am5.color(0xFF3333));
        }
      }
      return fill;
    });

    var self = this;
    series.columns.template.events.on("click", function (ev) {
      if (self.props.update_chart) {
        self.props.update_chart(
          parseInt(self.props.chartId),
          "heatmap_chart",
          ev.target.dataItem.dataContext
        );
      }
    });

    series.data.setAll(data);
    series.appear(1000, 100);
    chart.appear(1000, 100);

    let exporting = am5plugins_exporting.Exporting.new(this.root, {
      filePrefix: "heatmap_chart",
      dataSource: series,
    });

    this.root.events.once("frameended", () => {
      if (this.props.export) {
        this.props.export(exporting);
      }
    });
  }
}
