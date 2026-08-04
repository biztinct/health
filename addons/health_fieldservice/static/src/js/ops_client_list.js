/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const PAGE_SIZE = 20;

const STATUS_LABELS = {
    active: _t('Active'),
    inactive: _t('Inactive'),
};

class OpsClientList extends Component {
    static template = "health_fieldservice.OpsClientList";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");


        this.state = useState({
            isLoading: true,
            activeTab: 'all',
            searchQuery: '',
            facilityFilter: '',
            clients: [],
            totalCount: 0,
            page: 0,
            facilities: [],
            needsStaffCount: 0,
        });

        onWillStart(async () => {
            await this.loadFacilities();
            await this.loadClients();
            await this.loadNeedsStaffCount();
        });
    }

    // ===== DATA =====

    async loadFacilities() {
        try {
            this.state.facilities = await this.orm.searchRead(
                "health.facility",
                [['active', '=', true]],
                ['name'],
                { order: 'name asc' }
            );
        } catch (e) {
            console.error('Failed to load facilities:', e);
        }
    }

    get domain() {
        const domain = [['is_patient', '=', true]];

        switch (this.state.activeTab) {
            case 'active':
                domain.push(['patient_status', '=', 'active']);
                break;
            case 'inactive':
                domain.push(['patient_status', '=', 'inactive']);
                break;
            case 'recent':
                domain.push(['last_visit_date', '!=', false]);
                break;
        }

        if (this.state.facilityFilter) {
            domain.push(['primary_facility_id', '=', parseInt(this.state.facilityFilter)]);
        }

        if (this.state.searchQuery) {
            domain.push('|', '|', '|');
            domain.push(['name', 'ilike', this.state.searchQuery]);
            domain.push(['patient_code', 'ilike', this.state.searchQuery]);
            domain.push(['mobile', 'ilike', this.state.searchQuery]);
            domain.push(['email', 'ilike', this.state.searchQuery]);
        }

        return domain;
    }

    get orderBy() {
        if (this.state.activeTab === 'recent') {
            return 'last_visit_date desc';
        }
        return 'name asc';
    }

    async loadClients() {
        this.state.isLoading = true;
        try {
            const fields = [
                'name', 'patient_code', 'mobile', 'email', 'gender', 'age',
                'patient_status', 'catchment_province_id', 'primary_facility_id',
                'preferred_staff_id', 'last_visit_date', 'total_assignments',
                'patient_category_id', 'deleted',
            ];
            // deleted_test false: Delete requests stay visible in the record
            // table (chip in the status column); counts elsewhere exclude them.
            const lifecycleCtx = { context: { deleted_test: false } };
            const clients = await this.orm.searchRead(
                "res.partner",
                this.domain,
                fields,
                { limit: PAGE_SIZE, offset: this.state.page * PAGE_SIZE, order: this.orderBy, ...lifecycleCtx }
            );
            const count = await this.orm.searchCount("res.partner", this.domain, lifecycleCtx);
            this.state.clients = clients;
            this.state.totalCount = count;
        } catch (e) {
            console.error('Failed to load clients:', e);
            this.notification.add(_t("Error loading clients"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    async loadNeedsStaffCount() {
        try {
            const count = await this.orm.searchCount("health.fieldservice.order", [
                ['has_staff_assigned', '=', false],
                ['state', 'in', ['draft', 'confirmed']],
            ]);
            this.state.needsStaffCount = count;
        } catch (e) { /* ignore */ }
    }

    // ===== TABS =====

    setTab(tab) {
        this.state.activeTab = tab;
        this.state.page = 0;
        this.loadClients();
    }

    // ===== FILTERS =====

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
    }

    onSearchKeydown(ev) {
        if (ev.key === 'Enter') {
            this.state.page = 0;
            this.loadClients();
        }
    }

    onFacilityChange(ev) {
        this.state.facilityFilter = ev.target.value;
        this.state.page = 0;
        this.loadClients();
    }

    // ===== PAGINATION =====

    get totalPages() { return Math.ceil(this.state.totalCount / PAGE_SIZE); }
    get showingFrom() { return this.state.totalCount ? this.state.page * PAGE_SIZE + 1 : 0; }
    get showingTo() { return Math.min((this.state.page + 1) * PAGE_SIZE, this.state.totalCount); }

    prevPage() {
        if (this.state.page > 0) {
            this.state.page--;
            this.loadClients();
        }
    }

    nextPage() {
        if (this.state.page < this.totalPages - 1) {
            this.state.page++;
            this.loadClients();
        }
    }

    // ===== HELPERS =====

    getStatusChipClass(status) {
        return status === 'active' ? 'chip-completed' : 'chip-draft';
    }

    getStatusLabel(status) {
        return STATUS_LABELS[status] || status || '';
    }

    getInitials(name) {
        if (!name) return '?';
        return name.split(' ').filter(p => p).map(p => p[0]).join('').substring(0, 2).toUpperCase();
    }

    getFacilityName(c) { return c.primary_facility_id ? c.primary_facility_id[1] : ''; }
    getCatchmentName(c) { return c.catchment_province_id ? c.catchment_province_id[1] : ''; }
    getPreferredStaffName(c) { return c.preferred_staff_id ? c.preferred_staff_id[1] : ''; }
    getCategoryName(c) { return c.patient_category_id ? c.patient_category_id[1] : ''; }

    formatLastVisit(dt) {
        if (!dt) return 'Never';
        const d = new Date(dt);
        return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    }

    // ===== ACTIONS =====

    viewClientProfile(clientId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: clientId,
            views: [[false, 'form']],
            target: 'current',
            context: { form_view_ref: 'health_fieldservice.view_health_patient_form_ops' },
        }, { clearBreadcrumbs: true });
    }

    openQuickBooking(clientId) {
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_quick_booking',
            name: _t('Quick Booking'),
            target: 'current',
            context: { active_id: clientId, default_patient_id: clientId },
        });
    }

    openRecurringBooking(clientId) {
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_recurring_booking',
            target: 'fullscreen',
            context: { default_patient_id: clientId },
        }, { clearBreadcrumbs: true });
    }

}

registry.category("actions").add("ops_client_list", OpsClientList);

export default OpsClientList;
