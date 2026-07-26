/** @odoo-module **/

/**
 * Channel Connection Center (CC-C, architecture §9).
 *
 * A catalogue of channel cards plus a four-step stepper, and NOTHING else: the
 * component holds no channel knowledge of its own. Labels, status chips,
 * readiness wording and the stepper copy all arrive translated from
 * `center_overview` / `center_begin`, so the Vietnamese catalogue covers each
 * string once instead of once per surface.
 *
 * Three rules this file obeys:
 *  - the pasted key lives in component state for exactly as long as the
 *    validate RPC takes, and is zeroed the moment it returns (success OR
 *    failure). It is never logged, never stored, never re-displayed;
 *  - every stepper action disables its own button while its RPC is in flight —
 *    double-click safety on top of the server's idempotency;
 *  - the refresh poll runs only while the tab is visible. A background tab
 *    polling a setup screen is pure waste.
 */

import { registry } from "@web/core/registry";
import {
    Component,
    onWillStart,
    onWillUnmount,
    useRef,
    useState,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const MODEL = "care.channel.connection";
const REFRESH_MS = 15000;

// Icon + accent per channel key. The keys match the server Selection; the
// accents match Care Command's dock so the same channel is the same colour in
// both places.
const CHANNEL_STYLE = {
    zalo: { ic: "ic-chat", cv: "var(--ch-zalo)" },
    call: { ic: "ic-phone", cv: "var(--ch-call)" },
    email: { ic: "ic-mail", cv: "var(--ch-email)" },
    zns: { ic: "ic-send", cv: "var(--ch-zns)" },
    whatsapp: { ic: "ic-chat", cv: "var(--ch-whatsapp)" },
    fb: { ic: "ic-chat", cv: "var(--ch-fb)" },
    telegram: { ic: "ic-send", cv: "var(--ch-telegram)" },
    webchat: { ic: "ic-globe", cv: "var(--ch-webchat)" },
};

// Status chip tone. `state` is the server's, the tone is purely visual.
const STATE_TONE = {
    ready: "ok",
    expiring: "warn",
    action_required: "warn",
    error: "bad",
    disabled: "off",
    not_connected: "off",
    legacy: "off",
};

export class ChannelCenter extends Component {
    static template = "health_care_command_channels.ChannelCenter";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.CHANNEL_STYLE = CHANNEL_STYLE;
        this.modalRef = useRef("modal");

        this.state = useState({
            loading: true,
            error: null,
            cards: [],
            // stepper
            open: null, // the open card's channel key
            step: 0,
            busy: false,
            mode: null,
            steps: [],
            connectionId: null,
            hasCredentials: false,
            manage: false, // manage panel instead of the wizard
            // channel-specific working values
            token: "",
            botName: "",
            origins: "",
            greeting: "",
            snippet: "",
            demoUrl: "",
            copied: false,
            copiedWebhook: false,
            confirmOff: false,
            toast: null,
            // Zalo (CC-D): the sign-in popup and the portal-guided webhook step
            authUrl: "",
            popupBlocked: false,
            webhookUrl: "",
            webhookSecret: "",
            hasWebhookSecret: false,
        });

        // A hidden tab polls nothing: the interval is torn down on hide and
        // rebuilt (with one immediate refresh) on show.
        this._onVisibility = () => {
            if (document.hidden) {
                this._stopPolling();
            } else {
                this.load();
                this._startPolling();
            }
        };
        document.addEventListener("visibilitychange", this._onVisibility);

        onWillStart(async () => {
            await this.load();
            this._startPolling();
        });
        onWillUnmount(() => {
            this._stopPolling();
            document.removeEventListener("visibilitychange", this._onVisibility);
            clearTimeout(this._toastTimer);
            clearTimeout(this._copyTimer);
            clearTimeout(this._copyWebhookTimer);
            clearInterval(this._popupTimer);
        });
    }

    // -----------------------------------------------------------------
    // data
    // -----------------------------------------------------------------
    async load() {
        try {
            const cards = await this.orm.call(MODEL, "center_overview", []);
            this.state.cards = cards;
            this.state.error = null;
            if (this.state.open) {
                const card = this.card(this.state.open);
                if (card) {
                    this.state.connectionId = card.connection_id || this.state.connectionId;
                }
            }
        } catch (e) {
            this.state.error = this._msg(e);
        } finally {
            this.state.loading = false;
        }
    }

    _startPolling() {
        this._stopPolling();
        this._timer = setInterval(() => {
            if (!document.hidden) {
                this.load();
            }
        }, REFRESH_MS);
    }

    _stopPolling() {
        if (this._timer) {
            clearInterval(this._timer);
            this._timer = null;
        }
    }

    // -----------------------------------------------------------------
    // helpers
    // -----------------------------------------------------------------
    get cards() {
        return this.state.cards.filter((c) => !c.parent_channel);
    }

    subCards(channel) {
        return this.state.cards.filter((c) => c.parent_channel === channel);
    }

    card(channel) {
        return this.state.cards.find((c) => c.channel === channel) || null;
    }

    get openCard() {
        return this.state.open ? this.card(this.state.open) : null;
    }

    style(channel) {
        return CHANNEL_STYLE[channel] || { ic: "ic-chat", cv: "var(--mut)" };
    }

    tone(state) {
        return STATE_TONE[state] || "info";
    }

    /** "3 minutes ago" without pulling a date library in. */
    since(value) {
        if (!value) {
            return "";
        }
        const then = new Date(value.replace(" ", "T") + "Z");
        const mins = Math.floor((Date.now() - then.getTime()) / 60000);
        if (isNaN(mins)) {
            return "";
        }
        if (mins < 1) {
            return _t("just now");
        }
        if (mins < 60) {
            return _t("%s min ago", mins);
        }
        const hours = Math.floor(mins / 60);
        if (hours < 24) {
            return _t("%s h ago", hours);
        }
        return _t("%s d ago", Math.floor(hours / 24));
    }

    _msg(error) {
        const data = error && error.data;
        return (data && (data.message || data.arguments?.[0])) ||
            (error && error.message) ||
            _t("Something went wrong. Please try again.");
    }

    _err(error) {
        this.notification.add(this._msg(error), { type: "danger" });
    }

    toast(message) {
        this.state.toast = message;
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => (this.state.toast = null), 4000);
    }

    /** Run one RPC with the button disabled for its duration. */
    async _guarded(fn) {
        if (this.state.busy) {
            return null;
        }
        this.state.busy = true;
        try {
            return await fn();
        } catch (e) {
            this._err(e);
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    // -----------------------------------------------------------------
    // stepper lifecycle
    // -----------------------------------------------------------------
    async onPrimary(card) {
        if (card.primary_action === "unavailable") {
            return;
        }
        if (card.primary_action === "open") {
            return this.openManage(card);
        }
        await this._guarded(async () => {
            const info = await this.orm.call(MODEL, "center_begin", [card.channel]);
            this._resetWizard(card.channel, info);
            if (card.channel === "zalo" && info.connection_id) {
                await this._loadZaloInfo(info.connection_id);
            }
            if (card.channel === "webchat" && info.connection_id) {
                const settings = await this.orm.call(
                    MODEL, "center_webchat_settings", [info.connection_id]);
                this.state.origins = (settings.origins || []).join("\n");
                this.state.greeting = settings.greeting || "";
                this.state.snippet = settings.snippet || "";
                this.state.demoUrl = settings.demo_url || "";
            }
            await this.load();
            this._focusModal();
        });
    }

    _resetWizard(channel, info) {
        this.state.open = channel;
        this.state.manage = false;
        this.state.step = 0;
        this.state.mode = info.mode;
        this.state.steps = info.guide_steps || [];
        this.state.connectionId = info.connection_id;
        this.state.hasCredentials = !!info.has_credentials;
        this.state.token = "";
        this.state.botName = "";
        this.state.copied = false;
        this.state.copiedWebhook = false;
        this.state.confirmOff = false;
        this.state.authUrl = "";
        this.state.popupBlocked = false;
        this.state.webhookSecret = "";
        // A reconnect on a channel whose key we still hold skips the paste
        // screen: the tenant should never be asked for a credential twice.
        if (this.state.mode === "guided_secret" && this.state.hasCredentials) {
            this.state.step = 2;
        }
    }

    // -----------------------------------------------------------------
    // Zalo (CC-D): sign-in popup + the portal-guided webhook checklist
    // -----------------------------------------------------------------
    async _loadZaloInfo(connectionId) {
        const info = await this.orm.call(MODEL, "center_zalo_info", [connectionId]);
        this.state.webhookUrl = info.webhook_url || "";
        this.state.hasWebhookSecret = !!info.has_webhook_secret;
        // A tenant whose OA is already authorized starts on the webhook step.
        if (this.state.mode === "oauth_popup" && this.state.hasCredentials) {
            this.state.step = Math.max(this.state.step, 1);
        }
    }

    async authorizeZalo() {
        await this._guarded(async () => {
            const res = await this.orm.call(MODEL, "center_zalo_authorize",
                [this.state.connectionId]);
            this.state.authUrl = res.url || "";
            // A blocked popup must never look like a silent failure: the URL
            // is shown as a normal link the tenant can click themselves.
            const popup = window.open(res.url, "h19_zalo_signin",
                "width=520,height=720,noopener");
            this.state.popupBlocked = !popup;
            if (popup) {
                this._watchPopup(popup);
            }
            await this.load();
        });
    }

    /** Re-read the Center when the sign-in window closes or we regain focus. */
    _watchPopup(popup) {
        clearInterval(this._popupTimer);
        const finish = () => {
            clearInterval(this._popupTimer);
            this._popupTimer = null;
            window.removeEventListener("focus", finish);
            this.load().then(() => {
                const card = this.openCard;
                if (card && card.connection_id) {
                    this.state.hasCredentials = true;
                    this._loadZaloInfo(card.connection_id).catch(() => {});
                    if (this.state.step === 0) {
                        this.state.step = 1;
                    }
                }
            });
        };
        window.addEventListener("focus", finish, { once: true });
        this._popupTimer = setInterval(() => {
            let closed = false;
            try {
                closed = popup.closed;
            } catch (e) {
                closed = true;
            }
            if (closed) {
                finish();
            }
        }, 1000);
    }

    async copyWebhookUrl() {
        this.state.copiedWebhook = await this._copy(this.state.webhookUrl || "");
        if (this.state.copiedWebhook) {
            clearTimeout(this._copyWebhookTimer);
            this._copyWebhookTimer = setTimeout(
                () => (this.state.copiedWebhook = false), 3000);
        }
    }

    async saveZaloSecret() {
        const secret = (this.state.webhookSecret || "").trim();
        if (!secret) {
            return;
        }
        await this._guarded(async () => {
            try {
                await this.orm.call(MODEL, "center_zalo_set_webhook_secret",
                    [this.state.connectionId, secret]);
                this.state.hasWebhookSecret = true;
                this.state.step = 2;
                await this.load();
            } finally {
                // Zeroed on BOTH paths: a rejected paste is still a secret.
                this.state.webhookSecret = "";
            }
        });
    }

    openManage(card) {
        this.state.open = card.channel;
        this.state.manage = true;
        this.state.connectionId = card.connection_id;
        this.state.steps = card.guide_steps || [];
        this.state.mode = card.mode;
        this.state.confirmOff = false;
        this.state.token = "";
        this.state.webhookSecret = "";
        if (card.channel === "zalo" && card.connection_id) {
            this._loadZaloInfo(card.connection_id).catch((e) => this._err(e));
        }
        this._focusModal();
    }

    /** The ZNS sub-card's honest readiness, if the catalogue carries one. */
    get znsCard() {
        return this.state.cards.find((c) => c.channel === "zns") || null;
    }

    closeStepper() {
        this.state.open = null;
        this.state.manage = false;
        this.state.token = "";
        this.state.confirmOff = false;
        this.load();
    }

    get currentStep() {
        return this.state.steps[this.state.step] || {};
    }

    next() {
        if (this.state.step < this.state.steps.length - 1) {
            this.state.step += 1;
        } else {
            this.closeStepper();
        }
    }

    back() {
        if (this.state.step > 0) {
            this.state.step -= 1;
        }
    }

    // -----------------------------------------------------------------
    // Telegram
    // -----------------------------------------------------------------
    async validateToken() {
        const token = (this.state.token || "").trim();
        if (!token) {
            return;
        }
        await this._guarded(async () => {
            try {
                const res = await this.orm.call(
                    MODEL, "center_telegram_validate",
                    [this.state.connectionId, token]);
                this.state.botName = res.bot_username
                    ? "@" + res.bot_username
                    : res.bot_name || "";
                this.state.hasCredentials = true;
                this.state.step = 2;
                await this.load();
            } finally {
                // Zeroed on BOTH paths: a failed paste is still a credential.
                this.state.token = "";
            }
        });
    }

    async registerWebhook() {
        await this._guarded(async () => {
            await this.orm.call(MODEL, "center_telegram_register_webhook",
                [this.state.connectionId]);
            this.state.step = 3;
            await this.load();
        });
    }

    // -----------------------------------------------------------------
    // Web chat
    // -----------------------------------------------------------------
    async enableWebchat() {
        await this._guarded(async () => {
            const res = await this.orm.call(MODEL, "center_webchat_enable", [
                this.state.connectionId,
                this.state.origins,
                this.state.greeting,
            ]);
            this.state.snippet = res.snippet || "";
            this.state.demoUrl = res.demo_url || "";
            this.state.origins = (res.origins || []).join("\n");
            this.state.step = 1;
            await this.load();
        });
    }

    async copySnippet() {
        const done = await this._copy(this.state.snippet || "");
        this.state.copied = done;
        if (done) {
            clearTimeout(this._copyTimer);
            this._copyTimer = setTimeout(() => (this.state.copied = false), 3000);
        }
    }

    /** Clipboard with an execCommand fallback (the API needs a secure context). */
    async _copy(text) {
        let done = false;
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                done = true;
            }
        } catch (e) {
            done = false;
        }
        if (!done) {
            const area = document.createElement("textarea");
            area.value = text;
            area.setAttribute("readonly", "readonly");
            area.style.position = "fixed";
            area.style.opacity = "0";
            document.body.appendChild(area);
            area.select();
            try {
                done = document.execCommand("copy");
            } catch (e) {
                done = false;
            }
            document.body.removeChild(area);
        }
        if (!done) {
            this.toast(_t("Select the line and copy it manually."));
        }
        return done;
    }

    // -----------------------------------------------------------------
    // shared actions
    // -----------------------------------------------------------------
    async sendTest() {
        await this._guarded(async () => {
            const res = await this.orm.call(MODEL, "center_test",
                [this.state.connectionId]);
            this.toast(res.message || _t("Test message sent."));
            await this.load();
        });
    }

    askDisconnect() {
        this.state.confirmOff = true;
    }

    cancelDisconnect() {
        this.state.confirmOff = false;
    }

    async doDisconnect() {
        await this._guarded(async () => {
            await this.orm.call(MODEL, "center_disconnect",
                [this.state.connectionId]);
            this.state.confirmOff = false;
            await this.load();
            this.closeStepper();
        });
    }

    async doReconnect(card) {
        await this._guarded(async () => {
            const info = await this.orm.call(MODEL, "center_reconnect",
                [card.connection_id]);
            this._resetWizard(card.channel, info);
            await this.load();
            this._focusModal();
        });
    }

    // -----------------------------------------------------------------
    // accessibility: focus trap + escape
    // -----------------------------------------------------------------
    _focusables() {
        const root = this.modalRef.el;
        if (!root) {
            return [];
        }
        return [...root.querySelectorAll(
            "button:not([disabled]), a[href], input, textarea, [tabindex]:not([tabindex='-1'])"
        )].filter((el) => el.offsetParent !== null);
    }

    _focusModal() {
        setTimeout(() => {
            const items = this._focusables();
            if (items.length) {
                items[0].focus();
            }
        }, 0);
    }

    onModalKeydown(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            this.closeStepper();
            return;
        }
        if (ev.key !== "Tab") {
            return;
        }
        const items = this._focusables();
        if (!items.length) {
            return;
        }
        const first = items[0];
        const last = items[items.length - 1];
        if (ev.shiftKey && document.activeElement === first) {
            ev.preventDefault();
            last.focus();
        } else if (!ev.shiftKey && document.activeElement === last) {
            ev.preventDefault();
            first.focus();
        }
    }
}

registry.category("actions").add("channel_center", ChannelCenter);

export default ChannelCenter;
