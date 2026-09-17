/** @odoo-module **/

import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
// `rpc` is a plain FUNCTION on this version, not a service. Naming it as a
// dependency makes this service fail to start, and one service that cannot
// start takes the WHOLE application down — every screen, not only the phone.
import { rpc } from "@web/core/network/rpc";

/**
 * The phone runtime. One instance per application shell, mounted as a service
 * so backend navigation cannot destroy an active call: components come and go,
 * this does not.
 *
 * Two state machines are kept deliberately separate, because conflating them
 * is how a UI ends up claiming a call is connected when only the browser
 * thinks so:
 *
 *   browser   off -> initialising -> registering -> ready
 *                 -> dialling | ringing -> active -> ending -> wrap_up -> ready
 *   provider  unknown -> ringing -> answered -> ended_pending_cdr -> final
 *
 * `mute` and `held` are orthogonal flags on an active call, and both are
 * displayed only after the SDK confirms them — a pressed button is a request,
 * not a state.
 *
 * What this service will never do:
 *  - auto-answer a call,
 *  - retry `call()` after a timeout, a reconnect, a navigation or an offline
 *    period (a replayed dial rings a patient twice),
 *  - put a dial, an answer or a transfer in an offline queue,
 *  - keep SIP credentials anywhere but this closure.
 */

const PANEL_SOURCE = "voip24h-panel";
const HOST_SOURCE = "voip24h-host";

export class Voip24hPhone {
    constructor(env, services) {
        this.env = env;
        this.orm = services.orm;
        this.rpc = rpc;
        this.notification = services.notification;
        this.busService = services.bus_service;
        this.action = services.action;

        this.state = reactive({
            available: false,          // a phone exists for this user at all
            profile: null,
            browserState: "off",
            callState: "idle",
            muted: false,
            held: false,
            registered: false,
            diagnostic: null,          // a code, never a provider message
            error: null,
            activeCall: null,          // { number, name, direction, sessionId }
            incoming: null,            // { number, name } — SDK-owned ring
            awareness: [],             // server-only ring cards: no Answer
            callbacks: [],
            wrapUp: [],
            talkSeconds: 0,
            dtmfUsed: false,
            transferAvailable: false,
            panelOpen: false,
        });

        // Never on `this.state`: a reactive object is inspectable from the
        // console and ends up in error telemetry. Credentials live here, are
        // used once, and are dropped on release.
        this._sip = null;
        this._lease = null;
        this._frame = null;
        this._pendingAction = null;
        this._heartbeatTimer = null;
        this._talkTimer = null;
        this._browserUuid = null;

        this._onHostMessage = this._onHostMessage.bind(this);
    }

    // ------------------------------------------------------------------
    // Lifecycle
    // ------------------------------------------------------------------

    async start() {
        const result = await this._call("/voip24h/phone/profile");
        if (!result || !result.ok) {
            this.state.available = false;
            return;
        }
        this.state.profile = result.profile;
        this.state.available = Boolean(
            result.profile.calling_enabled ||
            result.profile.alerts_enabled ||
            result.profile.has_extension
        );
        this.state.transferAvailable = Boolean(result.profile.transfer_enabled);

        this.busService.subscribe("voip24h_call", (payload) =>
            this._onServerEvent(payload)
        );
        // Bus delivery is not durable, so the server is asked what is live
        // whenever we (re)connect rather than assuming we saw everything.
        this.busService.addEventListener?.("connect", () => this.refresh());
        await this.refresh();
    }

    async refresh() {
        const result = await this._call("/voip24h/calls/active");
        if (!result || !result.ok) {
            return;
        }
        this.state.profile = result.profile;
        this.state.callbacks = result.callbacks || [];
        this.state.wrapUp = result.wrap_up || [];
        const live = (result.live || []).filter(
            (session) => session.state === "ringing" || session.state === "answered"
        );
        // Awareness cards come from the server. They are NOT actionable: only
        // the browser that actually holds the incoming SDK session may answer.
        this.state.awareness = live.filter(
            (session) => !this.state.incoming || session.peer !== this.state.incoming.number
        );
    }

