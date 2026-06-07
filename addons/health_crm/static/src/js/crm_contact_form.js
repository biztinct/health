/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useState, onMounted, onPatched, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const STATUS_LABELS = {
    active: _t("Initial Contact"),
    booking: _t("Booking"),
    lead: _t("Lead"),
    lost_booking: _t("Lost Booking"),
    spam: _t("Spam"),
};

export class CrmContactFormController extends FormController {
    static template = "health_crm.CrmContactFormView";

    setup() {
        super.setup(...arguments);
        this.rootRef = useRef("root");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.headerState = useState({
            header: {},
            isLoaded: false,
        });

        onMounted(() => {
            this._adjustLayout();
            this._loadHeaderData();
        });
        onPatched(() => {
            this._adjustLayout();
        });
    }

    async _loadHeaderData() {
        const resId = this.model.root.resId;
        if (!resId) return;
        try {
            const data = await this.orm.call(
                "crm.lead",
                "get_contact_header_data",
                [resId]
            );
            this.headerState.header = data;
            this.headerState.isLoaded = true;
        } catch (e) {
            console.error("Failed to load contact header:", e);
        }
    }

    async saveButtonClicked(params) {
        const res = await super.saveButtonClicked(params);
        await this._loadHeaderData();
        return res;
    }

    _adjustLayout() {
        const el = this.rootRef.el;
        if (el) {
            const fc = el.querySelector(".o_form_view_container");
            const oc = el.querySelector(".o_content");
            if (fc) fc.style.width = "100%";
            if (oc) oc.style.width = "100%";
            requestAnimationFrame(() => {
                el.classList.add("crm-mounted");
            });
        }
    }

    get className() {
        const result = super.className;
        result["crm-contact-form-page"] = true;
        return result;
    }

    getStatusLabel(status) {
        return STATUS_LABELS[status] || status || _t("Unknown");
    }

    translateLabel(label) {
        return label ? _t(label) : "";
    }

    getStatusClass(status) {
        return "crm-hdr-status-" + (status || "active");
    }

    // Navigation
    goToContacts() {
        this.actionService.doAction(
            "health_crm.action_crm_contact_list_native",
            { clearBreadcrumbs: true }
        );
    }

    goToDashboard() {
        this.actionService.doAction(
            "health_crm.action_crm_dashboard",
            { clearBreadcrumbs: true }
        );
    }

    // Actions
    actionBook() {
        const resId = this.model.root.resId;
        this.orm.call("crm.lead", "action_convert_to_booking", [[resId]]).then((action) => {
            if (action) this.actionService.doAction(action);
        });
    }

    actionLogLead() {
        this.orm.call("crm.lead", "action_log_as_lead", [[this.model.root.resId]]).then((action) => {
            if (action) this.actionService.doAction(action);
            this._loadHeaderData();
        });
    }

    actionEscalate() {
        this.orm.call("crm.lead", "action_escalate_contact", [[this.model.root.resId]]).then((action) => {
            if (action) this.actionService.doAction(action);
        });
    }

    actionMarkSpam() {
        this.orm.call("crm.lead", "action_mark_spam_and_home", [[this.model.root.resId]]).then((action) => {
            if (action) this.actionService.doAction(action);
            else this._loadHeaderData();
        });
    }
}

registry.category("views").add("crm_contact_form_view", {
    ...registry.category("views").get("form"),
    Controller: CrmContactFormController,
});
