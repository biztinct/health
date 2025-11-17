/** @odoo-module **/

import { Component, onMounted, useEffect, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class TreemapChart extends Component {
  static template = "synconics_bi_dashboard.TreemapChart";
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
        this.render_treemap_chart();
      },
      () => [this.props.chartId, this.props.recordSets, this.props.data],
    );
    onMounted(() => {
      this.render_treemap_chart();
    });
  }

  render_treemap_chart() {
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

    this.root = am5.Root.new("treemap_chart__" + this.props.chartId);
    const theme = this.themeMap[this.props.theme];
    this.root.setThemes([theme.new(this.root)]);

    // Create hierarchical structure
    const treemapData = {
      name: "Root",
      children: data.map(record => ({
        name: record.category,
        value: record.value || 0
      }))
    };

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
      am5hierarchy.Treemap.new(this.root, {
        singleBranchOnly: false,
        downDepth: 1,
        initialDepth: 1,
        valueField: "value",
        categoryField: "name",
        childDataField: "children",
      })
    );

    series.rectangles.template.setAll({
      strokeWidth: 2,
      stroke: am5.color(0xffffff),
    });

    series.labels.template.setAll({
      fontSize: 11,
      fill: am5.color(0xffffff),
      text: "{name}",
      oversizedBehavior: "truncate",
    });

    series.rectangles.template.set(
      "tooltip",
      am5.Tooltip.new(this.root, {
        labelText: "[bold]{name}[/]\nValue: {value}",
      })
    );

    var self = this;
    series.rectangles.template.events.on("click", function (ev) {
      if (self.props.update_chart) {
        self.props.update_chart(
          parseInt(self.props.chartId),
          "treemap_chart",
          { category: ev.target.dataItem.dataContext.name }
        );
      }
    });

    series.data.setAll([treemapData]);
    series.set("selectedDataItem", series.dataItems[0]);
    series.appear(1000, 100);

    let exporting = am5plugins_exporting.Exporting.new(this.root, {
      filePrefix: "treemap_chart",
      dataSource: series,
    });

    this.root.events.once("frameended", () => {
      if (self.props.export) {
        self.props.export(exporting);
      }
    });
  }
}
