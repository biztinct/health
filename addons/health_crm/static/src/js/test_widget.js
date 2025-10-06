/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

export class TestWidget extends Component {
    static template = "health_crm.TestWidget";
    static props = {
        record: Object,
        name: String,
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        console.log("=== TEST WIDGET LOADED ===");
        console.log("Props:", this.props);
        console.log("Props.name:", this.props.name);
        console.log("Props.record:", this.props.record);
        console.log("Props.record.data:", this.props.record.data);

        const fieldValue = this.props.record.data[this.props.name];
        console.log("Field value:", fieldValue);
        console.log("Field value type:", typeof fieldValue);
        console.log("Field value is array:", Array.isArray(fieldValue));

        if (fieldValue) {
            console.log("Field value constructor:", fieldValue.constructor.name);
            console.log("Field value keys:", Object.keys(fieldValue));
            console.log("Field value.currentIds:", fieldValue.currentIds);
            console.log("Field value.records:", fieldValue.records);
            console.log("Field value.count:", fieldValue.count);

            // Try to get the actual record IDs
            if (fieldValue.records) {
                console.log("Number of records:", fieldValue.records.length);
                console.log("First record:", fieldValue.records[0]);
            }
        }
    }
}

registry.category("fields").add("test_widget", {
    component: TestWidget,
    supportedTypes: ["one2many"],
});
