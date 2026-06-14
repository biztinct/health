/** @odoo-module **/
/**
 * Unified Staff Schedule — engine A.
 * Extends the OCA web_timeline with:
 *   - ALL active staff as rows (not only those with assignments),
 *   - availability background shading (off-hours + leave) from the
 *     health.staff.assignment.get_schedule_overlay() API,
 *   - per-row capacity + status in the row label.
 * Drag constraints (validate_drop) and the unassigned side rail are layered on
 * top in the controller / template extensions.
 */
import {TimelineRenderer} from "@web_timeline/views/timeline/timeline_renderer.esm";
import {TimelineController} from "@web_timeline/views/timeline/timeline_controller.esm";
import {TimelineView} from "@web_timeline/views/timeline/timeline_view.esm";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {registry} from "@web/core/registry";
import {session} from "@web/session";
import {useService} from "@web/core/utils/hooks";
import {onWillStart, markup} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";

const {DateTime} = luxon;

/** Assignment-state palette — mirrors the <timeline colors="..."> in the view,
 *  reused for the legend so colours never drift between card and legend. */
const STATE_LEGEND = [
    {key: "assigned", label: _t("Assigned"), color: "#2563eb"},
    {key: "confirmed", label: _t("Confirmed"), color: "#0ea5e9"},
    {key: "in_progress", label: _t("In progress"), color: "#16a34a"},
    {key: "completed", label: _t("Completed"), color: "#14b8a6"},
    {key: "deferred", label: _t("Deferred"), color: "#f59e0b"},
    {key: "cancelled", label: _t("Cancelled"), color: "#ef4444"},
];

/** The Staff Schedule renders in the operator's FACILITY timezone (resolved
 *  server-side in session_info), NEVER the browser / physical-location tz.
 *
 *  Basis: every date handed to vis is a REAL UTC instant (foreground cards come
 *  from stored-UTC; overlay backgrounds are emitted in UTC by the backend). vis is
 *  configured (see init_timeline `moment`) to RENDER those instants at the facility
 *  offset, so the axis, the shading and the cards all read in facility time and
 *  stay mutually aligned on any browser. */
const DEFAULT_TZ = session.schedule_tz || "Asia/Ho_Chi_Minh";

/** A vis JS Date (real UTC instant) → real-UTC wall-clock string. The timeline
 *  items live on the real-UTC basis; validate_drop interprets these as UTC. */
function toUtcStr(d) {
    return DateTime.fromJSDate(d, {zone: "utc"}).toFormat("yyyy-MM-dd HH:mm:ss");
}

export class StaffScheduleRenderer extends TimelineRenderer {
    setup() {
        super.setup();
        this._facilityId = false;
        this.scheduleTz = DEFAULT_TZ;
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        // Bootstrap the facility-filter options + default facility before first paint.
        onWillStart(async () => {
            await this._loadMeta();
        });
    }

    async _loadMeta() {
        try {
            this._meta = await this.orm.call(
                "health.staff.assignment",
                "get_schedule_meta",
                []
            );
        } catch {
            this._meta = {tz: DEFAULT_TZ, facilities: [], default_facility_id: false};
        }
        this._facilityId = this._meta.default_facility_id || false;
        this.scheduleTz = this._facilityTz(this._facilityId);
    }

    /** The active grid timezone — the selected facility's tz, or the operator's
     *  facility tz when "All facilities" is shown. */
    _facilityTz(facId) {
        if (facId && this._meta) {
            const f = (this._meta.facilities || []).find((x) => x.id === facId);
            if (f && f.tz) {
                return f.tz;
            }
        }
        return (this._meta && this._meta.tz) || DEFAULT_TZ;
    }

    /** Active facility offset in minutes (read live so a facility switch re-renders
     *  the axis without rebuilding the timeline). */
    _tzOffsetMin() {
        return DateTime.now().setZone(this.scheduleTz).offset;
    }

    /** A vis JS Date → facility wall-clock string (for the overlay window API). */
    _winStr(d) {
        return DateTime.fromJSDate(d, {zone: "utc"})
            .setZone(this.scheduleTz)
            .toFormat("yyyy-MM-dd HH:mm:ss");
    }