    /**
     * Start the browser phone. Always an explicit user action: a page that
     * registers a SIP extension on load would take calls from someone who
     * only opened a tab.
     */
    async startPhone({ takeover = false } = {}) {
        if (this.state.browserState !== "off" && this.state.browserState !== "failed") {
            return;
        }
        this.state.error = null;
        this.state.browserState = "initialising";
        this._browserUuid = this._browserUuid || this._uuid();

        const result = await this._call("/voip24h/phone/bootstrap", {
            browser_uuid: this._browserUuid,
            takeover,
        });
        if (!result || !result.ok) {
            this.state.browserState = "failed";
            this.state.error = (result && result.error) || _t("The phone could not start.");
            this.state.diagnostic = (result && result.code) || "bootstrap_failed";
            return;
        }

        this._lease = result.lease;
        this._sip = result.sip;
        this.state.profile = result.profile;
        this.state.transferAvailable = Boolean(result.profile.transfer_enabled);

        const granted = await this._requestMicrophone();
        if (!granted) {
            // Distinct from "registration failed" and from "no device": the
            // recovery is different for each and the panel says which.
            this.state.browserState = "failed";
            this._sip = null;
            await this._releaseLease("microphone denied");
            return;
        }

        this.state.browserState = "registering";
        await this._mountFrame(result.sdk.host_url);
        this._startHeartbeat();
    }

    async stopPhone(reason = "user released") {
        this._stopHeartbeat();
        this._stopTalkTimer();
        if (this.state.callState === "active") {
            this._send("hangup");
        }
        this._unmountFrame();
        await this._releaseLease(reason);
        this._sip = null;
        this.state.browserState = "off";
        this.state.callState = "idle";
        this.state.registered = false;
        this.state.muted = false;
        this.state.held = false;
        this.state.activeCall = null;
        this.state.incoming = null;
    }

    // ------------------------------------------------------------------
    // Call controls
    // ------------------------------------------------------------------

    /**
     * Dial one number. Idempotent by a reference generated BEFORE the request,
     * so a double-click, a lost response or a refresh cannot produce a second
     * real call.
     */
    async dial(number, { resModel = null, resId = null } = {}) {
        if (!this._lease) {
            this.notification.add(_t("Start your phone first."), { type: "warning" });
            return;
        }
        if (this.state.callState !== "idle" && this.state.callState !== "wrap_up") {
            this.notification.add(_t("You are already on a call."), { type: "warning" });
            return;
        }
        const actionUuid = this._uuid();
        const result = await this._call("/voip24h/calls/intent", {
            action_uuid: actionUuid,
            number,
            lease_id: this._lease.id,
            token: this._lease.token,
            fence: this._lease.fence,
            res_model: resModel,
            res_id: resId,
        });
        if (!result || !result.ok) {
            this.notification.add(
                (result && result.error) || _t("That call could not be started."),
                { type: "danger" }
            );
            return;
        }
        if (result.repeat) {
            // We already asked for this exact call. Do not dial again.
            return;
        }
        this._pendingAction = result.action_id;
        this.state.dtmfUsed = false;
        this.state.callState = "dialling";
        this.state.activeCall = {
            number: result.dial,
            name: number,
            direction: "outgoing",
            sessionId: null,
        };
        this._send("call", { number: result.dial });
    }

    async answer() {
        if (!this.state.incoming) {
            return;
        }
        this.state.callState = "active";
        this.state.activeCall = {
            number: this.state.incoming.number,
            name: this.state.incoming.name,
            direction: "incoming",
            sessionId: this.state.incoming.sessionId || null,
        };
        this.state.incoming = null;
        this._startTalkTimer();
        this._send("answer");
        this._reportClientEvent("incoming_answered");
    }

    reject() {
        if (!this.state.incoming) {
            return;
        }
        this._send("reject");
        this.state.incoming = null;
        this.state.callState = "idle";
    }

    /**
     * Closing an awareness card is not rejecting a call. The two are different
     * actions with different consequences and the UI keeps them apart.
     */
    dismissAwareness(sessionId) {
        this.state.awareness = this.state.awareness.filter(
            (session) => session.id !== sessionId
        );
    }

