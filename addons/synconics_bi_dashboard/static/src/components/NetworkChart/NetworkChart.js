/** @odoo-module **/

import { Component, onMounted, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class NetworkChart extends Component {
  static template = "synconics_bi_dashboard.NetworkChart";
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
        this.render_network_chart();
      },
      () => [this.props.chartId, this.props.recordSets, this.props.data],
    );
    onMounted(() => {
      this.render_network_chart();
    });
  }

  render_network_chart() {
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

    this.root = am5.Root.new("network_chart__" + this.props.chartId);
    const theme = this.themeMap[this.props.theme];
    this.root.setThemes([theme.new(this.root)]);

    // Create hierarchical network structure
    const networkData = data.map((record) => ({
      id: record.category,
      name: record.category,
      value: record.value || 0,
    }));

    // Create container
    var container = this.root.container.children.push(
      am5.Container.new(this.root, {
        width: am5.percent(100),
        height: am5.percent(100),
        layout: this.root.verticalLayout,
      })
    );

    // Create series
    var series = container.children.push(
      am5flow.ForceDirected.new(this.root, {
        singleBranchOnly: false,
        downDepth: 1,
        topDepth: 1,
        initialDepth: 1,
        valueField: "value",
        categoryField: "name",
        childDataField: "children",
        idField: "id",
        centerStrength: 0.8,
      })
    );

    // Configure nodes
    series.nodes.template.setAll({
      tooltipText: "[bold]{name}[/]\nValue: {value}",
      fillOpacity: 0.8,
      strokeWidth: 2,
      stroke: am5.color(0xffffff),
    });

    series.nodes.labels.template.setAll({
      fontSize: 11,
      fill: am5.color(0x000000),
      text: "{name}",
      centerX: am5.p50,
      centerY: am5.p50,
    });

    // Configure links
    series.links.template.setAll({
      strokeOpacity: 0.3,
      strokeWidth: 1,
    });

    var self = this;
    series.nodes.template.events.on("click", function (ev) {
      if (self.props.update_chart) {
        self.props.update_chart(
          parseInt(self.props.chartId),
          "network_chart",
          ev.target.dataItem.dataContext
        );
      }
    });

    series.data.setAll(networkData);
    series.appear(1000, 100);

    let exporting = am5plugins_exporting.Exporting.new(this.root, {
      filePrefix: "network_chart",
      dataSource: series,
    });

    this.root.events.once("frameended", () => {
      if (this.props.export) {
        this.props.export(exporting);
      }
    });
  }
}
