/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// Channel dock definition. Active = zalo/call/email/zns. The rest render
// disabled ("Coming soon") per the Phase-1 non-goals.
// Labels go through _t (returns a LazyTranslatedString, safe at module load).
const CHANNELS = [
    { key: "zalo", label: _t("Zalo"), short: _t("ZALO"), ic: "ic-chat", cv: "var(--ch-zalo)", active: true },
    { key: "call", label: _t("Calls"), short: _t("CALLS"), ic: "ic-phone", cv: "var(--ch-call)", active: true },
    { key: "email", label: _t("Email"), short: _t("EMAIL"), ic: "ic-mail", cv: "var(--ch-email)", active: true },
    { key: "zns", label: _t("ZNS"), short: _t("ZNS"), ic: "ic-send", cv: "var(--ch-zns)", active: true },
    { key: "wa", label: _t("WhatsApp"), short: _t("WHATSAPP"), ic: "ic-chat", cv: "var(--ch-wa)", active: false },
    { key: "fb", label: _t("Messenger"), short: _t("FB MSGR"), ic: "ic-chat", cv: "var(--ch-fb)", active: false },
    { key: "tg", label: _t("Telegram"), short: _t("TELEGRAM"), ic: "ic-chat", cv: "var(--ch-tg)", active: false },
    { key: "web", label: _t("Web chat"), short: _t("WEB CHAT"), ic: "ic-globe", cv: "var(--ch-web)", active: false },
];
const CH_MAP = Object.fromEntries(CHANNELS.map((c) => [c.key, c]));

const LIST_SECTIONS = [
    { key: "needs_mine", label: _t("Needs reply — mine"), ic: "ic-bolt" },
    { key: "needs_un", label: _t("Unclaimed — anyone can take"), ic: "ic-warn" },
    { key: "needs_other", label: _t("With teammates"), ic: "ic-users" },
    { key: "waiting", label: _t("Waiting / done for now"), ic: "ic-clock" },
    { key: "junk", label: _t("Junk — confirm to archive"), ic: "ic-ban" },
];

export class CareCommand extends Component {
    static template = "health_care_command.CareCommand";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.busService = useService("bus_service");
        this.CHANNELS = CHANNELS;
        this.CH_MAP = CH_MAP;
        this.LIST_SECTIONS = LIST_SECTIONS;

        this.state = useState({
            loading: true,
            error: null,
            view: "wall",            // 'wall' | 'chat'
            mineOnly: true,
            filter: null,            // channel key or null
            data: null,              // workspace payload
            selected: null,          // conv id
            detail: null,
            detailLoading: false,
            detailError: null,
            railTab: "care",         // 'care' | 'history'
            composer: "",
            sending: false,
            toast: null,
            search: "",              // chat-list search box (server-side filter)
        });

        this._busChannel = null;
        this._pollTimer = null;
        this._debounce = null;
        this._searchDebounce = null;

