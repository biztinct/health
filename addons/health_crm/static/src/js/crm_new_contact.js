/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";

const MODE_OPTIONS = [
    { key: "phone", label: "Phone Call", icon: "fa-phone" },
    { key: "zalo", label: "Zalo", icon: "fa-comment" },
    { key: "facebook", label: "Facebook", icon: "fa-facebook" },
    { key: "email", label: "Email", icon: "fa-envelope" },
    { key: "website", label: "Website", icon: "fa-globe" },
    { key: "chatbox", label: "Chatbox", icon: "fa-comments" },
    { key: "walk_in", label: "Walk-in", icon: "fa-walking" },
];

const RELATIONSHIP_OPTIONS = [
    { key: "client", label: "Client (Self)" },
    { key: "payer", label: "Payer" },
    { key: "referrer", label: "Referrer" },
    { key: "emergency_contact", label: "Emergency Contact" },
    { key: "legal_guardian", label: "Legal Guardian" },
    { key: "client_representative", label: "Client Representative" },
];

const SERVICE_OPTIONS = [
    { key: "home_visit", label: "Home Visit", icon: "fa-home" },
    { key: "clinic_visit", label: "Clinic Visit", icon: "fa-hospital-o" },
    { key: "consultation", label: "Consultation", icon: "fa-comments" },
    { key: "follow_up", label: "Follow-up", icon: "fa-refresh" },
    { key: "emergency", label: "Emergency", icon: "fa-ambulance" },
    { key: "preventive", label: "Preventive", icon: "fa-shield" },
    { key: "rehabilitation", label: "Rehabilitation", icon: "fa-heartbeat" },
    { key: "palliative", label: "Palliative", icon: "fa-medkit" },
];

const PRIORITY_OPTIONS = [
    { key: "routine", label: "Routine" },
    { key: "urgent", label: "Urgent" },
    { key: "emergency", label: "Emergency" },
    { key: "preventive", label: "Preventive" },
];

const ACTIVITY_TYPE_OPTIONS = [
    { key: "todo", label: "To-Do", icon: "fa-check-square-o" },
    { key: "call", label: "Call", icon: "fa-phone" },
    { key: "email", label: "Email", icon: "fa-envelope" },
    { key: "meeting", label: "Meeting", icon: "fa-users" },
    { key: "follow_up", label: "Follow-up", icon: "fa-refresh" },
    { key: "reminder", label: "Reminder", icon: "fa-bell" },
];

const STEP3_ACTIONS = [
    { key: "booking", label: "New Booking", icon: "fa-calendar-plus-o", type: "navigate", accent: "default" },
    { key: "escalate", label: "Escalate", icon: "fa-arrow-up", type: "dialog", accent: "warning" },
    { key: "consult", label: "Consultation", icon: "fa-stethoscope", type: "dialog", accent: "info" },
    { key: "message", label: "Send Message", icon: "fa-comment", type: "dialog", accent: "default" },
    { key: "activity", label: "Log Activity", icon: "fa-tasks", type: "inline", accent: "default" },
    { key: "notes", label: "Add Notes", icon: "fa-sticky-note", type: "inline", accent: "default" },
    { key: "spam", label: "Mark Spam", icon: "fa-ban", type: "inline", accent: "danger" },
    { key: "open", label: "Open Record", icon: "fa-external-link", type: "navigate", accent: "default" },
];

class CrmNewContact extends Component {
    static template = "health_crm.CrmNewContact";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.modeOptions = MODE_OPTIONS;
        this.relationshipOptions = RELATIONSHIP_OPTIONS;
        this.serviceOptions = SERVICE_OPTIONS;
        this.priorityOptions = PRIORITY_OPTIONS;
        this.step3Actions = STEP3_ACTIONS;
        this.activityTypeOptions = ACTIVITY_TYPE_OPTIONS;

