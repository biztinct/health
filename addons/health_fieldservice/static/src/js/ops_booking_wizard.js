/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const SERVICE_OPTIONS = [
    { key: 'home_visit', name: 'Home Visit', desc: 'Staff travels to client\'s location', price: '2,000,000', icon: 'fa-house-medical', iconClass: 'hv', location: 'home' },
    { key: 'clinic_visit', name: 'Clinic Visit', desc: 'Client visits our facility', price: '1,200,000', icon: 'fa-hospital', iconClass: 'cv', location: 'clinic' },
    { key: 'consultation', name: 'Consultation', desc: 'Video or phone consultation', price: '500,000', icon: 'fa-video', iconClass: 'consult', location: 'online' },
    { key: 'follow_up', name: 'Follow-up', desc: 'Post-visit check-in', price: '800,000', icon: 'fa-user-check', iconClass: 'fu', location: 'home' },
    { key: 'emergency', name: 'Emergency', desc: 'Urgent medical response', price: '3,500,000', icon: 'fa-truck-medical', iconClass: 'em', location: 'home' },
    { key: 'telemedicine', name: 'Telemedicine', desc: 'Online/remote consultation', price: '400,000', icon: 'fa-laptop-medical', iconClass: 'tm', location: 'online' },
    { key: 'preventive', name: 'Preventive Care', desc: 'Routine health checkup', price: '1,500,000', icon: 'fa-shield-heart', iconClass: 'pv', location: 'home' },
    { key: 'rehabilitation', name: 'Rehabilitation', desc: 'Physical therapy sessions', price: '1,800,000', icon: 'fa-person-walking', iconClass: 'rh', location: 'home' },
];

const DURATION_OPTIONS = [
    { value: 60, label: '1 hour' },
    { value: 120, label: '2 hours' },
    { value: 180, label: '3 hours' },
    { value: 240, label: 'Half day (4 hours)' },
    { value: 480, label: 'Full day (8 hours)' },
];

const PRIORITY_OPTIONS = [
    { value: '0', label: 'Low' },
    { value: '1', label: 'Normal' },
    { value: '2', label: 'High' },
    { value: '3', label: 'Urgent' },
];

const COMMISSION_DURATION_OPTIONS = [
    { value: 'one_time', label: 'One Time' },
    { value: '30_days', label: '30 Days' },
];

function generateTimeSlots() {
    const morning = [];
    const afternoon = [];
    const evening = [];
    for (let h = 6; h < 12; h++) {
        morning.push({ hour: h, minute: 0, label: `${String(h).padStart(2,'0')}:00`, value: h });
        morning.push({ hour: h, minute: 30, label: `${String(h).padStart(2,'0')}:30`, value: h + 0.5 });
    }
    for (let h = 12; h < 18; h++) {
        afternoon.push({ hour: h, minute: 0, label: `${String(h).padStart(2,'0')}:00`, value: h });
        afternoon.push({ hour: h, minute: 30, label: `${String(h).padStart(2,'0')}:30`, value: h + 0.5 });
    }
    for (let h = 18; h < 22; h++) {
        evening.push({ hour: h, minute: 0, label: `${String(h).padStart(2,'0')}:00`, value: h });
        evening.push({ hour: h, minute: 30, label: `${String(h).padStart(2,'0')}:30`, value: h + 0.5 });
    }
    return { morning, afternoon, evening };
}

class OpsBookingWizard extends Component {
    static template = "health_fieldservice.OpsBookingWizard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.serviceOptions = SERVICE_OPTIONS;
        this.durationOptions = DURATION_OPTIONS;
        this.priorityOptions = PRIORITY_OPTIONS;
        this.commissionDurationOptions = COMMISSION_DURATION_OPTIONS;

        const allSlots = generateTimeSlots();
        this.morningSlots = allSlots.morning;
        this.afternoonSlots = allSlots.afternoon;
        this.eveningSlots = allSlots.evening;

        this.state = useState({
            step: 1,
            isSubmitting: false,

            // Step 1: Client
            clientSearch: '',
            clientResults: [],
            showResults: false,
            selectedClient: null,

            // Step 2: Service
            serviceType: 'home_visit',
            serviceCategory: '',
            serviceSubcategory: '',
            serviceLocation: 'home',
            priority: '1',
            serviceNotes: '',
            packageId: false,
            packages: [],
            // Commission
            commissionDueTo: false,
            commissionDueToName: '',
            commissionPercentage: 0,
            commissionDuration: 'one_time',
            serviceFeeVnd: 0,
            // Commission partner search
            commissionSearch: '',
            commissionResults: [],
            showCommissionResults: false,

            // Step 3: Schedule
            bookingDate: this.getTomorrowISO(),
            duration: 120,
            selectedTime: null,
            timeTab: 'morning',
            specialInstructions: '',
            catchmentProvinceId: false,
            facilityId: false,
            facilities: [],
            catchmentProvinces: [],

            // Step 4: Confirm
            paymentType: 'pay_after',
            sendSms: true,
            sendEmail: true,
            sendZalo: false,
        });

