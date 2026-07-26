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

// CC-E: Meta's JS SDK is an EXTERNAL script and is therefore loaded on demand,
// only when a tenant actually opens the WhatsApp stepper — never in the
// backend bundle, where every Odoo user would pay for it and a Meta outage
// would be a Health19 outage. If it does not arrive (an ad blocker, a locked
// down network, a blocked popup) the stepper says so in words instead of
// looking broken.
const META_SDK_TIMEOUT_MS = 8000;
const META_SIGNUP_ORIGINS = ["https://www.facebook.com", "https://web.facebook.com"];

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
            // Meta (CC-E): the SDK/dialog payload, the resource picker and the
            // provider-approval rows.
            meta: null,
            metaResources: [],
            metaSelected: "",
            metaLoadingResources: false,
            metaResourceError: "",
            metaMissingScopes: [],
            metaSdkBlocked: false,
            approvals: [],
            // Email (CC-F): the mailbox, the provider picker and whether the
            // provider's own callback actually stored a grant. `signedIn` is
            // read back from the server, never assumed from a closed popup.
            emailProviders: [],
            emailProvider: "",
            mailbox: "",
            emailSignedIn: false,
            // Calls (CC-F): receive-only, so there is an account id and a
            // webhook secret and nothing that could "test" an API.
            callAccountId: "",
            callSecret: "",
            hasCallSecret: false,
            callNotice: "",
        });

        // The ES popup posts its WABA / phone id back through postMessage.
        // Captured (origin-checked) purely as a HINT for the picker — the
        // authoritative list still comes from Meta's own debug_token.
        this._metaHint = {};
        this._onMetaMessage = (ev) => {
            if (!META_SIGNUP_ORIGINS.includes(ev.origin)) {
                return;
            }
            let payload = ev.data;
            if (typeof payload === "string") {
                try {
                    payload = JSON.parse(payload);
                } catch (e) {
                    return;
                }
            }
            if (!payload || payload.type !== "WA_EMBEDDED_SIGNUP") {
                return;
            }
            const d = payload.data || {};
            this._metaHint = {
                waba_id: d.waba_id || "",
                phone_number_id: d.phone_number_id || "",
            };
        };
        window.addEventListener("message", this._onMetaMessage);

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
            window.removeEventListener("message", this._onMetaMessage);
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
            if (this.isMetaChannel(card.channel) && info.connection_id) {
                await this._resumeMeta(info.connection_id, card);
            }
            if (card.channel === "email" && info.connection_id) {
                await this._loadEmailInfo(info.connection_id);
            }
            if (card.channel === "call" && info.connection_id) {
                await this._loadCallInfo(info.connection_id);
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
        this.state.meta = null;
        this.state.metaResources = [];
        this.state.metaSelected = "";
        this.state.metaResourceError = "";
        this.state.metaMissingScopes = [];
        this.state.metaSdkBlocked = false;
        this.state.approvals = [];
        this.state.emailSignedIn = false;
        this.state.mailbox = "";
        this.state.emailProvider = "";
        this.state.emailProviders = [];
        this.state.callAccountId = "";
        this.state.callSecret = "";
        this.state.hasCallSecret = false;
        this.state.callNotice = "";
        this._metaHint = {};
        // A reconnect on a channel whose key we still hold skips the paste
        // screen: the tenant should never be asked for a credential twice.
        if (this.isTelegram && this.state.hasCredentials) {
            this.state.step = 2;
        }
    }

    // -----------------------------------------------------------------
    // channel predicates — the stepper copy is per CHANNEL, not per mode
    //
    // CC-E re-keyed the Zalo screens off `mode === 'oauth_popup'` for exactly
    // the reason CC-F now makes concrete: a second channel joined that mode
    // (email) and would have inherited Zalo's words. CC-F finishes the job on
    // the other side — `call` joins `guided_secret`, whose branches were all
    // written for Telegram and talk about BotFather. Every stepper branch is
    // keyed on a CHANNEL below; none is keyed on a mode.
    // -----------------------------------------------------------------
    isMetaChannel(channel) {
        return channel === "whatsapp" || channel === "fb";
    }

    get isZalo() {
        return this.state.open === "zalo";
    }

    get isTelegram() {
        return this.state.open === "telegram";
    }

    get isEmail() {
        return this.state.open === "email";
    }

    get isCall() {
        return this.state.open === "call";
    }

    get isWebchat() {
        return this.state.open === "webchat";
    }

    get isMeta() {
        return this.isMetaChannel(this.state.open);
    }

    get isWhatsApp() {
        return this.state.open === "whatsapp";
    }

    get isMessenger() {
        return this.state.open === "fb";
    }

    /** Meta withheld a permission — true whichever flow noticed it first. */
    get scopesFailed() {
        const card = this.openCard;
        return !!(card && (card.checks || []).some(
            (c) => c.key === "scopes_granted" && c.status === "fail"));
    }

    // -----------------------------------------------------------------
    // Zalo (CC-D): sign-in popup + the portal-guided webhook checklist
    // -----------------------------------------------------------------
    async _loadZaloInfo(connectionId) {
        const info = await this.orm.call(MODEL, "center_zalo_info", [connectionId]);
        this.state.webhookUrl = info.webhook_url || "";
        this.state.hasWebhookSecret = !!info.has_webhook_secret;
        // A tenant whose OA is already authorized starts on the webhook step.
        // Keyed on the CHANNEL, not the mode: email shares `oauth_popup`.
        if (this.isZalo && this.state.hasCredentials) {
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
                this._watchPopup(popup, (card) => {
                    this.state.hasCredentials = true;
                    this._loadZaloInfo(card.connection_id).catch(() => {});
                    if (this.state.step === 0) {
                        this.state.step = 1;
                    }
                });
            }
            await this.load();
        });
    }

    /** Re-read the Center when the sign-in window closes or we regain focus. */
    _watchPopup(popup, onDone) {
        clearInterval(this._popupTimer);
        const finish = () => {
            clearInterval(this._popupTimer);
            this._popupTimer = null;
            window.removeEventListener("focus", finish);
            this.load().then(() => {
                const card = this.openCard;
                if (card && card.connection_id && onDone) {
                    onDone(card);
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

    // -----------------------------------------------------------------
    // Meta (CC-E): WhatsApp Embedded Signup v4 + Messenger FLB
    // -----------------------------------------------------------------
    /** Re-open a Meta stepper where the tenant left it. */
    async _resumeMeta(connectionId, card) {
        this.state.approvals = (card && card.approvals) || [];
        if (!this.state.hasCredentials) {
            return;
        }
        // Signed in already: the picker is the next thing that matters.
        this.state.step = Math.max(this.state.step, 1);
        if (card && card.resource_line) {
            this.state.step = Math.max(this.state.step, 2);
        }
        await this.loadMetaResources();
    }

    /**
     * Load Meta's JS SDK on demand. Resolves FALSE rather than throwing when
     * the script does not arrive — the stepper then explains that Meta's popup
     * is what this needs, instead of a dead button.
     */
    _loadMetaSdk(cfg) {
        if (window.FB && window.FB.login) {
            return Promise.resolve(true);
        }
        return new Promise((resolve) => {
            const done = (ok) => resolve(ok);
            const script = document.createElement("script");
            script.src = cfg.sdk_url;
            script.async = true;
            script.defer = true;
            script.crossOrigin = "anonymous";
            script.onload = () => {
                try {
                    window.FB.init({
                        appId: cfg.app_id,
                        cookie: true,
                        xfbml: false,
                        version: cfg.graph_version,
                    });
                    done(!!(window.FB && window.FB.login));
                } catch (e) {
                    done(false);
                }
            };
            script.onerror = () => done(false);
            document.head.appendChild(script);
            setTimeout(() => done(!!(window.FB && window.FB.login)),
                META_SDK_TIMEOUT_MS);
        });
    }

    /** Step 1 for both Meta channels: open the provider's own sign-in. */
    async startMeta() {
        await this._guarded(async () => {
            const cfg = await this.orm.call(MODEL, "center_meta_start",
                [this.state.open]);
            this.state.meta = cfg;
            this.state.metaSdkBlocked = false;
            if (this.isMessenger) {
                // Facebook Login for Business is an ordinary redirect flow:
                // the popup lands on our own OAuth callback.
                this.state.authUrl = cfg.url || "";
                const popup = window.open(cfg.url, "h19_fb_signin",
                    "width=560,height=740,noopener");
                this.state.popupBlocked = !popup;
                if (popup) {
                    this._watchPopup(popup, async (card) => {
                        this.state.hasCredentials = true;
                        this.state.step = Math.max(this.state.step, 1);
                        this.state.approvals = card.approvals || [];
                        await this.loadMetaResources();
                    });
                }
                await this.load();
                return;
            }
            // WhatsApp: the SDK owns the popup, and hands the code back to us.
            const ready = await this._loadMetaSdk(cfg);
            if (!ready) {
                this.state.metaSdkBlocked = true;
                return;
            }
            this._metaHint = {};
            const code = await this._metaEmbeddedSignup(cfg);
            if (!code) {
                // Cancelled or blocked — not an error, and nothing was stored.
                this.state.metaSdkBlocked = !window.FB;
                return;
            }
            const res = await this.orm.call(MODEL, "center_meta_exchange", [
                this.state.connectionId,
                code,
                cfg.state_token,
                this._metaHint,
            ]);
            this.state.metaMissingScopes = res.missing_scopes || [];
            this.state.hasCredentials = true;
            this.state.step = 1;
            await this.load();
            await this.loadMetaResources();
        });
    }

    /** Wrap FB.login's callback in a promise; never rejects. */
    _metaEmbeddedSignup(cfg) {
        return new Promise((resolve) => {
            try {
                window.FB.login(
                    (response) => {
                        const auth = (response && response.authResponse) || {};
                        resolve(auth.code || "");
                    },
                    {
                        config_id: cfg.config_id,
                        response_type: "code",
                        override_default_response_type: true,
                        extras: { setup: {}, sessionInfoVersion: 3 },
                    }
                );
            } catch (e) {
                resolve("");
            }
        });
    }

    async loadMetaResources() {
        if (!this.state.connectionId || !this.isMeta) {
            return;
        }
        this.state.metaLoadingResources = true;
        this.state.metaResourceError = "";
        try {
            const res = await this.orm.call(MODEL, "center_meta_resources",
                [this.state.connectionId]);
            this.state.metaResources = res.resources || [];
            this.state.metaSelected = res.selected || "";
            // The ES popup told us which number the tenant just onboarded —
            // preselect it so the picker is one click, never a guess.
            const hint = (this._metaHint && this._metaHint.phone_number_id)
                || res.hint || "";
            if (!this.state.metaSelected && hint) {
                const match = this.state.metaResources.find((r) => r.id === hint);
                if (match) {
                    this.state.metaSelected = match.id;
                }
            }
        } catch (e) {
            this.state.metaResources = [];
            this.state.metaResourceError = this._msg(e);
        } finally {
            this.state.metaLoadingResources = false;
        }
    }

    pickMetaResource(id) {
        this.state.metaSelected = id;
    }

    async selectMetaResource() {
        if (!this.state.metaSelected) {
            return;
        }
        await this._guarded(async () => {
            await this.orm.call(MODEL, "center_meta_select",
                [this.state.connectionId, this.state.metaSelected]);
            this.state.step = 2;
            await this.load();
        });
    }

    async subscribeMeta() {
        await this._guarded(async () => {
            await this.orm.call(MODEL, "center_meta_subscribe",
                [this.state.connectionId]);
            const res = await this.orm.call(MODEL, "center_meta_approvals",
                [this.state.connectionId, true]);
            this.state.approvals = res.approvals || [];
            this.state.step = 3;
            await this.load();
        });
    }

    async refreshApprovals() {
        await this._guarded(async () => {
            const res = await this.orm.call(MODEL, "center_meta_approvals",
                [this.state.connectionId, true]);
            this.state.approvals = res.approvals || [];
            await this.load();
        });
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

    // -----------------------------------------------------------------
    // Email (CC-F): Gmail / Microsoft 365 through Odoo's own OAuth
    // -----------------------------------------------------------------
    async _loadEmailInfo(connectionId) {
        const info = await this.orm.call(MODEL, "center_email_info", [connectionId]);
        this.state.emailProviders = info.providers || [];
        this.state.emailProvider = info.provider || "";
        this.state.mailbox = info.mailbox || "";
        this.state.emailSignedIn = !!info.signed_in;
        if (this.state.emailSignedIn) {
            this.state.step = Math.max(this.state.step, 1);
        }
    }

    pickEmailProvider(key) {
        this.state.emailProvider = key;
    }

    async startEmail() {
        const mailbox = (this.state.mailbox || "").trim();
        if (!mailbox) {
            return;
        }
        await this._guarded(async () => {
            const res = await this.orm.call(MODEL, "center_email_start", [
                this.state.connectionId,
                this.state.emailProvider,
                mailbox,
            ]);
            this.state.mailbox = res.mailbox || mailbox;
            this.state.emailProvider = res.provider || this.state.emailProvider;
            this.state.authUrl = res.url || "";
            const popup = window.open(res.url, "h19_email_signin",
                "width=560,height=740,noopener");
            this.state.popupBlocked = !popup;
            if (popup) {
                this._watchPopup(popup, () => this.refreshEmailStatus());
            }
            await this.load();
        });
    }

    /**
     * Ask the SERVER whether a grant was actually stored. A closed popup
     * proves nothing — the tenant may have cancelled, or the provider may
     * have refused the mailbox — so the sign-in is only "done" once Odoo's
     * own callback has written a refresh token we can see.
     */
    async refreshEmailStatus() {
        if (!this.state.connectionId || !this.isEmail) {
            return;
        }
        try {
            const res = await this.orm.call(MODEL, "center_email_status",
                [this.state.connectionId]);
            this.state.emailSignedIn = !!res.signed_in;
            this.state.mailbox = res.mailbox || this.state.mailbox;
            if (this.state.emailSignedIn && this.state.step === 0) {
                this.state.step = 1;
            }
            await this.load();
        } catch (e) {
            this._err(e);
        }
    }

    // -----------------------------------------------------------------
    // Calls (CC-F): receive only, and the UI says so
    // -----------------------------------------------------------------
    async _loadCallInfo(connectionId) {
        const info = await this.orm.call(MODEL, "center_call_info", [connectionId]);
        this.state.webhookUrl = info.webhook_url || "";
        this.state.callAccountId = info.account_id || "";
        this.state.hasCallSecret = !!info.has_webhook_secret;
        this.state.callNotice = info.notice || "";
        if (this.state.callAccountId) {
            this.state.step = Math.max(this.state.step, 1);
        }
    }

    async saveCallSetup() {
        const account = (this.state.callAccountId || "").trim();
        if (!account) {
            return;
        }
        await this._guarded(async () => {
            try {
                const res = await this.orm.call(MODEL, "center_call_configure", [
                    this.state.connectionId,
                    account,
                    this.state.callSecret,
                ]);
                this.state.hasCallSecret = !!res.has_webhook_secret;
                this.state.step = 2;
                await this.load();
            } finally {
                // Zeroed on BOTH paths: a rejected paste is still a secret.
                this.state.callSecret = "";
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
        this.state.approvals = card.approvals || [];
        this.state.metaResources = [];
        this.state.metaSelected = "";
        this.state.callSecret = "";
        this.state.callNotice = "";
        if (card.channel === "zalo" && card.connection_id) {
            this._loadZaloInfo(card.connection_id).catch((e) => this._err(e));
        }
        if (card.channel === "email" && card.connection_id) {
            this._loadEmailInfo(card.connection_id).catch((e) => this._err(e));
        }
        if (card.channel === "call" && card.connection_id) {
            this._loadCallInfo(card.connection_id).catch((e) => this._err(e));
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