    /** Reload foreground records + overlay (after assigning a booking). */
    async _reloadAll() {
        const sm = this.env.searchModel;
        await this.model.load({
            domain: sm.domain,
            context: sm.context,
            groupBy: sm.groupBy,
        });
        this._lastWinKey = null;
        await this.on_data_loaded(this.model.data);
    }

    /** Overlay datetimes are REAL UTC (backend emits UTC), same basis as the
     *  foreground cards → a plain UTC parse keeps shading and cards aligned. */
    _sqlToDate(sql) {
        return DateTime.fromSQL(sql, {zone: "utc"}).toJSDate();
    }
    /** The visible window, as facility wall-clock strings for the overlay API. */
    _windowAsLocal() {
        const win = this.timeline.getWindow();
        return [this._winStr(win.start), this._winStr(win.end)];
    }

    /** Fetch overlay for the current window + facility. Returns true if it
     *  actually fetched, false if the (window, facility) was unchanged — lets
     *  callers skip redundant DOM work (kills the Week-view shading flash). */
    async _loadOverlay() {
        if (!this.timeline) {
            return false;
        }
        const [start, end] = this._windowAsLocal();
        const key = `${start}|${end}|${this._facilityId || ""}`;
        if (key === this._lastWinKey && this._overlay) {
            return false;
        }
        this._lastWinKey = key;
        try {
            this._overlay = await this.orm.call(
                "health.staff.assignment",
                "get_schedule_overlay",
                [start, end, null, this._facilityId || false]
            );
        } catch {
            this._overlay = {rows: [], backgrounds: [], unassigned: []};
        }
        return true;
    }

    _backgroundItems() {
        return (this._overlay?.backgrounds || []).map((bg) => ({
            id: `bg_${bg.staff_id}_${bg.start}_${bg.kind}`,
            group: bg.staff_id,
            start: this._sqlToDate(bg.start),
            end: this._sqlToDate(bg.end),
            type: "background",
            className: `hf-av hf-av--${bg.kind}`,
        }));
    }

    /** Open on the working day (06:00–20:00 facility time) as REAL UTC instants. */
    _computeMode() {
        if (this.mode.data === "day") {
            // keep the [data-timeline-mode] hook in sync (the enhancer sets it in its
            // own _computeMode, which we bypass here for the day window).
            if (this._setTimelineModeAttr) {
                this._setTimelineModeAttr("day");
            }
            const base = DateTime.now().setZone(this.scheduleTz).startOf("day");
            this.options.start = base.plus({hours: 6}).toJSDate();
            this.options.end = base.plus({hours: 20}).toJSDate();
            return;
        }
        super._computeMode();
    }

    init_timeline() {
        // Render the axis (and position items) in the FACILITY timezone, not the
        // browser's — so cards, shading and labels read in facility time everywhere.
        // Reads this.scheduleTz live → a facility switch + redraw re-renders the axis.
        this.options.moment = (date) =>
            window.vis.moment(date).utcOffset(this._tzOffsetMin());
        // Wheel = vertical scroll (only zoom while Ctrl is held). Without this, vis
        // swallows the wheel for zoom in Day view, so the page can't scroll the rows.
        this.options.zoomKey = "ctrlKey";
        super.init_timeline();
        // enforce the daytime window (a global zoom enhancer may override it)
        if (this.mode.data === "day" && this.options.start && this.options.end) {
            this.timeline.setWindow(this.options.start, this.options.end, {animation: false});
        }
        // Drag an Unassigned booking from the rail onto a staff row → assign it.
        // vis' own 'drop' only fires for JSON-with-content payloads (and would then
        // trigger its create-item dialog), so we wire native listeners on the center
        // panel and use a non-JSON payload ("fso:<id>") that makes vis' handler bail
        // out early — leaving our listener to do the assignment.
        const center = this.timeline.dom && this.timeline.dom.center;
        if (center) {
            center.addEventListener("dragover", (e) => {
                e.preventDefault();
                if (e.dataTransfer) {
                    e.dataTransfer.dropEffect = "copy";
                }
            });
            center.addEventListener("drop", (e) => this._onRailDrop(e));
        }
        // Live drag feedback: flag drops over off-hours / leave zones in red
        // (client-side, from the cached overlay). The authoritative block +
        // double-booking confirm happens on drop in the controller's _onMove.
        // `snap` rounds drag/resize to the active day scale (15 / 30 / 60 min) so
        // start/end land on clean grid times (no 08:59 / 09:13).
        this.timeline.setOptions({
            onMoving: this._onMoving.bind(this),
            snap: (date) => this._snapToScale(date),
        });
        // Facility pills + legend (toolbar) and the unassigned side rail.
        this._mountFacilityPills();
        this._mountLegend();
        this._mountRail();
        // Re-fetch availability + side-rail whenever the visible window changes
        // (scroll, zoom, or the Day/Week/Month scale buttons).
        this.timeline.on("rangechanged", () => {
            clearTimeout(this._ovTimer);
            this._ovTimer = setTimeout(() => this._refreshOverlay(), 250);
        });
    }

