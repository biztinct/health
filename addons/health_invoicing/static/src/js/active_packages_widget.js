/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

/**
 * Rich Active Packages display for the client profile — replaces the stock grey
 * gauge kanban with branded donut cards (matching the package dialog aesthetic).
 */
export class ActivePackagesWidget extends Component {
    static template = "health_invoicing.ActivePackagesWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: true, packages: [] });
        onWillStart(() => this.load());
        onWillUpdateProps(() => this.load());
    }

    get recordId() {
        return this.props.record && this.props.record.resId;
    }

    async load() {
        const id = this.recordId;
        if (!id) {
            this.state.packages = [];
            this.state.loading = false;
            return;
        }
        try {
            this.state.packages =
                (await this.orm.call("res.partner", "get_active_packages_display", [id])) || [];
        } catch (e) {
            this.state.packages = [];
        }
        this.state.loading = false;
    }

    donutCircumference() {
        return 2 * Math.PI * 42;
    }

    donutOffset(pkg) {
        const pct = pkg.total_services ? pkg.remaining_services / pkg.total_services : 0;
        return this.donutCircumference() * (1 - pct);
    }

    donutColor(pkg) {
        if (pkg.remaining_services === 0) return "#EF5350";
        const pct = pkg.total_services ? pkg.remaining_services / pkg.total_services : 0;
        if (pct <= 0.25) return "#EF5350";
        if (pct <= 0.5) return "#FB8C00";
        return "#43A047";
    }

    usedPercent(pkg) {
        if (!pkg.total_services) return 0;
        return Math.round((pkg.consumed_services / pkg.total_services) * 100);
    }
}

registry.category("view_widgets").add("vu_active_packages", {
    component: ActivePackagesWidget,
});
