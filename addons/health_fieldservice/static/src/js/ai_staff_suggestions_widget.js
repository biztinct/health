/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class AiStaffSuggestionsWidget extends Component {
    static template = "health_fieldservice.AiStaffSuggestionsWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            suggestions: [],
            otherStaff: [],
            selectedStaffId: null,
            loading: true,
        });
        onWillStart(() => this._parseSuggestions());
        onWillUpdateProps((nextProps) => {
            this._parseSuggestionsFromProps(nextProps);
        });
    }

    _parseSuggestions() {
        const raw = this.props.record.data[this.props.name];
        this._parseRaw(raw);
    }

    _parseSuggestionsFromProps(props) {
        const raw = props.record.data[props.name];
        this._parseRaw(raw);
    }

    _parseRaw(raw) {
        try {
            const all = JSON.parse(raw || "[]");
            this.state.suggestions = all.slice(0, 3);
            this.state.otherStaff = all.slice(3);
            this.state.loading = false;
        } catch {
            this.state.suggestions = [];
            this.state.otherStaff = [];
            this.state.loading = false;
        }
    }

    getScoreClass(score) {
        if (score >= 80) return "score-high";
        if (score >= 60) return "score-med";
        return "score-low";
    }

    getStatusDotClass(status) {
        if (status === "available") return "dot-available";
        if (status === "busy") return "dot-busy";
        return "dot-off";
    }

    getAvatarClass(index) {
        const classes = ["green", "blue", "yellow"];
        return classes[index % classes.length];
    }

    getSkillClass(status) {
        if (status === "match") return "skill-match";
        if (status === "partial") return "skill-partial";
        if (status === "extra") return "skill-match";
        return "skill-missing";
    }

    getSkillIcon(status) {
        if (status === "match" || status === "extra") return "fa-check";
        if (status === "partial") return "fa-minus";
        return "fa-times";
    }

    getBlockStyle(block) {
        const dayStart = 7;
        const dayEnd = 18;
        const totalHours = dayEnd - dayStart;
        const left = ((block.start_hour - dayStart) / totalHours) * 100;
        const width = ((block.end_hour - block.start_hour) / totalHours) * 100;
        return `left:${Math.max(0, left)}%;width:${Math.min(width, 100 - left)}%`;
    }

    getBlockClass(block) {
        if (block.type === "proposed") return "tl-block proposed";
        if (block.conflict) return "tl-block conflict";
        return "tl-block existing";
    }

    getBlockLabel(block) {
        const sh = Math.floor(block.start_hour);
        const sm = Math.round((block.start_hour - sh) * 60);
        const eh = Math.floor(block.end_hour);
        const em = Math.round((block.end_hour - eh) * 60);
        const fmt = (h, m) => `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
        return `${fmt(sh, sm)}-${fmt(eh, em)}`;
    }

    selectStaff(staffId) {
        this.state.selectedStaffId = staffId;
        this.props.record.update({ selected_suggestion_staff_id: [staffId] });
    }

    isSelected(staffId) {
        return this.state.selectedStaffId === staffId;
    }

    get timelineHours() {
        return [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18];
    }

    get selectedStaff() {
        if (!this.state.selectedStaffId) return null;
        const all = [...this.state.suggestions, ...this.state.otherStaff];
        return all.find((s) => s.staff_id === this.state.selectedStaffId) || null;
    }
}

registry.category("fields").add("ai_staff_suggestions", {
    component: AiStaffSuggestionsWidget,
    supportedTypes: ["text"],
});
