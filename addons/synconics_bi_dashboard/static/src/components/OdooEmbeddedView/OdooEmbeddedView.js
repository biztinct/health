/** @odoo-module **/

import { Component, onWillStart, useState, useSubEnv } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

export class OdooEmbeddedView extends Component {
  static template = "synconics_bi_dashboard.OdooEmbeddedView";
  static components = { View };
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
      loading: true,
      viewProps: null,
    });

    // Provide a sub-environment for embedded context
    useSubEnv({
      config: {
        ...this.env.config,
        noBreadcrumbs: true,
      },
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

      try {
        // Prepare the view props for native Odoo View component
        const { model, view_type, domain, context, view_id, limit } = data;

        // Prepare context with limit
        const viewContext = {
          ...(context || {}),
          limit: limit || 80,
        };

        // Build view props
        this.state.viewProps = {
          resModel: model,
          type: view_type,
          domain: domain || [],
          context: viewContext,
          loadIrFilters: false,
          loadActionMenus: false,
          noContentHelp: false,
          selectRecord: (resId, context) => {
            // Handle record click - open in new action
            this.action.doAction({
              type: "ir.actions.act_window",
              res_model: model,
              res_id: resId,
              views: [[false, "form"]],
              target: "current",
            });
          },
        };

        // Add specific view_id if provided
        if (view_id) {
          this.state.viewProps.viewId = view_id;
        }

      } catch (error) {
        console.error("Error preparing view configuration:", error);
        this.state.errorMessage = "Failed to load view configuration";
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
}
