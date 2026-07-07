/** @odoo-module **/
// health_forms backend renderer (spec §4.5).
//
// health_form_renderer — form-view widget bound to schema_snapshot +
// answers_json on health.form.instance (and to schema_json in preview
// mode on the template form). Renders questions per the §4.2 shared
// JSON schema contract, evaluates visible_if, shows a live total-score
// footer with the band color chip (flat mono colors only).
//
// health_json_edit — small editable JSON textarea used for
// options_json / scoring_bands_json / visible_if_json authoring (the
// stock "json" widget is display-only).

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

function parseMaybeJson(value) {
    if (value == null || value === false) {
        return null;
    }
    if (typeof value === "string") {
        try {
            return JSON.parse(value);
        } catch {
            return null;
        }
    }
    return value;
}

export class HealthFormRenderer extends Component {
    static template = "health_forms.FormRenderer";
    static props = {
        ...standardFieldProps,
        schemaField: { type: String, optional: true },
        preview: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        // Preview mode keeps answers locally (never written to the
        // record) so authors can exercise visible_if and scoring.
        this.previewState = useState({ answers: {} });
    }

    get schema() {
        const source = this.props.preview
            ? this.props.record.data[this.props.name]
            : this.props.record.data[this.props.schemaField || "schema_snapshot"];
        const schema = parseMaybeJson(source);
        if (!schema || !Array.isArray(schema.questions)) {
            return { questions: [], scoring: { method: "none", bands: [] } };
        }
        return {
            questions: schema.questions,
            scoring: schema.scoring || { method: "none", bands: [] },
        };
    }

    get answers() {
        if (this.props.preview) {
            return this.previewState.answers;
        }
        return parseMaybeJson(this.props.record.data[this.props.name]) || {};
    }

    get isEditable() {
        return this.props.preview || !this.props.readonly;
    }

    get visibleQuestions() {
        return this.schema.questions.filter((question) =>
            this.isVisible(question)
        );
    }

    get hasScoring() {
        return this.schema.scoring && this.schema.scoring.method === "sum";
    }

    get totalScore() {
        let total = 0.0;
        for (const question of this.visibleQuestions) {
            total += this.contribution(question);
        }
        return total;
    }

    get band() {
        const bands = (this.schema.scoring && this.schema.scoring.bands) || [];
        const total = this.totalScore;
        for (const band of bands) {
            const min = band.min == null ? -Infinity : band.min;
            const max = band.max == null ? Infinity : band.max;
            if (total >= min && total <= max) {
                return band;
            }
        }
        return null;
    }

    // ------------------------------------------------------------------
    // §4.2 contract evaluation (mirrors health.form.instance Python)
    // ------------------------------------------------------------------
    isVisible(question) {
        const condition = question.visible_if;
        if (!condition) {
            return true;
        }
        const answer = this.answers[condition.key];
        const value = condition.value;
        switch (condition.operator || "=") {
            case "=":
                return answer === value;
            case "!=":
                return answer !== value;
            case "in":
                if (Array.isArray(answer)) {
                    return Array.isArray(value)
                        ? answer.some((item) => value.includes(item))
                        : answer.includes(value);
                }
                return Array.isArray(value)
                    ? value.includes(answer)
                    : answer === value;
            case ">=":
                return answer != null && parseFloat(answer) >= parseFloat(value);
            case "<=":
                return answer != null && parseFloat(answer) <= parseFloat(value);
            default:
                return true;
        }
    }

    contribution(question) {
        const answer = this.answers[question.key];
        const options = question.options || [];
        if (answer == null) {
            return 0.0;
        }
        switch (question.type) {
            case "number": {
                const weight = question.score_weight || 0.0;
                const value = parseFloat(answer);
                return weight > 0 && !isNaN(value) ? value * weight : 0.0;
            }
            case "selection": {
                const option = options.find((o) => o.value === answer);
                return option && option.score != null ? option.score : 0.0;
            }
            case "multiselect": {
                if (!Array.isArray(answer)) {
                    return 0.0;
                }
                return options
                    .filter((o) => answer.includes(o.value))
                    .reduce((sum, o) => sum + (o.score || 0), 0);
            }
            case "boolean": {
                const key = answer ? "true" : "false";
                const option = options.find(
                    (o) => String(o.value).toLowerCase() === key
                );
                return option && option.score != null ? option.score : 0.0;
            }
            default:
                return 0.0;
        }
    }

