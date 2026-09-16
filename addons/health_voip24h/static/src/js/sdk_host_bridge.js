/**
 * Bridge between the Odoo phone panel and VoIP24h's WebRTC globals.
 *
 * This file runs INSIDE the isolated host frame, alongside the supplier's
 * libraries. It is deliberately dumb: it translates messages into the SDK
 * calls the supplier documents, reports what the SDK reports, and makes no
 * decisions of its own. Every policy question — may this user dial, is this
 * destination allowed, is the call answered — is settled on the server before
 * a command ever reaches here.
 *
 * Contract with the panel (both directions carry `{source: "voip24h-host"}`
 * or `{source: "voip24h-panel"}` and are origin-checked):
 *
 *   panel -> host   init | register | call | answer | reject | hangup
 *                   | setMuted | setHeld | transfer | sendDigits | query
 *   host  -> panel  booted | init | register | incomingcall | progress
 *                   | accepted | ended | error | flags | missing
 *
 * Deliberate omissions, and why:
 *
 * - There is no `unregister` or `destroy` command. The supplier documents no
 *   such method. Pretending otherwise would let the panel claim it had signed
 *   the extension out of the PBX when it had done nothing of the kind; instead
 *   the frame is torn down and the limitation is stated in the UI (gate G07).
 * - `incomingCall` vs `incomingcall`: the prose and the example disagree about
 *   the casing. Both are probed at runtime and whichever exists is used; if
 *   neither does, the caller's number is simply unknown and the panel says so
 *   rather than showing an invented one.
 * - `sendDtmf` is documented as callable only once per call. That restriction
 *   is honoured here (a second attempt is refused and reported) rather than
 *   shipping a keypad that silently stops working after the first press.
 */
