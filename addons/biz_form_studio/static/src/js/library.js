/** @odoo-module **/
/**
 * `biz_form_studio.library` — every field made in Studio, on every screen.
 *
 * One table: which screen, the label, its type, who sees it, whether it holds
 * health information, whether it may be a list column, the mobile app, how
 * many records have a value, who made it and when — and a door into Studio
 * for that screen. The empty state names the screens that support Studio,
 * read from the server, so the sentence is right on every product.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@biz_kit/js/kit_icons";

export class FormStudioLibrary extends Component {
    static template = "biz_form_studio.Library";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.ic = ic;
        this.state = useState({ loading: true, error: "", data: null, screen: "" });
        onWillStart(async () => {
            await this.load();
        });
    }

    async load() {
        try {
            this.state.data = await this.orm.call("fs.studio", "library", []);
            this.state.error = "";
        } catch (error) {
            const data = error && error.data;
            this.state.error = (data && data.message) || _t("The field library could not be opened.");
        }
        this.state.loading = false;
    }

    get rows() {
        const rows = (this.state.data && this.state.data.rows) || [];
        return this.state.screen ? rows.filter((r) => r.model === this.state.screen) : rows;
    }

    get hosts() {
        return (this.state.data && this.state.data.hosts) || [];
    }

    get emptyHint() {
        const titles = this.hosts.map((h) => h.title);
        if (!titles.length) {
            return _t("No screen supports Studio yet.");
        }
        return _t("No custom fields yet. Open one of these screens and press Studio: %s.", titles.join(", "));
    }

    openLabel(title) {
        return _t("Open %s in Studio", title);
    }

    countFor(model) {
        const rows = (this.state.data && this.state.data.rows) || [];
        return rows.filter((r) => r.model === model).length;
    }

    setScreen(model) {
        this.state.screen = this.state.screen === model ? "" : model;
    }

    visLabel(vis) {
        return { all: _t("Everyone"), staff: _t("Staff"), admin: _t("Admins") }[vis] || "";
    }

    filled(row) {
        if (row.filled === null || row.filled === undefined) {
            return "—";
        }
        return `${row.filled} / ${row.total}`;
    }

    fillPct(row) {
        if (!row.total || row.filled === null || row.filled === undefined) {
            return 0;
        }
        return Math.round((100 * row.filled) / row.total);
    }

    async openStudio(model, viewId) {
        let resId = false;
        try {
            resId = await this.orm.call("fs.studio", "first_record", [model]);
        } catch {
            resId = false;
        }
        await this.actionService.doAction({
            type: "ir.actions.client",
            tag: "biz_form_studio.studio",
            name: _t("Form Studio"),
            params: { model, view_id: viewId, res_id: resId },
        });
    }
}

registry.category("actions").add("biz_form_studio.library", FormStudioLibrary);
