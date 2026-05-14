/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class OpsRecurringBooking extends Component {
    static template = "health_fieldservice.OpsRecurringBooking";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const context = this.props.action && this.props.action.context || {};
        this.patientId = context.active_id || context.default_patient_id || false;

        this.state = useState({
            isLoading: true,
            isCreating: false,
            patient: {},
            serviceTypes: [],
            facilities: [],
            preview: [],

            serviceType: 'home_visit',
            durationHours: 2,
            timeHour: 9,
            facilityId: false,
            pattern: 'weekly',
            selectedDays: [0, 3],
            startDate: this._getNextMonday(),
            occurrences: 8,
            notes: '',
        });

        onWillStart(async () => {
            await this.loadOptions();
        });
    }

    _getNextMonday() {
        const d = new Date();
        const day = d.getDay();
        const diff = day === 0 ? 1 : (8 - day);
        d.setDate(d.getDate() + diff);
        return d.toISOString().split('T')[0];
    }

    async loadOptions() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "health.fieldservice.order",
                "get_recurring_booking_options",
                [],
                { patient_id: this.patientId }
            );
            this.state.serviceTypes = data.service_types || [];
            this.state.facilities = data.facilities || [];
            this.state.patient = data.patient || {};
            if (data.facilities.length > 0 && !this.state.facilityId) {
                this.state.facilityId = data.facilities[0].id;
            }
            await this.refreshPreview();
        } catch (e) {
            console.error('Failed to load recurring booking options:', e);
        }
        this.state.isLoading = false;
    }

    async refreshPreview() {
        if (!this.state.startDate || this.state.selectedDays.length === 0) {
            this.state.preview = [];
            return;
        }
        try {
            const preview = await this.orm.call(
                "health.fieldservice.order",
                "get_recurring_preview",
                [],
                {
                    patient_id: this.patientId || false,
                    pattern: this.state.pattern,
                    selected_days: this.state.selectedDays,
                    start_date: this.state.startDate,
                    occurrences: this.state.occurrences,
                    time_hour: this.state.timeHour,
                }
            );
            this.state.preview = preview || [];
        } catch (e) {
            console.error('Preview error:', e);
            this.state.preview = [];
        }
    }

    formatCurrency(amount) {
        if (!amount) return '0 ₫';
        return Math.round(amount).toLocaleString('vi-VN') + ' ₫';
    }

    get conflictCount() {
        return this.state.preview.filter(p => p.conflict).length;
    }

    get previewSummary() {
        const count = this.state.preview.length;
        if (!count) return 'Select days and date range';
        const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const days = this.state.selectedDays.map(d => dayNames[d]).join(' & ');
        return `${count} bookings on ${days}`;
    }

    get serviceLabel() {
        const st = this.state.serviceTypes.find(s => s.key === this.state.serviceType);
        return st ? st.label : '';
    }

    get dateRange() {
        if (!this.state.preview.length) return '';
        const first = this.state.preview[0];
        const last = this.state.preview[this.state.preview.length - 1];
        return `${first.date} — ${last.date}`;
    }

    // Pattern selection
    selectPattern(p) {
        this.state.pattern = p;
        this.refreshPreview();
    }

    // Day toggling
    toggleDay(dayIndex) {
        const idx = this.state.selectedDays.indexOf(dayIndex);
        if (idx >= 0) {
            this.state.selectedDays.splice(idx, 1);
        } else {
            this.state.selectedDays.push(dayIndex);
            this.state.selectedDays.sort();
        }
        this.refreshPreview();
    }

    isDaySelected(dayIndex) {
        return this.state.selectedDays.includes(dayIndex);
    }

    // Form handlers
    onServiceTypeChange(ev) {
        this.state.serviceType = ev.target.value;
    }

    onDurationChange(ev) {
        this.state.durationHours = parseFloat(ev.target.value) || 1;
    }

    onTimeChange(ev) {
        this.state.timeHour = parseInt(ev.target.value) || 9;
        this.refreshPreview();
    }

    onFacilityChange(ev) {
        this.state.facilityId = parseInt(ev.target.value) || false;
    }

    onStartDateChange(ev) {
        this.state.startDate = ev.target.value;
        this.refreshPreview();
    }

    onOccurrencesChange(ev) {
        this.state.occurrences = parseInt(ev.target.value) || 1;
        this.refreshPreview();
    }

    onNotesChange(ev) {
        this.state.notes = ev.target.value;
    }

    goBack() {
        if (this.patientId) {
            this.action.doAction({
                type: 'ir.actions.client',
                tag: 'ops_client_profile',
                name: this.state.patient.name || 'Client',
                context: { active_id: this.patientId },
            }, { clearBreadcrumbs: true });
        } else {
            this.action.doAction('health_fieldservice.action_ops_booking_queue', { clearBreadcrumbs: true });
        }
    }

    async createBookings() {
        if (this.state.isCreating) return;
        if (!this.state.selectedDays.length) {
            this.notification.add(_t("Please select at least one day"), { type: "warning" });
            return;
        }
        if (!this.state.facilityId) {
            this.notification.add(_t("Please select a facility"), { type: "warning" });
            return;
        }

        this.state.isCreating = true;
        try {
            const result = await this.orm.call(
                "health.fieldservice.order",
                "action_create_recurring_from_owl",
                [],
                {
                    patient_id: this.patientId || false,
                    service_type: this.state.serviceType,
                    duration_hours: this.state.durationHours,
                    time_hour: this.state.timeHour,
                    facility_id: this.state.facilityId,
                    pattern: this.state.pattern,
                    selected_days: this.state.selectedDays,
                    start_date: this.state.startDate,
                    occurrences: this.state.occurrences,
                    notes: this.state.notes,
                }
            );

            if (result.success) {
                this.notification.add(
                    _t("%s recurring bookings created!", result.count),
                    { type: "success" }
                );
                this.action.doAction('health_fieldservice.action_ops_booking_queue', { clearBreadcrumbs: true });
            } else {
                this.notification.add(result.error || _t("Failed to create bookings"), { type: "danger" });
            }
        } catch (e) {
            console.error('Create recurring error:', e);
            this.notification.add(_t("Could not create recurring bookings"), { type: "danger" });
        }
        this.state.isCreating = false;
    }

    // Sidebar
}

registry.category("actions").add("ops_recurring_booking", OpsRecurringBooking);

export default OpsRecurringBooking;
