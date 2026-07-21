/** @odoo-module **/

// The AI layer composes from OUTSIDE the core: it patches the exported
// CareCommand OWL component and fetches its own flags via a gated service.
// With AI off (or this module absent) every flag is false → zero AI DOM, and
// the wall looks EXACTLY like Phase 3.

import { patch } from "@web/core/utils/patch";
import { useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { CareCommand } from "@health_care_command/js/care_command";

patch(CareCommand.prototype, {
    setup() {
        super.setup();
        this.ai = useState({
            enabled: false,
            drafts: false,
            brief: false,
            provider_name: "",
            drafting: false,
            briefing: false,
            briefOpen: false,
            briefConvId: null,
            briefText: [],
            briefStamp: "",
        });
        onWillStart(async () => {
            try {
                const flags = await this.orm.call("care.ai.assist", "ai_flags", []);
                Object.assign(this.ai, flags || {});
            } catch {
                // gate errored / module state odd → stay fully off (no AI DOM)
            }
        });
    },

    // --- gating getters (drive the .ai-only affordances) ------------------
    get aiCanDraft() {
        return this.ai.enabled && this.ai.drafts && !!this.state.selected && this.canReply;
    },
    get aiCanBrief() {
        return this.ai.enabled && this.ai.brief && !!this.state.selected;
    },
    get aiBriefShown() {
        return this.ai.briefOpen && this.ai.briefConvId === this.state.selected;
    },

    _aiError(e) {
        return (e && e.data && e.data.message) || _t("AI is unavailable — continue manually.");
    },

    // --- reply draft: fills the composer, never sends ---------------------
    async aiDraft() {
        if (this.ai.drafting || !this.state.selected) {
            return;
        }
        this.ai.drafting = true;
        try {
            const res = await this.orm.call("care.ai.assist", "ai_draft_reply", [this.state.selected]);
            const text = (res && res.text) || "";
            if (text) {
                this.state.composer = this.state.composer
                    ? this.state.composer + "\n" + text
                    : text;
                this.notification.add(_t("AI draft — review before sending"), { type: "info" });
            } else {
                this.notification.add(_t("The AI returned nothing — continue manually."), {
                    type: "warning",
                });
            }
        } catch (e) {
            this.notification.add(this._aiError(e), { type: "danger" });
        } finally {
            this.ai.drafting = false;
        }
    },

    // --- continuity brief: on-demand card, dismissible --------------------
    async aiBrief() {
        if (this.ai.briefing || !this.state.selected) {
            return;
        }
        this.ai.briefing = true;
        try {
            const res = await this.orm.call("care.ai.assist", "ai_brief", [this.state.selected]);
            this.ai.briefText = (res && res.bullets) || [];
            this.ai.briefStamp = (res && res.stamp) || "";
            this.ai.briefConvId = this.state.selected;
            this.ai.briefOpen = true;
        } catch (e) {
            this.notification.add(this._aiError(e), { type: "danger" });
        } finally {
            this.ai.briefing = false;
        }
    },

    dismissBrief() {
        this.ai.briefOpen = false;
        this.ai.briefText = [];
    },
});