    async _refreshOverlay() {
        const changed = await this._loadOverlay();
        if (!changed) {
            // window + facility unchanged — nothing to redraw (no flash).
            return;
        }
        // swap background items in place
        const items = this.timeline.itemsData;
        const old = items.get({filter: (it) => it.type === "background"}).map((it) => it.id);
        if (old.length) {
            items.remove(old);
        }
        items.add(this._backgroundItems());
        // rebuild rows (status/capacity can change with the window)
        const groups = await this.split_groups([]);
        this.timeline.setGroups(groups);
        this._renderRail();
        if (this.props.onOverlay) {
            this.props.onOverlay(this._overlay);
        }
    }

    // ---- Facility filter (toolbar pills) ------------------------------------
    /** Segmented facility pills in the toolbar (matching the scale/zoom pills),
     *  defaulting to the operator's own facility. Filters rows + assignment cards. */
    _mountFacilityPills() {
        const bar = this.rootRef.el?.querySelector(".oe_timeline_buttons");
        if (!bar || this._facWrap || !this._meta) {
            return;
        }
        const facs = this._meta.facilities || [];
        const pill = (id, name) =>
            `<button class="hf-fac-pill${
                (id || false) === (this._facilityId || false) ? " is-active" : ""
            }" data-fac="${id || ""}">${this._escape(name)}</button>`;
        const wrap = document.createElement("div");
        wrap.className = "hf-fac-pills oe_timeline_facpills";
        wrap.innerHTML =
            `<span class="hf-wt-ico hf-ico-building hf-fac-ico"></span>` +
            pill("", _t("All")) +
            facs.map((f) => pill(f.id, f.name)).join("");
        bar.appendChild(wrap);
        this._facWrap = wrap;
        wrap.addEventListener("click", (ev) => {
            const btn = ev.target.closest(".hf-fac-pill");
            if (!btn) {
                return;
            }
            wrap.querySelectorAll(".hf-fac-pill").forEach((b) =>
                b.classList.toggle("is-active", b === btn)
            );
            this._onFacilityChange(btn.dataset.fac ? Number(btn.dataset.fac) : false);
        });
    }

    async _onFacilityChange(facId) {
        this._facilityId = facId || false;
        this.scheduleTz = this._facilityTz(this._facilityId);
        this._lastWinKey = null; // force an overlay refetch for the new facility
        if (this.timeline) {
            this.timeline.redraw(); // re-render the axis in the new facility tz
        }
        await this.on_data_loaded(this.model.data);
    }

