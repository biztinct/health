/** @odoo-module **/
import {Component, onWillStart, onWillUpdateProps, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {registry} from "@web/core/registry";
import {standardWidgetProps} from "@web/views/widgets/standard_widget_props";

const EMPTY_DATA = {
    has_quote: false,
    has_packages: false,
    services: [],
    service_count: 0,
    total_amount: 0,
    currency_symbol: "đ",
    currency_position: "after",
    packages: [],
};

export class ServicesPackagesWidget extends Component {
    static template = "health_fieldservice.ServicesPackagesWidget";
    static props = {...standardWidgetProps};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            data: {...EMPTY_DATA},
        });
        onWillStart(() => this.loadData());
        onWillUpdateProps(() => this.loadData());
    }

    get recordId() {
        return this.props.record && this.props.record.resId;
    }

    async loadData() {
        const resId = this.recordId;
        if (!resId) {
            this.state.data = {...EMPTY_DATA};
            this.state.loading = false;
            return;
        }
        try {
            const result = await this.orm.call(
                "health.fieldservice.order",
                "get_services_packages_display_data",
                [resId]
            );
            this.state.data = result || {...EMPTY_DATA};
        } catch (e) {
            console.warn("ServicesPackagesWidget: failed to load data", e);
            this.state.data = {...EMPTY_DATA};
        }
        this.state.loading = false;
    }

    formatAmount(amount) {
        const d = this.state.data;
        const formatted = new Intl.NumberFormat("vi-VN").format(Math.round(amount || 0));
        const sym = d.currency_symbol || "đ";
        return d.currency_position === "before" ? `${sym} ${formatted}` : `${formatted} ${sym}`;
    }

    async onCreateQuote() {
        const resId = this.recordId;
        if (!resId) return;
        try {
            const action = await this.orm.call(
                "health.fieldservice.order",
                "action_create_and_open_quote",
                [resId]
            );
            this.action.doAction(action);
        } catch (e) {
            console.warn("ServicesPackagesWidget: failed to create quote", e);
        }
    }
}

registry.category("view_widgets").add("vu_services_packages", {
    component: ServicesPackagesWidget,
});
