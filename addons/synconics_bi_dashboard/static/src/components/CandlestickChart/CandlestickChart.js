/** @odoo-module **/

import { Component, onMounted, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CandlestickChart extends Component {
  static template = "synconics_bi_dashboard.CandlestickChart";
  static props = {
    chartId: String,
    name: String,
    isDirty: { optional: true, type: Boolean },
    data: { optional: true, type: Object },
    update_chart: { optional: true, type: Function },
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
        this.render_candlestick_chart();
      },
      () => [this.props.chartId, this.props.recordSets, this.props.data],
    );
    onMounted(() => {
      this.render_candlestick_chart();
    });
  }

  render_candlestick_chart() {
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

    this.root = am5.Root.new("candlestick_chart__" + this.props.chartId);
    const theme = this.themeMap[this.props.theme];
    this.root.setThemes([theme.new(this.root)]);

    // Simulate OHLC from value data
    const candlestickData = data.map((record) => {
      const value = record.value || 0;
      const variance = Math.abs(value) * 0.1;
      return {
        date: record.category,
        open: value,
        high: value + variance,
        low: value - variance,
        close: value + (Math.random() * variance * 2 - variance),
      };
    });

    // Create chart
    var chart = this.root.container.children.push(
      am5xy.XYChart.new(this.root, {
        panX: true,
        panY: false,
        wheelX: "panX",
        wheelY: "zoomX",
        layout: this.root.verticalLayout,
      })
    );

    // Create X axis
    var xAxis = chart.xAxes.push(
      am5xy.CategoryAxis.new(this.root, {
        categoryField: "date",
        renderer: am5xy.AxisRendererX.new(this.root, {
          minGridDistance: 50,
        }),
      })
    );

    xAxis.get("renderer").labels.template.setAll({
      fontSize: 11,
      rotation: -45,
      centerX: am5.p100,
      centerY: am5.p50,
    });

    xAxis.data.setAll(candlestickData);

    // Create Y axis
    var yAxis = chart.yAxes.push(
      am5xy.ValueAxis.new(this.root, {
        renderer: am5xy.AxisRendererY.new(this.root, {}),
      })
    );

    // Create series
    var series = chart.series.push(
      am5xy.CandlestickSeries.new(this.root, {
        name: "OHLC",
        xAxis: xAxis,
        yAxis: yAxis,
        valueYField: "close",
        openValueYField: "open",
        lowValueYField: "low",
        highValueYField: "high",
        categoryXField: "date",
        tooltip: am5.Tooltip.new(this.root, {
          labelText: "[bold]{date}[/]\nOpen: {openValueY}\nHigh: {highValueY}\nLow: {lowValueY}\nClose: {valueY}",
        }),
      })
    );

    series.columns.template.states.create("riseFromOpen", {
      fill: am5.color(0x4CAF50),
      stroke: am5.color(0x4CAF50),
    });

    series.columns.template.states.create("dropFromOpen", {
      fill: am5.color(0xF44336),
      stroke: am5.color(0xF44336),
    });

    var self = this;
    series.columns.template.events.on("click", function (ev) {
      if (self.props.update_chart) {
        self.props.update_chart(
          parseInt(self.props.chartId),
          "candlestick_chart",
          ev.target.dataItem.dataContext
        );
      }
    });

    series.data.setAll(candlestickData);
    series.appear(1000, 100);
    chart.appear(1000, 100);

    let exporting = am5plugins_exporting.Exporting.new(this.root, {
      filePrefix: "candlestick_chart",
      dataSource: series,
    });

    this.root.events.once("frameended", () => {
      if (this.props.export) {
        this.props.export(exporting);
      }
    });
  }
}