    // ------------------------------------------------------------------
    // Answer updates
    // ------------------------------------------------------------------
    setAnswer(key, value) {
        if (!this.isEditable) {
            return;
        }
        const next = { ...this.answers, [key]: value };
        if (this.props.preview) {
            this.previewState.answers = next;
        } else {
            this.props.record.update({ [this.props.name]: next });
        }
    }

    onNumberInput(question, ev) {
        const raw = ev.target.value;
        this.setAnswer(question.key, raw === "" ? null : parseFloat(raw));
    }

    onTextInput(question, ev) {
        this.setAnswer(question.key, ev.target.value || null);
    }

    onDateInput(question, ev) {
        this.setAnswer(question.key, ev.target.value || null);
    }

    onSelect(question, value) {
        this.setAnswer(question.key, value);
    }

    onBoolean(question, value) {
        this.setAnswer(question.key, value);
    }

    toggleMulti(question, value) {
        const current = Array.isArray(this.answers[question.key])
            ? [...this.answers[question.key]]
            : [];
        const index = current.indexOf(value);
        if (index >= 0) {
            current.splice(index, 1);
        } else {
            current.push(value);
        }
        this.setAnswer(question.key, current);
    }

    isMultiChecked(question, value) {
        const answer = this.answers[question.key];
        return Array.isArray(answer) && answer.includes(value);
    }

    // ------------------------------------------------------------------
    // Media (photo / signature): upload creates an ir.attachment and the
    // answer becomes {"attachment_id": id} per the §4.2 contract.
    // ------------------------------------------------------------------
    attachmentId(question) {
        const answer = this.answers[question.key];
        return answer && answer.attachment_id ? answer.attachment_id : null;
    }

    attachmentUrl(question) {
        const attachmentId = this.attachmentId(question);
        return attachmentId ? `/web/content/${attachmentId}` : null;
    }

    async onMediaFile(question, ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) {
            return;
        }
        const base64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () =>
                resolve(String(reader.result).split(",", 2)[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
        const values = {
            name: file.name || `${question.key}.png`,
            type: "binary",
            datas: base64,
            mimetype: file.type || "image/png",
        };
        if (this.props.record.resId) {
            values.res_model = this.props.record.resModel;
            values.res_id = this.props.record.resId;
        }
        try {
            const [attachmentId] = await this.orm.create("ir.attachment", [
                values,
            ]);
            this.setAnswer(question.key, { attachment_id: attachmentId });
        } catch (error) {
            this.notification.add(_t("Could not upload the file."), {
                type: "danger",
            });
            throw error;
        }
    }

    clearMedia(question) {
        this.setAnswer(question.key, null);
    }

    // ------------------------------------------------------------------
    // Labels
    // ------------------------------------------------------------------
    optionLabel(option) {
        return option.label_vi
            ? `${option.label} / ${option.label_vi}`
            : option.label;
    }
}

export const healthFormRenderer = {
    component: HealthFormRenderer,
    displayName: _t("Clinical Form Renderer"),
    supportedTypes: ["json"],
    extractProps: ({ options }) => ({
        schemaField: options.schema_field,
        preview: Boolean(options.preview),
    }),
};

registry.category("fields").add("health_form_renderer", healthFormRenderer);

// ---------------------------------------------------------------------
// health_json_edit — editable JSON textarea (authoring helper)
// ---------------------------------------------------------------------
export class HealthJsonEdit extends Component {
    static template = "health_forms.JsonEdit";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
        this.state = useState({ invalid: false });
    }

    get textValue() {
        const value = this.props.record.data[this.props.name];
        if (value == null || value === false) {
            return "";
        }
        return typeof value === "string"
            ? value
            : JSON.stringify(value, null, 2);
    }

    onChange(ev) {
        const raw = ev.target.value.trim();
        if (!raw) {
            this.state.invalid = false;
            this.props.record.update({ [this.props.name]: false });
            return;
        }
        try {
            const parsed = JSON.parse(raw);
            this.state.invalid = false;
            this.props.record.update({ [this.props.name]: parsed });
        } catch {
            this.state.invalid = true;
            this.notification.add(_t("Invalid JSON — value not saved."), {
                type: "warning",
            });
        }
    }
}

export const healthJsonEdit = {
    component: HealthJsonEdit,
    displayName: _t("JSON (editable)"),
    supportedTypes: ["json"],
};

registry.category("fields").add("health_json_edit", healthJsonEdit);