        this.state = useState({
            step: 1,
            isSubmitting: false,

            // Step 1
            name: "",
            phone: "",
            email: "",
            zaloNumber: "",
            modeOfContact: "phone",
            catchmentProvinceId: false,
            provinces: [],
            contactDatetime: "",

            // Duplicate check (displayed as search results panel)
            duplicateLeads: [],
            duplicatePartners: [],
            isSpam: false,
            spamLeadName: "",
            duplicateChecked: false,
            showDuplicateResults: false,

            // Name search
            nameSearchResults: null,
            nameSearchLoading: false,
            showNameSearch: false,

            // Step 2
            relationshipType: "client",
            clientName: "",
            selectedClientId: false,
            serviceInterest: "",
            clinicalPriority: "routine",
            contactReasonId: false,
            contactReasons: [],

            // Client search
            clientSearchResults: [],
            clientSearchLoading: false,
            showClientSearch: false,

            // Step 3
            createdLeadId: false,
            createdLeadName: "",
            createdLeadCode: "",
            isExistingContact: false,
            activeInlineAction: null,
            completedActions: {},

            // Inline action panels
            activityTypeKey: "todo",
            activitySummary: "",
            activityDeadline: "",
            noteBody: "",
            inlineSubmitting: false,
        });

        onWillStart(async () => {
            await Promise.all([
                this._loadProvinces(),
                this._loadContactReasons(),
                this._loadDefaultProvince(),
                this._loadActivityTypeIds(),
            ]);
            this._setContactDatetime();
        });
    }

    get stepInfo() {
        return [
            { num: 1, name: "Contact Info", desc: "Name, phone, channel" },
            { num: 2, name: "Details", desc: "Relationship, service" },
            { num: 3, name: "What's Next?", desc: "Choose action" },
        ];
    }

    getStepClass(num) {
        if (num < this.state.step) return "nc-step done";
        if (num === this.state.step) return "nc-step active";
        return "nc-step";
    }

    _normalizePhone(phone) {
        return phone ? phone.replace(/[^\d]/g, '') : '';
    }

    _setContactDatetime() {
        const now = new Date();
        this.state.contactDatetime = now.toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit', hour12: false,
        });
    }

    // =========================================================================
    // DATA LOADING
    // =========================================================================

    async _loadProvinces() {
        try {
            const provinces = await this.orm.searchRead(
                "health.catchment.province",
                [["active", "=", true]],
                ["name"],
                { order: "name asc" }
            );
            this.state.provinces = provinces;
        } catch (_e) { /* ignore */ }
    }

    async _loadContactReasons() {
        try {
            const reasons = await this.orm.searchRead(
                "health.contact.reason",
                [],
                ["name"],
                { order: "name asc" }
            );
            this.state.contactReasons = reasons;
        } catch (_e) { /* ignore */ }
    }

    async _loadDefaultProvince() {
        try {
            const userId = session.uid;
            if (!userId) return;
            const result = await this.orm.read("res.users", [userId], ["catchment_province_id"]);
            if (result.length && result[0].catchment_province_id) {
                this.state.catchmentProvinceId = result[0].catchment_province_id[0];
            }
        } catch (_e) { /* ignore */ }
    }

    async _loadActivityTypeIds() {
        try {
            const types = await this.orm.searchRead(
                "mail.activity.type",
                [],
                ["name", "res_model"],
                { order: "sequence asc", limit: 30 }
            );
            this._activityTypeMap = {};
            const nameToKey = {
                'to-do': 'todo', 'to do': 'todo',
                'email': 'email', 'e-mail': 'email',
                'call': 'call', 'phone call': 'call',
                'meeting': 'meeting',
                'follow-up': 'follow_up', 'follow up': 'follow_up',
                'reminder': 'reminder',
            };
            for (const t of types) {
                const lower = (t.name || '').toLowerCase();
                for (const [pattern, key] of Object.entries(nameToKey)) {
                    if (lower.includes(pattern)) {
                        this._activityTypeMap[key] = t.id;
                        break;
                    }
                }
            }
            if (!this._activityTypeMap['todo'] && types.length) {
                this._activityTypeMap['todo'] = types[0].id;
            }
        } catch (_e) {
            this._activityTypeMap = {};
        }
    }

    // =========================================================================
    // DUPLICATE CHECK (Enhanced)
    // =========================================================================

    async _checkDuplicates() {
        const phone = this.state.phone.trim();
        const email = this.state.email.trim();
        if (!phone && !email) {
            this.state.duplicateLeads = [];
            this.state.duplicatePartners = [];
            this.state.isSpam = false;
            this.state.spamLeadName = "";
            this.state.duplicateChecked = false;
            this.state.showDuplicateResults = false;
            return;
        }
        try {
            const result = await this.orm.call(
                "crm.lead",
                "check_contact_duplicates",
                [{ phone, email }]
            );
            this.state.duplicateLeads = result.lead_matches || [];
            this.state.duplicatePartners = result.partner_matches || [];
            this.state.isSpam = result.is_spam || false;
            this.state.spamLeadName = result.spam_lead_name || "";
            this.state.duplicateChecked = true;
            this.state.showDuplicateResults =
                this.state.duplicateLeads.length > 0 || this.state.duplicatePartners.length > 0;
        } catch (_e) {
            this.state.duplicateChecked = false;
        }
    }

    get hasDuplicates() {
        return this.state.duplicateLeads.length > 0 || this.state.duplicatePartners.length > 0;
    }

    onPhoneInput(ev) {
        this.state.phone = ev.target.value;
        if (this.state.zaloNumber === '' || this.state.zaloNumber === this._prevPhone) {
            this.state.zaloNumber = ev.target.value;
        }
        this._prevPhone = ev.target.value;
        clearTimeout(this._dupTimer);
        this._dupTimer = setTimeout(() => this._checkDuplicates(), 500);
    }

    onEmailInput(ev) {
        this.state.email = ev.target.value;
        clearTimeout(this._dupTimer);
        this._dupTimer = setTimeout(() => this._checkDuplicates(), 500);
    }

    selectDuplicateLead(lead) {
        this.state.createdLeadId = lead.id;
        this.state.createdLeadName = lead.name || '';
        this.state.createdLeadCode = lead.code || '';
        this.state.isExistingContact = true;
        this.state.showDuplicateResults = false;
        this.state.step = 3;
        this.state.completedActions = {};
        this.state.activeInlineAction = null;
    }

    selectDuplicatePartner(partner) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: partner.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    closeDuplicateResults() {
        this.state.showDuplicateResults = false;
    }

    // =========================================================================
    // NAME SEARCH
    // =========================================================================

    async searchByName() {
        const name = this.state.name.trim();
        if (name.length < 2) {
            this.notification.add(_t("Enter at least 2 characters to search"), { type: "warning" });
            return;
        }
        this.state.nameSearchLoading = true;
        this.state.showNameSearch = true;
        try {
            const results = await this.orm.call(
                "crm.lead",
                "search_contacts_for_wizard",
                [name]
            );
            this.state.nameSearchResults = results;
        } catch (_e) {
            this.state.nameSearchResults = { contacts: [], leads: [], clients: [] };
        }
        this.state.nameSearchLoading = false;
    }

    onNameKeydown(ev) {
        if (ev.key === 'Enter' && this.state.name.trim().length >= 2) {
            ev.preventDefault();
            this.searchByName();
        }
    }

    get nameSearchHasResults() {
        const r = this.state.nameSearchResults;
        if (!r) return false;
        return r.clients.length > 0 || r.leads.length > 0 || r.contacts.length > 0;
    }

    selectNameSearchResult(type, record) {
        this.state.showNameSearch = false;
        this.state.nameSearchResults = null;

        if (type === 'client') {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "res.partner",
                res_id: record.id,
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }

        if (type === 'lead' || type === 'contact') {
            this.state.createdLeadId = record.id;
            this.state.createdLeadName = record.name || '';
            this.state.createdLeadCode = record.code || '';
            this.state.isExistingContact = true;
            this.state.showDuplicateResults = false;
            this.state.step = 3;
            this.state.completedActions = {};
            this.state.activeInlineAction = null;
        }
    }

    closeNameSearch() {
        this.state.showNameSearch = false;
        this.state.nameSearchResults = null;
    }

    // =========================================================================
    // CLIENT SEARCH (Step 2)
    // =========================================================================

    async searchClientByName() {
        const name = this.state.clientName.trim();
        if (name.length < 2) {
            this.notification.add(_t("Enter at least 2 characters to search"), { type: "warning" });
            return;
        }
        this.state.clientSearchLoading = true;
        this.state.showClientSearch = true;
        try {
            const results = await this.orm.call(
                "crm.lead",
                "search_clients_for_wizard",
                [name]
            );
            this.state.clientSearchResults = results;
        } catch (_e) {
            this.state.clientSearchResults = [];
        }
        this.state.clientSearchLoading = false;
    }

    onClientNameKeydown(ev) {
        if (ev.key === 'Enter' && this.state.clientName.trim().length >= 2) {
            ev.preventDefault();
            this.searchClientByName();
        }
    }

    selectClient(client) {
        this.state.selectedClientId = client.id;
        this.state.clientName = client.name;
        this.state.showClientSearch = false;
        this.state.clientSearchResults = [];
    }

    closeClientSearch() {
        this.state.showClientSearch = false;
        this.state.clientSearchResults = [];
    }

    // =========================================================================
    // MODE / SELECTION HANDLERS
    // =========================================================================

    setMode(key) {
        this.state.modeOfContact = key;
    }

    onProvinceChange(ev) {
        this.state.catchmentProvinceId = ev.target.value ? parseInt(ev.target.value) : false;
    }

    setRelationship(key) {
        this.state.relationshipType = key;
    }

    setService(key) {
        this.state.serviceInterest = key;
    }

    setPriority(key) {
        this.state.clinicalPriority = key;
    }

    onReasonChange(ev) {
        this.state.contactReasonId = ev.target.value ? parseInt(ev.target.value) : false;
    }

    // =========================================================================
    // NAVIGATION
    // =========================================================================

    canGoNext() {
        if (this.state.step === 1) {
            return this.state.name.trim().length > 0;
        }
        return true;
    }

    nextStep() {
        if (!this.canGoNext()) return;
        if (this.state.step < 2) {
            this.state.step++;
        }
    }

    prevStep() {
        if (this.state.step > 1 && this.state.step <= 2) {
            this.state.step--;
        }
    }

    closeWizard() {
        this.action.doAction("health_crm.action_crm_contact_list_native", {
            clearBreadcrumbs: true,
        });
    }

    // =========================================================================
    // MARK AS JUNK (Step 1)
    // =========================================================================

    async markAsJunk() {
        if (!this.state.name.trim() && !this.state.phone.trim()) {
            this.notification.add(_t("Enter a name or phone number first"), { type: "warning" });
            return;
        }
        try {
            await this.orm.call("crm.lead", "action_create_spam_from_wizard", [{
                name: this.state.name.trim() || 'Unknown',
                phone: this.state.phone.trim() || false,
                email_from: this.state.email.trim() || false,
                catchment_province_id: this.state.catchmentProvinceId || false,
                mode_of_contact: this.state.modeOfContact,
            }]);
            this.notification.add(_t("Contact marked as junk"), { type: "info" });
            this.closeWizard();
        } catch (_e) {
            this.notification.add(_t("Failed to mark as junk"), { type: "danger" });
        }
    }

    // =========================================================================
    // SUBMIT (Create Contact → Step 3)
    // =========================================================================

    async submit() {
        if (this.state.isSubmitting) return;
        if (!this.state.name.trim()) {
            this.notification.add(_t("Contact name is required"), { type: "warning" });
            return;
        }

        this.state.isSubmitting = true;
        try {
            const vals = {
                name: this.state.name.trim(),
                phone: this.state.phone.trim() || false,
                email_from: this.state.email.trim() || false,
                mode_of_contact: this.state.modeOfContact,
                catchment_province_id: this.state.catchmentProvinceId || false,
                contact_relationship_type: this.state.relationshipType,
                client_name: this.state.clientName.trim() || false,
                service_interest: this.state.serviceInterest || false,
                clinical_priority: this.state.clinicalPriority,
                reason_for_contact_id: this.state.contactReasonId || false,
                zalo_number: this.state.zaloNumber.trim() || false,
                selected_client_id: this.state.selectedClientId || false,
            };

            const result = await this.orm.call(
                "crm.lead",
                "action_create_from_crm_wizard",
                [vals]
            );

            this.state.createdLeadId = result.res_id;
            this.state.createdLeadName = result.name || this.state.name.trim();
            this.state.createdLeadCode = result.code || '';
            this.state.step = 3;
            this.state.completedActions = {};
            this.state.activeInlineAction = null;

            this.notification.add(_t("Contact created successfully"), { type: "success" });
        } catch (e) {
            console.error("Failed to create contact:", e);
            this.notification.add(_t("Failed to create contact"), { type: "danger" });
        }
        this.state.isSubmitting = false;
    }

    // =========================================================================
    // STEP 3: ACTION HANDLERS (Hybrid)
    // =========================================================================

    async onStep3Action(actionKey) {
        const leadId = this.state.createdLeadId;
        if (!leadId) return;

        switch (actionKey) {
            case 'booking':
                await this._actionBooking(leadId);
                break;
            case 'open':
                this._actionOpenRecord(leadId);
                break;
            case 'escalate':
                await this._actionDialog(leadId, 'action_escalate_contact');
                break;
            case 'consult':
                await this._actionDialog(leadId, 'action_escalate_consultation');
                break;
            case 'message':
                await this._actionDialog(leadId, 'action_send_message');
                break;
            case 'activity':
            case 'notes':
            case 'spam':
                this.state.activeInlineAction = this.state.activeInlineAction === actionKey ? null : actionKey;
                break;
        }
    }

    async _actionBooking(leadId) {
        try {
            const lead = await this.orm.read("crm.lead", [leadId], [
                "name", "partner_id",
            ]);
            const l = lead[0];
            const partnerId = l.partner_id ? l.partner_id[0] : false;
            this.action.doAction({
                type: "ir.actions.client",
                tag: "ops_quick_booking",
                name: _t("Quick Booking"),
                target: "current",
                context: {
                    default_patient_id: partnerId,
                    default_lead_id: leadId,
                },
            });
        } catch (e) {
            console.error("Failed to open booking:", e);
            this.notification.add(_t("Failed to open booking wizard"), { type: "danger" });
        }
    }

    _actionOpenRecord(leadId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            res_id: leadId,
            views: [[false, "form"]],
            target: "current",
            context: { form_view_ref: "health_crm.view_crm_contact_form_crm_center" },
        });
    }

    async _actionDialog(leadId, methodName) {
        try {
            const result = await this.orm.call("crm.lead", methodName, [leadId]);
            if (result && result.type) {
                await this.action.doAction(result);
            }
        } catch (e) {
            console.error(`Action ${methodName} failed:`, e);
            this.notification.add(_t("Action failed"), { type: "danger" });
        }
    }

    // Inline: Log Activity
    setActivityType(key) {
        this.state.activityTypeKey = key;
    }

    async submitActivity() {
        if (this.state.inlineSubmitting) return;
        this.state.inlineSubmitting = true;
        try {
            const typeId = (this._activityTypeMap || {})[this.state.activityTypeKey] || false;
            await this.orm.call("crm.lead", "wizard_log_activity", [
                this.state.createdLeadId,
                typeId,
                this.state.activitySummary.trim() || false,
                this.state.activityDeadline || false,
            ]);
            this.state.completedActions = { ...this.state.completedActions, activity: true };
            this.state.activeInlineAction = null;
            this.state.activitySummary = "";
            this.state.activityDeadline = "";
            this.notification.add(_t("Activity scheduled"), { type: "success" });
        } catch (_e) {
            this.notification.add(_t("Failed to schedule activity"), { type: "danger" });
        }
        this.state.inlineSubmitting = false;
    }

    // Inline: Add Notes
    async submitNote() {
        if (this.state.inlineSubmitting) return;
        const body = this.state.noteBody.trim();
        if (!body) {
            this.notification.add(_t("Please enter a note"), { type: "warning" });
            return;
        }
        this.state.inlineSubmitting = true;
        try {
            await this.orm.call("crm.lead", "wizard_post_note", [
                this.state.createdLeadId,
                body,
            ]);
            this.state.completedActions = { ...this.state.completedActions, notes: true };
            this.state.activeInlineAction = null;
            this.state.noteBody = "";
            this.notification.add(_t("Note saved"), { type: "success" });
        } catch (_e) {
            this.notification.add(_t("Failed to save note"), { type: "danger" });
        }
        this.state.inlineSubmitting = false;
    }

    // Inline: Mark Spam
    async confirmSpam() {
        if (this.state.inlineSubmitting) return;
        this.state.inlineSubmitting = true;
        try {
            await this.orm.call("crm.lead", "action_mark_contact_spam", [
                this.state.createdLeadId,
            ]);
            this.state.completedActions = { ...this.state.completedActions, spam: true };
            this.state.activeInlineAction = null;
            this.notification.add(_t("Contact marked as spam"), { type: "info" });
        } catch (_e) {
            this.notification.add(_t("Failed to mark as spam"), { type: "danger" });
        }
        this.state.inlineSubmitting = false;
    }

    isActionCompleted(key) {
        return !!this.state.completedActions[key];
    }

    getActionCardClass(act) {
        let cls = `nc-action-card nc-action-card--${act.accent}`;
        if (this.state.activeInlineAction === act.key) cls += ' nc-action-card--active';
        if (this.isActionCompleted(act.key)) cls += ' nc-action-card--done';
        return cls;
    }
}

registry.category("actions").add("crm_new_contact", CrmNewContact);

export default CrmNewContact;
