/** @odoo-module **/
import {Component, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {useRecordObserver} from "@web/model/relational_model/utils";
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
        // Reload from the server whenever the SAVED booking changes (UAT
        // round 10, item 5): after the OM edits Driving Distance and saves,
        // the card showed the old distance chip and total until a reload,
        // because the record object never changes identity. The card reads
        // server figures, so it waits while the form has unsaved edits.
        this._loadedKey = null;
        useRecordObserver((record) => {
            const d = record.data;
            const key = [record.resId, d.write_date && String(d.write_date),
                d.travel_distance, d.service_fee_vnd, d.total_price,
                d.sale_order_id && d.sale_order_id.id].join("|");
            if (record.dirty || key === this._loadedKey) {
                return;
            }
            this._loadedKey = key;
            return this.loadData();
        });
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
    fieldDependencies: [
        {name: "write_date", type: "datetime"},
        {name: "travel_distance", type: "float"},
        {name: "service_fee_vnd", type: "monetary"},
        {name: "total_price", type: "monetary"},
        {name: "sale_order_id", type: "many2one"},
        {name: "currency_id", type: "many2one"},
    ],
});
