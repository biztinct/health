/** @odoo-module **/

/**
 * Channel Go-Live Studio (GL-2, design doc "Product design").
 *
 * The operator plane. The tenant Center guides a clinic through connecting its
 * own account; NOTHING guided the human who must first create the provider
 * applications those sign-ins run on. GL-1 turned that knowledge into an
 * ordered, translatable declaration; this is the console on top of it.
 *
 * Four rules this file obeys:
 *
 *  - **The server is the only source of truth.** Every screen repaints from
 *    `golive_state()` and from nothing else; each write RPC returns the whole
 *    refreshed state and we replace ours with it. A component that kept its own
 *    "step 3 is done" is a component that can disagree with the database.
 *  - **Server copy is rendered verbatim, and always escaped.** Titles, bodies
 *    and validation errors are `t-esc`, never `t-out` — an escaped `<script>`
 *    written into a template arch is served live (§5.64 is this module's own
 *    history).
 *  - **A secret lives in state for exactly as long as the input needs it** and
 *    is zeroed on BOTH paths, success and failure: a rejected paste is still a
 *    secret (the Center's `saveZaloSecret` precedent).
 *  - **One interval, ever.** The handshake poll runs only while a handshake
 *    step is the OPEN step, only while the tab is visible, and is torn down on
 *    step navigation, on going home, on success and on unmount.
 */

