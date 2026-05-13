/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onPatched, useRef } from "@odoo/owl";

export class OpsBookingFormController extends FormController {
    static template = "health_fieldservice.OpsBookingFormView";

    setup() {
        super.setup(...arguments);

        const sessionName = (window.odoo && window.odoo.session_info && window.odoo.session_info.name) || '';
        this.currentUserName = sessionName || 'Operations Manager';
        this.currentUserInitials = this.currentUserName
            .split(' ').filter(p => p).map(p => p[0]).join('').substring(0, 2).toUpperCase() || 'OM';

        this.rootRef = useRef("root");

        onMounted(() => {
            const el = this.rootRef.el || document.querySelector('.ops-booking-form-page');
            if (el) {
                const formContainer = el.querySelector('.o_form_view_container');
                const oContent = el.querySelector('.o_content');
                if (formContainer) formContainer.style.width = '100%';
                if (oContent) oContent.style.width = '100%';

                requestAnimationFrame(() => {
                    el.classList.add('ops-mounted');
                });
            }
        });

        onPatched(() => {
            const el = this.rootRef.el || document.querySelector('.ops-booking-form-page');
            if (el) {
                const formContainer = el.querySelector('.o_form_view_container');
                const oContent = el.querySelector('.o_content');
                if (formContainer) formContainer.style.width = '100%';
                if (oContent) oContent.style.width = '100%';
            }
        });
    }

    get className() {
        const result = super.className;
        result["ops-booking-form-page"] = true;
        return result;
    }

    navigateTo(page) {
        const actions = {
            dashboard: 'health_fieldservice.action_ops_command_center',
            bookings: 'health_fieldservice.action_ops_booking_queue',
            clients: 'health_fieldservice.action_ops_client_list',
            recurring: 'health_fieldservice.action_ops_recurring_booking',
            staff: 'health_fieldservice.action_ops_staff_roster',
            calendar: 'health_fieldservice.action_ops_calendar',
            workload: 'health_fieldservice.action_staff_workload_dashboard',
            analytics: 'health_fieldservice.action_staff_workload_dashboard',
        };
        if (actions[page]) {
            this.actionService.doAction(actions[page], { clearBreadcrumbs: true });
        }
    }

    navigateHome() {
        window.location.href = '/web';
    }

    goToBookings() {
        this.actionService.doAction('health_fieldservice.action_ops_booking_queue',
            { clearBreadcrumbs: true });
    }

    openAssignStaff() {
        this.actionService.doAction({
            type: 'ir.actions.client',
            tag: 'ops_staff_assignment',
            name: _t('Assign Staff'),
            context: { active_id: this.model.root.resId },
        }, { clearBreadcrumbs: true });
    }

    collectPayment() {
        this.actionService.doAction({
            type: 'ir.actions.client',
            tag: 'ops_payment_collection',
            name: _t('Collect Payment'),
            context: { active_id: this.model.root.resId },
        }, { clearBreadcrumbs: true });
    }

    openServiceInProgress() {
        this.actionService.doAction({
            type: 'ir.actions.client',
            tag: 'ops_service_in_progress',
            name: _t('Active Service'),
            context: { active_id: this.model.root.resId },
        }, { clearBreadcrumbs: true });
    }
}

registry.category("views").add("ops_booking_form", {
    ...registry.category("views").get("form"),
    Controller: OpsBookingFormController,
});