        onWillStart(async () => {
            await this.load();
        });
        onMounted(() => {
            this._subscribeBus();
            this._pollTimer = setInterval(() => this.load(true), 60000);
        });
        onWillUnmount(() => {
            if (this._pollTimer) clearInterval(this._pollTimer);
            if (this._debounce) clearTimeout(this._debounce);
            if (this._searchDebounce) clearTimeout(this._searchDebounce);
            if (this._toastTimer) clearTimeout(this._toastTimer);
            if (this._busChannel) this.busService.deleteChannel(this._busChannel);
            this.busService.unsubscribe?.("care.conversation/update", this._onBus);
        });
    }

    // ---------------------------------------------------------------
    // data loading
    // ---------------------------------------------------------------
    async load(silent = false) {
        if (!silent) this.state.loading = true;
        try {
            const data = await this.orm.call("care.conversation", "get_workspace_data", [], {
                channel: this.state.filter,
                mine_only: this.state.mineOnly,
                query: this.state.search || null,
            });
            this.state.data = data;
            this.state.error = null;
            if (!this._busChannel && data.company_id) {
                this._busChannel = `care_command_${data.company_id}`;
                this.busService.addChannel(this._busChannel);
            }
        } catch (e) {
            this.state.error = (e && e.message && e.message.data && e.message.data.message)
                || _t("Could not load Care Command.");
        } finally {
            this.state.loading = false;
        }
    }

    _subscribeBus() {
        this._onBus = () => {
            // debounce bus-triggered refetches (>=2s)
            if (this._debounce) clearTimeout(this._debounce);
            this._debounce = setTimeout(() => {
                this.load(true);
                if (this.state.selected) this._loadDetail(this.state.selected, true);
            }, 2000);
        };
        this.busService.subscribe("care.conversation/update", this._onBus);
    }

    // ---------------------------------------------------------------
    // derived getters
    // ---------------------------------------------------------------
    get conversations() {
        return (this.state.data && this.state.data.conversations) || [];
    }
    get me() {
        return (this.state.data && this.state.data.me) || {};
    }
    get channelCounts() {
        return (this.state.data && this.state.data.channel_counts) || {};
    }
    get team() {
        return (this.state.data && this.state.data.team) || [];
    }

    channelCount(key) {
        const c = this.channelCounts[key];
        return c ? c.total : 0;
    }
    channelNeeds(key) {
        const c = this.channelCounts[key];
        return c ? c.needs : 0;
    }

    sectionRows(key) {
        const uid = this.me.id;
        return this.conversations.filter((c) => {
            const owned = c.owner && c.owner.id;
            switch (key) {
                case "needs_mine": return c.status === "needs_reply" && owned === uid;
                case "needs_un": return c.status === "needs_reply" && !owned;
                case "needs_other": return c.status === "needs_reply" && owned && owned !== uid;
                case "waiting": return c.status === "waiting";
                case "junk": return c.status === "junk_suspect";
                default: return false;
            }
        });
    }

    get selectedConv() {
        return this.conversations.find((c) => c.id === this.state.selected) || null;
    }

    tileClass(c) {
        const cls = ["tile"];
        if (c.tier === "large") cls.push("t-lg");
        if (c.status === "waiting" || c.status === "junk_suspect") cls.push("dim");
        if (!c.owner && c.status !== "junk_suspect") cls.push("unclaimed");
        return cls.join(" ");
    }

    chan(key) {
        // Unknown / channel-less (e.g. a lead not yet reached) → neutral glyph,
        // never a misleading channel colour.
        return this.CH_MAP[key]
            || { key: "none", label: _t("Contact"), short: _t("CONTACT"), ic: "ic-user", cv: "var(--navy)", active: false };
    }

    // ---------------------------------------------------------------
    // navigation
    // ---------------------------------------------------------------
    async openChat(id) {
        this.state.selected = id;
        this.state.view = "chat";
        this.state.railTab = "care";
        await this._loadDetail(id);
    }
    toWall() {
        this.state.view = "wall";
        this.state.selected = null;
        this.state.detail = null;
    }
    async selectConv(id) {
        this.state.selected = id;
        this.state.railTab = "care";
        await this._loadDetail(id);
    }
    setFilter(key) {
        this.state.filter = this.state.filter === key ? null : key;
        this.load();
    }
    clearFilter() {
        this.state.filter = null;
        this.load();
    }
    setMine(mineOnly) {
        this.state.mineOnly = mineOnly;
        this.load();
    }
    onSearchInput(ev) {
        // server-side search, debounced 300ms (§5.4)
        this.state.search = ev.target.value;
        if (this._searchDebounce) clearTimeout(this._searchDebounce);
        this._searchDebounce = setTimeout(() => this.load(true), 300);
    }
    setRailTab(t) {
        this.state.railTab = t;
    }

    async _loadDetail(id, silent = false) {
        if (!silent) this.state.detailLoading = true;
        this.state.detailError = null;
        try {
            this.state.detail = await this.orm.call(
                "care.conversation", "get_conversation_detail", [id]);
            this.state.composer = "";
        } catch (e) {
            this.state.detailError = (e && e.message && e.message.data && e.message.data.message)
                || _t("Could not load the conversation.");
        } finally {
            this.state.detailLoading = false;
        }
    }

    // ---------------------------------------------------------------
    // helpers
    // ---------------------------------------------------------------
    relTime(iso) {
        if (!iso) return "";
        const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
        const mins = Math.floor((Date.now() - then.getTime()) / 60000);
        if (mins < 1) return _t("now");
        if (mins < 60) return `${mins}m`;
        const h = Math.floor(mins / 60);
        if (h < 24) return `${h}h`;
        return `${Math.floor(h / 24)}d`;
    }
    clockTime(iso) {
        if (!iso) return "";
        const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
        return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    toast(msg) {
        this.state.toast = msg;
        if (this._toastTimer) clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => (this.state.toast = null), 3000);
    }

    _err(e) {
        const msg = (e && e.message && e.message.data && e.message.data.message)
            || (e && e.message) || _t("Something went wrong.");
        this.notification.add(msg, { type: "danger" });
    }

    // ---------------------------------------------------------------
    // claim / ownership
    // ---------------------------------------------------------------
    async claim(id) {
        try {
            const res = await this.orm.call("care.conversation", "action_claim", [id]);
            if (res.claimed) {
                this.toast(_t("Claimed — it's yours now."));
            } else {
                const who = res.owner ? res.owner.name : _t("someone");
                this.toast(_t("Already claimed by %s", who));
            }
            await this.load(true);
            if (this.state.selected === id) await this._loadDetail(id, true);
        } catch (e) { this._err(e); }
    }
    async release(id) {
        try {
            await this.orm.call("care.conversation", "action_release", [id]);
            this.toast(_t("Released."));
            await this.load(true);
            if (this.state.selected === id) await this._loadDetail(id, true);
        } catch (e) { this._err(e); }
    }
    async takeOver(id) {
        try {
            await this.orm.call("care.conversation", "action_take_over", [id]);
            this.toast(_t("Taken over."));
            await this.load(true);
            if (this.state.selected === id) await this._loadDetail(id, true);
        } catch (e) { this._err(e); }
    }
    async setStatus(id, status) {
        try {
            await this.orm.call("care.conversation", "action_set_status", [id, status]);
            this.toast(status === "junk_suspect" ? _t("Marked as junk (reversible).") : _t("Updated."));
            await this.load(true);
            if (this.state.selected === id) await this._loadDetail(id, true);
        } catch (e) { this._err(e); }
    }

    // ---------------------------------------------------------------
    // composer
    // ---------------------------------------------------------------
    get canReply() {
        const d = this.state.detail;
        return d && d.capabilities && (d.capabilities.can_reply_zalo || d.capabilities.can_reply_email);
    }
    get sendChannel() {
        const d = this.state.detail;
        if (!d) return null;
        if (d.channel_primary === "zalo" && d.capabilities.can_reply_zalo) return "zalo";
        if (d.capabilities.can_reply_email) return "email";
        if (d.capabilities.can_reply_zalo) return "zalo";
        return null;
    }
    onComposerInput(ev) {
        this.state.composer = ev.target.value;
    }
    onComposerKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }
    async sendMessage() {
        const text = (this.state.composer || "").trim();
        if (!text || this.state.sending) return;
        const ch = this.sendChannel;
        if (!ch) return;
        this.state.sending = true;
        const method = ch === "zalo" ? "action_send_zalo" : "action_send_email";
        try {
            const bubble = await this.orm.call(
                "care.conversation", method, [this.state.selected, text]);
            if (this.state.detail && this.state.detail.timeline) {
                this.state.detail.timeline.push(bubble);
            }
            this.state.composer = "";
            await this.load(true);
        } catch (e) {
            // email/zalo server errors surfaced verbatim (report honestly)
            this._err(e);
        } finally {
            this.state.sending = false;
        }
    }

    // ---------------------------------------------------------------
    // header action strip
    // ---------------------------------------------------------------
    async _runAction(method, args = []) {
        try {
            const res = await this.orm.call("care.conversation", method,
                [this.state.selected, ...args]);
            if (res && res.type) {
                await this.action.doAction(res);   // an ir.actions.* dict
            } else if (res && res.message) {
                this.toast(res.message);
            }
            await this.load(true);
            if (this.state.selected) await this._loadDetail(this.state.selected, true);
        } catch (e) { this._err(e); }
    }
    doBook() { this._runAction("action_book"); }
    doCallback() { this._runAction("action_callback"); }
    doNote() {
        const text = (this.state.composer || "").trim();
        if (!text) {
            this.toast(_t("Type the note in the message box, then tap Note."));
            return;
        }
        this._runAction("action_add_note", [text]).then(() => (this.state.composer = ""));
    }
    doLog() { this._runAction("action_log"); }
    doLead() { this._runAction("action_create_lead"); }
    doClient() { this._runAction("action_open_client"); }
    doEscalate() { this._runAction("action_escalate"); }
    doJunk() { this.setStatus(this.state.selected, "junk_suspect"); }

    // Call button: no trivially-invokable click-to-dial exists as a public
    // seam, so Phase 1 ships a tel: fallback + toast (reported in §11).
    doCall() {
        const d = this.state.detail;
        const phone = d && d.header && d.header.phone;
        if (phone) {
            window.location.href = `tel:${phone}`;
        } else {
            this.toast(_t("No phone number on this conversation."));
        }
    }

    newContact() {
        this.action.doAction("health_crm.action_crm_new_contact");
    }
}

registry.category("actions").add("care_command", CareCommand);

export default CareCommand;
