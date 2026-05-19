/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

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
    { key: "caregiver", label: "Caregiver" },
    { key: "payer", label: "Payer" },
    { key: "referrer", label: "Referrer" },
    { key: "emergency_contact", label: "Emergency Contact" },
    { key: "family_member", label: "Family Member" },
    { key: "professional", label: "Professional" },
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

            // Duplicate check
            duplicateWarning: "",
            duplicateLeadId: false,

            // Step 2
            relationshipType: "client",
            clientName: "",
            serviceInterest: "",
            clinicalPriority: "routine",
            contactReasonId: false,
            contactReasons: [],
        });

        onWillStart(async () => {
            await this._loadProvinces();
            await this._loadContactReasons();
        });
    }

    get stepInfo() {
        return [
            { num: 1, name: "Contact Info", desc: "Name, phone, channel" },
            { num: 2, name: "Details", desc: "Relationship, service" },
        ];
    }

    getStepClass(num) {
        if (num < this.state.step) return "nc-step done";
        if (num === this.state.step) return "nc-step active";
        return "nc-step";
    }

    // Data loading
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

    // Duplicate check
    async _checkDuplicate() {
        const phone = this.state.phone.trim();
        if (!phone || phone.length < 5) {
            this.state.duplicateWarning = "";
            this.state.duplicateLeadId = false;
            return;
        }
        try {
            const existing = await this.orm.searchRead(
                "crm.lead",
                [["phone", "=", phone]],
                ["name", "unique_contact_code", "contact_status"],
                { limit: 1 }
            );
            if (existing.length) {
                const e = existing[0];
                this.state.duplicateWarning = `Existing contact: ${e.unique_contact_code || ""} ${e.name} (${e.contact_status || "active"})`;
                this.state.duplicateLeadId = e.id;
            } else {
                this.state.duplicateWarning = "";
                this.state.duplicateLeadId = false;
            }
        } catch (_e) { /* ignore */ }
    }

    onPhoneInput(ev) {
        this.state.phone = ev.target.value;
        clearTimeout(this._phoneTimer);
        this._phoneTimer = setTimeout(() => this._checkDuplicate(), 500);
    }

    // Mode selection
    setMode(key) {
        this.state.modeOfContact = key;
    }

    // Province selection
    onProvinceChange(ev) {
        this.state.catchmentProvinceId = ev.target.value ? parseInt(ev.target.value) : false;
    }

    // Step 2 handlers
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

    // Navigation
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
        if (this.state.step > 1) {
            this.state.step--;
        }
    }

    openDuplicate() {
        if (this.state.duplicateLeadId) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "crm.lead",
                res_id: this.state.duplicateLeadId,
                views: [[false, "form"]],
                target: "current",
                context: { form_view_ref: "health_crm.view_crm_contact_form_crm_center" },
            });
        }
    }

    closeWizard() {
        this.action.doAction("health_crm.action_crm_dashboard", {
            clearBreadcrumbs: true,
        });
    }

    // Submit
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
            };

            const result = await this.orm.call(
                "crm.lead",
                "action_create_from_crm_wizard",
                [vals]
            );

            this.notification.add(_t("Contact created successfully"), { type: "success" });

            if (result && result.res_id) {
                this.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "crm.lead",
                    res_id: result.res_id,
                    views: [[false, "form"]],
                    target: "current",
                    context: { form_view_ref: "health_crm.view_crm_contact_form_crm_center" },
                }, { clearBreadcrumbs: true });
            } else {
                this.action.doAction(
                    "health_crm.action_crm_contact_list_native",
                    { clearBreadcrumbs: true }
                );
            }
        } catch (e) {
            console.error("Failed to create contact:", e);
            this.notification.add(_t("Failed to create contact"), { type: "danger" });
        }
        this.state.isSubmitting = false;
    }
}

registry.category("actions").add("crm_new_contact", CrmNewContact);

export default CrmNewContact;
