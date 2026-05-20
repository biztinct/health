/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ProductCatalogDialog } from "./product_catalog_dialog";

const SERVICE_LOCATION_MAP = {
    home_visit: { label: 'Patient Home', icon: 'fa-home', cls: 'home' },
    clinic_visit: { label: 'Clinic', icon: 'fa-hospital-o', cls: 'clinic' },
    consultation: { label: 'Clinic', icon: 'fa-hospital-o', cls: 'clinic' },
    telemedicine: { label: 'Online', icon: 'fa-laptop', cls: 'online' },
    emergency: { label: 'Patient Home', icon: 'fa-ambulance', cls: 'home' },
    follow_up: { label: 'Patient Home', icon: 'fa-home', cls: 'home' },
    preventive: { label: 'Clinic', icon: 'fa-hospital-o', cls: 'clinic' },
    rehabilitation: { label: 'Clinic', icon: 'fa-hospital-o', cls: 'clinic' },
    vaccination: { label: 'Clinic', icon: 'fa-hospital-o', cls: 'clinic' },
    diagnostic: { label: 'Clinic', icon: 'fa-hospital-o', cls: 'clinic' },
};

const TIME_PERIODS = [
    { key: 'morning', label: 'Morning', icon: 'fa-sun-o', range: '7am - 12pm', startH: 7, endH: 12 },
    { key: 'afternoon', label: 'Afternoon', icon: 'fa-cloud', range: '12pm - 5pm', startH: 12, endH: 17 },
    { key: 'evening', label: 'Evening', icon: 'fa-moon-o', range: '5pm - 8pm', startH: 17, endH: 21 },
];

const DAY_NAMES = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];

class OpsQuickBooking extends Component {
    static template = "health_fieldservice.OpsQuickBooking";
    static components = { ProductCatalogDialog };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialogService = useService("dialog");

        const context = this.props.action && this.props.action.context || {};
        this.patientId = context.active_id || context.default_patient_id || false;
        this.leadId = context.default_lead_id || false;
        this.activeCenter = context.active_center || false;

