/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { localization } from "@web/core/l10n/localization";
import { ProductCatalogDialog } from "./product_catalog_dialog";
import { ClientMatchDialog } from "./client_match_dialog";
import { AddressDialog } from "@health_base/js/address_dialog";

const SERVICE_LOCATION_MAP = {
    home_visit: { label: _t('Patient Home'), icon: 'fa-home', cls: 'home' },
    clinic_visit: { label: _t('Clinic'), icon: 'fa-hospital-o', cls: 'clinic' },
    consultation: { label: _t('Clinic'), icon: 'fa-hospital-o', cls: 'clinic' },
    telemedicine: { label: _t('Online'), icon: 'fa-laptop', cls: 'online' },
    emergency: { label: _t('Patient Home'), icon: 'fa-ambulance', cls: 'home' },
    follow_up: { label: _t('Patient Home'), icon: 'fa-home', cls: 'home' },
    preventive: { label: _t('Clinic'), icon: 'fa-hospital-o', cls: 'clinic' },
    rehabilitation: { label: _t('Clinic'), icon: 'fa-hospital-o', cls: 'clinic' },
    vaccination: { label: _t('Clinic'), icon: 'fa-hospital-o', cls: 'clinic' },
    diagnostic: { label: _t('Clinic'), icon: 'fa-hospital-o', cls: 'clinic' },
};

// Editable Service Location choices (mirror service_location selection on the model)
const LOCATION_OPTIONS = [
    { key: 'home', label: _t('Patient Home'), icon: 'fa-home', cls: 'home' },
    { key: 'clinic', label: _t('Clinic'), icon: 'fa-hospital-o', cls: 'clinic' },
    { key: 'hospital', label: _t('Hospital'), icon: 'fa-hospital-o', cls: 'clinic' },
    { key: 'nursing_home', label: _t('Nursing Home'), icon: 'fa-bed', cls: 'clinic' },
    { key: 'office', label: _t('Office'), icon: 'fa-building-o', cls: 'clinic' },
    { key: 'online', label: _t('Online / Telemedicine'), icon: 'fa-laptop', cls: 'online' },
    { key: 'other', label: _t('Other Location'), icon: 'fa-map-marker', cls: 'other' },
];
// Default location per service type (user can still override)
const SERVICE_DEFAULT_LOCATION = {
    home_visit: 'home', clinic_visit: 'clinic', consultation: 'clinic',
    telemedicine: 'online', emergency: 'home', follow_up: 'home',
    preventive: 'clinic', rehabilitation: 'clinic', vaccination: 'clinic',
    diagnostic: 'clinic',
};

const TIME_PERIODS = [
    { key: 'morning', label: _t('Morning'), icon: 'fa-sun-o', range: _t('7am - 12pm'), startH: 7, endH: 12 },
    { key: 'afternoon', label: _t('Afternoon'), icon: 'fa-cloud', range: _t('12pm - 5pm'), startH: 12, endH: 17 },
    { key: 'evening', label: _t('Evening'), icon: 'fa-moon-o', range: _t('5pm - 8pm'), startH: 17, endH: 21 },
];

const DAY_NAMES = [_t('Mo'), _t('Tu'), _t('We'), _t('Th'), _t('Fr'), _t('Sa'), _t('Su')];

class OpsQuickBooking extends Component {
    static template = "health_fieldservice.OpsQuickBooking";
    static components = { ProductCatalogDialog };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialogService = useService("dialog");

        const context = this.props.action && this.props.action.context || {};
        const params = this.props.action && this.props.action.params || {};
        this.leadId = context.default_lead_id || false;
        // From a contact, only a client explicitly passed via default_patient_id is
        // a real client — never treat active_id (the lead's id) as the patient.
        this.patientId = this.leadId
            ? (context.default_patient_id || params.default_patient_id || false)
            : (context.active_id || context.default_patient_id || params.default_patient_id || false);
        this.activeCenter = context.active_center || false;

