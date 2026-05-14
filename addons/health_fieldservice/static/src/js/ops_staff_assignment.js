/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class OpsStaffAssignment extends Component {
    static template = "health_fieldservice.OpsStaffAssignment";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const context = this.props.action && this.props.action.context || {};
        this.bookingId = context.active_id || context.default_booking_id || false;

        this.state = useState({
            isLoading: true,
            isAssigning: false,
            booking: {},
            suggestions: [],
            others: [],
            scheduleBlocks: [],
            proposedBlock: null,
            selectedStaffId: false,
            selectedStaffName: '',
            selectedStaffScore: 0,
            assignmentNote: '',
            notifyStaff: true,
            notifyClient: true,
        });

        onWillStart(async () => {
            if (this.bookingId) {
                await this.loadData();
            }
        });
    }

    async loadData() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "health.fieldservice.order",
                "get_staff_assignment_data",
                [this.bookingId]
            );
            this.state.booking = data.booking || {};
            this.state.suggestions = data.suggestions || [];
            this.state.others = data.others || [];
            this.state.scheduleBlocks = data.schedule_blocks || [];
            this.state.proposedBlock = data.proposed_block || null;

            if (this.state.suggestions.length > 0) {
                const best = this.state.suggestions[0];
                this.state.selectedStaffId = best.id;
                this.state.selectedStaffName = best.name;
                this.state.selectedStaffScore = best.score;
            }
        } catch (e) {
            console.error('Failed to load staff assignment data:', e);
            this.notification.add(_t("Error loading assignment data"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    selectStaff(staff) {
        this.state.selectedStaffId = staff.id;
        this.state.selectedStaffName = staff.name;
        this.state.selectedStaffScore = staff.score;
    }

    isSelected(staffId) {
        return this.state.selectedStaffId === staffId;
    }

    getScoreClass(score) {
        if (score >= 85) return 'sa-score-high';
        if (score >= 70) return 'sa-score-med';
        return 'sa-score-low';
    }

    getAvatarColor(index) {
        const colors = ['green', 'blue', 'yellow'];
        return colors[index % colors.length];
    }

    getTimelineBlockStyle(block) {
        const startPct = ((block.start_hour - 7) / 11) * 100;
        const widthPct = ((block.end_hour - block.start_hour) / 11) * 100;
        return `left:${Math.max(0, startPct)}%;width:${Math.min(widthPct, 100 - startPct)}%`;
    }

    getProposedBlockStyle() {
        if (!this.state.proposedBlock) return '';
        const b = this.state.proposedBlock;
        const startPct = ((b.start_hour - 7) / 11) * 100;
        const widthPct = ((b.end_hour - b.start_hour) / 11) * 100;
        return `left:${Math.max(0, startPct)}%;width:${Math.min(widthPct, 100 - startPct)}%`;
    }

    getSelectedSchedule() {
        return this.state.scheduleBlocks.find(s => s.staff_id === this.state.selectedStaffId);
    }

    hasConflict() {
        if (!this.state.proposedBlock) return false;
        const schedule = this.getSelectedSchedule();
        if (!schedule) return false;
        const pb = this.state.proposedBlock;
        return schedule.blocks.some(b => b.start_hour < pb.end_hour && b.end_hour > pb.start_hour);
    }

    onNoteChange(ev) {
        this.state.assignmentNote = ev.target.value;
    }

    onNotifyStaffChange(ev) {
        this.state.notifyStaff = ev.target.checked;
    }

    onNotifyClientChange(ev) {
        this.state.notifyClient = ev.target.checked;
    }

    goBack() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.fieldservice.order',
            res_id: this.bookingId,
            views: [[false, 'form']],
            target: 'fullscreen',
            context: { form_view_ref: 'health_fieldservice.view_health_fso_form_ops' },
        }, { clearBreadcrumbs: true });
    }

    async confirmAssignment() {
        if (this.state.isAssigning) return;
        if (!this.state.selectedStaffId) {
            this.notification.add(_t("Please select a staff member"), { type: "warning" });
            return;
        }

        this.state.isAssigning = true;
        try {
            await this.orm.call(
                "health.fieldservice.order",
                "action_quick_assign_staff",
                [this.bookingId],
                { staff_id: this.state.selectedStaffId }
            );
            this.notification.add(
                _t("Staff assigned successfully!"),
                { type: "success" }
            );
            this.goBack();
        } catch (e) {
            console.error('Assignment error:', e);
            this.notification.add(_t("Could not assign staff"), { type: "danger" });
        }
        this.state.isAssigning = false;
    }

    // Sidebar
}

registry.category("actions").add("ops_staff_assignment", OpsStaffAssignment);

export default OpsStaffAssignment;
