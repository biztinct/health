/** @odoo-module */
import { Component, useState, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { deserializeDateTime } from "@web/core/l10n/dates";

export class BookingStaffSheet extends Component {
    static template = "health_fieldservice.BookingStaffSheet";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            isOpen: false,
            assignments: [],
            loading: false,
        });

        useExternalListener(window, "keydown", (ev) => {
            if (ev.key === "Escape" && this.state.isOpen) {
                this.close();
            }
        });
    }

    t(text) {
        return _t(text);
    }

    get resId() {
        return this.props.record.resId;
    }

    async open() {
        this.state.isOpen = true;
        this.state.loading = true;
        document.body.classList.add("vu-side-sheet-active");
        try {
            const assignments = await this.orm.searchRead(
                "health.staff.assignment",
                [["fso_id", "=", this.resId], ["state", "!=", "template"]],
                ["staff_id", "assignment_status", "assignment_date", "planned_start_time", "planned_end_time", "assignment_type"],
                { order: "assignment_date desc", limit: 20 }
            );
            this.state.assignments = assignments;
        } catch {
            this.state.assignments = [];
        }
        this.state.loading = false;
    }

    close() {
        this.state.isOpen = false;
        document.body.classList.remove("vu-side-sheet-active");
    }

    onBackdropClick() {
        this.close();
    }

    get assignmentCount() {
        return this.state.assignments.length;
    }

    get activeAssignments() {
        return this.state.assignments.filter(a => a.assignment_status === "assigned");
    }

    getStatusClass(status) {
        const map = {
            assigned: "text-bg-primary",
            in_progress: "text-bg-info",
            completed: "text-bg-success",
            cancelled: "text-bg-danger",
        };
        return map[status] || "text-bg-secondary";
    }

    getStatusLabel(status) {
        const map = {
            assigned: _t("Assigned"),
            in_progress: _t("In Progress"),
            completed: _t("Completed"),
            cancelled: _t("Cancelled"),
        };
        return map[status] || status;
    }

    /** planned_start_time / planned_end_time are datetimes ("2026-11-05
     *  07:00:00", UTC as stored), not float hours: read them as such and
     *  show the reader's wall clock. A float is still accepted. */
    formatTime(value) {
        if (value === false || value === null || value === undefined || value === "") {
            return "";
        }
        if (typeof value === "number") {
            const hours = Math.floor(value);
            const minutes = Math.round((value - hours) * 60);
            return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
        }
        const dt = deserializeDateTime(value);
        return dt.isValid ? dt.toFormat("HH:mm") : "";
    }

    async openFullTimeline() {
        this.close();
        await this.action.doActionButton({
            type: "object",
            name: "action_manual_assign_staff",
            resModel: "health.fieldservice.order",
            resId: this.resId,
            resIds: [this.resId],
        });
    }

    async openAIAssign() {
        this.close();
        await this.action.doActionButton({
            type: "object",
            name: "action_ai_assign_staff",
            resModel: "health.fieldservice.order",
            resId: this.resId,
            resIds: [this.resId],
        });
    }
}

registry.category("view_widgets").add("vu_staff_sheet", {
    component: BookingStaffSheet,
});
