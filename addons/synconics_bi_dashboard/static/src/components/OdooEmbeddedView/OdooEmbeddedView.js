/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class OdooEmbeddedView extends Component {
  static template = "synconics_bi_dashboard.OdooEmbeddedView";
  static props = {
    chartId: String,
    name: String,
    theme: String,
    recordSets: Object,
  };

  setup() {
    this.action = useService("action");
    this.orm = useService("orm");

    this.state = useState({
      viewConfig: null,
      errorMessage: null,
      recordCount: 0,
      records: [],
      displayFields: [],
      loading: true,
    });

    onWillStart(async () => {
      await this.loadViewConfig();
    });
  }

  async loadViewConfig() {
    const data = this.props.recordSets;

    // Check for error
    if (data && data.type === "error") {
      this.state.viewConfig = null;
      this.state.errorMessage = data.message || "Error loading view configuration";
      this.state.loading = false;
      return;
    }

    // Check for embedded view configuration
    if (data && data.type === "embedded_view") {
      this.state.viewConfig = data;
      this.state.errorMessage = null;

      // Fetch records for preview
      try {
        const limit = Math.min(data.limit || 20, 20); // Show max 20 records in preview
        const fields = await this.orm.call(
          data.model,
          'fields_get',
          [],
          { attributes: ['string', 'type'] }
        );

        // Get list of fields to display (exclude binary, one2many, many2many)
        const displayFields = Object.keys(fields)
          .filter(fname => !['binary', 'one2many', 'many2many'].includes(fields[fname].type))
          .slice(0, 5); // Show first 5 fields

        if (!displayFields.includes('display_name') && !displayFields.includes('name')) {
          displayFields.unshift('display_name');
        }

        const records = await this.orm.searchRead(
          data.model,
          data.domain || [],
          displayFields,
          { limit: limit }
        );

        const recordCount = await this.orm.searchCount(
          data.model,
          data.domain || []
        );

        this.state.records = records;
        this.state.recordCount = recordCount;
        this.state.displayFields = displayFields.map(fname => ({
          name: fname,
          string: fields[fname]?.string || fname,
          type: fields[fname]?.type || 'char'
        }));
      } catch (error) {
        console.error("Error fetching records:", error);
        this.state.records = [];
        this.state.recordCount = 0;
        this.state.displayFields = [];
      }

      this.state.loading = false;
    } else {
      this.state.viewConfig = null;
      this.state.errorMessage = "Invalid view configuration";
      this.state.loading = false;
    }
  }

  openFullView() {
    if (!this.state.viewConfig) {
      return;
    }

    const { model, view_type, domain, context, view_id } = this.state.viewConfig;

    this.action.doAction({
      type: "ir.actions.act_window",
      name: this.props.name,
      res_model: model,
      views: [[view_id || false, view_type]],
      domain: domain || [],
      context: context || {},
      target: "current",
    });
  }

  getViewTypeIcon() {
    const viewType = this.state.viewConfig?.view_type || 'list';
    const icons = {
      'list': 'fa-list',
      'kanban': 'fa-th-large',
      'pivot': 'fa-table',
      'calendar': 'fa-calendar',
    };
    return icons[viewType] || 'fa-list';
  }

  getViewTypeName() {
    const viewType = this.state.viewConfig?.view_type || 'list';
    const names = {
      'list': 'List View',
      'kanban': 'Kanban View',
      'pivot': 'Pivot View',
      'calendar': 'Calendar View',
    };
    return names[viewType] || 'View';
  }
}
