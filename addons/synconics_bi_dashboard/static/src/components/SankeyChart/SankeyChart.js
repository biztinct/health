/** @odoo-module **/

import { Component, onMounted, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class SankeyChart extends Component {
  static template = "synconics_bi_dashboard.SankeyChart";
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
        this.render_sankey_chart();
      },
      () => [this.props.chartId, this.props.recordSets, this.props.data],
    );
    onMounted(() => {
      this.render_sankey_chart();
    });
  }

  render_sankey_chart() {
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

    this.root = am5.Root.new("sankey_chart__" + this.props.chartId);
    // Remove amCharts branding/logo
    if (this.root._logo) {
      this.root._logo.dispose();
    }
    const theme = this.themeMap[this.props.theme];
    this.root.setThemes([theme.new(this.root)]);

    // Transform data: create flow from categories to values
    const sankeyData = [];
    const targetNode = "Total";

    data.forEach((record, index) => {
      const value = record.value || 0;
      if (value > 0) {
        sankeyData.push({
          from: record.category || `Item ${index + 1}`,
          to: targetNode,
          value: value
        });
      }
    });

    if (!sankeyData.length) {
      this.state.isError = true;
      this.state.errorMessage = "No Data to display!";
      return;
    }

    // Create series
    var series = this.root.container.children.push(
      am5flow.Sankey.new(this.root, {
        sourceIdField: "from",
        targetIdField: "to",
        valueField: "value",
        paddingRight: 50,
        paddingLeft: 50,
      })
    );

    // Configure nodes
    series.nodes.rectangles.template.setAll({
      fillOpacity: 0.8,
      strokeWidth: 2,
    });

    series.nodes.labels.template.setAll({
      fontSize: 11,
      fill: am5.color(0x000000),
    });

    // Configure links
    series.links.template.setAll({
      fillOpacity: 0.5,
    });

    // Add tooltips
    series.nodes.rectangles.template.set(
      "tooltip",
      am5.Tooltip.new(this.root, {
        labelText: "[bold]{name}[/]\nTotal: {sum}",
      })
    );

    series.links.template.set(
      "tooltip",
      am5.Tooltip.new(this.root, {
        labelText: "[bold]{sourceId} → {targetId}[/]\nValue: {value}",
      })
    );

    var self = this;
    // Add click events
    series.nodes.rectangles.template.events.on("click", function (ev) {
      if (self.props.update_chart) {
        self.props.update_chart(
          parseInt(self.props.chartId),
          "sankey_chart",
          { category: ev.target.dataItem.dataContext.name }
        );
      }
    });

    // Set data
    series.data.setAll(sankeyData);

    // Animate on appear
    series.appear(1000, 100);

    // Export functionality
    let exporting = am5plugins_exporting.Exporting.new(this.root, {
      filePrefix: "sankey_chart",
      dataSource: series,
    });

    this.root.events.once("frameended", () => {
      if (this.props.export) {
        this.props.export(exporting);
      }
    });
  }
}
