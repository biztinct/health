/** @odoo-module **/
/**
 * The cockpit: four screens over one set of facts.
 *
 *   fleet   every customer, one row each, and what this machine has left.
 *   wizard  THE HERO — six steps completing in front of you, with the log
 *           lines they produce, ending on an address, a sign-in name and a
 *           one-time password.
 *   detail  one customer: overview, copies, in step, and the dangerous half.
 *   sync    where every system stands against the master.
 *
 * WHY THE WIZARD IS THE HERO. Creating a customer used to be nine commands in
 * a runbook, four of which had a trap in them that produced a system which
 * LOOKED right and was not. The screen is not a prettier way to run those
 * commands: it is the difference between an act somebody can watch and an act
 * somebody has to audit afterwards. Every step says what it did, in the words
 * of the thing it did it to, as it does it.
 *
 * ZERO DEAD ENDS, AND THAT IS THE ACCEPTANCE TEST. Every step that can fail
 * says what failed, what it left behind, and offers the one button that
 * continues or the one that undoes. There is no state this screen can reach
 * where the answer is "go and look at the machine".
 *
 * THE GOTCHAS THIS FILE IS WRITTEN AGAINST, ALL OF THEM PAID FOR ONCE:
 *   F47  `useState`'s RETURN VALUE is the subscription. `useState(x)` with the
 *        result thrown away watches nothing, silently.
 *   F16  JavaScript built-ins are not in scope inside a template. Everything a
 *        template needs is computed here.
 *   F10  a keyboard shortcut bound to `window` never fires in this web client.
 *   F37  a state colour on a kit control needs `.bzk` in front of it, or the
 *        kit out-specifies it and the rule silently loses.
 *   F57  the kit's dialog scrim is `bzk-modal-scrim`, with ONE hyphen.
 */
