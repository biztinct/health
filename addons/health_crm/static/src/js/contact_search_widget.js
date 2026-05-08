/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Contact Search Dialog - Shows grouped search results for contacts, leads, and clients
 */
class ContactSearchDialog extends Component {
    static template = "health_crm.ContactSearchDialog";
    static components = { Dialog };
    static props = {
        searchTerm: { type: String },
        results: { type: Object },
        onSelect: { type: Function },
        close: { type: Function },
    };

    setup() {
        this.state = useState({
            selectedIndex: -1,
        });
    }

    t(text) {
        return _t(text);
    }

    get hasResults() {
        const { contacts, leads, clients } = this.props.results;
        return (contacts?.length > 0) || (leads?.length > 0) || (clients?.length > 0);
    }

    selectContact(type, record) {
        this.props.onSelect(type, record);
        this.props.close();
    }
}

/**
 * Contact Search Service - Provides search functionality for the initial contact wizard
 */
export const contactSearchService = {
    dependencies: ["orm", "dialog", "action"],

    start(env, { orm, dialog, action }) {
        return {
            async searchContacts(searchTerm) {
                if (!searchTerm || searchTerm.length < 2) {
                    return { contacts: [], leads: [], clients: [] };
                }

                const domain = [
                    '|', '|',
                    ['name', 'ilike', searchTerm],
                    ['phone', 'ilike', searchTerm],
                    ['email', 'ilike', searchTerm],
                ];

                // Search CRM Leads (contacts)
                const leads = await orm.searchRead(
                    "crm.lead",
                    [...domain, ['contact_status', 'in', ['active', 'lead']]],
                    ['id', 'name', 'phone', 'email', 'contact_status', 'unique_contact_code'],
                    { limit: 10 }
                );

                // Search Clients (res.partner with is_patient=True)
                const clients = await orm.searchRead(
                    "res.partner",
                    [...domain, ['is_patient', '=', true]],
                    ['id', 'name', 'phone', 'email', 'patient_code'],
                    { limit: 10 }
                );

                // Separate leads based on contact_status
                const activeContacts = leads.filter(l => l.contact_status === 'active');
                const leadContacts = leads.filter(l => l.contact_status === 'lead');

                return {
                    contacts: activeContacts,
                    leads: leadContacts,
                    clients: clients,
                };
            },

            async openSearchDialog(searchTerm, onSelect) {
                const results = await this.searchContacts(searchTerm);

                dialog.add(ContactSearchDialog, {
                    searchTerm,
                    results,
                    onSelect: async (type, record) => {
                        onSelect(type, record);
                    },
                });
            },

            async navigateToRecord(type, record, action) {
                if (type === 'client') {
                    // Navigate to client form (res.partner)
                    await action.doAction({
                        type: 'ir.actions.act_window',
                        name: _t('Client Details'),
                        res_model: 'res.partner',
                        res_id: record.id,
                        view_mode: 'form',
                        views: [[false, 'form']],
                        context: { 'form_view_ref': 'health_base.view_health_patient_form' },
                        target: 'current',
                    });
                } else {
                    // Navigate to lead/contact form (crm.lead)
                    await action.doAction({
                        type: 'ir.actions.act_window',
                        name: _t('Contact Details'),
                        res_model: 'crm.lead',
                        res_id: record.id,
                        view_mode: 'form',
                        views: [[false, 'form']],
                        context: { 'form_view_ref': 'health_crm.view_healthcare_opportunity_form' },
                        target: 'current',
                    });
                }
            }
        };
    },
};

registry.category("services").add("contactSearch", contactSearchService);

/**
 * ContactNameField - Custom widget that adds Tab key search functionality
 */
export class ContactNameField extends Component {
    static template = "health_crm.ContactNameField";
    static props = {
        value: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        readonly: { type: Boolean, optional: true },
        onChange: { type: Function, optional: true },
    };

    setup() {
        this.inputRef = useRef("input");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.contactSearch = useService("contactSearch");

        this.state = useState({
            value: this.props.value || "",
            showPopup: false,
            results: { contacts: [], leads: [], clients: [] },
            loading: false,
        });

        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.addEventListener('keydown', this.onKeyDown.bind(this));
            }
        });

        onWillUnmount(() => {
            if (this.inputRef.el) {
                this.inputRef.el.removeEventListener('keydown', this.onKeyDown.bind(this));
            }
        });
    }

    t(text) {
        return _t(text);
    }

    async onKeyDown(ev) {
        if (ev.key === 'Tab' && this.state.value && this.state.value.length >= 2) {
            ev.preventDefault();
            await this.showSearchPopup();
        }
    }

    async showSearchPopup() {
        this.state.loading = true;
        const results = await this.contactSearch.searchContacts(this.state.value);

        if (results.contacts.length || results.leads.length || results.clients.length) {
            this.state.results = results;
            this.state.showPopup = true;

            // Open dialog with results
            this.dialog.add(ContactSearchDialog, {
                searchTerm: this.state.value,
                results: results,
                onSelect: async (type, record) => {
                    await this.contactSearch.navigateToRecord(type, record, this.action);
                },
            });
        }
        this.state.loading = false;
    }

    onInput(ev) {
        this.state.value = ev.target.value;
        if (this.props.onChange) {
            this.props.onChange(ev.target.value);
        }
    }
}
