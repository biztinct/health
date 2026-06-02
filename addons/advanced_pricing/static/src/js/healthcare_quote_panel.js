/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Unified Healthcare Quote panel.
 *
 * A field widget on the sale.order `order_line` (one2many). It replaces the plain
 * Quote Lines table AND the static pricing breakdown with one interactive panel:
 *   - context chips (Home Visit / After Hours / ...) with highlighted SVG icons,
 *   - one card per service: catalog price -> applied rules -> final price,
 *     with a qty stepper, discount, subtotal and delete,
 *   - Add from Catalog + live totals.
 *
 * It reads/mutates the order_line records through the form record (keeping the
 * form dirty/saveable) and reads structured rule data from the order's
 * `pricing_breakdown_data` JSON field (reactive, recomputed on every edit).
 */
class HealthcareQuotePanel extends Component {
    static template = "advanced_pricing.HealthcareQuotePanel";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    // ---- reactive getters (read directly so the template re-renders on change) ----
    get order() {
        return this.props.record;
    }
    get lineList() {
        return this.props.record.data[this.props.name];
    }
    get lines() {
        return (this.lineList && this.lineList.records) || [];
    }
    get breakdown() {
        return this.props.record.data.pricing_breakdown_data || {};
    }
    get factors() {
        return this.breakdown.factors || [];
    }
    get readonly() {
        return this.props.readonly;
    }

    /** Per-line structured info {code,name,base,rules,...} keyed by db id, with
     *  a product-code fallback for freshly-added (unsaved) lines. */
    info(line) {
        const map = this.breakdown.lines || {};
        if (line.resId && map[String(line.resId)]) {
            return map[String(line.resId)];
        }
        // fallback: match by product default_code
        const code = this._lineCode(line);
        for (const k in map) {
            if (map[k].code && map[k].code === code) return map[k];
        }
        return {};
    }

    _lineCode(line) {
        const p = line.data.product_id;
        // product_id display is "[code] Name" — try to pull the code
        const dn = (p && p.display_name) || "";
        const m = dn.match(/^\[(.+?)\]/);
        return m ? m[1] : "";
    }

    productLabel(line) {
        const i = this.info(line);
        if (i.name) return i.name;
        const p = line.data.product_id;
        return (p && p.display_name) || line.data.name || "";
    }
    productCode(line) {
        return this.info(line).code || this._lineCode(line);
    }

    base(line) {
        const i = this.info(line);
        return i.base != null ? i.base : line.data.price_unit || 0;
    }
    final(line) {
        return line.data.price_unit || 0;
    }
    qty(line) {
        return line.data.product_uom_qty || 0;
    }
    discount(line) {
        return line.data.discount || 0;
    }
    subtotal(line) {
        return line.data.price_subtotal || 0;
    }
    rules(line) {
        return this.info(line).rules || [];
    }
    hasAdjustment(line) {
        return Math.abs(this.final(line) - this.base(line)) > 0.01 || this.rules(line).length > 0;
    }

    fmt(amount) {
        return (Math.round(amount || 0)).toLocaleString("en-US") + " đ";
    }

    iconClass(key) {
        return "hf-wt-ico hf-ico-" + (key || "pin");
    }

    // ---- totals ----
    get amountUntaxed() {
        return this.fmt(this.order.data.amount_untaxed);
    }
    get amountTax() {
        return this.fmt(this.order.data.amount_tax);
    }
    get amountTotal() {
        return this.fmt(this.order.data.amount_total);
    }

    // ---- mutations (keep the form dirty/saveable) ----
    async setQty(line, qty) {
        const n = Math.max(0, parseFloat(qty) || 0);
        await line.update({ product_uom_qty: n });
    }
    async incQty(line) {
        await this.setQty(line, this.qty(line) + 1);
    }
    async decQty(line) {
        await this.setQty(line, Math.max(1, this.qty(line) - 1));
    }
    async onQtyInput(line, ev) {
        await this.setQty(line, ev.target.value);
    }
    async onDiscountInput(line, ev) {
        const d = Math.min(100, Math.max(0, parseFloat(ev.target.value) || 0));
        await line.update({ discount: d });
    }
    async removeLine(line) {
        await this.lineList.delete(line);
    }

    async addFromCatalog() {
        // Save pending edits first so catalog additions attach to a saved order
        // and the reopened modal reflects current lines (mirrors the server button).
        await this.order.save();
        const action = await this.orm.call(
            "sale.order",
            "action_add_from_catalog",
            [this.order.resId],
            { context: { order_id: this.order.resId, child_field: "order_line" } }
        );
        if (action) {
            // The catalog's product_catalog_get_sections endpoint requires these
            // context keys (the original button passed them via context="..."),
            // so guarantee they're present on the action we dispatch.
            action.context = Object.assign({}, action.context, {
                order_id: this.order.resId,
                child_field: "order_line",
            });
            await this.action.doAction(action);
        }
    }
}

registry.category("fields").add("hf_quote_panel", {
    component: HealthcareQuotePanel,
    supportedTypes: ["one2many"],
});
