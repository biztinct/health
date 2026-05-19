/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ProductCatalogDialog } from "./product_catalog_dialog";

class OpsRecurringBooking extends Component {
    static template = "health_fieldservice.OpsRecurringBooking";

    static components = { ProductCatalogDialog };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialogService = useService("dialog");

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

            // Staff & Doctor
            staffList: [],
            staffId: false,
            preferredStaffId: false,
            doctorList: [],
            doctorId: false,

            // Products & Packages
            products: [],
            selectedProducts: [],
            productCategories: [],
            packageId: false,
            packages: [],

            // Assigned staff
            assignedStaffIds: [],

            // Validation
            validationErrors: [],

            // Confirmation modal
            showConfirmation: false,
            creationResult: null,
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
            this.state.staffList = data.staff_list || [];
            this.state.packages = data.packages || [];
            this.state.preferredStaffId = data.preferred_staff_id || false;
            this.state.doctorList = data.doctor_list || [];
            this.state.products = data.products || [];
            this.state.productCategories = data.product_categories || [];
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
        if (!amount) return '0 d';
        return Math.round(amount).toLocaleString('vi-VN') + ' d';
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
    onServiceTypeChange(ev) { this.state.serviceType = ev.target.value; }
    onDurationChange(ev) { this.state.durationHours = parseFloat(ev.target.value) || 1; }
    onTimeChange(ev) { this.state.timeHour = parseInt(ev.target.value) || 9; this.refreshPreview(); }
    onFacilityChange(ev) { this.state.facilityId = parseInt(ev.target.value) || false; }
    onStartDateChange(ev) { this.state.startDate = ev.target.value; this.refreshPreview(); }
    onOccurrencesChange(ev) { this.state.occurrences = parseInt(ev.target.value) || 1; this.refreshPreview(); }
    onNotesChange(ev) { this.state.notes = ev.target.value; }
    onStaffChange(ev) { this.state.staffId = parseInt(ev.target.value) || false; }
    onDoctorChange(ev) { this.state.doctorId = parseInt(ev.target.value) || false; }

    isStaffAssigned(staffId) {
        return this.state.assignedStaffIds.includes(staffId);
    }

    toggleAssignedStaff(staffId) {
        const idx = this.state.assignedStaffIds.indexOf(staffId);
        if (idx >= 0) {
            this.state.assignedStaffIds.splice(idx, 1);
            if (this.state.staffId === staffId) {
                this.state.staffId = this.state.assignedStaffIds.length > 0
                    ? this.state.assignedStaffIds[0]
                    : false;
            }
        } else {
            this.state.assignedStaffIds.push(staffId);
            if (!this.state.staffId) {
                this.state.staffId = staffId;
            }
        }
    }

    get assignedStaffOptions() {
        if (this.state.assignedStaffIds.length === 0) return this.state.staffList;
        return this.state.staffList.filter(s => this.state.assignedStaffIds.includes(s.id));
    }
    onPackageChange(ev) { this.state.packageId = parseInt(ev.target.value) || false; }
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

    get hasProducts() {
        return this.state.selectedProducts.length > 0;
    }

    get productTotal() {
        return this.state.selectedProducts.reduce((sum, p) => sum + (p.price * p.qty), 0);
    }

    get hasServiceOrPackage() {
        return this.hasProducts || this.state.packageId;
    }

    addProduct(productId) {
        const id = parseInt(productId);
        if (!id) return;
        const existing = this.state.selectedProducts.find(p => p.product_id === id);
        if (existing) {
            existing.qty += 1;
            return;
        }
        const product = this.state.products.find(p => p.id === id);
        if (product) {
            this.state.selectedProducts.push({
                product_id: product.id,
                name: product.name,
                price: product.price,
                qty: 1,
            });
        }
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

    onAddProductSelect(ev) {
        this.addProduct(ev.target.value);
        ev.target.value = "";
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

    get packageWarning() {
        const pkg = this.selectedPackage;
        if (!pkg) return false;
        return this.state.preview.length > pkg.remaining_services;
    }

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

    async createBookings() {
        if (this.state.isCreating) return;

        const missing = [];
        if (!this.state.facilityId) missing.push('Facility');
        if (!this.hasServiceOrPackage) missing.push('Services or Package (add via Quote section)');
        if (!this.state.selectedDays.length && this.state.pattern !== 'daily' && this.state.pattern !== 'monthly') {
            missing.push('Repeat on days (select at least one day)');
        }
        if (!this.state.startDate) missing.push('Start Date');
        if (!this.state.preview.length) missing.push('No bookings to create (check schedule settings)');

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
                    product_lines: productLines.length > 0 ? productLines : null,
                    staff_id: this.state.staffId || false,
                    doctor_id: this.state.doctorId || false,
                    package_id: this.state.packageId || false,
                    assigned_staff_ids: this.state.assignedStaffIds.length > 0 ? this.state.assignedStaffIds : null,
                }
            );

            if (result.success) {
                this.state.creationResult = result;
                this.state.showConfirmation = true;
            } else {
                this.notification.add(result.error || _t("Failed to create bookings"), { type: "danger" });
            }
        } catch (e) {
            console.error('Create recurring error:', e);
            this.notification.add(_t("Could not create recurring bookings"), { type: "danger" });
        }
        this.state.isCreating = false;
    }

    dismissValidation() {
        this.state.validationErrors = [];
    }

    viewBookings() {
        const ids = this.state.creationResult?.ids || [];
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Recurring Bookings Created'),
            res_model: 'health.fieldservice.order',
            views: [[false, 'list'], [false, 'form']],
            domain: [['id', 'in', ids]],
            target: 'current',
        }, { clearBreadcrumbs: true });
    }

    async deleteBookings() {
        const result = this.state.creationResult;
        if (!result || !result.ids) return;

        try {
            await this.orm.call(
                "health.fieldservice.order",
                "cancel_recurring_bookings",
                [],
                { fso_ids: result.ids }
            );
            this.notification.add(_t("All bookings deleted"), { type: "warning" });
            this.state.showConfirmation = false;
            this.state.creationResult = null;
        } catch (e) {
            console.error('Delete error:', e);
            this.notification.add(_t("Error deleting bookings"), { type: "danger" });
        }
    }
}

registry.category("actions").add("ops_recurring_booking", OpsRecurringBooking);

export default OpsRecurringBooking;
