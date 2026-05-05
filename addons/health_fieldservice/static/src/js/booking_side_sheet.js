/** @odoo-module */
import { Component, useState, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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
            assigned: "Assigned",
            in_progress: "In Progress",
            completed: "Completed",
            cancelled: "Cancelled",
        };
        return map[status] || status;
    }

    formatTime(timeFloat) {
        if (!timeFloat && timeFloat !== 0) return "";
        const hours = Math.floor(timeFloat);
        const minutes = Math.round((timeFloat - hours) * 60);
        return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
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