        this.timePeriods = TIME_PERIODS;
        this.dayNames = DAY_NAMES;

        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];

        this.state = useState({
            isLoading: true,
            isCreating: false,
            isSaving: false,

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
            serviceLocation: 'home',
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
            isDraftSave: false,

            clientSearch: '',
            clientResults: [],
            showClientResults: false,
            clientSearching: false,
            currentPatientId: this.patientId,

            // Contact-driven booking (opened from a New Contact / crm.lead)
            fromContact: !!this.leadId,
            contactClientName: '',
            clientResolved: false,
            createNewClient: false,
            clientAddress: {},
        });

        onWillStart(async () => {
            // Booking opened from a contact with no linked client yet: resolve the
            // contact's identity, then surface matching existing clients (dedup).
            if (!this.patientId && this.leadId) {
                await this.resolveContactClient();
            }
            if (this.patientId || this.leadId) {
                // A lead (contact flow) still needs service types / facilities even
                // before a client is resolved, so load options either way.
                await this.loadOptions();
            } else {
                this.state.isLoading = false;
            }
        });
    }

    // =========================================================================
    // CONTACT-DRIVEN BOOKING (opened from a New Contact)
    // =========================================================================

    async resolveContactClient() {
        try {
            const ctx = await this.orm.call(
                "crm.lead", "get_contact_booking_context", [this.leadId]
            );
            if (!ctx) { return; }
            // The lead already resolves to a client → just use it.
            if (ctx.patient_id) {
                this.patientId = ctx.patient_id;
                this.state.currentPatientId = ctx.patient_id;
                this.state.clientResolved = true;
                this.state.contactClientName = ctx.patient_name || ctx.client_name || '';
                this.state.clientSearch = ctx.patient_name || ctx.client_name || '';
                return;
            }
            this.state.contactClientName = ctx.client_name || '';
            // Carry over any home-visit address captured on the contact.
            if (ctx.address && typeof ctx.address === 'object') {
                this.state.clientAddress = ctx.address;
            }
            // Dedup: surface existing clients matching name / phone / email.
            const matches = await this.orm.call(
                "crm.lead", "search_clients_for_contact",
                [ctx.client_name || '', ctx.phone || '', ctx.email || '']
            );
            if (matches && matches.length) {
                this.dialogService.add(ClientMatchDialog, {
                    clients: matches,
                    clientName: ctx.client_name || '',
                    onPick: (clientId) => this.pickContactClient(clientId),
                    onCreateNew: () => { this.state.createNewClient = true; },
                });
            }
        } catch (e) {
            console.error('Failed to resolve contact client:', e);
        }
    }

    async pickContactClient(clientId) {
        this.patientId = clientId;
        this.state.currentPatientId = clientId;
        this.state.createNewClient = false;
        this.state.clientResolved = true;
        await this.loadOptions();
        // Reflect the picked client's real name in the banner.
        if (this.state.patient && this.state.patient.name) {
            this.state.contactClientName = this.state.patient.name;
        }
    }

    // =========================================================================
    // CLIENT SELECTOR (when no patient in context)
    // =========================================================================

    get needsClientSelector() {
        // Hide the free client search when booking is driven by a contact.
        return !this.state.currentPatientId && !this.state.fromContact;
    }

    get showContactBanner() {
        // Contact flow: always show the client banner (it reflects either the
        // name of the to-be-created client or the resolved/picked client).
        return this.state.fromContact;
    }

    get contactBannerName() {
        // Prefer the resolved/loaded client's real name; fall back to the
        // contact's client name (when a client will be auto-created).
        return (this.state.patient && this.state.patient.name)
            || this.state.contactClientName
            || 'New client';
    }

    onClientSearchKeydown(ev) {
        if (ev.key === 'Enter') {
            ev.preventDefault();
            this.doClientSearch();
        }
    }

    async doClientSearch() {
        const query = this.state.clientSearch.trim();
        if (query.length < 2) {
            this.state.clientResults = [];
            this.state.showClientResults = false;
            return;
        }
        this.state.clientSearching = true;
        try {
            const results = await this.orm.call(
                "res.partner",
                "search_read",
                [['&', ['is_patient', '=', true], '|', '|',
                    ['name', 'ilike', query], ['mobile', 'ilike', query], ['patient_code', 'ilike', query]],
                 ['id', 'name', 'mobile', 'patient_code']],
                { limit: 10, order: 'name asc' }
            );
            this.state.clientResults = results;
            this.state.showClientResults = results.length > 0;
        } catch (e) {
            console.error('Client search failed:', e);
            this.state.clientResults = [];
            this.state.showClientResults = false;
        }
        this.state.clientSearching = false;
    }

    onClientSearchBlur() {
        setTimeout(() => { this.state.showClientResults = false; }, 300);
    }

    async selectClient(client) {
        this.patientId = client.id;
        this.state.currentPatientId = client.id;
        this.state.clientSearch = client.name;
        this.state.showClientResults = false;
        this.state.clientResults = [];
        await this.loadOptions();
    }

    clearClient() {
        this.patientId = false;
        this.state.currentPatientId = false;
        this.state.clientSearch = '';
        this.state.clientResults = [];
        this.state.showClientResults = false;
        this.state.patient = {};
        this.state.packages = [];
        this.state.packageId = false;
        this.state.preferredStaffId = false;
        this.state.selectedProducts = [];
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
            if (!this.state.facilityId) {
                this.state.facilityId = data.default_facility_id
                    || (data.facilities.length > 0 ? data.facilities[0].id : false);
            }
            this.state.serviceLocation = SERVICE_DEFAULT_LOCATION[this.state.serviceType] || 'home';
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
        return LOCATION_OPTIONS.find(l => l.key === this.state.serviceLocation) || LOCATION_OPTIONS[0];
    }

    get locationOptions() {
        return LOCATION_OPTIONS;
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
        return new Date(this.state.calendarYear, this.state.calendarMonth, 1)
            .toLocaleDateString(localization.code.replace("_", "-"), {
                month: "long",
                year: "numeric",
            });
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
        this.previewPricing();  // appointment hour affects time-based pricing
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

    onServiceTypeChange(ev) {
        this.state.serviceType = ev.target.value;
        // Reset location to the sensible default for this service type (still overridable)
        this.state.serviceLocation = SERVICE_DEFAULT_LOCATION[this.state.serviceType] || 'home';
        this.previewPricing();
    }
    onDurationChange(ev) { this.state.durationHours = parseFloat(ev.target.value) || 1; }
    onLocationChange(ev) {
        this.state.serviceLocation = ev.target.value;
        this.previewPricing();
    }
    async onFacilityChange(ev) {
        this.state.facilityId = parseInt(ev.target.value) || false;
        // Refresh staff/doctors for the newly selected facility
        try {
            const data = await this.orm.call(
                "health.fieldservice.order", "get_quick_booking_staff",
                [this.state.facilityId || false]
            );
            this.state.staffList = data.staff_list || [];
            this.state.doctorList = data.doctor_list || [];
            // Drop any selected staff/lead/doctor no longer in this facility
            const staffIds = new Set(this.state.staffList.map(s => s.id));
            this.state.assignedStaffIds = this.state.assignedStaffIds.filter(id => staffIds.has(id));
            if (this.state.staffId && !staffIds.has(this.state.staffId)) this.state.staffId = false;
            const docIds = new Set(this.state.doctorList.map(d => d.id));
            if (this.state.doctorId && !docIds.has(this.state.doctorId)) this.state.doctorId = false;
        } catch (e) {
            console.error('Failed to reload staff for facility:', e);
        }
        this.checkAvailability();
    }

    get clientAddressPreview() {
        const a = this.state.clientAddress || {};
        const parts = [
            a.building_name, a.apartment_number, a.house_number,
            a.alley_number, a.sub_alley_number, a.street,
            a.ward_commune, a.named_area, a.city, a.zip,
        ].filter(Boolean);
        return parts.join(', ');
    }

    async editClientAddress() {
        // No client record yet (contact flow): capture the address in-memory; it
        // is applied to the client auto-created at booking time.
        if (!this.patientId) {
            this.dialogService.add(AddressDialog, {
                title: _t('Client Address'),
                address: this.state.clientAddress || {},
                onSave: (addr) => { this.state.clientAddress = addr; },
            });
            return;
        }
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Edit Address'),
            res_model: 'res.partner',
            res_id: this.patientId,
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: { form_view_ref: 'health_base.view_health_patient_address_form' },
        }, {
            onClose: async () => {
                // Refresh the client's address shown in the wizard
                try {
                    const data = await this.orm.call(
                        "health.fieldservice.order", "get_quick_booking_options",
                        [], { patient_id: this.patientId, facility_id: this.state.facilityId || false }
                    );
                    this.state.patient = data.patient || this.state.patient;
                } catch (e) {
                    console.error('Failed to refresh client address:', e);
                }
            },
        });
    }

    async previewPricing() {
        // Auto-price the quote lines from the booking conditions via advanced pricing
        if (!this.state.selectedProducts.length) return;
        try {
            const result = await this.orm.call(
                "health.fieldservice.order", "preview_quick_booking_pricing",
                [{
                    patient_id: this.patientId || false,
                    service_type: this.state.serviceType,
                    service_location: this.state.serviceLocation,
                    facility_id: this.state.facilityId || false,
                    date: this.state.selectedDate,
                    time_hour: this.finetuneHourDecimal,
                    product_lines: this.state.selectedProducts.map(p => ({
                        product_id: p.product_id, qty: p.qty,
                    })),
                }]
            );
            const priced = (result && result.lines) || [];
            for (const line of priced) {
                const item = this.state.selectedProducts.find(p => p.product_id === line.product_id);
                if (item) {
                    item.price = line.unit_price;
                    item.autopriced = !!line.adjusted;
                }
            }
        } catch (e) {
            console.error('Pricing preview failed:', e);
        }
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
                this.previewPricing();
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
            this.previewPricing();
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
        if (!this.patientId && !this.leadId) missing.push('Client');
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
                    create_new_client: this.state.createNewClient || false,
                    client_address: this.state.clientAddress || null,
                    service_type: this.state.serviceType,
                    duration_hours: this.state.durationHours,
                    time_hour: this.finetuneHourDecimal,
                    date: this.state.selectedDate,
                    facility_id: this.state.facilityId,
                    service_location: this.state.serviceLocation,
                    service_address: this.state.patient.address || '',
                    notes: this.state.notes,
                    product_lines: productLines.length > 0 ? productLines : null,
                    staff_id: this.state.staffId || false,
                    doctor_id: this.state.doctorId || false,
                    package_id: this.state.packageId || false,
                    assigned_staff_ids: this.state.assignedStaffIds.length > 0 ? this.state.assignedStaffIds : [],
                }]
            );

            if (result.success) {
                this.state.isDraftSave = false;
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

    async saveBookingDraft() {
        if (this.state.isSaving) return;

        const missing = [];
        if (!this.patientId && !this.leadId) missing.push('Client');
        if (!this.state.selectedDate) missing.push('Date');
        if (!this.state.selectedSlot) missing.push('Time slot');

        if (missing.length > 0) {
            this.state.validationErrors = missing;
            return;
        }
        this.state.validationErrors = [];
        this.state.isSaving = true;

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
                    create_new_client: this.state.createNewClient || false,
                    client_address: this.state.clientAddress || null,
                    service_type: this.state.serviceType,
                    duration_hours: this.state.durationHours,
                    time_hour: this.finetuneHourDecimal,
                    date: this.state.selectedDate,
                    facility_id: this.state.facilityId || false,
                    service_location: this.state.serviceLocation,
                    service_address: this.state.patient.address || '',
                    notes: this.state.notes,
                    product_lines: productLines.length > 0 ? productLines : null,
                    staff_id: this.state.staffId || false,
                    doctor_id: this.state.doctorId || false,
                    package_id: this.state.packageId || false,
                    assigned_staff_ids: this.state.assignedStaffIds.length > 0 ? this.state.assignedStaffIds : [],
                    draft_only: true,
                }]
            );

            if (result.success) {
                this.state.isDraftSave = true;
                this.state.creationResult = result;
                this.state.showConfirmation = true;
            } else {
                this.notification.add(result.error || _t("Failed to save booking"), { type: "danger" });
            }
        } catch (e) {
            console.error('Save draft error:', e);
            this.notification.add(_t("Could not save booking"), { type: "danger" });
        }
        this.state.isSaving = false;
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
