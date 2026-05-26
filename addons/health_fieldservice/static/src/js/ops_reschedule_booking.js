/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const TIME_PERIODS = [
    { key: 'morning', label: 'Morning', icon: 'fa-sun-o', range: '7am – 12pm', startH: 7, endH: 12 },
    { key: 'afternoon', label: 'Afternoon', icon: 'fa-cloud', range: '12pm – 5pm', startH: 12, endH: 17 },
    { key: 'evening', label: 'Evening', icon: 'fa-moon-o', range: '5pm – 8pm', startH: 17, endH: 21 },
];

const DAY_NAMES = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];

class OpsRescheduleBooking extends Component {
    static template = "health_fieldservice.OpsRescheduleBooking";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const ctx = this.props.action?.context || {};
        this.bookingId = ctx.active_id || false;
        this.activeCenter = ctx.active_center || 'ops_center';

        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];

        this.state = useState({
            loading: true,
            booking: {},
            selectedDate: todayStr,
            calendarYear: today.getFullYear(),
            calendarMonth: today.getMonth(),
            timeOfDay: 'morning',
            selectedSlot: null,
            slots: [],
            slotsLoading: false,
            finetuneH: 7,
            finetuneM: 0,
            assignedStaffIds: [],
            staffList: [],
            isSubmitting: false,
            showConfirmation: false,
            result: {},
            validationErrors: [],
            durationHours: 1,
        });

        this.timePeriods = TIME_PERIODS;
        this.dayNames = DAY_NAMES;

        onWillStart(async () => {
            await this._loadBookingData();
        });
    }

    async _loadBookingData() {
        if (!this.bookingId) {
            this.state.loading = false;
            return;
        }
        try {
            const data = await this.orm.call("health.fieldservice.order", "get_reschedule_data", [this.bookingId]);
            this.state.booking = data;
            this.state.assignedStaffIds = data.assigned_staff_ids || [];
            this.state.staffList = data.staff_list || [];
            this.state.durationHours = data.duration_hours || 1;

            if (data.current_date) {
                this.state.selectedDate = data.current_date;
                const [y, m] = data.current_date.split('-').map(Number);
                this.state.calendarYear = y;
                this.state.calendarMonth = m - 1;
            }
            if (data.current_hour) {
                this.state.finetuneH = Math.floor(data.current_hour);
                this.state.finetuneM = Math.round((data.current_hour % 1) * 60);
                if (data.current_hour < 12) this.state.timeOfDay = 'morning';
                else if (data.current_hour < 17) this.state.timeOfDay = 'afternoon';
                else this.state.timeOfDay = 'evening';
            }
            await this.checkAvailability();
        } catch (e) {
            console.error('Failed to load booking data:', e);
        }
        this.state.loading = false;
    }

    // Calendar
    get calendarDays() {
        const year = this.state.calendarYear;
        const month = this.state.calendarMonth;
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        let startWeekday = firstDay.getDay() - 1;
        if (startWeekday < 0) startWeekday = 6;

        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];

        const days = [];
        for (let i = 0; i < startWeekday; i++) {
            days.push({ num: '', date: '', disabled: true, today: false, selected: false, empty: true });
        }
        for (let d = 1; d <= lastDay.getDate(); d++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const isPast = dateStr < todayStr;
            days.push({
                num: d,
                date: dateStr,
                disabled: isPast,
                today: dateStr === todayStr,
                selected: dateStr === this.state.selectedDate,
                empty: false,
            });
        }
        return days;
    }

    get calendarTitle() {
        const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'];
        return `${monthNames[this.state.calendarMonth]} ${this.state.calendarYear}`;
    }

    prevMonth() {
        if (this.state.calendarMonth === 0) { this.state.calendarMonth = 11; this.state.calendarYear--; }
        else { this.state.calendarMonth--; }
    }

    nextMonth() {
        if (this.state.calendarMonth === 11) { this.state.calendarMonth = 0; this.state.calendarYear++; }
        else { this.state.calendarMonth++; }
    }

    selectDate(day) {
        if (day.disabled || day.empty) return;
        this.state.selectedDate = day.date;
        this.state.selectedSlot = null;
        this.checkAvailability();
    }

    // Time slots
    selectTimeOfDay(key) { this.state.timeOfDay = key; }

    selectSlot(slot) {
        if (slot.patient_conflict) return;
        this.state.selectedSlot = slot;
        this.state.finetuneH = Math.floor(slot.hour);
        this.state.finetuneM = Math.round((slot.hour % 1) * 60);
    }

    getSlotClass(slot) {
        let cls = 'rsb-slot';
        if (this.state.selectedSlot && this.state.selectedSlot.time === slot.time) cls += ' rsb-slot--selected';
        else if (slot.patient_conflict) cls += ' rsb-slot--busy';
        else if (!slot.available) cls += ' rsb-slot--conflict';
        return cls;
    }

    get filteredSlots() {
        const period = TIME_PERIODS.find(p => p.key === this.state.timeOfDay);
        if (!period) return this.state.slots;
        return this.state.slots.filter(s => s.hour >= period.startH && s.hour < period.endH);
    }

    async checkAvailability() {
        if (!this.state.selectedDate) return;
        this.state.slotsLoading = true;
        try {
            const result = await this.orm.call(
                "health.fieldservice.order",
                "check_slot_availability",
                [this.state.booking.patient_id || false, this.state.selectedDate, this.state.booking.facility_id || false, this.state.assignedStaffIds.length > 0 ? this.state.assignedStaffIds : []]
            );
            this.state.slots = result.slots || [];
        } catch (e) {
            console.error('Availability check failed:', e);
            this.state.slots = [];
        }
        this.state.slotsLoading = false;
    }

    // Fine-tune time
    get finetuneHour() { return String(this.state.finetuneH).padStart(2, '0'); }
    get finetuneMinute() { return String(this.state.finetuneM).padStart(2, '0'); }
    get finetuneDisplay() {
        const h = this.state.finetuneH;
        const m = this.state.finetuneM;
        const ampm = h >= 12 ? 'PM' : 'AM';
        const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
        return `${h12}:${String(m).padStart(2, '0')} ${ampm}`;
    }
    get finetuneHourDecimal() { return this.state.finetuneH + this.state.finetuneM / 60; }

    adjustHour(delta) {
        let h = this.state.finetuneH + delta;
        if (h < 0) h = 23;
        if (h > 23) h = 0;
        this.state.finetuneH = h;
    }

    adjustMinute(delta) {
        let m = this.state.finetuneM + delta;
        if (m < 0) { m = 55; this.adjustHour(-1); }
        else if (m >= 60) { m = 0; this.adjustHour(1); }
        this.state.finetuneM = m;
    }

    // Staff
    isStaffAssigned(staffId) { return this.state.assignedStaffIds.includes(staffId); }

    toggleAssignedStaff(staffId) {
        const idx = this.state.assignedStaffIds.indexOf(staffId);
        if (idx >= 0) {
            this.state.assignedStaffIds.splice(idx, 1);
        } else {
            this.state.assignedStaffIds.push(staffId);
        }
        this.checkAvailability();
    }

    // Duration
    adjustDuration(delta) {
        let d = this.state.durationHours + delta;
        if (d < 0.5) d = 0.5;
        if (d > 12) d = 12;
        this.state.durationHours = d;
    }

    get durationDisplay() {
        const h = Math.floor(this.state.durationHours);
        const m = Math.round((this.state.durationHours - h) * 60);
        if (h === 0) return `${m} mins`;
        if (m === 0) return h === 1 ? '1 hour' : `${h} hours`;
        return `${h}h ${m}m`;
    }

    // Submit
    async confirmReschedule() {
        if (this.state.isSubmitting) return;
        const missing = [];
        if (!this.state.selectedDate) missing.push('Date');
        if (!this.state.selectedSlot && !this.state.finetuneH) missing.push('Time');
        if (missing.length > 0) {
            this.state.validationErrors = missing;
            return;
        }
        this.state.validationErrors = [];
        this.state.isSubmitting = true;

        try {
            const result = await this.orm.call(
                "health.fieldservice.order",
                "action_reschedule_from_wizard",
                [this.bookingId, this.state.selectedDate, this.finetuneHourDecimal, this.state.assignedStaffIds, this.state.durationHours]
            );
            if (result.success) {
                this.state.result = result;
                this.state.showConfirmation = true;
            } else {
                this.notification.add(result.error || _t("Failed to reschedule"), { type: "danger" });
            }
        } catch (e) {
            console.error('Reschedule error:', e);
            this.notification.add(_t("Could not reschedule booking"), { type: "danger" });
        }
        this.state.isSubmitting = false;
    }

    viewBooking() {
        const bookingId = this.state.result?.booking_id || this.bookingId;
        if (!bookingId) return;
        const ctx = { active_id: bookingId };
        if (this.activeCenter) ctx.active_center = this.activeCenter;
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_booking_detail',
            name: this.state.result.booking_name || _t('Booking'),
            target: 'current',
            context: ctx,
        }, { clearBreadcrumbs: true });
    }

    goBack() {
        const bookingId = this.bookingId;
        if (!bookingId) { window.history.back(); return; }
        const ctx = { active_id: bookingId };
        if (this.activeCenter) ctx.active_center = this.activeCenter;
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_booking_detail',
            name: this.state.booking.booking_name || _t('Booking'),
            target: 'current',
            context: ctx,
        }, { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("ops_reschedule_booking", OpsRescheduleBooking);
export default OpsRescheduleBooking;
