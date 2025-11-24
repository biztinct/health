/** @odoo-module **/

import { Component, onMounted, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class WaterfallChart extends Component {
  static template = "synconics_bi_dashboard.WaterfallChart";
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
        this.render_waterfall_chart();
      },
      () => [this.props.chartId, this.props.recordSets, this.props.data],
    );
    onMounted(() => {
      this.render_waterfall_chart();
    });
  }

  render_waterfall_chart() {
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

    this.root = am5.Root.new("waterfall_chart__" + this.props.chartId);
    // Remove amCharts branding/logo
    if (this.root._logo) {
      this.root._logo.dispose();
    }
    const theme = this.themeMap[this.props.theme];
    this.root.setThemes([theme.new(this.root)]);

    // Transform for waterfall: calculate running totals
    const waterfallData = [];
    let runningTotal = 0;

    data.forEach((record) => {
      const stepValue = record.value || 0;
      runningTotal += stepValue;

      waterfallData.push({
        category: record.category,
        value: stepValue,
        open: runningTotal - stepValue,
        close: runningTotal,
        stepColor: stepValue >= 0 ? am5.color(0x4CAF50) : am5.color(0xF44336),
      });
    });

    // Create chart
    var chart = this.root.container.children.push(
      am5xy.XYChart.new(this.root, {
        panX: false,
        panY: false,
        wheelX: "panX",
        wheelY: "zoomX",
        layout: this.root.verticalLayout,
      })
    );

    // Create X axis
    var xAxis = chart.xAxes.push(
      am5xy.CategoryAxis.new(this.root, {
        categoryField: "category",
        renderer: am5xy.AxisRendererX.new(this.root, {
          minGridDistance: 30,
        }),
      })
    );

    xAxis.get("renderer").labels.template.setAll({
      fontSize: 11,
      rotation: -45,
      centerX: am5.p100,
      centerY: am5.p50,
      paddingTop: 10,
    });

    xAxis.data.setAll(waterfallData);

    // Create Y axis
    var yAxis = chart.yAxes.push(
      am5xy.ValueAxis.new(this.root, {
        renderer: am5xy.AxisRendererY.new(this.root, {}),
      })
    );

    // Create series
    var series = chart.series.push(
      am5xy.ColumnSeries.new(this.root, {
        name: "Waterfall",
        xAxis: xAxis,
        yAxis: yAxis,
        valueYField: "close",
        openValueYField: "open",
        categoryXField: "category",
      })
    );

    series.columns.template.setAll({
      strokeOpacity: 0,
      cornerRadiusTL: 3,
      cornerRadiusTR: 3,
      tooltipText: "[bold]{categoryX}[/]\nChange: {valueY}\nTotal: {close}",
    });

    series.columns.template.adapters.add("fill", function (fill, target) {
      if (target.dataItem) {
        return target.dataItem.dataContext.stepColor;
      }
      return fill;
    });

    var self = this;
    series.columns.template.events.on("click", function (ev) {
      if (self.props.update_chart) {
        self.props.update_chart(
          parseInt(self.props.chartId),
          "waterfall_chart",
          ev.target.dataItem.dataContext
        );
      }
    });

    series.data.setAll(waterfallData);
    series.appear(1000, 100);
    chart.appear(1000, 100);

    let exporting = am5plugins_exporting.Exporting.new(this.root, {
      filePrefix: "waterfall_chart",
      dataSource: series,
    });

    this.root.events.once("frameended", () => {
      if (this.props.export) {
        this.props.export(exporting);
      }
    });
  }
}