        this.timePeriods = TIME_PERIODS;
        this.dayNames = DAY_NAMES;

        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];

        this.state = useState({
            isLoading: true,
            isCreating: false,

            patient: {},
            serviceTypes: [],
            facilities: [],
            staffList: [],
            doctorList: [],
            products: [],
            productCategories: [],
            packages: [],
            preferredStaffId: false,

            serviceType: 'home_visit',
            durationHours: 2,
            facilityId: false,
            notes: '',

            selectedDate: todayStr,
            calendarYear: today.getFullYear(),
            calendarMonth: today.getMonth(),
            timeOfDay: 'morning',
            selectedSlot: null,
            slots: [],
            slotsLoading: false,
            finetuneH: 7,
            finetuneM: 0,

            staffId: false,
            assignedStaffIds: [],
            doctorId: false,

            selectedProducts: [],
            packageId: false,

            validationErrors: [],
            showConfirmation: false,
            creationResult: null,
        });

        onWillStart(async () => {
            await this.loadOptions();
        });
    }

    async loadOptions() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "health.fieldservice.order",
                "get_quick_booking_options",
                [],
                { patient_id: this.patientId }
            );
            this.state.serviceTypes = data.service_types || [];
            this.state.facilities = data.facilities || [];
            this.state.patient = data.patient || {};
            this.state.staffList = data.staff_list || [];
            this.state.packages = data.packages || [];
            this.state.preferredStaffId = data.preferred_staff_id || false;
            this.state.doctorList = data.doctor_list || [];
            this.state.products = data.products || [];
            this.state.productCategories = data.product_categories || [];
            if (data.facilities.length > 0 && !this.state.facilityId) {
                this.state.facilityId = data.facilities[0].id;
            }
            await this.checkAvailability();
        } catch (e) {
            console.error('Failed to load quick booking options:', e);
        }
        this.state.isLoading = false;
    }

    // =========================================================================
    // COMPUTED
    // =========================================================================

    get serviceLocation() {
        return SERVICE_LOCATION_MAP[this.state.serviceType] || SERVICE_LOCATION_MAP.home_visit;
    }

    get serviceLabel() {
        const st = this.state.serviceTypes.find(s => s.key === this.state.serviceType);
        return st ? st.label : '';
    }

    get facilityName() {
        const f = this.state.facilities.find(x => x.id === this.state.facilityId);
        return f ? f.name : '';
    }

    get selectedStaffName() {
        const s = this.state.staffList.find(x => x.id === this.state.staffId);
        return s ? s.name : '';
    }

    get selectedDoctorName() {
        const d = this.state.doctorList.find(x => x.id === this.state.doctorId);
        return d ? d.name : '';
    }

    get selectedPackage() {
        return this.state.packages.find(p => p.id === this.state.packageId) || null;
    }

    get hasProducts() {
        return this.state.selectedProducts.length > 0;
    }

    get productTotal() {
        return this.state.selectedProducts.reduce((sum, p) => sum + (p.price * p.qty), 0);
    }

    get hasServiceOrPackage() {
        return this.hasProducts || this.state.packageId;
    }

    get selectedDateDisplay() {
        if (!this.state.selectedDate) return '';
        const d = new Date(this.state.selectedDate + 'T00:00:00');
        return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    }

    get selectedTimeDisplay() {
        if (!this.state.selectedSlot) return '';
        return this.state.selectedSlot.time;
    }

    get summaryDateTime() {
        if (!this.state.selectedDate || !this.state.selectedSlot) return 'Not selected';
        const time = `${this.finetuneHour}:${this.finetuneMinute}`;
        return `${this.selectedDateDisplay}, ${time}`;
    }

    get filteredSlots() {
        const period = TIME_PERIODS.find(p => p.key === this.state.timeOfDay);
        if (!period) return this.state.slots;
        return this.state.slots.filter(s => s.hour >= period.startH && s.hour < period.endH);
    }

    get assignedStaffOptions() {
        if (this.state.assignedStaffIds.length === 0) return this.state.staffList;
        return this.state.staffList.filter(s => this.state.assignedStaffIds.includes(s.id));
    }

    formatCurrency(amount) {
        if (!amount) return '0 d';
        return Math.round(amount).toLocaleString('vi-VN') + ' d';
    }

    // =========================================================================
    // MINI CALENDAR
    // =========================================================================

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
        if (this.state.calendarMonth === 0) {
            this.state.calendarMonth = 11;
            this.state.calendarYear--;
        } else {
            this.state.calendarMonth--;
        }
    }

    nextMonth() {
        if (this.state.calendarMonth === 11) {
            this.state.calendarMonth = 0;
            this.state.calendarYear++;
        } else {
            this.state.calendarMonth++;
        }
    }

    selectDate(day) {
        if (day.disabled || day.empty) return;
        this.state.selectedDate = day.date;
        this.state.selectedSlot = null;
        this.checkAvailability();
    }

    // =========================================================================
    // SLOT AVAILABILITY
    // =========================================================================

    selectTimeOfDay(key) {
        this.state.timeOfDay = key;
    }

    selectSlot(slot) {
        if (slot.patient_conflict) return;
        this.state.selectedSlot = slot;
        this.state.finetuneH = Math.floor(slot.hour);
        this.state.finetuneM = Math.round((slot.hour % 1) * 60);
    }

    getSlotClass(slot) {
        let cls = 'qb-slot';
        if (this.state.selectedSlot && this.state.selectedSlot.time === slot.time) cls += ' qb-slot--selected';
        else if (slot.patient_conflict) cls += ' qb-slot--busy';
        else if (!slot.available) cls += ' qb-slot--conflict';
        return cls;
    }

    // Fine-tune time
    get finetuneHour() {
        return String(this.state.finetuneH).padStart(2, '0');
    }

    get finetuneMinute() {
        return String(this.state.finetuneM).padStart(2, '0');
    }

    get finetuneDisplay() {
        const h = this.state.finetuneH;
        const m = this.state.finetuneM;
        const suffix = h >= 12 ? 'PM' : 'AM';
        const h12 = h > 12 ? h - 12 : (h === 0 ? 12 : h);
        return `${h12}:${String(m).padStart(2, '0')} ${suffix}`;
    }

    get finetuneHourDecimal() {
        return this.state.finetuneH + this.state.finetuneM / 60;
    }

    adjustHour(delta) {
        let h = this.state.finetuneH + delta;
        if (h < 7) h = 7;
        if (h > 20) h = 20;
        this.state.finetuneH = h;
        this._syncSlotFromFinetune();
    }

    adjustMinute(delta) {
        let m = this.state.finetuneM + delta;
        if (m >= 60) {
            m -= 60;
            if (this.state.finetuneH < 20) this.state.finetuneH++;
        }
        if (m < 0) {
            m += 60;
            if (this.state.finetuneH > 7) this.state.finetuneH--;
        }
        this.state.finetuneM = m;
        this._syncSlotFromFinetune();
    }

    _syncSlotFromFinetune() {
        const h = this.state.finetuneH;
        const m = this.state.finetuneM;
        const hour = h + m / 60;
        const time = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
        this.state.selectedSlot = { time, hour, available: true, conflicts: [], patient_conflict: false };
    }

    async checkAvailability() {
        if (!this.state.selectedDate) return;
        this.state.slotsLoading = true;
        try {
            const result = await this.orm.call(
                "health.fieldservice.order",
                "check_slot_availability",
                [this.patientId || false, this.state.selectedDate, this.state.facilityId || false, this.state.assignedStaffIds.length > 0 ? this.state.assignedStaffIds : []]
            );
            this.state.slots = result.slots || [];
        } catch (e) {
            console.error('Availability check failed:', e);
            this.state.slots = [];
        }
        this.state.slotsLoading = false;
    }

    // =========================================================================
    // FORM HANDLERS
    // =========================================================================

    onServiceTypeChange(ev) { this.state.serviceType = ev.target.value; }
    onDurationChange(ev) { this.state.durationHours = parseFloat(ev.target.value) || 1; }
    onFacilityChange(ev) {
        this.state.facilityId = parseInt(ev.target.value) || false;
        this.checkAvailability();
    }
    onNotesChange(ev) { this.state.notes = ev.target.value; }
    onStaffChange(ev) { this.state.staffId = parseInt(ev.target.value) || false; }
    onDoctorChange(ev) { this.state.doctorId = parseInt(ev.target.value) || false; }
    onPackageChange(ev) { this.state.packageId = parseInt(ev.target.value) || false; }

    isStaffAssigned(staffId) {
        return this.state.assignedStaffIds.includes(staffId);
    }

    toggleAssignedStaff(staffId) {
        const idx = this.state.assignedStaffIds.indexOf(staffId);
        if (idx >= 0) {
            this.state.assignedStaffIds.splice(idx, 1);
            if (this.state.staffId === staffId) {
                this.state.staffId = this.state.assignedStaffIds.length > 0
                    ? this.state.assignedStaffIds[0] : false;
            }
        } else {
            this.state.assignedStaffIds.push(staffId);
            if (!this.state.staffId) {
                this.state.staffId = staffId;
            }
        }
        this.checkAvailability();
    }

    // =========================================================================
    // PRODUCTS
    // =========================================================================

    openServiceCatalog() {
        this.dialogService.add(ProductCatalogDialog, {
            products: this.state.products,
            categories: this.state.productCategories,
            selected: this.state.selectedProducts.map(p => ({ ...p })),
            onDone: (selections) => {
                this.state.selectedProducts.splice(0, this.state.selectedProducts.length, ...selections);
            },
        });
    }

    removeProduct(index) {
        this.state.selectedProducts.splice(index, 1);
    }

    updateProductQty(index, ev) {
        const qty = parseInt(ev.target.value) || 1;
        if (this.state.selectedProducts[index]) {
            this.state.selectedProducts[index].qty = Math.max(1, qty);
        }
    }

    // =========================================================================
    // NAVIGATION
    // =========================================================================

    navigateTo(page) {
        const actions = {
            dashboard: 'health_fieldservice.action_ops_command_center',
            bookings: 'health_fieldservice.action_ops_booking_list_native',
        };
        const actionId = actions[page];
        if (actionId) {
            this.action.doAction(actionId, { clearBreadcrumbs: true });
        }
    }

    goBack() {
        if (this.patientId) {
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'res.partner',
                res_id: this.patientId,
                views: [[false, 'form']],
                target: 'current',
                context: { form_view_ref: 'health_fieldservice.view_health_patient_form_ops' },
            }, { clearBreadcrumbs: true });
        } else {
            this.action.doAction('health_fieldservice.action_ops_booking_list_native', { clearBreadcrumbs: true });
        }
    }

    // =========================================================================
    // CREATE BOOKING
    // =========================================================================

    dismissValidation() {
        this.state.validationErrors = [];
    }

    async createBooking() {
        if (this.state.isCreating) return;

        const missing = [];
        if (!this.state.facilityId) missing.push('Facility');
        if (!this.hasServiceOrPackage) missing.push('Services or Package (add via Quote section)');
        if (!this.state.selectedDate) missing.push('Date');
        if (!this.state.selectedSlot) missing.push('Time slot');

        if (missing.length > 0) {
            this.state.validationErrors = missing;
            return;
        }
        this.state.validationErrors = [];
        this.state.isCreating = true;

        try {
            const productLines = this.state.selectedProducts.map(p => ({
                product_id: p.product_id,
                qty: p.qty,
            }));

            const result = await this.orm.call(
                "health.fieldservice.order",
                "action_create_from_quick_booking_owl",
                [{
                    patient_id: this.patientId || false,
                    lead_id: this.leadId || false,
                    service_type: this.state.serviceType,
                    duration_hours: this.state.durationHours,
                    time_hour: this.finetuneHourDecimal,
                    date: this.state.selectedDate,
                    facility_id: this.state.facilityId,
                    notes: this.state.notes,
                    product_lines: productLines.length > 0 ? productLines : null,
                    staff_id: this.state.staffId || false,
                    doctor_id: this.state.doctorId || false,
                    package_id: this.state.packageId || false,
                    assigned_staff_ids: this.state.assignedStaffIds.length > 0 ? this.state.assignedStaffIds : [],
                }]
            );

            if (result.success) {
                this.state.creationResult = result;
                this.state.showConfirmation = true;
            } else {
                this.notification.add(result.error || _t("Failed to create booking"), { type: "danger" });
            }
        } catch (e) {
            console.error('Create booking error:', e);
            this.notification.add(_t("Could not create booking"), { type: "danger" });
        }
        this.state.isCreating = false;
    }

    // =========================================================================
    // CONFIRMATION MODAL ACTIONS
    // =========================================================================

    viewBooking() {
        const bookingId = this.state.creationResult?.booking_id;
        if (!bookingId) return;
        const ctx = { active_id: bookingId };
        if (this.activeCenter) ctx.active_center = this.activeCenter;
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_booking_detail',
            name: this.state.creationResult.booking_name || _t('Booking'),
            target: 'current',
            context: ctx,
        }, { clearBreadcrumbs: true });
    }

    createAnother() {
        this.state.showConfirmation = false;
        this.state.creationResult = null;
        this.state.selectedSlot = null;
        this.state.notes = '';
        this.state.selectedProducts.splice(0, this.state.selectedProducts.length);
        this.state.packageId = false;
        this.state.validationErrors = [];
        this.checkAvailability();
    }

    async deleteBooking() {
        const result = this.state.creationResult;
        if (!result || !result.booking_id) return;
        try {
            await this.orm.call(
                "health.fieldservice.order",
                "cancel_recurring_bookings",
                [],
                { fso_ids: [result.booking_id] }
            );
            this.notification.add(_t("Booking deleted"), { type: "warning" });
            this.state.showConfirmation = false;
            this.state.creationResult = null;
        } catch (e) {
            console.error('Delete error:', e);
            this.notification.add(_t("Error deleting booking"), { type: "danger" });
        }
    }
}

registry.category("actions").add("ops_quick_booking", OpsQuickBooking);

export default OpsQuickBooking;