    // ---- Drag an Unassigned booking onto a staff row → assign ---------------
    async _onRailDrop(ev) {
        const data =
            (ev.dataTransfer &&
                (ev.dataTransfer.getData("text/plain") || ev.dataTransfer.getData("text"))) ||
            "";
        if (data.indexOf("fso:") !== 0) {
            return; // not one of our rail cards
        }
        ev.preventDefault();
        ev.stopPropagation();
        const fsoId = Number(data.slice(4));
        const props = this.timeline.getEventProperties(ev);
        const staffId = props && props.group;
        if (!fsoId) {
            return;
        }
        if (!staffId || staffId === -1) {
            this.notification.add(_t("Drop the booking on a staff member's row."), {
                type: "warning",
            });
            return;
        }
        const u = (this._overlay?.unassigned || []).find((x) => x.fso_id === fsoId);
        if (!u || !u.start_utc) {
            return;
        }
        // Keep the booking's own time — validate the staff is free at that UTC slot.
        const startUtc = u.start_utc;
        const endUtc = DateTime.fromSQL(startUtc, {zone: "utc"})
            .plus({minutes: u.duration_min || 60})
            .toFormat("yyyy-MM-dd HH:mm:ss");
        let res;
        try {
            res = await this.orm.call("health.staff.assignment", "validate_drop", [
                staffId,
                startUtc,
                endUtc,
                null,
            ]);
        } catch {
            res = {ok: true};
        }
        if (res.hard_block) {
            this.notification.add(res.message || _t("Staff is not available in that slot."), {
                type: "danger",
                title: _t("Unavailable"),
            });
            return;
        }
        if (res.overlap) {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Double-booking"),
                body: res.message || _t("This overlaps another assignment. Continue?"),
                confirmLabel: _t("Assign anyway"),
                cancelLabel: _t("Cancel"),
                confirm: () => this._assignBooking(fsoId, staffId),
            });
            return;
        }
        await this._assignBooking(fsoId, staffId);
    }

    async _assignBooking(fsoId, staffId) {
        let r;
        try {
            r = await this.orm.call("health.staff.assignment", "assign_booking", [
                fsoId,
                staffId,
            ]);
        } catch {
            r = {ok: false};
        }
        if (!r.ok) {
            this.notification.add(r.message || _t("Could not assign this booking."), {
                type: "warning",
            });
            return;
        }
        this.notification.add(_t("Booking assigned."), {type: "success"});
        await this._reloadAll();
    }

    // ---- Legend (shading + assignment-state colours) ------------------------
    _mountLegend() {
        const bar = this.rootRef.el?.querySelector(".oe_timeline_buttons");
        if (!bar || this._legendEl) {
            return;
        }
        const swatch = (cls, label) =>
            `<span class="hf-lg-item"><span class="hf-lg-sw ${cls}"></span>${label}</span>`;
        const dot = (color, label) =>
            `<span class="hf-lg-item"><span class="hf-lg-dot" style="background:${color}"></span>${label}</span>`;
        const el = document.createElement("div");
        el.className = "hf-legend";
        el.innerHTML =
            swatch("hf-lg-work", _t("Working hours")) +
            swatch("hf-lg-off", _t("Off-hours")) +
            swatch("hf-lg-leave", _t("Leave / time off")) +
            `<span class="hf-lg-sep"></span>` +
            STATE_LEGEND.map((s) => dot(s.color, s.label)).join("");
        bar.appendChild(el);
        this._legendEl = el;
    }

    // ---- Unassigned-bookings side rail --------------------------------------
    _escape(s) {
        return String(s == null ? "" : s).replace(
            /[&<>"']/g,
            (c) =>
                ({
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#39;",
                }[c])
        );
    }

    /** Wrap the vis canvas + a rail aside in a flex body (once). */
    _mountRail() {
        if (this._railEl) {
            return;
        }
        const canvas = this.canvasRef.el;
        if (!canvas || !canvas.parentNode) {
            return;
        }
        const body = document.createElement("div");
        body.className = "hf-tl-body";
        canvas.parentNode.insertBefore(body, canvas);
        body.appendChild(canvas);
        this._railEl = document.createElement("aside");
        this._railEl.className = "hf-rail";
        body.appendChild(this._railEl);
        this._railEl.addEventListener("click", (ev) => {
            const card = ev.target.closest("[data-fso-id]");
            if (card) {
                this._openBooking(Number(card.dataset.fsoId));
            }
        });
        this._railEl.addEventListener("dragstart", (ev) => {
            const card = ev.target.closest("[data-fso-id]");
            if (card) {
                // Non-JSON payload so vis' own drop handler bails (see init_timeline).
                ev.dataTransfer.setData("text/plain", "fso:" + card.dataset.fsoId);
                ev.dataTransfer.effectAllowed = "copy";
                card.classList.add("hf-rail-card--dragging");
            }
        });
        this._railEl.addEventListener("dragend", (ev) => {
            const card = ev.target.closest("[data-fso-id]");
            if (card) {
                card.classList.remove("hf-rail-card--dragging");
            }
        });
        // vis measured the canvas at full width; remeasure now it's narrower.
        this.timeline.redraw();
        this._renderRail();
    }

    _openBooking(fsoId) {
        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.fieldservice.order",
            res_id: fsoId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    _renderRail() {
        if (!this._railEl) {
            return;
        }
        const items = this._overlay?.unassigned || [];
        const fmtWhen = (iso) =>
            iso
                ? DateTime.fromSQL(iso).toFormat("ccc d LLL · HH:mm")
                : _t("Unscheduled");
        const cards = items
            .map((u) => {
                const dur = u.duration_min
                    ? `${Math.round((u.duration_min / 60) * 10) / 10}h`
                    : "";
                return (
                    `<div class="hf-rail-card" data-fso-id="${u.fso_id}" draggable="true" title="${this._escape(
                        u.patient_name
                    )}">` +
                    `<div class="hf-rail-card-top">` +
                    `<span class="hf-rail-card-name">${this._escape(u.patient_name || _t("Booking"))}</span>` +
                    (dur ? `<span class="hf-rail-card-dur">${dur}</span>` : "") +
                    `</div>` +
                    (u.service_label
                        ? `<div class="hf-rail-card-svc">${this._escape(u.service_label)}</div>`
                        : "") +
                    `<div class="hf-rail-card-when">${this._escape(fmtWhen(u.start_iso))}</div>` +
                    (u.facility
                        ? `<div class="hf-rail-card-fac">${this._escape(u.facility)}</div>`
                        : "") +
                    `</div>`
                );
            })
            .join("");
        this._railEl.innerHTML =
            `<div class="hf-rail-head">` +
            `<span class="hf-rail-title">${_t("Unassigned")}</span>` +
            `<span class="hf-rail-count">${items.length}</span>` +
            `</div>` +
            (items.length
                ? `<div class="hf-rail-list">${cards}</div>`
                : `<div class="hf-rail-empty">${_t("No unassigned bookings in view.")}</div>`);
    }

    async on_data_loaded(records, adjust_window) {
        await this._loadOverlay();
        // When a facility is selected, only show cards for that facility's staff
        // (the overlay rows are the allowed set).
        const allowed = new Set((this._overlay?.rows || []).map((r) => r.id));
        const data = [];
        for (const record of records) {
            if (!record[this.date_start]) {
                continue;
            }
            const item = this.model._event_data_transform(record);
            if (this._facilityId && !allowed.has(item.group)) {
                continue;
            }
            data.push(item);
        }
        data.push(...this._backgroundItems());
        const groups = await this.split_groups(records);
        this.timeline.setGroups(groups);
        this.timeline.setItems(data);
        const fitMode = !this.mode.data || this.mode.data === "fit";
        const adjust = typeof adjust_window === "undefined" || adjust_window;
        if (fitMode && adjust) {
            this.timeline.fit();
        }
        this._renderRail();
        if (this.props.onOverlay) {
            this.props.onOverlay(this._overlay);
        }
    }

    async split_groups(records) {
        const rows = this._overlay?.rows || [];
        if (!rows.length) {
            return super.split_groups(records);
        }
        const groups = [
            {
                id: -1,
                content:
                    `<div class="hf-tl-label hf-tl-label--unassigned">` +
                    `<div class="hf-tl-avatar hf-tl-avatar--unassigned">?</div>` +
                    `<div class="hf-tl-meta"><div class="hf-tl-name">${_t("UNASSIGNED")}</div></div>` +
                    `</div>`,
                order: -1,
            },
        ];
        let seq = 1;
        for (const r of rows) {
            groups.push({id: r.id, content: this._buildRowLabel(r), order: seq++});
        }
        return groups;
    }

    _buildRowLabel(r) {
        const cap = r.cap ? `${r.used}/${r.cap}` : `${r.used}`;
        const util = Math.min(Math.max(r.util_pct || 0, 0), 100);
        const st =
            r.status === "available"
                ? "av"
                : r.status === "on_leave"
                ? "leave"
                : r.status === "busy" || r.status === "full"
                ? "busy"
                : "off";
        // The status pill is a single-day concept (computed for the window's
        // first day) — only meaningful in Day view. In Week/Month it would read
        // a misleading uniform "Off-Hours", so we drop it there; the capacity
        // bar already conveys the window-cumulative load.
        const pill =
            this.mode.data === "day"
                ? `<span class="hf-tl-st hf-tl-st--${st}">${r.status_label || ""}</span>`
                : "";
        return (
            `<div class="hf-tl-label">` +
            `<div class="hf-tl-avatar hf-hue-${(r.color || 0) % 10}">${r.initials || "?"}</div>` +
            `<div class="hf-tl-meta">` +
            `<div class="hf-tl-name">${r.name}</div>` +
            (r.facility ? `<div class="hf-tl-sub">${r.facility}</div>` : "") +
            `<div class="hf-tl-cap">` +
            `<div class="hf-tl-cap-bar"><div class="hf-tl-cap-fill" style="width:${util}%"></div></div>` +
            `<span class="hf-tl-cap-txt">${cap}</span>` +
            `</div>` +
            `</div>` +
            pill +
            `</div>`
        );
    }

    /** True if [start, end) overlaps an off-hours / leave background for this
     *  staff row (uses the cached overlay; same wall-clock-as-UTC basis as items). */
    _isUnavailable(groupId, start, end) {
        if (groupId === -1) {
            return true;
        }
        const bgs = (this._overlay?.backgrounds || []).filter(
            (b) => b.staff_id === groupId
        );
        const s = start.getTime();
        const e = (end || start).getTime();
        return bgs.some((b) => {
            const bs = this._sqlToDate(b.start).getTime();
            const be = this._sqlToDate(b.end).getTime();
            return s < be && e > bs;
        });
    }

    /** vis onMoving — show the card as a dashed "preview" while dragging, and tint
     *  it red over an off-hours / leave zone (for the dragged staff). */
    _onMoving(item, callback) {
        const bad = this._isUnavailable(item.group, item.start, item.end);
        const cls = (item.className || "")
            .replace(/\s*hf-drag--bad/g, "")
            .replace(/\s*hf-dragging/g, "");
        item.className = `${cls} hf-dragging${bad ? " hf-drag--bad" : ""}`;
        callback(item);
    }

    /** Snap a dragged/resized time to the active day scale (15 / 30 / 60 min),
     *  rounded in facility-local time so the grid lines up with the axis. */
    _snapToScale(date) {
        const step =
            {"15min": 15, "30min": 30, "1hr": 60}[
                this.dayScale && this.dayScale.value
            ] || 30;
        const dt = DateTime.fromJSDate(date).setZone(this.scheduleTz);
        const mins = dt.hour * 60 + dt.minute + dt.second / 60;
        const snapped = Math.round(mins / step) * step;
        return dt.startOf("day").plus({minutes: snapped}).toJSDate();
    }

    /** Allow the markup our row labels use through vis' XSS filter. */
    getXSSWhiteList() {
        const wl = super.getXSSWhiteList();
        wl.div = ["class", "style"];
        wl.span = ["class", "style", "name"];
        wl.i = ["class", "style"];
        return wl;
    }
}

export class StaffScheduleController extends TimelineController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    _timelineMode() {
        const el =
            (this.rootRef.el && this.rootRef.el.closest(".o_timeline_view")) ||
            document.querySelector(".o_timeline_view");
        return (el && el.dataset.timelineMode) || "day";
    }

    async _reloadTimeline() {
        await this.model.load(this.getSearchProps());
        this.render();
    }

    /**
     * Drag/resize an assignment. Validates the change on the server
     * (validate_timeline_change), then confirms before applying:
     *   - hard_block (off-hours / leave / another assigned staff conflicts /
     *     already in progress)  → snap back + toast
     *   - reschedule (time/date) → confirm; Week/Month notes the time is unchanged;
     *     multi-staff bookings list the other staff who move + get notified
     *   - reassignment (staff change) → confirm; new + removed staff are notified
     * Persisted via apply_timeline_change (writes the FSO, which cascades to every
     * assignment) — NOT the base move, which the model would force back to the FSO.
     * @override
     */
    async _onMove(item, callback) {
        const staffId = item.group && item.group !== -1 ? item.group : false;
        if (!staffId) {
            this.notification.add(_t("Drop the assignment on a staff member's row."), {
                type: "warning",
            });
            callback(null);
            return;
        }
        const mode = this._timelineMode();
        const id = Number(item.id) || item.id;
        const startIso = toUtcStr(item.start);
        const endIso = item.end ? toUtcStr(item.end) : startIso;
        let res;
        try {
            res = await this.orm.call("health.staff.assignment", "validate_timeline_change", [
                id,
                startIso,
                endIso,
                staffId,
                mode,
            ]);
        } catch {
            res = {ok: false, hard_block: true, message: _t("Could not validate the change.")};
        }
        if (res.hard_block) {
            this.notification.add(res.message || _t("That change isn't allowed."), {
                type: "danger",
                title: _t("Blocked"),
            });
            callback(null);
            return;
        }
        if (!res.time_changed && !res.staff_changed) {
            callback(item); // dropped back where it was — nothing to do
            return;
        }
        const apply = async () => {
            callback(item);
            try {
                await this.orm.call("health.staff.assignment", "apply_timeline_change", [
                    id,
                    startIso,
                    endIso,
                    staffId,
                    mode,
                ]);
            } catch {
                this.notification.add(_t("Could not save the change."), {type: "warning"});
            }
            await this._reloadTimeline();
        };
        const {title, body, confirmLabel} = this._changeConfirm(res, mode);
        this.dialogService.add(ConfirmationDialog, {
            title,
            body,
            confirmLabel,
            cancelLabel: _t("Cancel"),
            confirm: apply,
            cancel: () => callback(null),
        });
    }

    /** Build the "smashing" confirm-dialog copy for a validated change. */
    _changeConfirm(res, mode) {
        const esc = (s) =>
            String(s == null ? "" : s).replace(
                /[&<>"']/g,
                (c) =>
                    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])
            );
        const who = esc(res.patient_name || _t("this booking"));
        const rows = [];
        const headline =
            res.staff_changed && res.time_changed
                ? `${_t("Move")} <b>${who}</b> → <b>${esc(res.new_staff_name)}</b> ${_t("and reschedule")}`
                : res.staff_changed
                ? `${_t("Reassign")} <b>${who}</b> → <b>${esc(res.new_staff_name)}</b>`
                : mode === "day"
                ? `${_t("Reschedule")} <b>${who}</b> ${_t("to")} <b>${esc(res.new_time_label)}</b>`
                : `${_t("Reschedule")} <b>${who}</b> ${_t("to")} <b>${esc(res.new_date_label)}</b>`;
        rows.push(`<div class="hf-resched-head">${headline}</div>`);
        const notes = [];
        if (res.time_changed && mode !== "day") {
            notes.push(
                `${_t("Time stays")} <b>${esc(res.new_time_label)}</b> — ${_t(
                    "switch to Day view (or open the card) to change the time."
                )}`
            );
        }
        if (res.time_changed && res.multi) {
            notes.push(
                `${_t("Also moves")} ${res.co_staff_names.length} ${_t("other staff:")} ` +
                    `<b>${esc(res.co_staff_names.join(", "))}</b>. ${_t("All assigned staff will be notified.")}`
            );
        } else if (res.time_changed) {
            notes.push(_t("Assigned staff will be notified."));
        }
        if (res.staff_changed) {
            notes.push(
                `<b>${esc(res.old_staff_name)}</b> ${_t("will be notified of the cancellation")}; ` +
                    `<b>${esc(res.new_staff_name)}</b> ${_t("of the new assignment.")}`
            );
        }
        for (const n of notes) {
            rows.push(`<div class="hf-resched-note">${n}</div>`);
        }
        return {
            title: _t("Confirm change"),
            body: markup(`<div class="hf-resched">${rows.join("")}</div>`),
            confirmLabel: _t("Confirm"),
        };
    }
}

export const StaffScheduleTimelineView = {
    ...TimelineView,
    Renderer: StaffScheduleRenderer,
    Controller: StaffScheduleController,
};

registry.category("views").add("staff_schedule_timeline", StaffScheduleTimelineView);