(function () {
    "use strict";

    var PANEL_SOURCE = "voip24h-panel";
    var HOST_SOURCE = "voip24h-host";

    var state = {
        initialised: false,
        registered: false,
        dtmfSent: false,
        lastIncoming: null,
    };

    function post(type, payload) {
        try {
            window.parent.postMessage(
                Object.assign({ source: HOST_SOURCE, type: type }, payload || {}),
                window.location.origin
            );
        } catch (error) {
            // Nothing useful to do: the parent is gone or cross-origin.
        }
    }

    function fn(name) {
        return typeof window[name] === "function" ? window[name] : null;
    }

    /** Report a documented function that is not actually present. */
    function missing(name) {
        post("missing", { method: name });
        return null;
    }

    function callSdk(name, args) {
        var handler = fn(name);
        if (!handler) {
            return missing(name);
        }
        try {
            return handler.apply(window, args || []);
        } catch (error) {
            post("error", { code: "sdk_threw", method: name });
            return null;
        }
    }

    /**
     * The supplier's own callbacks. `init`, `register`, `incomingcall`,
     * `progress` and `accepted` are the five the document names. There is no
     * documented end or error callback, which is why a call's end is also
     * inferred from an explicit hangUp and reported as such — the panel is
     * told which of the two it got.
     */
    function bootGateway() {
        var initGateWay = fn("initGateWay");
        if (!initGateWay) {
            post("error", { code: "sdk_not_loaded" });
            return;
        }
        try {
            initGateWay(function (event, data) {
                switch (event) {
                    case "init":
                        state.initialised = true;
                        post("init", { data: safe(data) });
                        break;
                    case "register":
                        state.registered = isRegistered();
                        post("register", {
                            registered: state.registered,
                            data: safe(data),
                        });
                        break;
                    case "incomingcall":
                        state.dtmfSent = false;
                        state.lastIncoming = readIncomingNumber(data);
                        post("incomingcall", {
                            number: state.lastIncoming,
                            data: safe(data),
                        });
                        break;
                    case "progress":
                        post("progress", { data: safe(data) });
                        break;
                    case "accepted":
                        post("accepted", { data: safe(data) });
                        break;
                    default:
                        post("sdk_event", { event: String(event), data: safe(data) });
                }
            });
            post("booted", {});
        } catch (error) {
            post("error", { code: "init_threw" });
        }
    }

    /** Never forward anything but plain, bounded data to the panel. */
    function safe(data) {
        if (data === null || data === undefined) {
            return null;
        }
        if (typeof data === "string") {
            return data.slice(0, 256);
        }
        if (typeof data === "number" || typeof data === "boolean") {
            return data;
        }
        try {
            return JSON.parse(JSON.stringify(data));
        } catch (error) {
            return String(data).slice(0, 256);
        }
    }

    function readIncomingNumber(data) {
        // The callback payload's shape is not documented, so the value is
        // taken from whichever of the plausible places actually holds a
        // string, and the documented lookup function is tried last.
        if (typeof data === "string" && data) {
            return data.slice(0, 64);
        }
        if (data && typeof data === "object") {
            var keys = ["number", "phone", "from", "caller", "displayName"];
            for (var i = 0; i < keys.length; i++) {
                if (typeof data[keys[i]] === "string" && data[keys[i]]) {
                    return data[keys[i]].slice(0, 64);
                }
            }
        }
        var lookup = fn("incomingcall") || fn("incomingCall");
        if (lookup) {
            try {
                var value = lookup();
                if (typeof value === "string") {
                    return value.slice(0, 64);
                }
            } catch (error) {
                // fall through: an unknown caller is better than a wrong one
            }
        }
        return null;
    }

    function isRegistered() {
        var check = fn("isRegistered");
        if (!check) {
            return false;
        }
        try {
            return Boolean(check());
        } catch (error) {
            return false;
        }
    }

    function reportFlags() {
        var muted = null;
        var held = null;
        if (fn("isMute")) {
            try {
                muted = Boolean(window.isMute());
            } catch (error) {
                muted = null;
            }
        }
        if (fn("isHold")) {
            try {
                held = Boolean(window.isHold());
            } catch (error) {
                held = null;
            }
        }
        post("flags", { muted: muted, held: held, registered: isRegistered() });
    }

    var handlers = {
        init: function () {
            bootGateway();
        },
        register: function (message) {
            if (!message.sip_host || !message.sip_username) {
                post("register", { registered: false, code: "incomplete" });
                return;
            }
            callSdk("registerSip", [
                message.sip_host,
                message.sip_username,
                message.sip_password || "",
            ]);
            // `isRegistered` may not be true yet; the `register` callback is
            // the authority and the panel waits for it.
            window.setTimeout(reportFlags, 1500);
        },
        call: function (message) {
            if (!isRegistered()) {
                post("error", { code: "not_registered" });
                return;
            }
            if (!message.number) {
                post("error", { code: "no_number" });
                return;
            }
            state.dtmfSent = false;
            callSdk("call", [String(message.number)]);
        },
        answer: function () {
            state.dtmfSent = false;
            callSdk("answer", []);
        },
        reject: function () {
            callSdk("reject", []);
            post("ended", { cause: "rejected" });
        },
        hangup: function () {
            callSdk("hangUp", []);
            // The supplier documents no terminal callback, so the panel is
            // told this is OUR observation, not the SDK confirming an end.
            post("ended", { cause: "local_hangup", confirmed: false });
        },
        setMuted: function (message) {
            // toggleMute has no explicit setter. Read the current state first
            // so a repeated request from the UI is safe.
            var current = fn("isMute") ? Boolean(window.isMute()) : null;
            if (current === null || current !== Boolean(message.value)) {
                callSdk("toggleMute", []);
            }
            window.setTimeout(reportFlags, 200);
        },
        setHeld: function (message) {
            var current = fn("isHold") ? Boolean(window.isHold()) : null;
            if (current === null || current !== Boolean(message.value)) {
                callSdk("toggleHold", []);
            }
            window.setTimeout(reportFlags, 200);
        },
        transfer: function (message) {
            if (!message.target) {
                post("error", { code: "no_transfer_target" });
                return;
            }
            callSdk("transfer", [String(message.target)]);
            post("transfer_requested", { target: String(message.target) });
        },
        sendDigits: function (message) {
            if (state.dtmfSent) {
                post("error", { code: "dtmf_already_sent" });
                return;
            }
            var digits = String(message.digits || "").replace(/[^0-9*#]/g, "");
            if (!digits) {
                post("error", { code: "no_digits" });
                return;
            }
            state.dtmfSent = true;
            callSdk("sendDtmf", [digits]);
            post("dtmf_sent", { digits: digits.length });
        },
        query: function () {
            reportFlags();
        },
    };

    window.addEventListener("message", function (event) {
        if (event.origin !== window.location.origin) {
            return;
        }
        var message = event.data;
        if (!message || message.source !== PANEL_SOURCE) {
            return;
        }
        var handler = handlers[message.type];
        if (handler) {
            handler(message);
        }
    });

    post("booted", { loaded: Boolean(fn("initGateWay")) });
})();
