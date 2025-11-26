/** @odoo-module **/

import { Component, onMounted, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class FunnelChart extends Component {
  static template = "synconics_bi_dashboard.FunnelChart";
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
        this.render_funnel_chart();
      },
      () => [this.props.chartId, this.props.recordSets, this.props.data],
    );
    onMounted(() => {
      this.render_funnel_chart();
    });
  }

  render_funnel_chart() {
    let data = this.props.recordSets;
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
    this.root = am5.Root.new("funnel_chart__" + this.props.chartId);
    // Remove amCharts branding/logo
    if (this.root._logo) {
      this.root._logo.dispose();
    }
    const theme = this.themeMap[this.props.theme];
    this.root.setThemes([theme.new(this.root)]);

    var chart = this.root.container.children.push(
      am5percent.SlicedChart.new(this.root, {
        layout: this.root.verticalLayout,
      }),
    );

    // Determine if we should show values or percentages
    const showDataValueType = this.props.show_data_value_type || 'value';
    const tooltipText = showDataValueType === 'percent'
      ? "{category}: {valuePercentTotal.formatNumber('#.0')}%"
      : "{category}: {value}";
    const legendValueText = showDataValueType === 'percent'
      ? "{valuePercentTotal.formatNumber('#.0')}%"
      : "{value}";
    const labelText = showDataValueType === 'percent'
      ? "{category}: {valuePercentTotal.formatNumber('#.0')}%"
      : "{category}: {value}";

    var series = chart.series.push(
      am5percent.FunnelSeries.new(this.root, {
        alignLabels: false,
        orientation: "vertical",
        valueField: "value",
        categoryField: "category",
        legendValueText: legendValueText,
      }),
    );
    var self = this;

    // Configure tooltip based on show_data_value_type setting
    series.slices.template.setAll({
      tooltipText: tooltipText,
    });

    // Configure slice labels to show values or percentages
    series.labels.template.setAll({
      text: labelText,
      fontSize: 12,
      fill: am5.color(0xffffff),
    });

    series.slices.template.events.on("click", function (ev) {
      if (self.props.update_chart) {
        self.props.update_chart(
          parseInt(self.props.chartId),
          "funnel_chart",
          ev.target.dataItem.dataContext,
        );
      }
    });

    series.data.setAll(data);

    series.appear();

    var legend = chart.children.push(
      am5.Legend.new(this.root, {
        centerX: am5.p50,
        x: am5.p50,
        marginTop: 15,
        marginBottom: 15,
      }),
    );

    legend.data.setAll(series.dataItems);

    chart.appear(1000, 100);
    let exporting = am5plugins_exporting.Exporting.new(this.root, {
      filePrefix: "my_chart",
      dataSource: chart.series.getIndex(0),
    });
    this.root.events.once("frameended", () => {
      if (this.props.export) {
        this.props.export(exporting);
      }
    });
  }
}
