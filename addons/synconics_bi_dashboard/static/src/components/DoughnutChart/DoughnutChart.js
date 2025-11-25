/** @odoo-module **/

import { Component, onMounted, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DoughnutChart extends Component {
  static template = "synconics_bi_dashboard.DoughnutChart";
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
    show_data_value_type: { optional: true, type: String },
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
        this.render_doughnut_chart();
      },
      () => [this.props.chartId, this.props.recordSets, this.props.data],
    );
    onMounted(() => {
      this.render_doughnut_chart();
    });
  }

  render_doughnut_chart() {
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
    this.root = am5.Root.new("doughnut_chart__" + this.props.chartId);
    // Remove amCharts branding/logo
    if (this.root._logo) {
      this.root._logo.dispose();
    }
    const theme = this.themeMap[this.props.theme];
    this.root.setThemes([theme.new(this.root)]);
    const formatLabel = (text, maxLength = 15) => {
      if (!text) return text;
      if (typeof text !== "string") return text;
      if (text.length <= maxLength) return text;
      return (
        text
          .replace(/\[/g, "(")
          .replace(/\]/g, ")")
          .substring(0, maxLength - 3) + "..."
      );
    };

    // Apply formatting to your data
    data = data.map((item) => ({
      ...item,
      category: formatLabel(item.category), // Assuming 'category' is your label field
    }));
    var chartContainer = this.root.container.children.push(
      am5.Container.new(this.root, {
        layout: this.root.horizontalLayout,
        width: am5.percent(100),
        height: am5.percent(100),
      }),
    );

    var chart = chartContainer.children.push(
      am5percent.PieChart.new(this.root, {
        layout: this.root.verticalLayout,
        innerRadius: am5.percent(40),
      }),
    );

    let keys = Object.keys(data[0]).filter(
      (k) => k !== "category" && k !== "record_id" && k !== "isSubGroupBy",
    );
    var self = this;

    // Helper function to capitalize first letter
    const capitalizeFirst = (str) => {
      // Handle keys that start with " - " prefix (e.g., " - count")
      const dashPrefix = ' - ';
      if (str.startsWith(dashPrefix)) {
        const word = str.substring(dashPrefix.length);
        return dashPrefix + word.charAt(0).toUpperCase() + word.slice(1);
      }
      // Normal capitalization for keys without prefix
      return str.charAt(0).toUpperCase() + str.slice(1);
    };

    var legend = chartContainer.children.push(
      am5.Legend.new(this.root, {
        width: 300,
        centerY: am5.percent(50),
        y: am5.percent(50),
        layout: this.root.verticalLayout,
        useDefaultMarker: true,
      }),
    );

    legend.markerRectangles.template.setAll({
      width: 15,
      height: 15,
      cornerRadiusTL: 5,
      cornerRadiusTR: 5,
      cornerRadiusBL: 5,
      cornerRadiusBR: 5,
    });

    // Configure legend value labels based on show_data_value_type setting
    const showDataValueType = this.props.show_data_value_type || 'value';
    const legendValueText = showDataValueType === 'percent'
      ? "{valuePercentTotal.formatNumber('#.0')}%"
      : "{value}";

    for (let key = 0; key < keys.length; key++) {
      var series = chart.series.push(
        am5percent.PieSeries.new(this.root, {
          valueField: keys[key],
          name: capitalizeFirst(keys[key]),
          categoryField: "category",
          alignLabels: false,
          legendValueText: legendValueText,
        }),
      );
      var bgColor = this.root.interfaceColors.get("background");
      series.slices.template.events.on("click", function (ev) {
        if (self.props.update_chart) {
          self.props.update_chart(
            parseInt(self.props.chartId),
            "doughnut_chart",
            ev.target.dataItem.dataContext,
          );
        }
      });
      series.ticks.template.setAll({ forceHidden: true });
      series.labels.template.setAll({ forceHidden: true });

      // Set tooltip text based on show_data_value_type setting
      const tooltipText = showDataValueType === 'percent'
        ? "{name}, {category}: {valuePercentTotal.formatNumber('#.0')}%"
        : "{name}, {category}: {value}";

      series.slices.template.setAll({
        stroke: bgColor,
        strokeWidth: 2,
        tooltipText: tooltipText,
      });
      series.slices.template.states.create("hover", { scale: 0.95 });
      series.data.setAll(data);
      series.appear(1000, 100);
      legend.data.push(series);
      legend.data.setAll(series.dataItems);
    }
    let exporting = am5plugins_exporting.Exporting.new(this.root, {
      filePrefix: "my_chart",
      dataSource: chart.series.getIndex(0), // optional
    });
    this.root.events.once("frameended", () => {
      if (this.props.export) {
        this.props.export(exporting);
      }
    });
  }
}
