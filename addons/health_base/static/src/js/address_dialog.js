/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Reusable Vietnamese address editor dialog. Works without a saved record:
 * it edits an in-memory address dict and returns it via onSave. Fields mirror
 * res.partner / view_health_patient_address_form; the live preview mirrors
 * res_partner._compute_vietnamese_address.
 */
export class AddressDialog extends Component {
    static template = "health_base.AddressDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: { type: String, optional: true },
        address: { type: Object, optional: true },
        onSave: Function,
    };

    setup() {
        const a = this.props.address || {};
        this.state = useState({
            house_number: a.house_number || "",
            alley_number: a.alley_number || "",
            sub_alley_number: a.sub_alley_number || "",
            street: a.street || "",
            ward_commune: a.ward_commune || "",
            named_area: a.named_area || "",
            building_name: a.building_name || "",
            apartment_number: a.apartment_number || "",
            city: a.city || "",
            zip: a.zip || "",
        });
    }

    get dialogTitle() {
        return this.props.title || "Home Address";
    }

    get preview() {
        const s = this.state;
        const parts = [];
        if (s.apartment_number) parts.push(`Căn hộ ${s.apartment_number}`);
        if (s.building_name) parts.push(s.building_name);
        if (s.named_area) parts.push(s.named_area);
        const street = [];
        if (s.house_number) street.push(s.house_number);
        if (s.sub_alley_number) street.push(`Ngách ${s.sub_alley_number}`);
        if (s.alley_number) street.push(`Ngõ ${s.alley_number}`);
        if (s.street) street.push(s.street);
        if (street.length) parts.push(street.join(", "));
        if (s.ward_commune) parts.push(`Phường/Xã ${s.ward_commune}`);
        if (s.city) parts.push(s.city);
        if (s.zip) parts.push(s.zip);
        return parts.join(", ");
    }

    save() {
        this.props.onSave({ ...this.state, preview: this.preview });
        this.props.close();
    }
}