    hangup() {
        // Stays available even when new outgoing calls have just been switched
        // off: taking away the ability to end a call in progress is never the
        // right behaviour.
        this._send("hangup");
        this.state.callState = "ending";
    }

    setMuted(value) {
        if (this._muteBusy) {
            return;
        }
        this._muteBusy = true;
        this._send("setMuted", { value });
        window.setTimeout(() => {
            this._muteBusy = false;
        }, 400);
    }

    setHeld(value) {
        if (this._holdBusy) {
            return;
        }
        this._holdBusy = true;
        this._send("setHeld", { value });
        window.setTimeout(() => {
            this._holdBusy = false;
        }, 400);
    }

    transfer(target) {
        if (!this.state.transferAvailable) {
            this.notification.add(
                _t("Transfer is not switched on for your extension."),
                { type: "warning" }
            );
            return;
        }
        this._send("transfer", { target });
    }

    sendDigits(digits) {
        if (this.state.dtmfUsed) {
            this.notification.add(
                _t("Keypad tones can only be sent once during a call on this phone system."),
                { type: "warning" }
            );
            return;
        }
        this.state.dtmfUsed = true;
        this._send("sendDigits", { digits });
    }

    // ------------------------------------------------------------------
    // Wrap-up
    // ------------------------------------------------------------------

    async saveDisposition(sessionId, { notes, outcome, version }) {
        const result = await this._call("/voip24h/calls/disposition", {
            session_id: sessionId,
            notes,
            outcome,
            version,
        });
        if (!result || !result.ok) {
            this.notification.add(
                (result && result.error) || _t("That could not be saved."),
                { type: "danger" }
            );
            return null;
        }
        await this.refresh();
        return result.version;
    }

    async markCalledBack(sessionId) {
        const result = await this._call("/voip24h/calls/mark_called_back", {
            session_id: sessionId,
        });
        if (result && result.ok) {
            await this.refresh();
        }
        return result;
    }

    async openSession(sessionId) {
        const result = await this._call("/voip24h/calls/session", {
            session_id: sessionId,
        });
        return result && result.ok ? result.session : null;
    }

    // ------------------------------------------------------------------
    // Server events
    // ------------------------------------------------------------------

    _onServerEvent(payload) {
        if (!payload || !payload.session_id) {
            return;
        }
        switch (payload.kind) {
            case "incoming_ring":
                // Server awareness only. The Answer button appears when — and
                // only when — this browser's SDK reports the incoming session.
                this.state.awareness = [
                    ...this.state.awareness.filter((s) => s.id !== payload.session_id),
                    { id: payload.session_id, state: payload.state, awareness: true },
                ];
                break;
            case "answered":
                // Somebody took it. Stop ringing elsewhere — and this is NOT a
                // missed call for the extensions that lost the race.
                this.dismissAwareness(payload.session_id);
                break;
            case "ended":
                this.dismissAwareness(payload.session_id);
                this.refresh();
                break;
            case "missed_inbound":
            case "callback_due":
            case "outbound_unanswered":
            case "unmatched_caller":
            case "call_recorded":
                this.refresh();
                break;
            default:
                break;
        }
    }

    // ------------------------------------------------------------------
    // Host frame
    // ------------------------------------------------------------------

    async _mountFrame(hostUrl) {
        this._unmountFrame();
        const frame = document.createElement("iframe");
        frame.src = hostUrl;
        frame.allow = "microphone";
        frame.setAttribute("title", "VoIP24h phone runtime");
        frame.style.cssText =
            "position:fixed;width:1px;height:1px;left:-9999px;top:0;border:0;";
        document.body.appendChild(frame);
        this._frame = frame;
        window.addEventListener("message", this._onHostMessage);
        await new Promise((resolve) => {
            frame.addEventListener("load", resolve, { once: true });
            window.setTimeout(resolve, 8000);
        });
        this._send("init");
    }

    _unmountFrame() {
        window.removeEventListener("message", this._onHostMessage);
        if (this._frame && this._frame.parentNode) {
            this._frame.parentNode.removeChild(this._frame);
        }
        this._frame = null;
    }

