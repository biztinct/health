/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useState, onMounted, onPatched, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class OpsClientProfileFormController extends FormController {
    static template = "health_fieldservice.OpsClientProfileFormView";

    setup() {
        super.setup(...arguments);
        this.rootRef = useRef("root");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.profileState = useState({
            profile: {},
            stats: {},
            isLoaded: false,
        });

        onMounted(() => {
            this._adjustLayout();
            this._loadProfileData();
        });
        onPatched(() => {
            this._adjustLayout();
        });
    }

    async _loadProfileData() {
        const resId = this.model.root.resId;
        if (!resId) return;
        try {
            const data = await this.orm.call(
                "res.partner",
                "get_client_profile_data",
                [resId]
            );
            this.profileState.profile = data.profile || {};
            this.profileState.stats = data.stats || {};
            this.profileState.isLoaded = true;
        } catch (e) {
            console.error("Failed to load profile data:", e);
        }
    }

    async saveButtonClicked(params) {
        const res = await super.saveButtonClicked(params);
        await this._loadProfileData();
        return res;
    }

    _adjustLayout() {
        const el = this.rootRef.el;
        if (el) {
            const fc = el.querySelector('.o_form_view_container');
            const oc = el.querySelector('.o_content');
            if (fc) fc.style.width = '100%';
            if (oc) oc.style.width = '100%';
            requestAnimationFrame(() => {
                el.classList.add('ops-mounted');
            });
        }
    }

    get className() {
        const result = super.className;
        result["ops-client-profile-form-page"] = true;
        return result;
    }

    formatCurrency(amount) {
        if (!amount) return '0';
        if (amount >= 1000000) {
            return (amount / 1000000).toFixed(1) + 'M';
        }
        return amount.toLocaleString('vi-VN');
    }

    goToClients() {
        this.actionService.doAction(
            'health_fieldservice.action_ops_client_list_native',
            { clearBreadcrumbs: true }
        );
    }

    navigateTo(page) {
        const routes = {
            dashboard: 'health_fieldservice.action_ops_command_center',
        };
        if (routes[page]) {
            this.actionService.doAction(routes[page], { clearBreadcrumbs: true });
        }
    }

    openCreateBooking() {
        this.doPartnerAction('action_open_quick_booking_owl');
    }

    async doPartnerAction(methodName) {
        const resId = this.model.root.resId;
        if (!resId) return;
        try {
            const action = await this.orm.call("res.partner", methodName, [resId]);
            if (action) {
                this.actionService.doAction(action);
            }
        } catch (e) {
            this.notification.add(
                _t("Action not available. The required module may not be installed."),
                { type: "warning" }
            );
        }
    }

    onCallClient() {
        const phone = this.profileState.profile.phone;
        if (phone) {
            window.open(`tel:${phone}`, '_self');
        }
    }

    onSmsClient() {
        const phone = this.profileState.profile.phone;
        if (phone) {
            window.open(`sms:${phone}`, '_self');
        }
    }

    onEmailClient() {
        const email = this.profileState.profile.email;
        if (email) {
            window.open(`mailto:${email}`, '_self');
        }
    }
}

registry.category("views").add("ops_client_profile_form", {
    ...registry.category("views").get("form"),
    Controller: OpsClientProfileFormController,
});
