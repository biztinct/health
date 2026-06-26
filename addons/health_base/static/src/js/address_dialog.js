/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

/**
 * Reusable Vietnamese address editor dialog. Works without a saved record:
 * it edits an in-memory address dict and returns it via onSave. Fields mirror
 * res.partner / view_health_patient_address_form; the live preview mirrors
 * res_partner._compute_vietnamese_address.
 *
 * City = catchment province (dropdown); District = health.vietnamese.district
 * (dropdown filtered by the chosen City). The denormalized `city` string is
 * derived ("<District>, <City>") and returned alongside, so existing geocoding
 * / address formatting that read `city` keep working.
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
        this.orm = useService("orm");
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
            // City = catchment province; District = vietnamese district.
            catchment_province_id: a.catchment_province_id || false,
            district_id: a.district_id || false,
            zip: a.zip || "",
        });
        this.provinces = [];   // [{id, name}]
        this.districts = [];   // [{id, name, province_name}]

        onWillStart(async () => {
            this.provinces = await this.orm.searchRead(
                "health.catchment.province", [], ["id", "name"], { order: "sequence, name" });
            this.districts = await this.orm.searchRead(
                "health.vietnamese.district", [], ["id", "name", "province_name"],
                { order: "province_name, name" });
        });
    }

    get dialogTitle() {
        return this.props.title || "Home Address";
    }

    get cityName() {
        const p = this.provinces.find((x) => x.id === this.state.catchment_province_id);
        return p ? p.name : "";
    }

    // Districts that belong to the selected City (match on province name).
    get districtOptions() {
        const city = this.cityName;
        if (!city) {
            return [];
        }
        return this.districts.filter((d) => d.province_name === city);
    }

    get districtName() {
        const d = this.districts.find((x) => x.id === this.state.district_id);
        return d ? d.name : "";
    }

    onCityChange(ev) {
        this.state.catchment_province_id = parseInt(ev.target.value, 10) || false;
        // Drop a district that no longer belongs to the chosen city.
        if (this.state.district_id) {
            const stillValid = this.districtOptions.some((d) => d.id === this.state.district_id);
            if (!stillValid) {
                this.state.district_id = false;
            }
        }
    }

    onDistrictChange(ev) {
        this.state.district_id = parseInt(ev.target.value, 10) || false;
    }

    // Derived denormalized city string ("<District>, <City>").
    get cityString() {
        return [this.districtName, this.cityName].filter(Boolean).join(", ");
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
        if (this.cityString) parts.push(this.cityString);
        if (s.zip) parts.push(s.zip);
        return parts.join(", ");
    }

    save() {
        this.props.onSave({
            ...this.state,
            // Keep the denormalized string for callers/back-compat consumers.
            city: this.cityString,
            preview: this.preview,
        });
        this.props.close();
    }
}