import { Component, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@biz_kit/js/kit_icons";
import { HubBackChip, hubBack } from "@biz_kit/js/kit_nav";
import { BizMiniRail } from "@biz_access/js/mini_rail";
import { _t } from "@web/core/l10n/translation";

/** How a state reads on screen, and which badge tone it wears. */
const STATE_WORDS = {
    draft: { label: _t("Not started"), tone: "muted" },
    provisioning: { label: _t("Being set up"), tone: "info" },
    live: { label: _t("Live"), tone: "ok" },
    error: { label: _t("Needs attention"), tone: "err" },
    decommissioned: { label: _t("Closed"), tone: "muted" },
};

const HEALTH_WORDS = {
    ok: { label: _t("Healthy"), tone: "ok" },
    warn: { label: _t("Worth a look"), tone: "warn" },
    down: { label: _t("Not answering"), tone: "err" },
    unknown: { label: _t("Not checked"), tone: "muted" },
};

const RELEASE_WORDS = {
    on: { label: _t("In step"), tone: "ok" },
    behind: { label: _t("Behind"), tone: "warn" },
    none: { label: _t("Not on a release"), tone: "muted" },
    unknown: { label: _t("Not checked"), tone: "muted" },
};

/** The six tabs on one customer. */
const TABS = [
    { key: "overview", label: _t("Overview"), icon: "gauge" },
    { key: "backups", label: _t("Copies"), icon: "archive" },
    { key: "updates", label: _t("Updates"), icon: "rocket" },
    { key: "instep", label: _t("In step"), icon: "gitMerge" },
    { key: "support", label: _t("Support access"), icon: "shield" },
    { key: "danger", label: _t("Closing down"), icon: "alert" },
];

/** How a support session reads on the customer's own record. */
const SUPPORT_WORDS = {
    issued: { label: _t("A link was made and not used"), tone: "info" },
    active: { label: _t("Somebody is in there now"), tone: "warn" },
    ended: { label: _t("Finished"), tone: "ok" },
    expired: { label: _t("The time ran out"), tone: "muted" },
    refused: { label: _t("Refused"), tone: "err" },
};

/** How one step of a rollout reads, and the tone it wears. */
const TASK_WORDS = {
    waiting: { label: _t("Waiting for their window"), tone: "muted" },
    due: { label: _t("Their window is open"), tone: "info" },
    running: { label: _t("Being updated"), tone: "info" },
    done: { label: _t("Done"), tone: "ok" },
    failed: { label: _t("Failed"), tone: "err" },
    skipped: { label: _t("Left behind"), tone: "warn" },
};

const ROLLOUT_WORDS = {
    draft: { label: _t("Not started"), tone: "muted" },
    rehearsing: { label: _t("Practising on a copy"), tone: "info" },
    running: { label: _t("Running"), tone: "info" },
    waiting: { label: _t("Waiting"), tone: "warn" },
    paused: { label: _t("Stopped"), tone: "err" },
    done: { label: _t("Finished"), tone: "ok" },
    aborted: { label: _t("Called off"), tone: "muted" },
};

/** The three words, and the floor under them: an `info` is never announced
 *  as something that needs attention (ledger F68). */
const SEVERITY_WORDS = {
    critical: { label: _t("Needs attention now"), tone: "err" },
    warning: { label: _t("Worth a look"), tone: "warn" },
    info: { label: _t("For information"), tone: "info" },
};

/** How often the rollout screen asks again while something is moving. Only
 *  while the tab is in front (ledger F14): a background tab does not update,
 *  and pretending otherwise makes a screenshot lie. */
const ROLLOUT_POLL_MS = 15000;

/**
 * A local wall-clock moment as the platform's own stored spelling.
 *
 * The two boxes on the message composer speak the reader's clock; the server
 * stores UTC. Converting HERE, explicitly, in both directions, is the whole of
 * ledger F17/F32 — the alternative moves every window by the operator's offset
 * with no error anywhere, and the customer's bar announces maintenance in the
 * middle of their morning.
 */
export function toStored(localValue) {
    if (!localValue) { return ""; }
    const d = new Date(localValue);
    if (isNaN(d.getTime())) { return ""; }
    return d.toISOString().slice(0, 19).replace("T", " ");
}

/** And back, for a box that has to open on what was sent. */
export function toLocalInput(stored) {
    if (!stored) { return ""; }
    const d = new Date(String(stored).replace(" ", "T") + "Z");
    if (isNaN(d.getTime())) { return ""; }
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
         + `T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export class BizTenants extends Component {
    static template = "biz_tenants.Cockpit";
    // ⚠ THE MINIATURE IS THE ACCESS HOME'S OWN COMPONENT, NOT A SECOND ONE.
    // It already draws a left menu the way this product's screens draw one,
    // and a copy here would be a second thing to keep in step with the first.
    static components = { HubBackChip, BizMiniRail };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.back = hubBack(this.props);
        this.slugInput = useRef("slugInput");

        this.state = useState({
            view: "fleet",
            loading: true,
            busy: "",
            fleet: null,
            sync: null,
            releases: [],
            tenant: null,
            tab: "overview",
            search: "",
            // the wizard
            form: { name: "", slug: "", contact_name: "", contact_email: "",
                    note: "" },
            slugCheck: null,
            preview: null,
            wizard: null,
            // the composer, the two confirmations, and the last plan
            composer: null,
            confirm: null,
            cutting: null,
            // Declared here rather than assigned into later: a key that
            // arrives after the fact is a key nothing was watching when the
            // screen was first painted.
            plan: null,
            slugTouched: false,
            // the rollout screen and the alerts screen
            rollout: null,
            rolloutPlan: null,
            alerts: null,
            settings: null,
            taskConfirm: null,
            aborting: null,
            updates: null,
            alertHistory: false,
            // the feature matrix and the support door
            features: null,
            featureBulk: null,
            support: null,
            supportForm: null,
            supportLink: null,
        });

        onWillStart(() => this.loadFleet());

        // ⚠ THE POLL RUNS ONLY WHILE THE TAB IS IN FRONT (ledger F14). A
        // background tab that quietly stopped asking is a screen that says a
        // rollout is still on its first ring twenty minutes after it finished.
        this._poll = setInterval(() => {
            if (document.hidden) { return; }
            if (this.state.view !== "rollout") { return; }
            if (this.state.busy) { return; }
            if (!this.rolloutIsMoving) { return; }
            this.pollRollout();
        }, ROLLOUT_POLL_MS);
        onWillUnmount(() => clearInterval(this._poll));

        // ⚠ `document` WITH `{capture: true}`, NEVER `window` (ledger F10).
        // Something in the shared client listens for keydown on the body and
        // stops the event there, so a window listener hears nothing at all —
        // silently.
        this._onKey = (ev) => this.handleKey(ev);
        document.addEventListener("keydown", this._onKey, { capture: true });
        onWillUnmount(() => {
            document.removeEventListener("keydown", this._onKey,
                                         { capture: true });
        });
    }

    // ------------------------------------------------------------- plumbing
    ic(name, size = 16) { return ic(name, size); }

    get TABS() { return TABS; }

    /**
     * The two lines at the top. Computed HERE rather than assembled in the
     * template, because a template expression is compiled against the
     * component and has no built-ins of its own (ledger F16).
     */
    get headline() {
        if (this.state.view === "wizard") { return _t("A new customer"); }
        if (this.state.view === "sync") { return _t("In step with master"); }
        if (this.state.view === "rollout") { return _t("Sending a release out"); }
        if (this.state.view === "alerts") { return _t("Alerts"); }
        if (this.state.view === "features") {
            return _t("What each customer has");
        }
        if (this.state.view === "detail" && this.state.tenant) {
            return this.state.tenant.name;
        }
        return _t("Customers");
    }

    get subhead() {
        const f = this.state.fleet;
        if (this.state.view === "wizard") {
            return _t("Six steps, about a minute, and you watch every one.");
        }
        if (this.state.view === "sync") {
            return _t("What each system has, against what this platform runs.");
        }
        if (this.state.view === "rollout") {
            return _t("A practice run, then the blank system, then one " +
                      "customer, then the rest — each inside their own night.");
        }
        if (this.state.view === "alerts") {
            return _t("Everything this platform has noticed. Nothing is " +
                      "emailed yet, so this screen is where it all appears.");
        }
        if (this.state.view === "features") {
            return _t("Every part of the product down the side, every " +
                      "customer across the top. Their own menu is drawn " +
                      "beside it as you click.");
        }
        if (this.state.view === "detail" && this.state.tenant) {
            return _t("Set up %(when)s.",
                      { when: this.state.tenant.created_on || "—" });
        }
        if (!f) { return ""; }
        return _t("Every system this machine runs, and what it has left.");
    }

    /** ".example.com" — the fixed half of the address, beside the box. */
    get apexSuffix() {
        const apex = (this.state.fleet && this.state.fleet.apex) || "";
        return apex ? `.${apex}` : "";
    }

    /** Every live customer, for "send this to everybody". */
    get liveIds() {
        const rows = (this.state.fleet && this.state.fleet.tenants) || [];
        return rows.filter((row) => row.state === "live").map((row) => row.id);
    }

    /** Two letters for the round badge. Uppercased here — see F16. */
    get initials() {
        const name = (this.state.tenant && this.state.tenant.name) || "";
        return name.trim().slice(0, 2).toUpperCase();
    }

    stateWord(key) { return STATE_WORDS[key] || STATE_WORDS.draft; }
    healthWord(key) { return HEALTH_WORDS[key] || HEALTH_WORDS.unknown; }
    releaseWord(key) { return RELEASE_WORDS[key] || RELEASE_WORDS.unknown; }
    taskWord(key) { return TASK_WORDS[key] || TASK_WORDS.waiting; }
    rolloutWord(key) { return ROLLOUT_WORDS[key] || ROLLOUT_WORDS.draft; }
    sevWord(key) { return SEVERITY_WORDS[key] || SEVERITY_WORDS.warning; }

    /** Every call the cockpit makes goes through here, so "busy" and "the
     *  reason it failed" are decided in exactly one place. */
    async call(method, args = [], what = "") {
        this.state.busy = what || method;
        try {
            return await this.orm.call("biz.tenants", method, args);
        } finally {
            this.state.busy = "";
        }
    }

    async loadFleet() {
        this.state.loading = true;
        try {
            this.state.fleet = await this.orm.call("biz.tenants", "get_fleet", []);
        } finally {
            this.state.loading = false;
        }
    }

    handleKey(ev) {
        // Bow out for anything somebody is typing into, and for an open dialog:
        // a shortcut that fires inside a text box is a shortcut that eats
        // somebody's sentence.
        const el = ev.target;
        const tag = (el && el.tagName) || "";
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT"
            || (el && el.isContentEditable)) { return; }
        if (document.querySelector(".o_dialog, .modal.show")) { return; }
        if (this.anyOverlay) {
            if (ev.key === "Escape") { this.closeOverlays(); ev.preventDefault(); }
            return;
        }
        if (ev.key === "Escape" && this.state.view !== "fleet") {
            this.goFleet();
            ev.preventDefault();
        } else if (ev.key === "r" && !ev.metaKey && !ev.ctrlKey) {
            this.refresh();
            ev.preventDefault();
        } else if (ev.key === "n" && !ev.metaKey && !ev.ctrlKey) {
            this.openWizard();
            ev.preventDefault();
        } else if (ev.key === "a" && !ev.metaKey && !ev.ctrlKey) {
            this.openAlerts();
            ev.preventDefault();
        }
    }

    closeOverlays() {
        this.state.composer = null;
        this.state.confirm = null;
        this.state.cutting = null;
        this.state.rolloutPlan = null;
        this.state.settings = null;
        this.state.taskConfirm = null;
        this.state.aborting = null;
    }

    get anyOverlay() {
        const s = this.state;
        return !!(s.composer || s.confirm || s.cutting || s.rolloutPlan
                  || s.settings || s.taskConfirm || s.aborting);
    }

    // ---------------------------------------------------------- the fleet
    get tenants() {
        const rows = (this.state.fleet && this.state.fleet.tenants) || [];
        const q = this.state.search.trim().toLowerCase();
        if (!q) { return rows; }
        return rows.filter((row) =>
            row.name.toLowerCase().includes(q)
            || row.slug.toLowerCase().includes(q)
            || (row.contact_email || "").toLowerCase().includes(q));
    }

    get hasTenants() {
        return !!(this.state.fleet && this.state.fleet.tenants.length);
    }

    get machine() {
        return (this.state.fleet && this.state.fleet.machine) || {};
    }

    /** "635 MB spare, and the floor is 400 MB." Said as a sentence, because a
     *  bare number means nothing without the floor beside it. */
    get memorySentence() {
        const m = this.machine;
        if (!m.free_mb || m.free_mb < 0) {
            return _t("This machine's spare memory could not be read.");
        }
        if (m.free_mb < m.floor_mb) {
            return _t(
                "%(free)s MB spare — below the %(floor)s MB floor. No new " +
                "customer can be created until there is more.",
                { free: m.free_mb, floor: m.floor_mb });
        }
        return _t("%(free)s MB of memory spare, %(disk)s of disk.",
                  { free: m.free_mb, disk: m.disk_free });
    }

    get configured() {
        return !!(this.state.fleet && this.state.fleet.configured);
    }

    goFleet() {
        this.state.view = "fleet";
        this.state.tenant = null;
        this.closeOverlays();
    }

    async refresh() {
        if (this.state.view === "detail" && this.state.tenant) {
            this.state.tenant = await this.call(
                "refresh_health", [this.state.tenant.id],
                _t("Reading their system…"));
        } else if (this.state.view === "sync") {
            this.state.sync = await this.call("sync_report", [],
                                              _t("Reading every system…"));
        } else if (this.state.view === "rollout") {
            this.state.rollout = await this.call("rollout_state", [],
                                                 _t("Reading the rollout…"));
        } else if (this.state.view === "alerts") {
            this.state.alerts = await this.call(
                "alert_check_now", [], _t("Looking at everything again…"));
        } else {
            await this.loadFleet();
        }
        this.notification.add(_t("Up to date."), { type: "success" });
    }

    openUrl(url) { window.open(url, "_blank", "noreferrer"); }

    // ------------------------------------------------- the wizard (the hero)
    openWizard() {
        this.state.view = "wizard";
        this.state.form = { name: "", slug: "", contact_name: "",
                            contact_email: "", note: "" };
        this.state.slugCheck = null;
        this.state.preview = null;
        this.state.wizard = null;
    }

    /**
     * A short name suggested from the customer's name, so the commonest case
     * is one field instead of two — and still editable, because the suggestion
     * is a guess and the field is an address.
     */
    onName(ev) {
        this.state.form.name = ev.target.value;
        if (!this.state.form.slug || this.state.slugTouched !== true) {
            const guess = String(ev.target.value || "")
                .toLowerCase().normalize("NFD")
                // The accent marks that `NFD` just split off, named by their
                // code points rather than pasted in: a combining mark typed
                // literally into a source file is invisible to the next reader
                // and does not survive every editor.
                .replace(/[\u0300-\u036f]/g, "")
                .replace(/[^a-z0-9]/g, "")
                .slice(0, 20);
            this.state.form.slug = guess;
            this.checkSlug();
        }
    }

    onSlug(ev) {
        this.state.slugTouched = true;
        this.state.form.slug = ev.target.value;
        this.checkSlug();
    }

    onField(field, ev) { this.state.form[field] = ev.target.value; }

    async checkSlug() {
        const slug = this.state.form.slug;
        if (!slug) { this.state.slugCheck = null; return; }
        clearTimeout(this._slugTimer);
        this._slugTimer = setTimeout(async () => {
            try {
                this.state.slugCheck = await this.orm.call(
                    "biz.tenants", "check_slug", [slug]);
            } catch {
                this.state.slugCheck = null;
            }
        }, 250);
    }

    get canPreview() {
        const f = this.state.form;
        return !!(f.name.trim() && f.contact_email.includes("@")
                  && this.state.slugCheck && this.state.slugCheck.ok);
    }

    async doPreview() {
        this.state.preview = await this.call(
            "provision_preview", [{ ...this.state.form }],
            _t("Working out what would happen…"));
    }

    /**
     * The whole run: create the record, then walk the six steps one at a time.
     *
     * ONE STEP PER CALL, ON PURPOSE. A single call that did all six would give
     * the screen nothing to draw until it finished or failed, on an act that
     * takes the better part of a minute — and would leave a failure in the
     * middle with nothing said about the five that had already happened.
     */
    /** Carry on from where a resumed customer stopped. */
    async resumeRun() {
        const w = this.state.wizard;
        if (!w) { return; }
        w.paused = false;
        await this.continueFrom(w.failedAt || "clone", false);
    }

    async runAll(preview = false) {
        const started = await this.call(
            "provision_start", [{ ...this.state.form }], _t("Creating…"));
        this.state.wizard = {
            tenantId: started.tenant_id,
            steps: started.steps.map((s) => ({ ...s, state: "waiting" })),
            log: [],
            done: false,
            failed: false,
            credentials: null,
            url: "",
            retry: "",
            preview,
        };
        await this.continueFrom(started.steps[0].key, preview);
    }

    /** Run from this step onwards, stopping at the first failure. */
    async continueFrom(startKey, preview = false) {
        const w = this.state.wizard;
        if (!w) { return; }
        w.failed = false;
        w.paused = false;
        let key = startKey;
        while (key) {
            const step = w.steps.find((s) => s.key === key);
            if (step) { step.state = "running"; }
            const res = await this.call(
                "provision_run", [w.tenantId, key, preview],
                (step && step.label) || key);
            for (const line of res.log || []) {
                w.log.push({ ...line, step: key });
            }
            if (step) {
                step.state = res.ok ? "done" : "failed";
                step.ms = res.ms;
            }
            if (res.credentials) { w.credentials = res.credentials; }
            if (res.url) { w.url = res.url; }
            if (res.retry) { w.retry = res.retry; }
            if (!res.ok) {
                w.failed = true;
                w.error = res.error;
                w.failedAt = key;
                break;
            }
            key = res.next;
        }
        w.done = !w.failed;
        await this.loadFleet();
    }

    async retryStep() {
        const w = this.state.wizard;
        if (w && w.failedAt) { await this.continueFrom(w.failedAt, w.preview); }
    }

    /**
     * Pick a half-made customer back up — ZERO DEAD ENDS, ACROSS A RELOAD.
     *
     * THE GAP THIS CLOSES, FOUND BY WALKING IT. A run that fails leaves the
     * screen offering "try again" and "undo", which is right — until somebody
     * closes the tab. After that the customer sits on the fleet in "Being set
     * up" with their short name taken, their system half-built, and no way
     * back into the six steps: the only remaining move was to go and look at
     * the machine, which is the one outcome this screen exists to make
     * impossible.
     *
     * The record already carries everything needed — the step it reached, and
     * the log of what happened — so resuming is a read, not a repair.
     */
    async resume(id) {
        const t = await this.call("get_tenant", [id], _t("Opening…"));
        this.state.form = {
            name: t.name, slug: t.slug, contact_name: t.contact_name,
            contact_email: t.contact_email, note: t.note || "",
        };
        this.state.slugTouched = true;
        this.state.preview = null;
        const fleet = this.state.fleet || {};
        const reached = t.step || "";
        let past = !!reached;
        this.state.wizard = {
            tenantId: t.id,
            steps: (fleet.steps || []).map((s) => {
                const row = { ...s, state: past ? "done" : "waiting" };
                if (s.key === reached) { past = false; }
                return row;
            }),
            // The lines the earlier attempt produced, so the screen it comes
            // back to is the screen it left.
            log: (t.log || "").split("\n").filter((l) => l.trim())
                .map((l) => ({ line: l, level: l.includes("FAILED") ? "error"
                                     : l.includes("NOTE") ? "warn" : "info",
                               step: "" })),
            done: false,
            failed: t.state === "error",
            // Not failed and not finished: somebody walked away. The screen
            // then offers ONE button — carry on from the step it reached.
            paused: t.state !== "error",
            failedAt: t.next_step,
            error: t.error || "",
            credentials: null,
            url: "",
            retry: "",
            preview: false,
        };
        this.state.view = "wizard";
    }

    /** Is this row a customer somebody started and did not finish? */
    unfinished(row) {
        return row.state === "draft" || row.state === "provisioning"
            || row.state === "error";
    }

    async undoWizard() {
        const w = this.state.wizard;
        if (!w) { return; }
        await this.call("provision_undo",
                        [w.tenantId, this.state.form.slug], _t("Undoing…"));
        this.notification.add(_t("Undone. Nothing was left behind."),
                              { type: "success" });
        await this.loadFleet();
        this.goFleet();
    }

    get wizardStepsDone() {
        const w = this.state.wizard;
        if (!w) { return 0; }
        return w.steps.filter((s) => s.state === "done").length;
    }

    copyText(text) {
        try {
            navigator.clipboard.writeText(String(text || ""));
            this.notification.add(_t("Copied."), { type: "success" });
        } catch {
            this.notification.add(
                _t("This browser would not let the page copy it — select it " +
                   "and copy it by hand."), { type: "warning" });
        }
    }

    // ------------------------------------------------------- one customer
    async openTenant(id) {
        this.state.tenant = await this.call("get_tenant", [id], _t("Opening…"));
        this.state.tab = "overview";
        this.state.view = "detail";
    }

    async setTab(key) {
        // The answer first, the tab second (H72) — these tabs read their own
        // data and would otherwise render against nothing, which throws inside
        // the component's lifecycle and puts a stack trace in front of
        // somebody before recovering a second later.
        if (key === "updates") { await this.openUpdates(); }
        if (key === "support") { await this.openSupport(); }
        this.state.tab = key;
    }

    get logLines() {
        const t = this.state.tenant;
        if (!t || !t.log) { return []; }
        return t.log.split("\n").filter((l) => l.trim()).reverse();
    }

    get healthRows() {
        const t = this.state.tenant;
        const d = (t && t.health_detail) || {};
        const rows = [];
        rows.push({ key: "answers",
                    label: _t("Their address answers"),
                    value: t.http_status === 200
                        ? _t("Yes, in %(ms)s ms", { ms: t.ping_ms })
                        : _t("No — it answered %(code)s",
                             { code: t.http_status || _t("nothing") }),
                    tone: t.http_status === 200 ? "ok" : "err" });
        rows.push({ key: "skipped",
                    label: _t("Parts that did not load"),
                    value: t.skipped_count < 0
                        ? _t("Could not be determined")
                        : String(t.skipped_count),
                    tone: t.skipped_count === 0 ? "ok"
                        : t.skipped_count < 0 ? "muted" : "err" });
        rows.push({ key: "errors",
                    label: _t("Errors in their log, last day"),
                    value: String(d.error_count === undefined ? "—" : d.error_count)
                        + (d.ignored_count
                            ? _t(" (%(n)s more were on the ignore list)",
                                 { n: d.ignored_count })
                            : ""),
                    tone: d.error_count ? "warn" : "ok" });
        rows.push({ key: "jobs",
                    label: _t("Scheduled jobs running late"),
                    value: d.failing_jobs === undefined ? "—"
                        : String(d.failing_jobs),
                    tone: d.failing_jobs ? "warn" : "ok" });
        rows.push({ key: "backup",
                    label: _t("Last copy"),
                    value: t.last_backup && !d.backup_stale
                        ? t.last_backup
                        : t.last_backup
                            ? _t("%(when)s — older than two days",
                                 { when: t.last_backup })
                            : _t("Never"),
                    tone: t.last_backup && !d.backup_stale ? "ok" : "warn" });
        rows.push({ key: "cert",
                    label: _t("Certificate"),
                    value: t.cert_state === "own"
                        ? _t("Its own, until %(when)s", { when: t.cert_expires_on })
                        : t.cert_state === "shared"
                            ? _t("Falling back to the shared one — a browser " +
                                 "warns about the name")
                            : _t("Could not be read"),
                    tone: t.cert_state === "own" ? "ok" : "warn" });
        rows.push({ key: "seen",
                    label: _t("Last time somebody was in"),
                    value: d.last_seen || _t("Nobody yet"),
                    tone: "muted" });
        return rows;
    }

    get logErrors() {
        const d = (this.state.tenant && this.state.tenant.health_detail) || {};
        return d.errors || [];
    }

    async backupNow() {
        this.state.tenant = await this.call(
            "backup_now", [this.state.tenant.id, "manual"],
            _t("Taking a copy — this can take a minute…"));
        this.notification.add(_t("Copy kept."), { type: "success" });
    }

    async restoreStaging(backupId) {
        const res = await this.call(
            "restore_to_staging", [this.state.tenant.id, backupId],
            _t("Putting the copy back into a practice system…"));
        this.notification.add(res.note, { type: "success", sticky: true });
        this.state.tenant = await this.call("get_tenant",
                                            [this.state.tenant.id]);
    }

    async dropStaging() {
        this.state.tenant = await this.call(
            "drop_staging", [this.state.tenant.id], _t("Removing…"));
        this.notification.add(_t("Practice system removed."),
                              { type: "success" });
    }

    // -------------------------------------------------------- the composer
    openComposer(tenantIds) {
        const now = new Date();
        const later = new Date(now.getTime() + 6 * 3600 * 1000);
        this.state.composer = {
            tenantIds,
            kind: "maintenance",
            text: "",
            from: toLocalInput(toStored(now)),
            to: toLocalInput(toStored(later)),
        };
    }

    onComposer(field, ev) { this.state.composer[field] = ev.target.value; }

    async sendNotice() {
        const c = this.state.composer;
        const res = await this.call("notice_send", [
            c.tenantIds, c.kind, c.text, toStored(c.from), toStored(c.to),
        ], _t("Sending…"));
        this.state.composer = null;
        this.notification.add(
            res.skipped
                ? _t("Sent to %(sent)s. %(skipped)s could not be reached — " +
                     "bring them in step first.",
                     { sent: res.sent, skipped: res.skipped })
                : _t("Sent to %(sent)s.", { sent: res.sent }),
            { type: res.skipped ? "warning" : "success" });
        await this.loadFleet();
        if (this.state.view === "detail" && this.state.tenant) {
            this.state.tenant = await this.call("get_tenant",
                                                [this.state.tenant.id]);
        }
    }

    async clearNotice(tenantId) {
        await this.call("notice_clear", [[tenantId]], _t("Clearing…"));
        this.notification.add(_t("The bar has come down."), { type: "success" });
        await this.loadFleet();
        if (this.state.view === "detail" && this.state.tenant) {
            this.state.tenant = await this.call("get_tenant",
                                                [this.state.tenant.id]);
        }
    }

    // ----------------------------------------------------- in step / releases
    /**
     * ⚠ THE ANSWER FIRST, THE VIEW SECOND. Switching the view before the read
     * finishes renders a screen against `null` — and this one reads its data
     * on its very first line, so it throws inside the component's lifecycle
     * and the person gets a red technical box with a stack trace in it. It
     * recovers a second later when the answer lands, which is what made it
     * look like a flicker rather than a fault.
     *
     * Found in a browser and nowhere else. The template guards the null as
     * well — belt and braces, because the next caller will not have read this.
     */
    async openSync() {
        const [report, releases] = await Promise.all([
            this.call("sync_report", [], _t("Reading every system…")),
            this.call("release_list", []),
        ]);
        this.state.sync = report;
        this.state.releases = releases;
        this.state.view = "sync";
    }

    async bringInStep(target, dryRun) {
        const plan = await this.call(
            "sync_bring_in_step", [target, dryRun],
            dryRun ? _t("Working out what would change…")
                   : _t("Bringing it in step — this can take a few minutes…"));
        this.state.plan = plan;
        this.notification.add(plan.message,
                              { type: dryRun ? "info" : "success",
                                sticky: !dryRun });
        if (!dryRun) { await this.openSync(); }
        return plan;
    }

    openCut() { this.state.cutting = { notes: "" }; }

    onCutNotes(ev) { this.state.cutting.notes = ev.target.value; }

    async cutRelease() {
        const notes = this.state.cutting.notes;
        this.state.cutting = null;
        this.state.sync = await this.call("release_cut", [notes],
                                          _t("Taking the photograph…"));
        this.state.releases = await this.call("release_list", []);
        this.notification.add(
            _t("Release cut. Every customer moved onto it from now on gets " +
               "your note on their own About screen."),
            { type: "success" });
        await this.loadFleet();
    }

    async quietTemplate() {
        const res = await this.call("template_quiet_now", [],
                                    _t("Switching them off…"));
        this.notification.add(
            _t("%(n)s scheduled jobs switched off on the blank system.",
               { n: res.disabled }),
            { type: "success" });
    }

    // =====================================================================
    //  THE ROLLOUT SCREEN — the hero. A release walking the fleet, ring by
    //  ring, with Pause / Continue / Retry / Leave behind / Call it off always
    //  one press away and every one of them saying what it will do.
    // =====================================================================
    /**
     * ⚠ THE ANSWER FIRST, THE VIEW SECOND (ledger H72). This screen reads its
     * data on its very first line, so switching to it before the read lands
     * renders it against `null`, throws inside the component's lifecycle, and
     * puts a stack trace in front of somebody — which then recovers a second
     * later, so it reads as a flicker rather than as a fault.
     */
    async openRollout() {
        const data = await this.call("rollout_state", [],
                                     _t("Reading the rollout…"));
        this.state.rollout = data;
        this.state.view = "rollout";
    }

    /** Quietly, for the poll: no spinner, and a failure is not a dialog. */
    async pollRollout() {
        try {
            this.state.rollout = await this.orm.call("biz.tenants",
                                                     "rollout_state", []);
        } catch {
            // A poll that fails is a poll. The next one will say so if it is
            // not a blip, and a red box every fifteen seconds is not help.
        }
    }

    get current() {
        return (this.state.rollout && this.state.rollout.current) || null;
    }

    /**
     * ⚠ A STRING, NOT THE OBJECT (ledger F47, second half). Watching the
     * rollout object itself would repaint on every poll for ever, because the
     * poll replaces it with a fresh one whether or not anything moved. This
     * changes only when the answer changes.
     */
    get rolloutSignature() {
        const c = this.current;
        if (!c) { return "none"; }
        return [c.id, c.state, c.ring, c.done_count, c.failed_count,
                c.queued_count].join("|");
    }

    /* Every one of these is a list membership computed HERE rather than in the
     * template. A template is compiled against the component and has no
     * built-ins of its own (ledger F16), and a list written inline is also a
     * list nothing can test. */
    get rolloutIsMoving() {
        const c = this.current;
        return !!(c && ["rehearsing", "running", "waiting"].includes(c.state));
    }

    get rolloutIsOver() {
        const c = this.current;
        return !!(c && ["done", "aborted"].includes(c.state));
    }

    /** Waiting for a window, or in one and not yet started. */
    taskIsQueued(task) {
        return !!task && ["waiting", "due"].includes(task.state);
    }

    /** Anything not already done can still be left behind. */
    taskCanBeLeft(task) {
        return !!task && ["waiting", "due", "failed"].includes(task.state);
    }

    /** The one line under the title: where this release has got to. */
    get rolloutSentence() {
        const c = this.current;
        if (!c) { return _t("No release is going out."); }
        if (c.state === "done") {
            return _t("Release %(name)s is out. %(n)s of %(total)s customers " +
                      "have it, and it took %(mins)s minutes.",
                      { name: c.release, n: c.customer_done,
                        total: c.customer_total, mins: c.minutes });
        }
        if (c.state === "aborted") {
            return _t("Release %(name)s was called off.", { name: c.release });
        }
        if (c.state === "paused") {
            return _t("Stopped on %(ring)s. Nothing goes any further until " +
                      "somebody decides what to do.", { ring: c.ring_label });
        }
        if (c.state === "waiting" && c.watch_until) {
            return _t("Watching %(ring)s for another %(h)s hours before the " +
                      "next ring opens.",
                      { ring: c.ring_label, h: c.watch_left_h });
        }
        if (c.state === "waiting") {
            return _t("Waiting for the next customer's quiet window to open.");
        }
        return _t("On %(ring)s. %(done)s of %(total)s systems done.",
                  { ring: c.ring_label, done: c.done_count,
                    total: c.task_count });
    }

    /** 0–100, for the bar across the top of the ring diagram. */
    get rolloutPercent() {
        const c = this.current;
        if (!c || !c.task_count) { return 0; }
        return Math.round((c.done_count * 100) / c.task_count);
    }

    ringMeaning(ring) {
        const r = this.state.rollout;
        return (r && r.ring_meaning && r.ring_meaning[ring]) || "";
    }

    async openRolloutPlan() {
        const plan = await this.call("rollout_plan", [],
                                     _t("Working out what would happen…"));
        this.state.rolloutPlan = plan;
    }

    async startRollout() {
        const plan = this.state.rolloutPlan;
        this.state.rolloutPlan = null;
        this.state.rollout = await this.call(
            "rollout_start",
            [plan.release.id, plan.watch_canary, plan.watch_early],
            _t("Practising on a throwaway copy — this takes a minute or two…"));
        this.state.view = "rollout";
        this.notification.add(
            _t("Started. The practice run has just happened; everything after " +
               "it waits for its own window."),
            { type: "success", sticky: true });
    }

    async rolloutAct(method, args, what) {
        this.state.rollout = await this.call(method, args, what);
        await this.loadFleet();
    }

    pauseRollout() {
        return this.rolloutAct("rollout_pause", [this.current.id, ""],
                               _t("Stopping it…"));
    }

    resumeRollout() {
        return this.rolloutAct("rollout_resume", [this.current.id],
                               _t("Carrying on…"));
    }

    continueNow() {
        return this.rolloutAct("rollout_continue_now", [this.current.id],
                               _t("Ending the watch period…"));
    }

    retryTask(id) {
        return this.rolloutAct("task_retry", [id], _t("Trying it again…"));
    }

    runTaskNow(id) {
        return this.rolloutAct("task_run_now", [id], _t("Updating them now…"));
    }

    /** Leaving a customer behind needs their short name typed. */
    askSkip(task) {
        this.state.taskConfirm = { task, typed: "" };
    }

    onSkipType(ev) { this.state.taskConfirm.typed = ev.target.value; }

    get skipMatches() {
        const c = this.state.taskConfirm;
        if (!c) { return false; }
        if (!c.task.slug) { return true; }
        return c.typed.trim().toLowerCase() === c.task.slug;
    }

    async doSkip() {
        const c = this.state.taskConfirm;
        this.state.taskConfirm = null;
        await this.rolloutAct("task_skip", [c.task.id, c.typed],
                              _t("Leaving them behind…"));
    }

    askAbort() { this.state.aborting = { typed: "" }; }

    onAbortType(ev) { this.state.aborting.typed = ev.target.value; }

    get abortMatches() {
        const a = this.state.aborting;
        return !!(a && this.current
                  && a.typed.trim() === this.current.release);
    }

    async doAbort() {
        const typed = this.state.aborting.typed;
        this.state.aborting = null;
        await this.rolloutAct("rollout_abort", [this.current.id, typed],
                              _t("Calling it off…"));
    }

    // ---------------------------------------------- one customer's updates
    async openUpdates() {
        this.state.updates = await this.call(
            "tenant_updates", [this.state.tenant.id], _t("Reading…"));
    }

    /**
     * The hours and the lengths, as lists on the COMPONENT. A template is
     * compiled against the component and has no built-ins of its own (F16), so
     * anything it loops over is computed here rather than written inline.
     */
    get hourChoices() {
        return Array.from({ length: 24 }, (_v, i) => i);
    }

    get lengthChoices() { return [1, 2, 3, 4, 5, 6, 8, 10, 12]; }

    async setWindow(field, value) {
        const u = this.state.updates;
        const args = [u.id, null, null, null];
        const at = { ring: 1, start_hour: 2, hours: 3 }[field];
        args[at] = field === "ring" ? value : parseInt(value, 10);
        this.state.updates = await this.call("tenant_set_window", args,
                                             _t("Saving…"));
        this.notification.add(_t("Saved."), { type: "success" });
    }

    setRing(key) { return this.setWindow("ring", key); }
    onWindowHour(ev) { return this.setWindow("start_hour", ev.target.value); }
    onWindowLength(ev) { return this.setWindow("hours", ev.target.value); }

    // =====================================================================
    //  THE FEATURE MATRIX — the hero of this phase.
    //
    //  Every part of the product down the side, every customer across the top,
    //  and a MINIATURE OF THAT CUSTOMER'S OWN LEFT MENU beside it, redrawing as
    //  the switches move. A grid answers both questions people actually ask —
    //  "who has Telehealth?" and "what does this one get?" — and the miniature
    //  turns a promise into a picture: the owner sees what the customer will
    //  see BEFORE pressing anything.
    // =====================================================================
    /** ⚠ THE ANSWER FIRST, THE VIEW SECOND (ledger H72). */
    async openFeatures(tenantId) {
        const data = await this.call(
            "features_data", [tenantId || null],
            _t("Reading what each customer has…"));
        this.state.features = data;
        this.state.view = "features";
    }

    get featureRows() {
        return (this.state.features && this.state.features.features) || [];
    }

    get featureCols() {
        return (this.state.features && this.state.features.tenants) || [];
    }

    get featureFocus() {
        const f = this.state.features;
        if (!f) { return null; }
        return f.tenants.find((t) => t.id === f.focus_id) || null;
    }

    /**
     * One cell.
     *
     * Read out of the answers map the server sent, which is keyed by the
     * customer's id AS A STRING — a JSON object cannot have a number for a key,
     * and reading it with a number silently answers `undefined` for every cell
     * on the grid.
     */
    featureCell(tenantId, key) {
        const f = this.state.features;
        if (!f) { return { on: true, reason: "", decided: false }; }
        const row = f.answers[String(tenantId)] || {};
        return row[key] || { on: true, reason: "", decided: false };
    }

    featureCellClass(tenantId, key) {
        const cell = this.featureCell(tenantId, key);
        const focus = this.state.features
            && this.state.features.focus_id === tenantId;
        return "bzt-fx-cell"
             + (cell.on ? " is-on" : " is-off")
             + (cell.decided ? " is-decided" : "")
             + (focus ? " is-focus" : "");
    }

    featureCellTitle(tenantId, key) {
        const cell = this.featureCell(tenantId, key);
        if (cell.on) { return _t("They have this. Click to switch it off."); }
        return cell.reason
            ? _t("Off — %(why)s. Click to switch it back on.",
                 { why: cell.reason })
            : _t("Off, with no reason written down. Click to switch it on.");
    }

    /** Clicking a cell picks that column AND moves the switch. */
    async toggleFeature(tenantId, key) {
        const cell = this.featureCell(tenantId, key);
        const res = await this.call(
            "feature_set", [tenantId, key, !cell.on, ""],
            cell.on ? _t("Switching it off…") : _t("Switching it on…"));
        this.state.features.answers[String(tenantId)] = res.answers;
        this.state.features.focus_id = tenantId;
        this.state.features.preview = res.preview;
        const col = this.featureCols.find((t) => t.id === tenantId);
        if (col) {
            col.off = Object.keys(res.answers)
                .filter((k) => !res.answers[k].on).sort();
        }
        this.notification.add(res.message, {
            type: res.pushed && res.pushed.ok ? "success" : "warning",
        });
        if (res.pushed && !res.pushed.ok) {
            this.notification.add(
                _t("It is recorded here, but their system could not be told: " +
                   "%(why)s", { why: res.pushed.reason || "" }),
                { type: "warning", sticky: true });
        }
    }

    /** Picking a column redraws the miniature beside the grid. */
    async focusFeatureColumn(tenantId) {
        if (!this.state.features
            || this.state.features.focus_id === tenantId) { return; }
        const preview = await this.call("feature_preview", [tenantId]);
        this.state.features.focus_id = tenantId;
        this.state.features.preview = preview;
    }

    /** The miniature's sections, in the shape the shared component draws. */
    get previewSections() {
        const p = this.state.features && this.state.features.preview;
        return (p && p.sections) || [];
    }

    get previewKnown() {
        const p = this.state.features && this.state.features.preview;
        return !!(p && p.known);
    }

    get previewNote() {
        const p = this.state.features && this.state.features.preview;
        return (p && p.note) || "";
    }

    get previewHidden() {
        const p = this.state.features && this.state.features.preview;
        return (p && p.hidden) || 0;
    }

    /** Bulk, in either direction: a whole column or a whole row. */
    askFeatureBulk(axis, id, on) {
        const f = this.state.features;
        const what = axis === "column"
            ? (f.tenants.find((t) => t.id === id) || {}).name
            : (f.features.find((r) => r.key === id) || {}).name;
        this.state.featureBulk = { axis, id, on, what, reason: "" };
    }

    onFeatureBulkReason(ev) {
        this.state.featureBulk.reason = ev.target.value;
    }

    get featureBulkTitle() {
        const b = this.state.featureBulk;
        if (!b) { return ""; }
        if (b.axis === "column") {
            return b.on
                ? _t("Switch everything on for %(who)s?", { who: b.what })
                : _t("Switch everything off for %(who)s?", { who: b.what });
        }
        return b.on
            ? _t("Switch %(what)s on for every live customer?", { what: b.what })
            : _t("Switch %(what)s off for every live customer?",
                 { what: b.what });
    }

    async runFeatureBulk() {
        const b = this.state.featureBulk;
        this.state.featureBulk = null;
        const res = b.axis === "column"
            ? await this.call("feature_set_column", [b.id, b.on, b.reason],
                              _t("Moving every switch…"))
            : await this.call("feature_set_row", [b.id, b.on, b.reason],
                              _t("Telling every customer…"));
        this.notification.add(res.message, { type: "success" });
        await this.openFeatures(b.axis === "column" ? b.id
                                                    : this.state.features.focus_id);
    }

    async pushFeaturesAgain() {
        const res = await this.call("features_push_all", [],
                                    _t("Telling every customer again…"));
        this.notification.add(
            res.skipped
                ? _t("Told %(sent)s. %(skipped)s could not be reached.",
                     { sent: res.sent, skipped: res.skipped })
                : _t("Told all %(sent)s.", { sent: res.sent }),
            { type: res.skipped ? "warning" : "success" });
    }

    // =====================================================================
    //  SUPPORT ACCESS — a reason, a time box, one link, and a trail.
    // =====================================================================
    async openSupport() {
        const t = this.state.tenant;
        if (!t) { return; }
        this.state.support = await this.call(
            "support_data", [t.id], _t("Reading their own record…"));
    }

    supportWords(state) {
        return SUPPORT_WORDS[state]
            || { label: state, tone: "muted" };
    }

    askSupport() {
        const s = this.state.support;
        this.state.supportForm = {
            reason: "", minutes: 30,
            boxes: (s && s.time_boxes) || [15, 30, 60],
        };
        this.state.supportLink = null;
    }

    onSupportReason(ev) { this.state.supportForm.reason = ev.target.value; }

    setSupportMinutes(n) { this.state.supportForm.minutes = n; }

    /**
     * The reason is required and the screen says so before the button is
     * pressed, not after: a refusal a person could have been warned about is a
     * refusal that should have been a hint.
     */
    get supportReady() {
        const f = this.state.supportForm;
        return !!(f && f.reason.trim().length
                  >= ((this.state.support && this.state.support.min_reason) || 12));
    }

    async startSupport() {
        const f = this.state.supportForm;
        const t = this.state.tenant;
        const res = await this.call(
            "support_start", [t.id, f.reason, f.minutes],
            _t("Making the link…"));
        this.state.supportForm = null;
        this.state.supportLink = res;
        await this.openSupport();
    }

    async endSupport(sessionId) {
        const t = this.state.tenant;
        const res = await this.call("support_end", [t.id, sessionId || null],
                                    _t("Ending it…"));
        this.notification.add(res.message, { type: "success" });
        await this.openSupport();
    }

    // =====================================================================
    //  THE ALERTS SCREEN — the second hero, and today the ONLY channel.
    //  With nothing being emailed, this screen is the whole of how a problem
    //  reaches a person, which is why it opens on "since you were last here".
    // =====================================================================
    async openAlerts() {
        const data = await this.call("alerts_data", [],
                                     _t("Reading what has been noticed…"));
        this.state.alerts = data;
        this.state.view = "alerts";
    }

    get alertGroups() {
        const a = this.state.alerts;
        if (!a) { return []; }
        return [
            { key: "critical", label: _t("Needs attention now"),
              tone: "err", rows: a.critical },
            { key: "warning", label: _t("Worth a look"),
              tone: "warn", rows: a.warning },
            { key: "info", label: _t("For information"),
              tone: "info", rows: a.info },
            { key: "acknowledged", label: _t("You said you know about these"),
              tone: "muted", rows: a.acknowledged },
        ].filter((g) => g.rows && g.rows.length);
    }

    /** Who would be told, as one readable line. Joined HERE, not in the
     *  template (F16), and honest when the answer is "nobody". */
    get recipientLine() {
        const a = this.state.alerts;
        const rows = (a && a.channel && a.channel.recipients) || [];
        return rows.length ? rows.join(", ") : _t("nobody has an address");
    }

    get defaultRecipientLine() {
        const s = this.state.settings;
        const rows = (s && s.default_recipients) || [];
        return rows.length ? rows.join(", ") : _t("nobody has one");
    }

    get nothingWrong() {
        const a = this.state.alerts;
        return !!(a && !a.open_count);
    }

    async alertAct(method, args, what) {
        this.state.alerts = await this.call(method, args, what);
        await this.loadFleet();
    }

    ackAlert(id) {
        return this.alertAct("alert_ack", [id], _t("Noted…"));
    }

    resolveAlert(id) {
        return this.alertAct("alert_resolve", [id, ""], _t("Closing it…"));
    }

    /**
     * ⚠ NOT THE SAME BUTTON AS "IT IS OVER" (ledger F41). A RESOLVED urgent
     * alert shows on the PUBLIC page as an incident for seven days, which is
     * right for something that really happened and wrong for one raised while
     * somebody was testing the alarm. The wording on the button says so.
     */
    deleteAlert(id) {
        return this.alertAct("alert_delete", [id], _t("Removing it…"));
    }

    toggleAlertHistory() {
        this.state.alertHistory = !this.state.alertHistory;
    }

    async sendTestEmail() {
        const res = await this.call("mail_test", [], _t("Trying…"));
        this.notification.add(res.message,
                              { type: res.ok ? "success" : "warning",
                                sticky: true });
        this.state.alerts = await this.call("alerts_data", [false]);
    }

    async openSettings() {
        this.state.settings = await this.call("alert_settings", [],
                                              _t("Reading the settings…"));
    }

    onSetting(field, ev) {
        this.state.settings[field] = ev.target.value;
    }

    onThreshold(field, ev) {
        this.state.settings.thresholds[field] = ev.target.value;
    }

    async saveSettings() {
        const s = this.state.settings;
        const saved = await this.call("alert_settings_save", [{
            alert_to: s.alert_to,
            interval_critical: s.interval_critical,
            interval_warning: s.interval_warning,
            tenant_cost_mb: s.tenant_cost_mb,
            reserve_mb: s.reserve_mb,
            status_tz: s.status_tz,
            health_ignore: s.health_ignore,
            thresholds: s.thresholds,
        }], _t("Saving…"));
        this.state.settings = saved;
        this.notification.add(_t("Saved."), { type: "success" });
        await this.loadFleet();
    }

    closeSettings() { this.state.settings = null; }

    async refreshStatusPage() {
        const res = await this.call("status_page_refresh", [],
                                    _t("Rewriting the public page…"));
        this.notification.add(
            res.ok
                ? _t("Rewritten. Anybody visiting the public address sees it now.")
                : _t("It could not be written: %(why)s", { why: res.reason }),
            { type: res.ok ? "success" : "warning", sticky: !res.ok });
        this.state.alerts = await this.call("alerts_data", [false]);
    }

    // ------------------------------------------------------ the capacity gauge
    get capacity() {
        return (this.state.fleet && this.state.fleet.capacity) || {};
    }

    /** How full the bar reads. Room for six or more paints a full bar: past
     *  that the number is the answer and the bar is decoration. */
    get capacityPercent() {
        const c = this.capacity;
        const room = c.headroom || 0;
        return Math.max(4, Math.min(100, Math.round((room / 6) * 100)));
    }

    get capacitySentence() {
        const c = this.capacity;
        if (!c.reason) { return ""; }
        return c.reason;
    }

    get banner() {
        return (this.state.fleet && this.state.fleet.alert) || {};
    }

    // ------------------------------------------------------------- danger
    askConfirm(kind) {
        this.state.confirm = { kind, typed: "" };
    }

    onConfirmType(ev) { this.state.confirm.typed = ev.target.value; }

    get confirmMatches() {
        const c = this.state.confirm;
        const t = this.state.tenant;
        return !!(c && t && c.typed.trim().toLowerCase() === t.slug);
    }

    async doConfirm() {
        const c = this.state.confirm;
        const t = this.state.tenant;
        this.state.confirm = null;
        if (c.kind === "undo") {
            await this.call("provision_undo", [t.id, c.typed], _t("Undoing…"));
            this.notification.add(_t("Undone."), { type: "success" });
        } else if (c.kind === "reopen") {
            // ⚠ ZERO DEAD ENDS ACROSS A CLOSURE. A closed customer keeps
            // their short name, so the new-customer screen refuses it — and
            // a customer whose system has to be rebuilt would have no way
            // forward. This walks straight into the six steps, on their own
            // record, so their copies and their log stay in one place.
            const res = await this.call("reopen", [t.id, c.typed],
                                        _t("Putting them back at the start…"));
            this.notification.add(res.message, { type: "success" });
            await this.loadFleet();
            await this.resume(t.id);
            return;
        } else {
            const res = await this.call("decommission", [t.id, c.typed],
                                        _t("Closing down…"));
            this.notification.add(
                _t("Closed. The final copy is at %(path)s (%(size)s).",
                   { path: res.final_backup, size: res.final_size }),
                { type: "success", sticky: true });
        }
        await this.loadFleet();
        this.goFleet();
    }
}

registry.category("actions").add("biz_tenants", BizTenants);