    _send(type, payload = {}) {
        if (!this._frame || !this._frame.contentWindow) {
            return;
        }
        this._frame.contentWindow.postMessage(
            Object.assign({ source: PANEL_SOURCE, type }, payload),
            window.location.origin
        );
    }

    _onHostMessage(event) {
        if (event.origin !== window.location.origin) {
            return;
        }
        const message = event.data;
        if (!message || message.source !== HOST_SOURCE) {
            return;
        }
        switch (message.type) {
            case "booted":
                if (message.loaded === false) {
                    this.state.browserState = "failed";
                    this.state.diagnostic = "sdk_not_loaded";
                    this.state.error = _t(
                        "The phone software could not be loaded. Check the connection settings."
                    );
                }
                break;
            case "init":
                if (this._sip) {
                    this._send("register", this._sip);
                    // Used once, then forgotten. It stays only in the frame's
                    // own memory from here.
                    this._sip = null;
                }
                break;
            case "register":
                this.state.registered = Boolean(message.registered);
                // Ready means REGISTERED. Not a lease, not an HTTP 200.
                this.state.browserState = message.registered ? "ready" : "failed";
                if (!message.registered) {
                    this.state.diagnostic = message.code || "registration_failed";
                    this.state.error = _t(
                        "Your extension could not sign in to the phone system."
                    );
                }
                this._beat();
                break;
            case "incomingcall":
                this.state.incoming = {
                    number: message.number || null,
                    name: message.number || _t("Unknown caller"),
                    sessionId: null,
                };
                this.state.callState = "ringing";
                this.state.dtmfUsed = false;
                this._ringOnce();
                break;
            case "progress":
                if (this.state.callState === "dialling") {
                    this._reportClientEvent("progress");
                }
                break;
            case "accepted":
                this.state.callState = "active";
                this._startTalkTimer();
                this._reportClientEvent("accepted");
                break;
            case "ended":
                this._onCallEnded(message);
                break;
            case "flags":
                if (message.muted !== null && message.muted !== undefined) {
                    this.state.muted = message.muted;
                }
                if (message.held !== null && message.held !== undefined) {
                    this.state.held = message.held;
                }
                break;
            case "missing":
                // A documented function the runtime does not actually have.
                // Surfaced rather than swallowed: it is exactly the kind of
                // gap that makes a control look broken for no visible reason.
                this.state.diagnostic = `missing:${message.method}`;
                break;
            case "error":
                this._onHostError(message);
                break;
            default:
                break;
        }
    }

    _onCallEnded(message) {
        this._stopTalkTimer();
        const session = this.state.activeCall;
        this.state.callState = session ? "wrap_up" : "idle";
        this.state.activeCall = null;
        this.state.incoming = null;
        this.state.muted = false;
        this.state.held = false;
        if (message.confirmed === false) {
            // We asked it to end; the SDK has not confirmed. Say so.
            this.state.diagnostic = "end_unconfirmed";
        }
        this._reportClientEvent("ended");
        this.refresh();
    }

    _onHostError(message) {
        const codes = {
            not_registered: _t("Your phone is not signed in yet."),
            no_number: _t("There is no number to call."),
            sdk_not_loaded: _t("The phone software is not available."),
            dtmf_already_sent: _t(
                "This phone system allows keypad tones only once per call."
            ),
            no_transfer_target: _t("Choose who to transfer the call to."),
        };
        this.state.diagnostic = message.code || "sdk_error";
        const text = codes[message.code];
        if (text) {
            this.notification.add(text, { type: "warning" });
        }
        if (message.code === "not_registered") {
            this.state.browserState = "failed";
        }
        if (this.state.callState === "dialling") {
            this.state.callState = "idle";
            this.state.activeCall = null;
            this._reportClientEvent("failed", message.code);
        }
    }

    // ------------------------------------------------------------------
    // Plumbing
    // ------------------------------------------------------------------

