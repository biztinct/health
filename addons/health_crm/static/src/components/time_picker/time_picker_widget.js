/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FloatTimeField } from "@web/views/fields/float_time/float_time_field";
import { Component, useState, useRef, onPatched } from "@odoo/owl";

/**
 * Premium Time Picker Widget
 * 
 * Renders a beautiful grid of clickable time slot pills instead of the
 * default float_time text input. Designed for healthcare booking wizards
 * with a modern, Calendly-inspired design.
 * 
 * Usage in XML: <field name="booking_time" widget="time_picker"/>
 */
export class TimePickerWidget extends Component {
    static template = "health_crm.TimePickerWidget";
    static props = {
        ...FloatTimeField.props,
    };

    setup() {
        this.state = useState({
            section: this._getInitialSection(),
            editingManual: false,
            manualInput: "",
        });
        this.morningSlots = this._generateSlots(6, 12);
        this.afternoonSlots = this._generateSlots(12, 18);
        this.eveningSlots = this._generateSlots(18, 22);
        this.manualInputRef = useRef("manualInput");
        onPatched(() => {
            if (this.state.editingManual && this.manualInputRef.el) {
                const el = this.manualInputRef.el;
                el.focus();
                const len = el.value.length;
                el.setSelectionRange(len, len);
            }
        });
    }

    // ------- helpers -------

    _getInitialSection() {
        const val = this.props.record.data[this.props.name] || 0;
        if (val >= 18) return "evening";
        if (val >= 12) return "afternoon";
        return "morning";
    }

    _generateSlots(startHour, endHour) {
        const slots = [];
        for (let h = startHour; h < endHour; h++) {
            for (let m = 0; m < 60; m += 30) {
                const floatVal = h + m / 60;
                const label = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
                slots.push({ value: floatVal, label });
            }
        }
        return slots;
    }

    get currentValue() {
        return this.props.record.data[this.props.name] || 0;
    }

    get displayTime() {
        const val = this.currentValue;
        const h = Math.floor(val);
        const m = Math.round((val - h) * 60);
        return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
    }

    get activeSlots() {
        switch (this.state.section) {
            case "morning": return this.morningSlots;
            case "afternoon": return this.afternoonSlots;
            case "evening": return this.eveningSlots;
            default: return this.morningSlots;
        }
    }

    isSelected(slotValue) {
        // Match within 0.001 tolerance for float comparison
        return Math.abs(this.currentValue - slotValue) < 0.001;
    }

    isNow(slotValue) {
        const now = new Date();
        const nowFloat = now.getHours() + now.getMinutes() / 60;
        return Math.abs(nowFloat - slotValue) < 0.5; // within 30 min
    }

    // ------- actions -------

    onSelectSlot(slotValue) {
        if (this.props.readonly) return;
        this.props.record.update({ [this.props.name]: slotValue });
        this.state.editingManual = false;
    }

    onSetSection(section) {
        this.state.section = section;
    }

    onDisplayClick() {
        if (this.props.readonly) return;
        this.state.editingManual = true;
        this.state.manualInput = this.displayTime;
    }

    onManualInput(ev) {
        this.state.manualInput = ev.target.value;
    }

    onManualKeydown(ev) {
        if (ev.key === "Enter") {
            this._applyManualTime();
        } else if (ev.key === "Escape") {
            this.state.editingManual = false;
        }
    }

    onManualBlur() {
        this._applyManualTime();
    }

    _applyManualTime() {
        const raw = this.state.manualInput.trim();
        const match = raw.match(/^(\d{1,2}):(\d{2})$/);
        if (match) {
            const h = parseInt(match[1], 10);
            const m = parseInt(match[2], 10);
            if (h >= 0 && h <= 23 && m >= 0 && m <= 59) {
                const floatVal = h + m / 60;
                this.props.record.update({ [this.props.name]: floatVal });
                // Switch section to match new time
                if (floatVal >= 18) this.state.section = "evening";
                else if (floatVal >= 12) this.state.section = "afternoon";
                else this.state.section = "morning";
            }
        }
        this.state.editingManual = false;
    }
}

registry.category("fields").add("time_picker", {
    component: TimePickerWidget,
    supportedTypes: ["float"],
});
