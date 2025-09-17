/** @odoo-module alias=biz_analytics.DashboardView **/

import { DashboardArchParser } from "./dashboard_arch_parser";
import { DashboardController } from "./dashboard_controller";  
import { DashboardModel } from "./dashboard_model";
import { DashboardRenderer } from "./dashboard_renderer";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const viewRegistry = registry.category("views");

export const AnalyticsDashboardView = {
    display_name: _t("Analytics Dashboard"),
    icon: "fa fa-dashboard",
    multiRecord: true,
    ArchParser: DashboardArchParser,
    Controller: DashboardController,
    Renderer: DashboardRenderer,
    Model: DashboardModel,
    jsLibs: ["/web/static/lib/Chart/Chart.js"],
    cssLibs: [],
    type: "analytics_dashboard",

    props: (genericProps, view) => {
        const { arch, fields, resModel } = genericProps;
        const parser = new view.ArchParser();
        const archInfo = parser.parse(arch, fields);
        const modelParams = {
            ...archInfo,
            resModel: resModel,
            fields: fields,
        };

        return {
            ...genericProps,
            modelParams,
            Model: view.Model,
            Renderer: view.Renderer,
        };
    },
};

viewRegistry.add("analytics_dashboard", AnalyticsDashboardView);