        onWillStart(async () => {
            await Promise.all([
                this.loadFacilities(),
                this.loadCatchmentProvinces(),
            ]);
        });
    }

    getTomorrowISO() {
        const d = new Date();
        d.setDate(d.getDate() + 1);
        return d.toISOString().split('T')[0];
    }

    // ===== STEP NAVIGATION =====

    get stepInfo() {
        return [
            { num: 1, name: 'Client', desc: 'Select or create' },
            { num: 2, name: 'Service', desc: 'Choose service type' },
            { num: 3, name: 'Schedule', desc: 'Date & time' },
            { num: 4, name: 'Confirm', desc: 'Review & book' },
        ];
    }

    getStepClass(stepNum) {
        if (stepNum < this.state.step) return 'step completed';
        if (stepNum === this.state.step) return 'step active';
        return 'step';
    }

    canGoNext() {
        switch (this.state.step) {
            case 1: return !!this.state.selectedClient;
            case 2: return !!this.state.serviceType;
            case 3: return this.state.selectedTime !== null && !!this.state.bookingDate && !!this.state.facilityId;
            case 4: return true;
            default: return false;
        }
    }

    nextStep() {
        if (!this.canGoNext()) {
            const msgs = {
                1: _t('Please select a client first.'),
                2: _t('Please select a service type.'),
                3: _t('Please select date, facility, and time.'),
            };
            this.notification.add(msgs[this.state.step] || '', { type: 'warning' });
            return;
        }
        if (this.state.step < 4) {
            this.state.step++;
        } else {
            this.confirmBooking();
        }
    }

    prevStep() {
        if (this.state.step > 1) this.state.step--;
    }

    // ===== STEP 1: CLIENT =====

    async onClientSearchInput(ev) {
        const query = ev.target.value.trim();
        this.state.clientSearch = ev.target.value;
        if (query.length < 2) {
            this.state.clientResults = [];
            this.state.showResults = false;
            return;
        }
        try {
            const results = await this.orm.searchRead(
                "res.partner",
                ['&', ('is_patient', '=', true), '|', '|',
                    ('name', 'ilike', query), ('mobile', 'ilike', query), ('patient_code', 'ilike', query)],
                ['id', 'name', 'mobile', 'patient_code', 'catchment_province_id', 'primary_facility_id'],
                { limit: 8, order: 'name asc' }
            );
            this.state.clientResults = results;
            this.state.showResults = results.length > 0;
        } catch (e) {
            console.error('Client search failed:', e);
        }
    }

    onClientSearchFocus() {
        if (this.state.clientResults.length > 0) this.state.showResults = true;
    }

    onClientSearchBlur() {
        setTimeout(() => { this.state.showResults = false; }, 250);
    }

    selectClient(client) {
        this.state.selectedClient = client;
        this.state.clientSearch = client.name;
        this.state.showResults = false;
        if (client.primary_facility_id) {
            this.state.facilityId = client.primary_facility_id[0];
        }
        if (client.catchment_province_id) {
            this.state.catchmentProvinceId = client.catchment_province_id[0];
        }
        this.loadClientPackages(client.id);
    }

    clearClient() {
        this.state.selectedClient = null;
        this.state.clientSearch = '';
        this.state.packages = [];
        this.state.packageId = false;
    }

    getInitials(name) {
        if (!name) return '?';
        return name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase();
    }

    async loadClientPackages(clientId) {
        try {
            const packages = await this.orm.searchRead(
                "health.prepaid.package",
                [['patient_id', '=', clientId], ['state', '=', 'active']],
                ['id', 'name', 'remaining_sessions'],
                { limit: 10 }
            );
            this.state.packages = packages;
        } catch {
            this.state.packages = [];
        }
    }

    // ===== STEP 2: SERVICE =====

    selectService(key) {
        this.state.serviceType = key;
        const svc = this.serviceOptions.find(s => s.key === key);
        if (svc) this.state.serviceLocation = svc.location;
    }

    isServiceSelected(key) {
        return this.state.serviceType === key;
    }

    onPriorityChange(ev) { this.state.priority = ev.target.value; }
    onSubTypeChange(ev) { this.state.serviceSubcategory = ev.target.value; }
    onPackageChange(ev) { this.state.packageId = ev.target.value ? parseInt(ev.target.value) : false; }
    onCategoryChange(ev) { this.state.serviceCategory = ev.target.value; }
    onServiceNotesChange(ev) { this.state.serviceNotes = ev.target.value; }
    onServiceLocationChange(ev) { this.state.serviceLocation = ev.target.value; }

    // Commission
    onCommissionPercentageChange(ev) { this.state.commissionPercentage = parseFloat(ev.target.value) || 0; }
    onCommissionDurationChange(ev) { this.state.commissionDuration = ev.target.value; }
    onServiceFeeChange(ev) { this.state.serviceFeeVnd = parseFloat(ev.target.value) || 0; }

    async onCommissionSearchInput(ev) {
        const query = ev.target.value.trim();
        this.state.commissionSearch = ev.target.value;
        if (query.length < 2) {
            this.state.commissionResults = [];
            this.state.showCommissionResults = false;
            return;
        }
        try {
            const results = await this.orm.searchRead(
                "res.partner",
                [('name', 'ilike', query)],
                ['id', 'name'],
                { limit: 5, order: 'name asc' }
            );
            this.state.commissionResults = results;
            this.state.showCommissionResults = results.length > 0;
        } catch { this.state.commissionResults = []; }
    }

    onCommissionSearchBlur() {
        setTimeout(() => { this.state.showCommissionResults = false; }, 250);
    }

    selectCommissionPartner(partner) {
        this.state.commissionDueTo = partner.id;
        this.state.commissionDueToName = partner.name;
        this.state.commissionSearch = partner.name;
        this.state.showCommissionResults = false;
    }

    clearCommissionPartner() {
        this.state.commissionDueTo = false;
        this.state.commissionDueToName = '';
        this.state.commissionSearch = '';
    }

    // ===== STEP 3: SCHEDULE =====

    async loadFacilities() {
        try {
            const facilities = await this.orm.searchRead(
                "health.facility", [['active', '=', true]],
                ['id', 'name', 'timezone', 'catchment_province_id'],
                { order: 'name asc' }
            );
            this.state.facilities = facilities;
            if (facilities.length === 1) this.state.facilityId = facilities[0].id;
        } catch (e) { console.error('Failed to load facilities:', e); }
    }

    async loadCatchmentProvinces() {
        try {
            const provinces = await this.orm.searchRead(
                "health.catchment.province", [],
                ['id', 'name', 'timezone'],
                { order: 'name asc' }
            );
            this.state.catchmentProvinces = provinces;
        } catch (e) { console.error('Failed to load provinces:', e); }
    }

    get filteredFacilities() {
        if (!this.state.catchmentProvinceId) return this.state.facilities;
        return this.state.facilities.filter(f =>
            f.catchment_province_id && f.catchment_province_id[0] === this.state.catchmentProvinceId
        );
    }

    onProvinceChange(ev) {
        this.state.catchmentProvinceId = ev.target.value ? parseInt(ev.target.value) : false;
        if (this.state.facilityId) {
            const f = this.state.facilities.find(f => f.id === this.state.facilityId);
            if (f && f.catchment_province_id && f.catchment_province_id[0] !== this.state.catchmentProvinceId) {
                this.state.facilityId = false;
            }
        }
    }

    onFacilityChange(ev) {
        this.state.facilityId = ev.target.value ? parseInt(ev.target.value) : false;
    }

    onDateChange(ev) {
        this.state.bookingDate = ev.target.value;
        this.state.selectedTime = null;
    }

    onDurationChange(ev) { this.state.duration = parseInt(ev.target.value); }

    setTimeTab(tab) { this.state.timeTab = tab; }

    get activeTimeSlots() {
        switch (this.state.timeTab) {
            case 'morning': return this.morningSlots;
            case 'afternoon': return this.afternoonSlots;
            case 'evening': return this.eveningSlots;
            default: return this.morningSlots;
        }
    }

    selectTimeSlot(slot) {
        this.state.selectedTime = slot.value;
    }

    isTimeSelected(slot) {
        return this.state.selectedTime === slot.value;
    }

    getTimeSlotClass(slot) {
        let cls = 'bw-time-slot';
        if (this.isTimeSelected(slot)) cls += ' selected';
        return cls;
    }

    get selectedTimeLabel() {
        if (this.state.selectedTime === null) return '';
        const h = Math.floor(this.state.selectedTime);
        const m = (this.state.selectedTime % 1) * 60;
        return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
    }

    onInstructionsChange(ev) { this.state.specialInstructions = ev.target.value; }

    // ===== STEP 4: CONFIRM =====

    selectPayment(type) { this.state.paymentType = type; }
    toggleSms() { this.state.sendSms = !this.state.sendSms; }
    toggleEmail() { this.state.sendEmail = !this.state.sendEmail; }
    toggleZalo() { this.state.sendZalo = !this.state.sendZalo; }

    get selectedServiceOption() {
        return this.serviceOptions.find(s => s.key === this.state.serviceType) || this.serviceOptions[0];
    }

    get selectedFacilityName() {
        const f = this.state.facilities.find(f => f.id === this.state.facilityId);
        return f ? f.name : '';
    }

    get selectedProvinceName() {
        const p = this.state.catchmentProvinces.find(p => p.id === this.state.catchmentProvinceId);
        return p ? p.name : '';
    }

    get summaryDateTime() {
        if (!this.state.bookingDate || this.state.selectedTime === null) return '';
        const d = new Date(this.state.bookingDate + 'T00:00:00');
        const dateStr = d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
        const startH = Math.floor(this.state.selectedTime);
        const startM = Math.round((this.state.selectedTime % 1) * 60);
        const endMinutes = this.state.selectedTime * 60 + this.state.duration;
        const endH = Math.floor(endMinutes / 60);
        const endM = Math.round(endMinutes % 60);
        const start = `${String(startH).padStart(2,'0')}:${String(startM).padStart(2,'0')}`;
        const end = `${String(endH).padStart(2,'0')}:${String(endM).padStart(2,'0')}`;
        return `${dateStr} • ${start} — ${end}`;
    }

    get durationLabel() {
        const opt = this.durationOptions.find(d => d.value === this.state.duration);
        return opt ? opt.label : this.state.duration + ' min';
    }

    get serviceLocationLabel() {
        const map = {
            home: _t('Patient Home'),
            clinic: _t('Clinic'),
            hospital: _t('Hospital'),
            nursing_home: _t('Nursing Home'),
            office: _t('Office'),
            online: _t('Online/Telemedicine'),
            other: _t('Other'),
        };
        return map[this.state.serviceLocation] || this.state.serviceLocation;
    }

    get priorityLabel() {
        const opt = this.priorityOptions.find(p => p.value === this.state.priority);
        return opt ? opt.label : 'Normal';
    }

    formatCurrency(amount) {
        if (!amount) return '0 ₫';
        return new Intl.NumberFormat('vi-VN').format(amount) + ' ₫';
    }

    // ===== CREATE BOOKING =====

    async confirmBooking() {
        if (this.state.isSubmitting) return;
        this.state.isSubmitting = true;

        try {
            const client = this.state.selectedClient;
            const facility = this.state.facilities.find(f => f.id === this.state.facilityId);
            const tz = (facility && facility.timezone) || 'Asia/Ho_Chi_Minh';

            const vals = {
                patient_id: client.id,
                service_type: this.state.serviceType,
                service_location: this.state.serviceLocation,
                scheduled_duration: this.state.duration,
                priority: this.state.priority,
                intake_notes: this.state.specialInstructions || false,
                facility_id: this.state.facilityId,
                service_category: this.state.serviceCategory || false,
                service_notes: this.state.serviceNotes || false,
                booking_notes: this.state.specialInstructions || false,
            };

            // Commission fields
            if (this.state.commissionDueTo) vals.commission_due_to = this.state.commissionDueTo;
            if (this.state.commissionPercentage) vals.commission_percentage = this.state.commissionPercentage;
            if (this.state.commissionDuration) vals.commission_duration = this.state.commissionDuration;
            if (this.state.serviceFeeVnd) vals.service_fee_vnd = this.state.serviceFeeVnd;

            // Schedule
            if (this.state.bookingDate && this.state.selectedTime !== null) {
                vals.booking_date = this.state.bookingDate;
                vals.booking_time = this.state.selectedTime;
                vals.booking_timezone = tz;
            }

            const bookingId = await this.orm.call(
                "health.fieldservice.order",
                "create_booking_from_wizard",
                [vals]
            );

            this.notification.add(_t("Booking created successfully!"), { type: "success" });

            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'health.fieldservice.order',
                res_id: bookingId,
                views: [[false, 'form']],
                target: 'current',
            });
        } catch (e) {
            console.error('Booking creation failed:', e);
            this.notification.add(_t("Failed to create booking. Please try again."), { type: "danger" });
        }

        this.state.isSubmitting = false;
    }

    // ===== CLOSE =====

    closeWizard() {
        window.history.back();
    }
}

registry.category("actions").add("ops_booking_wizard", OpsBookingWizard);

export default OpsBookingWizard;