import { registry } from "@web/core/registry";
import { Component, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const MODEL = "channel.platform.app";

// The provider's own check can take a few seconds to reach us after the
// operator presses "Verify and save" in their dashboard. 5s is the floor the
// handover sets; the Center polls at 15s because nobody is watching it.
const POLL_MS = 5000;

// Brand names, deliberately NOT translated: "WhatsApp" is "WhatsApp" in every
// language, and a translated product name is a support call.
const PROVIDER_NAME = {
    meta: "Meta",
    zalo: "Zalo",
    google: "Google",
    microsoft: "Microsoft",
};
const CHANNEL_NAME = {
    whatsapp: "WhatsApp",
    fb: "Messenger",
    zalo: "Zalo",
    zns: "ZNS",
    email: "Email",
};

// Which stylised console screen belongs to which step (D2). A step with no
// entry here simply gets no illustration — the copy still stands alone.
const STEP_ART = {
    meta: {
        create_app: "meta_creation",
        store_secret: "meta_basic",
        business_verification: "meta_security",
        app_review: "meta_review",
        webhooks: "meta_webhooks",
        config_ids: "meta_config",
    },
    zalo: {
        create_app: "zalo_create",
        credentials: "zalo_settings",
        oauth_redirect: "zalo_settings",
        webhook: "zalo_webhook",
    },
    // GL-4. Google reuses ONE Credentials diagram across its three do-steps:
    // all three happen on that same screen, and a second drawing of it would
    // only imply the operator has to go somewhere else. The consent screen and
    // Entra's Authentication / API permissions pages get no diagram at all —
    // an invented one is worse than none, and the copy stands alone (the
    // component already renders a step with no art).
    google: {
        create_app: "google_credentials",
        store_secret: "google_credentials",
        redirect_uri: "google_credentials",
    },
    // The "Certificates & secrets" drawing IS the not-the-Secret-ID lesson:
    // the highlighted column is Value.
    microsoft: {
        create_app: "ms_register",
        store_secret: "ms_secret",
    },
};

/**
 * D4 — the Calls truth card.
 *
 * Static, UI-only, and deliberately NOT a flow. `CallAdapter` declares
 * `needs_platform_app: false`: calls never touch `channel.platform.app`, the
 * channel is receive-only and proven by inbound traffic, and VoIP24h's API
 * contract is still uncaptured. There is no operator paperwork to guide, so a
 * guided journey would be an invented lie — this card says what is true
 * instead. `_golive_step('call'|'voip24h', …)` raises on the server, and a
 * test pins that it keeps raising.
 *
 * `_t` is lazy (translation.js returns a LazyTranslatedString before the
 * catalogue is loaded), so a module-level constant is safe and is still
 * rendered in the operator's language.
 */
const CALLS_CARD = {
    title: "Calls (VoIP24h)",
    body: _t(
        "No provider application is needed here. A clinic connects its phone " +
        "system from the Channel Center with the webhook secret from its own " +
        "VoIP24h portal, so there is nothing for you to register."),
    caveat: _t(
        "Receiving calls works today. Placing calls and syncing call history " +
        "wait on VoIP24h's API contract, which is still being captured."),
};

export class GoliveStudio extends Component {
    static template = "health_care_command_channels.GoliveStudio";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // The paste-back fields are UNCONTROLLED (no `t-att-value`): OWL would
        // otherwise fight the caret on every keystroke. The ref is how a
        // secret is wiped out of the DOM as well as out of state.
        this.formRef = useRef("form");

        this.state = useState({
            loading: true,
            // `denied` is set ONLY for the server's own operator refusal. Any
            // other failure is an error, and saying "you are not the operator"
            // to somebody whose network blipped would be a lie.
            denied: false,
            error: null,
            providers: [],
            view: "home",      // "home" | provider key
            stepKey: null,
            busy: false,
            inputs: {},        // {input name: pasted value}
            inputErrors: {},   // {input name: the DECLARED error string}
            formError: null,   // the server's ValidationError, verbatim
            copied: null,      // which copy chip just flipped
            flash: null,       // the step key whose milestone just went green
            waiting: false,    // a handshake poll is live
            // GL-3 — delegation. The email box is revealed in place, never in
            // a dialog: the operator is reading the step it belongs to.
            inviteOpen: false,
            inviteEmail: "",
        });

        // A hidden tab polls nothing (the Center's discipline, §D1).
        this._onVisibility = () => {
            if (document.hidden) {
                this._stopPolling();
            } else if (this._shouldPoll()) {
                this.load();
                this._startPolling();
            }
        };
        document.addEventListener("visibilitychange", this._onVisibility);

        onWillStart(async () => {
            await this.load({ first: true });
        });
        onWillUnmount(() => {
            this._stopPolling();
            document.removeEventListener("visibilitychange", this._onVisibility);
            clearTimeout(this._copyTimer);
            clearTimeout(this._flashTimer);
        });
    }

    // -----------------------------------------------------------------
    // data
    // -----------------------------------------------------------------
    async load({ first = false } = {}) {
        try {
            const providers = await this.orm.silent.call(MODEL, "golive_state", []);
            this._apply(providers);
            this.state.error = null;
        } catch (error) {
            if (first && this._isRefusal(error)) {
                this.state.denied = true;
            } else {
                this.state.error = this._msg(error);
            }
        } finally {
            this.state.loading = false;
        }
    }

    /** Replace the payload and notice a milestone that just turned green. */
    _apply(providers) {
        const before = this.step;
        this.state.providers = Array.isArray(providers) ? providers : [];
        const after = this.step;
        if (before && after && before.key === after.key &&
                before.status !== "done" && after.status === "done") {
            this._flashStep(after.key);
        }
        this._syncPolling();
    }

    _flashStep(key) {
        this.state.flash = key;
        clearTimeout(this._flashTimer);
        this._flashTimer = setTimeout(() => (this.state.flash = null), 1200);
    }

    /**
     * The server's operator gate raises a plain `UserError`. Anything else —
     * a dropped connection, a 500 — is an error and is shown as one.
     */
    _isRefusal(error) {
        const name = (error && error.data && error.data.name) || "";
        return name.endsWith("UserError") || name.endsWith("AccessError");
    }

    _msg(error) {
        const data = error && error.data;
        return (data && (data.message || (data.arguments && data.arguments[0]))) ||
            (error && error.message) ||
            _t("Something went wrong. Please try again.");
    }

    // -----------------------------------------------------------------
    // polling — one interval, only for an OPEN, unfinished handshake step
    // -----------------------------------------------------------------
    _shouldPoll() {
        const step = this.step;
        return !!step && step.verify === "handshake" && step.status !== "done";
    }

    _syncPolling() {
        if (this._shouldPoll() && !document.hidden) {
            this._startPolling();
        } else {
            this._stopPolling();
        }
    }

    _startPolling() {
        if (this._timer) {
            return;
        }
        this.state.waiting = true;
        this._timer = setInterval(() => {
            if (!document.hidden && this._shouldPoll()) {
                this.load();
            } else if (!this._shouldPoll()) {
                this._stopPolling();
            }
        }, POLL_MS);
    }

    _stopPolling() {
        if (this._timer) {
            clearInterval(this._timer);
            this._timer = null;
        }
        this.state.waiting = false;
    }

    // -----------------------------------------------------------------
    // selectors
    // -----------------------------------------------------------------
    get provider() {
        return this.state.providers.find(
            (p) => p.provider === this.state.view) || null;
    }

    get step() {
        const provider = this.provider;
        if (!provider) {
            return null;
        }
        return (provider.steps || []).find(
            (s) => s.key === this.state.stepKey) || null;
    }

    providerName(provider) {
        return PROVIDER_NAME[provider.provider] || provider.provider;
    }

    channelName(channel) {
        return CHANNEL_NAME[channel] || channel;
    }

    doneCount(provider) {
        return (provider.steps || []).filter((s) => s.status === "done").length;
    }

    /** The ring's stroke length, as a `stroke-dasharray` pair on r=25. */
    ringDash(provider) {
        const total = (provider.steps || []).length || 1;
        const circumference = 2 * Math.PI * 25;
        const done = (this.doneCount(provider) / total) * circumference;
        return `${done.toFixed(2)} ${circumference.toFixed(2)}`;
    }

    ringLabel(provider) {
        return _t("%s of %s steps done", this.doneCount(provider),
                  (provider.steps || []).length);
    }

    /** The rail item's classes — built here rather than as a computed key in
     *  the template, which is harder to read and harder to test. */
    railClass(step) {
        const classes = ["gl-rail-item", `st-${step.status}`];
        if (step.key === this.state.stepKey) {
            classes.push("is-open");
        }
        if (this.state.flash === step.key) {
            classes.push("gl-flash");
        }
        return classes.join(" ");
    }

    get canvasClass() {
        const step = this.step;
        return step && step.key === "done"
            ? "gl-canvas gl-done" : "gl-canvas";
    }

    /** No steps done yet — the ring's round linecap would otherwise paint a
     *  dot that reads as progress (browser QA, pixel pass 1). */
    isEmpty(provider) {
        return this.doneCount(provider) === 0;
    }

    isComplete(provider) {
        return (provider.steps || []).length > 0 &&
            this.doneCount(provider) === provider.steps.length;
    }

    /** The first unfinished step — the one "Continue" opens. */
    nextStep(provider) {
        const steps = provider.steps || [];
        return steps.find((s) => s.status !== "done") || steps[steps.length - 1] ||
            null;
    }

    /**
     * The honest time line, derived from the DECLARED estimates rather than
     * invented here: the provider reviews are what an operator actually waits
     * on, and a provider with none of them should not be made to sound slow.
     */
    estLine(provider) {
        const waits = (provider.steps || [])
            .filter((s) => s.kind === "wait" && s.est)
            .map((s) => s.est);
        if (waits.length) {
            return _t("Mostly waiting on %s: %s.",
                      this.providerName(provider), waits.join(" · "));
        }
        return _t("No provider review to wait for — every step below is yours.");
    }

    /**
     * "What you'll need before you start". These are prerequisites of the
     * PAPERWORK, not of our data model, so there is nothing on the server to
     * read them from — they are the plain-language counterpart of the step
     * bodies GL-1 declares.
     */
    prerequisites(provider) {
        if (provider.provider === "meta") {
            return [
                _t("A Facebook account with administrator access to your company's Business portfolio."),
                _t("Your company registration documents, for Business Verification."),
                _t("Somebody who can record a short screen video of the clinics using each permission, for App Review."),
                _t("About an hour of hands-on time, spread over the weeks Meta takes to review."),
            ];
        }
        if (provider.provider === "zalo") {
            return [
                _t("A Zalo account that already administers the Official Account the clinics will message from."),
                _t("Access to the Official Account's settings, to add our addresses."),
                _t("About half an hour, all of it yours — Zalo reviews nothing here."),
            ];
        }
        if (provider.provider === "google") {
            return [
                _t("Administrator access to your company's Google Cloud organisation."),
                _t("Permission to publish a consent screen for that organisation."),
                _t("About an hour of your own time, plus a few days if Google asks questions about the consent screen."),
            ];
        }
        if (provider.provider === "microsoft") {
            return [
                _t("Administrator access to your company's Microsoft Entra directory."),
                _t("Someone who can press Grant admin consent for the mailbox permissions."),
                _t("About an hour, all of it yours — Microsoft reviews nothing here."),
            ];
        }
        return [];
    }

    /** D4 — the static Calls card. Not a provider, not a flow, not clickable
     *  into a canvas: one honest paragraph and a link into the Center. */
    get callsCard() {
        return CALLS_CARD;
    }

    /** The step's illustration key, or false. */
    get art() {
        const provider = this.provider;
        const step = this.step;
        if (!provider || !step) {
            return false;
        }
        return (STEP_ART[provider.provider] || {})[step.key] || false;
    }

    /** The illustration's caption — orientation in words, no trade dress. */
    get artCaption() {
        return {
            meta_creation: _t("Meta App Dashboard → Create app → Business"),
            meta_basic: _t("Meta App Dashboard → Settings → Basic"),
            meta_security: _t("Meta Business settings → Security Center"),
            meta_review: _t("Meta App Dashboard → App Review → Permissions"),
            meta_webhooks: _t("Meta App Dashboard → Webhooks"),
            meta_config: _t("Meta App Dashboard → the two sign-in configurations"),
            zalo_create: _t("Zalo Developers → Create application"),
            zalo_settings: _t("Zalo Developers → your app → Settings"),
            zalo_webhook: _t("Zalo Developers → your app → Webhook"),
            google_credentials: _t("Google Cloud Console → APIs & Services → Credentials"),
            ms_register: _t("Microsoft Entra admin center → App registrations → Overview"),
            ms_secret: _t("Microsoft Entra admin center → your app → Certificates & secrets — copy the Value column, not the Secret ID"),
        }[this.art] || "";
    }

    get artLabel() {
        return _t("A diagram of the provider console screen this step is about, with the field you need highlighted.");
    }

    // -----------------------------------------------------------------
    // copy chips
    // -----------------------------------------------------------------
    /**
     * `copy_values` is a list of KEYS into the provider's `values`. Two of them
     * are single strings; `webhook_urls` is several lines of "Label: address"
     * and each line is its own chip, because the operator pastes them into
     * different boxes.
     */
    get copyChips() {
        const provider = this.provider;
        const step = this.step;
        if (!provider || !step) {
            return [];
        }
        const labels = {
            oauth_redirect_uri: _t("Sign-in redirect address"),
            verify_token: _t("Webhook verify token"),
        };
        const chips = [];
        for (const key of step.copy_values || []) {
            const raw = (provider.values || {})[key];
            if (key === "webhook_urls") {
                for (const line of String(raw || "").split("\n")) {
                    if (!line.trim()) {
                        continue;
                    }
                    const cut = line.indexOf(": ");
                    chips.push({
                        id: `${key}:${line}`,
                        label: cut > 0
                            ? _t("Webhook address — %s", line.slice(0, cut))
                            : _t("Webhook address"),
                        value: cut > 0 ? line.slice(cut + 2) : line,
                    });
                }
                continue;
            }
            chips.push({
                id: key,
                label: labels[key] || key,
                value: raw ? String(raw) : "",
                missing: !raw,
            });
        }
        return chips;
    }

    /** True when this step needs the verify token and none has been minted. */
    get needsVerifyToken() {
        const provider = this.provider;
        const step = this.step;
        return !!provider && !!step && provider.provider === "meta" &&
            (step.copy_values || []).includes("verify_token") &&
            !(provider.values || {}).verify_token && !!provider.app_id;
    }

    async copy(chip) {
        if (!chip.value) {
            return;
        }
        const done = await this._copy(chip.value);
        if (done) {
            this.state.copied = chip.id;
            clearTimeout(this._copyTimer);
            this._copyTimer = setTimeout(() => (this.state.copied = null), 2500);
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
        } catch (error) {
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
            } catch (error) {
                done = false;
            }
            document.body.removeChild(area);
        }
        if (!done) {
            this.state.error = _t("Select the value and copy it manually.");
        }
        return done;
    }

    // -----------------------------------------------------------------
    // navigation
    // -----------------------------------------------------------------
    openProvider(provider) {
        const next = this.nextStep(provider);
        this.state.view = provider.provider;
        this.state.stepKey = next ? next.key : null;
        this._resetForm();
        this._syncPolling();
    }

    openStep(key) {
        this.state.stepKey = key;
        this._resetForm();
        this._syncPolling();
    }

    goHome() {
        this.state.view = "home";
        this.state.stepKey = null;
        this._resetForm();
        this._stopPolling();
    }

    _resetForm() {
        this.state.inputs = {};
        this.state.inputErrors = {};
        this.state.formError = null;
        this.state.copied = null;
        this.state.inviteOpen = false;
        this.state.inviteEmail = "";
        this._clearFields();
    }

    /**
     * Wipe the rendered inputs. State alone is not enough: the fields are
     * uncontrolled, so a value the operator typed lives in the DOM until
     * somebody removes it — and OWL may reuse the same `<input>` element for
     * the next step (same `t-key`).
     *
     * @param {boolean} [secretsOnly] keep a non-secret paste the server has
     *   just refused, so it can be corrected instead of retyped.
     */
    _clearFields(secretsOnly = false) {
        const root = this.formRef.el;
        if (!root) {
            return;
        }
        for (const field of root.querySelectorAll("input")) {
            if (!secretsOnly || field.type === "password") {
                field.value = "";
            }
        }
    }

    async openCenter() {
        await this.action.doAction(
            "health_care_command_channels.action_channel_center");
    }

    // -----------------------------------------------------------------
    // inputs
    // -----------------------------------------------------------------
    onInput(spec, ev) {
        this.state.inputs[spec.name] = ev.target.value;
        if (this.state.inputErrors[spec.name]) {
            delete this.state.inputErrors[spec.name];
        }
        this.state.formError = null;
    }

    /** The server's own rule, mirrored — so the operator sees the DECLARED
     *  explanation before a round trip, and the identical one after it. */
    _matches(spec, value) {
        try {
            return new RegExp(spec.regex).test(value);
        } catch (error) {
            // An unusable declaration must not block a paste: let the server,
            // which owns the rule, be the judge.
            return true;
        }
    }

    get filledInputs() {
        const step = this.step;
        if (!step) {
            return {};
        }
        const filled = {};
        for (const spec of step.inputs || []) {
            const value = (this.state.inputs[spec.name] || "").trim();
            if (value) {
                filled[spec.name] = value;
            }
        }
        return filled;
    }

    get canSubmit() {
        return !this.state.busy && Object.keys(this.filledInputs).length > 0;
    }

    async submit() {
        const provider = this.provider;
        const step = this.step;
        if (!provider || !step || this.state.busy) {
            return;
        }
        const payload = this.filledInputs;
        const errors = {};
        for (const spec of step.inputs || []) {
            if (payload[spec.name] && !this._matches(spec, payload[spec.name])) {
                errors[spec.name] = spec.error;
            }
        }
        if (Object.keys(errors).length) {
            this.state.inputErrors = errors;
            return;
        }
        if (!Object.keys(payload).length) {
            return;
        }

        this.state.busy = true;
        this.state.formError = null;
        try {
            const providers = await this.orm.silent.call(
                MODEL, "golive_submit", [provider.provider, step.key, payload]);
            this._apply(providers);
            this.state.inputErrors = {};
        } catch (error) {
            // A ValidationError from the server IS the human explanation —
            // the declared `error` string, raised verbatim. Rendered inline,
            // never as a crash dialog.
            this.state.formError = this._msg(error);
        } finally {
            // Zeroed on BOTH paths: a rejected paste is still a secret, and a
            // successful one has no business surviving the RPC. A refused
            // NON-secret value is kept so it can be corrected, not retyped.
            const failed = !!this.state.formError;
            for (const spec of step.inputs || []) {
                if (spec.secret || !failed) {
                    this.state.inputs[spec.name] = "";
                }
            }
            this._clearFields(failed);
            this.state.busy = false;
        }
    }

    // -----------------------------------------------------------------
    // marks, checks and the verify token
    // -----------------------------------------------------------------
    async mark(marked) {
        const provider = this.provider;
        const step = this.step;
        if (!provider || !step || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const providers = await this.orm.silent.call(
                MODEL, "golive_mark", [provider.provider, step.key, marked]);
            this._apply(providers);
        } catch (error) {
            this.state.formError = this._msg(error);
        } finally {
            this.state.busy = false;
        }
    }

    /** "Check again" re-reads the state; it re-submits nothing, because a
     *  re-submit would need the secret again and we do not keep it. */
    async checkAgain() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.load();
        } finally {
            this.state.busy = false;
        }
    }

    /**
     * Mint the webhook verify token.
     *
     * DEVIATION (declared in the report): GL-1 mints the token as a side
     * effect of the FIRST `extra_json` write, which happens at `config_ids` —
     * the step AFTER `webhooks`. So an operator standing on the webhooks step,
     * which declares `verify_token` among the values to copy, has no token to
     * copy. Rather than reshape the GL-1 payload, the Studio calls the CC-G
     * method that already owns this (`action_generate_verify_token`, itself
     * operator-gated and refusing to overwrite a token Meta already holds).
     */
    async generateVerifyToken() {
        const provider = this.provider;
        if (!provider || !provider.app_id || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.formError = null;
        try {
            await this.orm.silent.call(
                MODEL, "action_generate_verify_token", [[provider.app_id]]);
            await this.load();
        } catch (error) {
            this.state.formError = this._msg(error);
        } finally {
            this.state.busy = false;
        }
    }

    // -----------------------------------------------------------------
    // GL-3 — delegation
    // -----------------------------------------------------------------
    /** The invitations that belong to the OPEN step. The server sends every
     *  live one plus the newest dead one per step; the rail is not the place
     *  to show somebody else's step's invitations. */
    get stepInvites() {
        const provider = this.provider;
        const step = this.step;
        if (!provider || !step) {
            return [];
        }
        return (provider.invites || []).filter((i) => i.step_key === step.key);
    }

    /** Only a step somebody can DO travels; a provider review cannot be
     *  delegated to a colleague, because it is not ours to finish. */
    get canDelegate() {
        const step = this.step;
        return !!step && step.kind === "do";
    }

    /**
     * A do-step whose completion Health19 cannot observe at all.
     *
     * GL-4 DEVIATION (declared): the handover said the GL-2 canvas already
     * offered this — it did not. `.gl-mark` renders only for `kind === 'wait'`,
     * so a do-step that produces no artifact (paste our address into their
     * console; tick four permissions) had NO way to be completed and sat at
     * "to do" for ever, with the ring stuck one short. Zalo's redirect step
     * has been in that state since GL-2; GL-4 would have added three more.
     *
     * The set is exactly "declared do + verify manual + nothing to type", which
     * is the same condition `_golive_step_status` falls through to its
     * mark-decides branch on. Steps with an artifact (a client id, a secret,
     * a configuration id) all declare inputs and are excluded here, so a mark
     * can never overrule an observation — the server refuses those anyway.
     */
    get canMarkDone() {
        const step = this.step;
        return !!step && step.kind === "do" && step.verify === "manual" &&
            !(step.inputs || []).length && step.key !== "done";
    }

    openInvite(email) {
        this.state.inviteOpen = true;
        this.state.inviteEmail = email || "";
        this.state.formError = null;
    }

    closeInvite() {
        this.state.inviteOpen = false;
        this.state.inviteEmail = "";
        this.state.formError = null;
    }

    onInviteInput(ev) {
        this.state.inviteEmail = ev.target.value;
        this.state.formError = null;
    }

    async sendInvite() {
        const provider = this.provider;
        const step = this.step;
        const email = (this.state.inviteEmail || "").trim();
        if (!provider || !step || !email || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.formError = null;
        try {
            const providers = await this.orm.silent.call(
                MODEL, "golive_invite_send", [provider.provider, step.key, email]);
            this._apply(providers);
            this.state.inviteOpen = false;
            this.state.inviteEmail = "";
        } catch (error) {
            // A refused address and a mail server that will not answer are both
            // sentences from the server, rendered inline — never a crash dialog.
            this.state.formError = this._msg(error);
        } finally {
            this.state.busy = false;
        }
    }

    async revokeInvite(invite) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.formError = null;
        try {
            const providers = await this.orm.silent.call(
                MODEL, "golive_invite_revoke", [invite.id]);
            this._apply(providers);
        } catch (error) {
            this.state.formError = this._msg(error);
        } finally {
            this.state.busy = false;
        }
    }

    /** Server datetimes are `YYYY-MM-DD HH:MM:SS`; the day is all this line
     *  needs, and slicing it is deterministic where a locale parse is not. */
    day(value) {
        return String(value || "").slice(0, 10);
    }

    inviteLine(invite) {
        if (invite.revoked) {
            return _t("Revoked — the link sent to %s no longer opens.",
                      invite.email);
        }
        if (invite.expired) {
            return _t("The link sent to %s expired on %s.", invite.email,
                      this.day(invite.expires_at));
        }
        if (invite.view_count) {
            return _t("Sent to %s on %s — works until %s · Opened %s times.",
                      invite.email, this.day(invite.sent_on),
                      this.day(invite.expires_at), invite.view_count);
        }
        return _t("Sent to %s on %s — works until %s · Not opened yet.",
                  invite.email, this.day(invite.sent_on),
                  this.day(invite.expires_at));
    }

    // -----------------------------------------------------------------
    // small view helpers
    // -----------------------------------------------------------------
    stepNumber(key) {
        const provider = this.provider;
        if (!provider) {
            return 0;
        }
        return (provider.steps || []).findIndex((s) => s.key === key) + 1;
    }

    stepHeading(step) {
        return `${this.stepNumber(step.key)}. ${step.title}`;
    }

    // Interpolated sentences live HERE, not in the template: a QWeb text node
    // split by a `<t t-esc/>` is extracted as two half-sentences that no
    // translator can reassemble (§5.85's family).
    submittedOn(date) {
        return _t("Submitted %s", date);
    }

    markedOnNote(date) {
        return _t("Submitted on %s. We cannot see the provider's queue, so this date is your own note.", date);
    }

    markedDoneNote(date) {
        return _t("Marked done on %s. This one leaves no trace we can see, so it is your own note.", date);
    }

    lastSeen(when) {
        return _t("Last seen %s.", when);
    }

    secretHint(hint) {
        return _t("A secret is already saved (ending %s). Pasting a new one replaces it.", hint);
    }

    preflightEcho(detail) {
        return _t("It came back as \"%s\" — if that is not your app, the App ID belongs to a different one.", detail);
    }

    statusLabel(status) {
        return {
            done: _t("Done"),
            waiting: _t("Waiting on the provider"),
            fail: _t("Needs attention"),
            todo: _t("To do"),
        }[status] || _t("To do");
    }
}

registry.category("actions").add("channel_golive_studio", GoliveStudio);

export default GoliveStudio;
