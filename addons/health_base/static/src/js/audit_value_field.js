/** @odoo-module **/
/**
 * Audit Log From / To values (UAT round 10, item 3).
 *
 * The log stores the old and new value as text; for a date-time field that
 * text is the stored UTC instant ("2026-11-12 02:00:00" for 09:00 in Vietnam).
 * Show it in the viewer's time zone with the same formatter every other
 * date-time list column uses. Date-only and all other values are unchanged.
 */
import { registry } from "@web/core/registry";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { formatDateTime } from "@web/views/fields/formatters";
import { CharField, charField } from "@web/views/fields/char/char_field";

export class AuditValueField extends CharField {
    get formattedValue() {
        const record = this.props.record;
        const value = record.data[this.props.name];
        if (value && record.data.field_type === "datetime") {
            const instant = deserializeDateTime(String(value).slice(0, 19));
            if (instant.isValid) {
                return formatDateTime(instant);
            }
        }
        return super.formattedValue;
    }
}

registry.category("fields").add("audit_value", {
    ...charField,
    component: AuditValueField,
    fieldDependencies: [{ name: "field_type", type: "char" }],
});
