/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class OpsServiceInProgress extends Component {
    static template = "health_fieldservice.OpsServiceInProgress";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const context = this.props.action && this.props.action.context || {};
        this.bookingId = context.active_id || context.default_booking_id || false;
        this._timerInterval = null;

        this.state = useState({
            isLoading: true,
            booking: {},
            patient: {},
            staff: null,
            timer: {},
            checklist: [],
            payment: {},
            timeline: [],

            elapsedSeconds: 0,
            timerDisplay: '00:00:00',

            vitals: {
                bp: '',
                hr: '',
                temp: '',
                spo2: '',
                weight: '',
                glucose: '',
            },
            clinicalNotes: '',
        });

        onWillStart(async () => {
            if (this.bookingId) {
                await this.loadData();
            }
        });

        onMounted(() => {
            this._startTimer();
        });

        onWillUnmount(() => {
            this._stopTimer();
        });
    }

    async loadData() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "health.fieldservice.order",
                "get_service_in_progress_data",
                [this.bookingId]
            );
            this.state.booking = data.booking || {};
            this.state.patient = data.patient || {};
            this.state.staff = data.staff || null;
            this.state.timer = data.timer || {};
            this.state.checklist = data.checklist || [];
            this.state.payment = data.payment || {};
            this.state.timeline = data.timeline || [];

            if (data.timer && data.timer.start_iso) {
                const start = new Date(data.timer.start_iso);
                const now = new Date();
                this.state.elapsedSeconds = Math.max(0, Math.floor((now - start) / 1000));
            }
            this._updateTimerDisplay();
        } catch (e) {
            console.error('Failed to load service data:', e);
            this.notification.add(_t("Error loading service data"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    _startTimer() {
        this._timerInterval = setInterval(() => {
            this.state.elapsedSeconds++;
            this._updateTimerDisplay();
        }, 1000);
    }

    _stopTimer() {
        if (this._timerInterval) {
            clearInterval(this._timerInterval);
            this._timerInterval = null;
        }
    }

    _updateTimerDisplay() {
        const s = this.state.elapsedSeconds;
        const h = String(Math.floor(s / 3600)).padStart(2, '0');
        const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
        const sec = String(s % 60).padStart(2, '0');
        this.state.timerDisplay = `${h}:${m}:${sec}`;
    }

    formatCurrency(amount) {
        if (!amount) return '0 ₫';
        return Math.round(amount).toLocaleString('vi-VN') + ' ₫';
    }

    get completedCount() {
        return this.state.checklist.filter(c => c.done).length;
    }

    get totalChecklistCount() {
        return this.state.checklist.length;
    }

    get progressPercent() {
        if (!this.totalChecklistCount) return 0;
        return Math.round((this.completedCount / this.totalChecklistCount) * 100);
    }

    toggleCheckItem(index) {
        const item = this.state.checklist[index];
        if (item) {
            item.done = !item.done;
            if (item.done) {
                const now = new Date();
                item.time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
            } else {
                item.time = '';
            }
        }
    }

    onVitalChange(field, ev) {
        this.state.vitals[field] = ev.target.value;
    }

    onNotesChange(ev) {
        this.state.clinicalNotes = ev.target.value;
    }

    goBack() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.fieldservice.order',
            res_id: this.bookingId,
            views: [[false, 'form']],
            target: 'fullscreen',
            context: { form_view_ref: 'health_fieldservice.view_health_fso_form_ops' },
        }, { clearBreadcrumbs: true });
    }

    openClientProfile() {
        if (!this.state.patient.id) return;
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_client_profile',
            name: this.state.patient.name,
            context: { active_id: this.state.patient.id },
        }, { clearBreadcrumbs: true });
    }

    collectPayment() {
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_payment_collection',
            name: _t('Collect Payment'),
            context: { active_id: this.bookingId },
        }, { clearBreadcrumbs: true });
    }

    async saveDraft() {
        try {
            const notes = this.state.clinicalNotes;
            if (notes) {
                await this.orm.call("health.fieldservice.order", "message_post", [this.bookingId], {
                    body: `Clinical notes: ${notes}`,
                    subject: 'Service Notes (Draft)',
                });
            }
            this.notification.add(_t("Draft saved"), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Could not save draft"), { type: "danger" });
        }
    }

    async completeService() {
        try {
            await this.orm.call("health.fieldservice.order", "action_complete_service", [this.bookingId]);
            this._stopTimer();
            this.notification.add(_t("Service completed!"), { type: "success" });
            this.goBack();
        } catch (e) {
            this.notification.add(_t("Could not complete service"), { type: "danger" });
        }
    }

    // Sidebar
    navigateTo(page) {
        const actions = {
            dashboard: 'health_fieldservice.action_ops_command_center',
            bookings: 'health_fieldservice.action_ops_booking_queue',
            clients: 'health_fieldservice.action_ops_client_list',
            recurring: 'health_fieldservice.action_ops_recurring_booking',
            staff: 'health_fieldservice.action_ops_staff_roster',
            calendar: 'health_fieldservice.action_ops_calendar',
            workload: 'health_fieldservice.action_staff_workload_dashboard',
        };
        if (actions[page]) {
            this.action.doAction(actions[page], { clearBreadcrumbs: true });
        }
    }

    navigateHome() {
        window.location.href = '/web';
    }
}

registry.category("actions").add("ops_service_in_progress", OpsServiceInProgress);

export default OpsServiceInProgress;