    async _requestMicrophone() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.state.diagnostic = "no_media_api";
            this.state.error = _t(
                "This browser cannot use the microphone. A secure (https) page is required."
            );
            return false;
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach((track) => track.stop());
            return true;
        } catch (error) {
            const name = (error && error.name) || "";
            if (name === "NotAllowedError" || name === "SecurityError") {
                this.state.diagnostic = "microphone_denied";
                this.state.error = _t(
                    "Microphone access was blocked. Allow it for this site, then start the phone again."
                );
            } else if (name === "NotFoundError" || name === "OverconstrainedError") {
                this.state.diagnostic = "no_microphone";
                this.state.error = _t(
                    "No microphone was found. Plug one in, then start the phone again."
                );
            } else {
                this.state.diagnostic = "microphone_unavailable";
                this.state.error = _t("The microphone could not be used.");
            }
            return false;
        }
    }

    _startHeartbeat() {
        this._stopHeartbeat();
        const seconds = (this._lease && this._lease.heartbeat_seconds) || 10;
        this._heartbeatTimer = window.setInterval(() => this._beat(), seconds * 1000);
    }

    _stopHeartbeat() {
        if (this._heartbeatTimer) {
            window.clearInterval(this._heartbeatTimer);
            this._heartbeatTimer = null;
        }
    }

    async _beat() {
        if (!this._lease) {
            return;
        }
        const result = await this._call("/voip24h/phone/heartbeat", {
            lease_id: this._lease.id,
            token: this._lease.token,
            fence: this._lease.fence,
            state: this.state.browserState,
            diagnostic: this.state.diagnostic,
        });
        if (result && !result.ok && result.code === "lease_lost") {
            this._stopHeartbeat();
            this.state.error = result.error;
            this.state.browserState = "disconnected";
            this._unmountFrame();
            this._lease = null;
        }
    }

    async _releaseLease(reason) {
        if (!this._lease) {
            return;
        }
        const lease = this._lease;
        this._lease = null;
        await this._call("/voip24h/phone/release", {
            lease_id: lease.id,
            token: lease.token,
            fence: lease.fence,
            reason,
        });
    }

    async _reportClientEvent(event, diagnostic = null) {
        if (!this._lease) {
            return;
        }
        await this._call("/voip24h/calls/client_event", {
            action_id: this._pendingAction,
            event,
            diagnostic,
            lease_id: this._lease.id,
            token: this._lease.token,
            fence: this._lease.fence,
        });
    }

    _startTalkTimer() {
        this._stopTalkTimer();
        this.state.talkSeconds = 0;
        this._talkTimer = window.setInterval(() => {
            this.state.talkSeconds += 1;
        }, 1000);
    }

    _stopTalkTimer() {
        if (this._talkTimer) {
            window.clearInterval(this._talkTimer);
            this._talkTimer = null;
        }
    }

    _ringOnce() {
        // One audible alert, in the tab that owns the SDK session. Other tabs
        // render a passive panel and stay silent.
        try {
            const context = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = context.createOscillator();
            const gain = context.createGain();
            oscillator.type = "sine";
            oscillator.frequency.value = 660;
            gain.gain.value = 0.06;
            oscillator.connect(gain).connect(context.destination);
            oscillator.start();
            window.setTimeout(() => {
                oscillator.stop();
                context.close();
            }, 600);
        } catch (error) {
            // Autoplay policy blocked it. The visual alert still shows, and
            // the panel does not pretend a sound was played.
            this.state.diagnostic = "alert_sound_blocked";
        }
    }

    async _call(route, params = {}) {
        try {
            return await this.rpc(route, params);
        } catch (error) {
            this.state.error = _t("The server could not be reached.");
            return null;
        }
    }

    _uuid() {
        if (window.crypto && window.crypto.randomUUID) {
            return window.crypto.randomUUID();
        }
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            const v = c === "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }
}

export const voip24hPhoneService = {
    dependencies: ["orm", "notification", "bus_service", "action"],
    start(env, services) {
        const phone = new Voip24hPhone(env, services);
        // Started lazily and quietly: a user with no extension and no alerts
        // enabled must not pay for any of this.
        phone.start();
        // A refresh can end the media session. Warn where the browser allows
        // it — and never promise the call survives.
        window.addEventListener("beforeunload", (event) => {
            if (phone.state.callState === "active") {
                event.preventDefault();
                event.returnValue = "";
            }
        });
        return phone;
    },
};

registry.category("services").add("voip24h_phone", voip24hPhoneService);
