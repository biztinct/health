/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * The phone panel. Rendered once, from the main_components registry, so it
 * survives navigation — the service holds the call, this only draws it.
 *
 * The one rule that shapes the whole component: a control is shown when it can
 * actually do something. Answer appears only when THIS browser holds the
 * ringing SDK session; an awareness card from the server offers "open the
 * record" and, where an extension exists, "answer on your phone" — never a
 * button that would pretend to pick up a call this browser cannot reach.
 */
export class Voip24hPhonePanel extends Component {
    static template = "health_voip24h.PhonePanel";
    static props = {};

    setup() {
        this.phone = useService("voip24h_phone");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState(this.phone.state);
        this.local = useState({
            dialInput: "",
            transferInput: "",
            digitsInput: "",
            showKeypad: false,
            showTransfer: false,
            wrapUpNotes: "",
            wrapUpOutcome: "",
            wrapUpSession: null,
            tab: "phone",
        });

        onWillStart(async () => {
            await this.phone.refresh();
        });
    }

    // ------------------------------------------------------------------

    get statusLabel() {
        const map = {
            off: _t("Phone off"),
            initialising: _t("Starting…"),
            registering: _t("Signing in…"),
            ready: _t("Ready"),
            failed: _t("Not working"),
            disconnected: _t("Signed out"),
        };
        return map[this.state.browserState] || this.state.browserState;
    }

    get callLabel() {
        const map = {
            idle: "",
            dialling: _t("Calling…"),
            ringing: _t("Ringing"),
            active: _t("On a call"),
            ending: _t("Ending…"),
            wrap_up: _t("Write up this call"),
        };
        return map[this.state.callState] || "";
    }

    get talkDisplay() {
        const total = this.state.talkSeconds || 0;
        const minutes = String(Math.floor(total / 60)).padStart(2, "0");
        const seconds = String(total % 60).padStart(2, "0");
        return `${minutes}:${seconds}`;
    }

    get canDial() {
        return (
            this.state.browserState === "ready" &&
            this.state.profile &&
            this.state.profile.outgoing_enabled &&
            (this.state.callState === "idle" || this.state.callState === "wrap_up")
        );
    }

    /** Hang up stays live even when new outgoing calls are switched off. */
    get canHangUp() {
        return ["dialling", "active", "ending"].includes(this.state.callState);
    }

    get showKeypadControl() {
        return (
            this.state.callState === "active" &&
            this.state.profile &&
            this.state.profile.dtmf_enabled
        );
    }

    // ------------------------------------------------------------------

    togglePanel() {
        this.state.panelOpen = !this.state.panelOpen;
    }

    async onStartPhone() {
        await this.phone.startPhone();
    }

    async onTakeOver() {
        await this.phone.startPhone({ takeover: true });
    }

    async onStopPhone() {
        await this.phone.stopPhone();
    }

    onDial() {
        const number = (this.local.dialInput || "").trim();
        if (!number) {
            return;
        }
        this.phone.dial(number);
        this.local.dialInput = "";
    }

    onAnswer() {
        this.phone.answer();
    }

    onReject() {
        this.phone.reject();
    }

    onHangUp() {
        this.phone.hangup();
    }

    onToggleMute() {
        this.phone.setMuted(!this.state.muted);
    }

    onToggleHold() {
        this.phone.setHeld(!this.state.held);
    }

    onSendDigits() {
        const digits = (this.local.digitsInput || "").replace(/[^0-9*#]/g, "");
        if (!digits) {
            return;
        }
        this.phone.sendDigits(digits);
        this.local.digitsInput = "";
        this.local.showKeypad = false;
    }

    onTransfer() {
        const target = (this.local.transferInput || "").trim();
        if (!target) {
            return;
        }
        this.phone.transfer(target);
        this.local.transferInput = "";
        this.local.showTransfer = false;
    }

    // ------------------------------------------------------------------

    async openWrapUp(session) {
        const detail = await this.phone.openSession(session.id);
        if (!detail) {
            return;
        }
        this.local.wrapUpSession = detail;
        this.local.wrapUpNotes = detail.notes || "";
        this.local.wrapUpOutcome = detail.business_outcome || "";
        this.local.tab = "wrapup";
    }

    async saveWrapUp() {
        const session = this.local.wrapUpSession;
        if (!session) {
            return;
        }
        const version = await this.phone.saveDisposition(session.id, {
            notes: this.local.wrapUpNotes,
            outcome: this.local.wrapUpOutcome,
            version: session.version,
        });
        if (version !== null) {
            this.notification.add(_t("Call notes saved."), { type: "success" });
            this.local.wrapUpSession = null;
            this.local.tab = "phone";
        }
    }

    async onCalledBack(session) {
        await this.phone.markCalledBack(session.id);
    }

    async openRecord(session) {
        if (session.partner_id) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "res.partner",
                res_id: session.partner_id,
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }
        if (session.lead_id) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "crm.lead",
                res_id: session.lead_id,
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "voip.call.session",
            res_id: session.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onDismissAwareness(session) {
        // Explicitly NOT a reject: the call keeps ringing wherever it is
        // ringing, this only clears the card.
        this.phone.dismissAwareness(session.id);
    }

    callbackFor(session) {
        const number = session.peer;
        if (!number) {
            this.notification.add(
                _t("This caller withheld their number, so there is nothing to ring back."),
                { type: "warning" }
            );
            return;
        }
        this.phone.dial(number);
    }
}

registry.category("main_components").add("Voip24hPhonePanel", {
    Component: Voip24hPhonePanel,
});
