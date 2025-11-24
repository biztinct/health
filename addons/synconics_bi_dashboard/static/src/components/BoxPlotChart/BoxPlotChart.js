/** @odoo-module **/

import { Component, onMounted, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class BoxPlotChart extends Component {
  static template = "synconics_bi_dashboard.BoxPlotChart";
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
        this.render_boxplot_chart();
      },
      () => [this.props.chartId, this.props.recordSets, this.props.data],
    );
    onMounted(() => {
      this.render_boxplot_chart();
    });
  }

  render_boxplot_chart() {
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

    this.root = am5.Root.new("boxplot_chart__" + this.props.chartId);
    // Remove amCharts branding/logo
    if (this.root._logo) {
      this.root._logo.dispose();
    }
    const theme = this.themeMap[this.props.theme];
    this.root.setThemes([theme.new(this.root)]);

    // Simulate box plot stats from value
    const boxplotData = data.map((record) => {
      const value = record.value || 0;
      const stdDev = Math.abs(value) * 0.15;

      return {
        category: record.category,
        low: value - stdDev * 2,
        q1: value - stdDev,
        median: value,
        q3: value + stdDev,
        high: value + stdDev * 2,
      };
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
    });

    xAxis.data.setAll(boxplotData);

    // Create Y axis
    var yAxis = chart.yAxes.push(
      am5xy.ValueAxis.new(this.root, {
        renderer: am5xy.AxisRendererY.new(this.root, {}),
      })
    );

    // Create candlestick series to simulate box plot
    var series = chart.series.push(
      am5xy.CandlestickSeries.new(this.root, {
        name: "Box Plot",
        xAxis: xAxis,
        yAxis: yAxis,
        valueYField: "median",
        openValueYField: "q1",
        lowValueYField: "low",
        highValueYField: "high",
        categoryXField: "category",
      })
    );

    series.columns.template.setAll({
      strokeOpacity: 1,
      strokeWidth: 2,
      fillOpacity: 0.5,
      fill: am5.color(0x3366CC),
      stroke: am5.color(0x3366CC),
      tooltipText: "[bold]{category}[/]\nMax: {highValueY}\nQ3: {q3}\nMedian: {valueY}\nQ1: {openValueY}\nMin: {lowValueY}",
    });

    var self = this;
    series.columns.template.events.on("click", function (ev) {
      if (self.props.update_chart) {
        self.props.update_chart(
          parseInt(self.props.chartId),
          "boxplot_chart",
          ev.target.dataItem.dataContext
        );
      }
    });

    series.data.setAll(boxplotData);
    series.appear(1000, 100);
    chart.appear(1000, 100);

    let exporting = am5plugins_exporting.Exporting.new(this.root, {
      filePrefix: "boxplot_chart",
      dataSource: series,
    });

    this.root.events.once("frameended", () => {
      if (this.props.export) {
        this.props.export(exporting);
      }
    });
  }
}
