/*
 * Health19 web-chat widget — dependency-free vanilla JS.
 *
 * Embed on any page:
 *   <script src="https://care.example.com/health_care_command_channels/static/src/webchat/widget.js"
 *           data-origin="https://care.example.com"></script>
 *
 * Design rules this file obeys:
 *  - no framework, no Odoo assets, no external request beyond our own origin;
 *  - flat mono colours, no gradients (house style);
 *  - the session id comes from the SERVER and is kept in localStorage;
 *  - bodies are posted as text/plain so every request stays a CORS "simple"
 *    request — no preflight to get wrong;
 *  - polling backs off when the tab is hidden or the visitor goes quiet; the
 *    server's rate counter is the hard bound, this is the polite one.
 */
(function () {
    "use strict";

    var script = document.currentScript;
    var declared = script && script.getAttribute("data-origin");
    // Only an absolute http(s) origin is honoured; anything else falls back to
    // the hosting page's own origin. A junk data-origin would otherwise build
    // relative URLs that 404 (or worse, load from somewhere unexpected).
    var ORIGIN = (/^https?:\/\/[^\s/]+$/.test((declared || "").trim())
        ? declared.trim().replace(/\/$/, "")
        : window.location.origin);
    if (window.__h19WebchatLoaded) return;   // never mount twice on one page
    window.__h19WebchatLoaded = true;
    var STORAGE_KEY = "h19_webchat_session";
    var POLL_MIN = 4000;
    var POLL_MAX = 60000;
    var TEXT_CAP = 2000;

    var state = {
        session: null,
        open: false,
        afterId: 0,
        pollDelay: POLL_MIN,
        timer: null,
        greeting: "",
        starting: false,
    };

    // ---------------------------------------------------------------
    // transport
    // ---------------------------------------------------------------
    function post(path, body) {
        return fetch(ORIGIN + path, {
            method: "POST",
            headers: { "Content-Type": "text/plain;charset=UTF-8" },
            body: JSON.stringify(body || {}),
            credentials: "omit",
        }).then(function (r) {
            return r.ok ? r.json() : Promise.reject(r.status);
        });
    }


    // ---------------------------------------------------------------
    // DOM
    // ---------------------------------------------------------------
    var els = {};

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text) node.textContent = text;   // textContent: never innerHTML
        return node;
    }

    function ensureStyles() {
        // Reuse our own ?v= stamp for the stylesheet: Odoo serves
        // /module/static/… with max-age=604800 and no revalidation, so an
        // unversioned URL would keep a stale widget on visitor browsers for a
        // week after an upgrade (measured on vietuat).
        var mine = (script && script.getAttribute("src")) || "";
        var version = mine.indexOf("?") >= 0 ? mine.slice(mine.indexOf("?")) : "";
        var href = ORIGIN +
            "/health_care_command_channels/static/src/webchat/widget.css" + version;
        // Compare RESOLVED urls: a host page that links the stylesheet
        // relatively (the demo page does) would not match an attribute
        // selector, and the widget would inject a duplicate.
        var links = document.querySelectorAll("link[rel=stylesheet]");
        for (var i = 0; i < links.length; i++) {
            if (links[i].href === href) return;
        }
        var link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = href;
        document.head.appendChild(link);
    }

    function build() {
        ensureStyles();
        var root = el("div", "h19wc");

        var launcher = el("button", "h19wc-launch");
        launcher.setAttribute("aria-label", "Chat");
        launcher.textContent = "Chat";
        launcher.addEventListener("click", toggle);

        var panel = el("div", "h19wc-panel");
        panel.setAttribute("role", "dialog");
        panel.setAttribute("aria-label", "Chat");

        var head = el("div", "h19wc-head");
        head.appendChild(el("span", "h19wc-title", "Chat"));
        var close = el("button", "h19wc-close", "×");
        close.setAttribute("aria-label", "Close");
        close.addEventListener("click", toggle);
        head.appendChild(close);

        var log = el("div", "h19wc-log");
        log.setAttribute("aria-live", "polite");

        var form = el("form", "h19wc-form");
        var input = el("input", "h19wc-input");
        input.type = "text";
        input.name = "h19wc_message";
        input.id = "h19wc_message";
        input.maxLength = TEXT_CAP;
        input.placeholder = "Type a message";
        input.setAttribute("aria-label", "Message");
        var send = el("button", "h19wc-send", "Send");
        send.type = "submit";
        form.appendChild(input);
        form.appendChild(send);
        form.addEventListener("submit", onSubmit);

        panel.appendChild(head);
        panel.appendChild(log);
        panel.appendChild(form);
        root.appendChild(panel);
        root.appendChild(launcher);
        document.body.appendChild(root);

        els = { root: root, panel: panel, log: log, input: input, launcher: launcher };
    }

    function addBubble(direction, text) {
        var bubble = el("div", "h19wc-msg " + (direction === "outgoing" ? "out" : "in"), text);
        els.log.appendChild(bubble);
        els.log.scrollTop = els.log.scrollHeight;
    }

    function note(text) {
        els.log.appendChild(el("div", "h19wc-note", text));
    }

    // ---------------------------------------------------------------
    // flow
    // ---------------------------------------------------------------
    function toggle() {
        state.open = !state.open;
        els.root.classList.toggle("open", state.open);
        if (state.open) {
            start().then(function () {
                els.input.focus();
                state.pollDelay = POLL_MIN;
                schedule(0);
            });
        }
    }

    function start() {
        if (state.session || state.starting) return Promise.resolve();
        state.starting = true;
        var known = null;
        try { known = window.localStorage.getItem(STORAGE_KEY); } catch (e) { /* private mode */ }
        return post("/care_channels/webchat/start", { session: known })
            .then(function (data) {
                state.session = data.session;
                state.greeting = data.greeting || "";
                try { window.localStorage.setItem(STORAGE_KEY, data.session); } catch (e) { /* ignore */ }
                if (state.greeting) note(state.greeting);
            })
            .catch(function () {
                note("Chat is unavailable right now.");
            })
            .then(function () { state.starting = false; });
    }

    function onSubmit(ev) {
        ev.preventDefault();
        var text = (els.input.value || "").trim().slice(0, TEXT_CAP);
        if (!text || !state.session) return;
        els.input.value = "";
        post("/care_channels/webchat/message", { session: state.session, text: text })
            .then(function () {
                state.pollDelay = POLL_MIN;
                schedule(400);
            })
            .catch(function () {
                note("That message could not be sent.");
            });
    }

    function poll() {
        if (!state.session) return;
        // POST, not GET: the session id is this visitor's credential for their
        // own thread, and a query string lands in every proxy access log.
        post("/care_channels/webchat/poll",
             { session: state.session, after_id: state.afterId })
            .then(function (data) {
                var rows = (data && data.messages) || [];
                rows.forEach(function (row) {
                    addBubble(row.direction, row.body);
                    if (row.id > state.afterId) state.afterId = row.id;
                });
                // Back off when nothing is happening; snap back on traffic.
                state.pollDelay = rows.length
                    ? POLL_MIN
                    : Math.min(POLL_MAX, Math.round(state.pollDelay * 1.6));
            })
            .catch(function () {
                state.pollDelay = Math.min(POLL_MAX, Math.round(state.pollDelay * 2));
            })
            .then(function () { schedule(state.pollDelay); });
    }

    function schedule(delay) {
        if (state.timer) clearTimeout(state.timer);
        if (!state.open) return;
        state.timer = setTimeout(poll, document.hidden ? POLL_MAX : delay);
    }

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden && state.open) {
            state.pollDelay = POLL_MIN;
            schedule(0);
        }
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", build);
    } else {
        build();
    }
})();
