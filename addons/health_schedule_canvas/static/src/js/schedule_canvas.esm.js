/** @odoo-module **/
/**
 * Schedule canvas — draw-to-create + off-hours compression + month overlay
 * thinning, layered on the unified Staff Schedule (js_class
 * staff_schedule_timeline) by PATCHING its controller and renderer (no addon-file
 * edit; composes with health_schedule_drag's _onMove patch).
 *
 *  - Controller._onAdd  → double-click a staff lane opens the quick-booking dialog
 *    pre-filled with that staff + snapped time (§2.1).
 *  - Renderer           → vis hiddenDates collapse empty night/weekend columns in
 *    Day/Week (toggle-able, default hidden; windows containing a booking stay
 *    visible), and the month overlay is fetched thinned (§2.2, §2.3b).
 *
 * Everything visual is defensive: any failure clears the effect and falls back to
 * the shipped behaviour rather than breaking the live schedule.
 */
import {patch} from "@web/core/utils/patch";
import {
    StaffScheduleController,
    StaffScheduleRenderer,
} from "@health_fieldservice/js/staff_schedule_timeline.esm";
import {ScheduleQuickCreateDialog} from "@health_schedule_canvas/js/quick_create_dialog.esm";
import {_t} from "@web/core/l10n/translation";

const {DateTime} = luxon;

/** vis JS Date (real-UTC instant) → real-UTC wall-clock string (the server reads
 *  these as UTC; schedule_canvas_prefill converts to facility-local). */
function toUtcStr(d) {
    return DateTime.fromJSDate(d, {zone: "utc"}).toFormat("yyyy-MM-dd HH:mm:ss");
}

/** Snap a click to the nearest 15 minutes (15-min boundaries coincide in UTC and
 *  in whole-hour-offset facility zones, so snapping the UTC instant is safe). */
function snap15(d) {
    const step = 15 * 60 * 1000;
    return new Date(Math.round(d.getTime() / step) * step);
}

// ---------------------------------------------------------------------------
// §2.1 Draw-to-create
// ---------------------------------------------------------------------------
patch(StaffScheduleController.prototype, {
    async _onAdd(item, callback) {
        // Never keep the tentative vis item — the real block arrives via reload.
        callback(null);
        const groupId = item.group;
        if (!groupId || groupId === -1) {
            return; // unassigned rail / no staff row
        }
        const mode = this._timelineMode();
        if (mode === "month") {
            this.notification.add(
                _t("Switch to Day or Week view to create a booking."),
                {type: "info"}
            );
            return;
        }
        const startIso = toUtcStr(snap15(item.start));
        let res;
        try {
            res = await this.orm.call(
                "health.staff.assignment",
                "schedule_canvas_prefill",
                [groupId, startIso]
            );
        } catch {
            res = null;
        }
        if (!res || !res.ok) {
            this.notification.add(
                (res && res.message) || _t("Could not open the booking form."),
                {type: "warning"}
            );
            return;
        }
        if (!res.can_create) {
            this.notification.add(
                _t(
                    "Only operations staff can create bookings here — ask an operations manager or head nurse."
                ),
                {type: "warning"}
            );
            return;
        }
        this.dialogService.add(ScheduleQuickCreateDialog, {
            staffId: res.staff_id,
            staffName: res.staff_name,
            facilityId: res.facility_id,
            facilityName: res.facility_name,
            date: res.date,
            timeHour: res.time_hour,
            dateLabel: res.date_label,
            timeLabel: res.time_label,
            warning: res.warning || "",
            onCreated: async (result) => {
                this.notification.add(
                    _t("Booking created — %s.", result.date_display || res.time_label || ""),
                    {type: "success"}
                );
                await this._reloadTimeline();
            },
        });
    },
});

// ---------------------------------------------------------------------------
// §2.2 Off-hours compression + §2.3(b,c) overlay thinning / clustering
// ---------------------------------------------------------------------------
const OFFHOURS_KEY = "vu_sched_offhours"; // 'hidden' (default) | 'shown'
// Month clustering (§2.3c) is OFF by default — windowed fetch (§2.3a) + overlay
// thinning (§2.3b) are expected to hit the Month target on their own, and
// clusters don't compose cleanly with the custom background items / drag gate.
// Flip to true only if measurement shows Month is still over budget.
const ENABLE_MONTH_CLUSTER = false;
// vis-timeline renders/lay-out of background items is super-linear — a Week with
// ~900 'off' segments froze the main thread ~18 s (measured on vietuat). Beyond
// this many 'off' backgrounds we drop them entirely (keep 'leave'); off-hours
// shading is decorative and the hidden-mode synergy already removes most.
const OFF_BG_CAP = 300;

function offHoursHidden() {
    try {
        return localStorage.getItem(OFFHOURS_KEY) !== "shown";
    } catch {
        return true;
    }
}

/** Merge a list of {s,e} ms intervals (sorted, coalesced). */
function mergeIntervals(list) {
    if (!list.length) {
        return [];
    }
    const sorted = list.slice().sort((a, b) => a.s - b.s);
    const out = [sorted[0]];
    for (let i = 1; i < sorted.length; i++) {
        const last = out[out.length - 1];
        if (sorted[i].s <= last.e) {
            last.e = Math.max(last.e, sorted[i].e);
        } else {
            out.push({s: sorted[i].s, e: sorted[i].e});
        }
    }
    return out;
}

/** Intersection of two sorted, merged interval lists. */
function intersectIntervals(a, b) {
    const out = [];
    let i = 0;
    let j = 0;
    while (i < a.length && j < b.length) {
        const s = Math.max(a[i].s, b[j].s);
        const e = Math.min(a[i].e, b[j].e);
        if (s < e) {
            out.push({s, e});
        }
        if (a[i].e < b[j].e) {
            i++;
        } else {
            j++;
        }
    }
    return out;
}

patch(StaffScheduleRenderer.prototype, {
    init_timeline() {
        super.init_timeline();
        try {
            this._mountOffHoursToggle();
        } catch {
            // toolbar not ready / non-fatal
        }
    },

    /** Fetch the overlay thinned at month scale (drops 'off' backgrounds server
     *  side — §2.3b). Mirrors the shipped _loadOverlay but adds the granularity
     *  arg and folds it into the cache key. */
    async _loadOverlay() {
        if (!this.timeline) {
            return false;
        }
        const [start, end] = this._windowAsLocal();
        const gran = this.mode.data === "month" ? "month" : null;
        const key = `${start}|${end}|${this._facilityId || ""}|${gran || ""}`;
        if (key === this._lastWinKey && this._overlay) {
            return false;
        }
        this._lastWinKey = key;
        try {
            this._overlay = await this.orm.call(
                "health.staff.assignment",
                "get_schedule_overlay",
                [start, end, null, this._facilityId || false, gran]
            );
        } catch {
            this._overlay = {rows: [], backgrounds: [], unassigned: []};
        }
        return true;
    },

    async on_data_loaded(records, adjust_window) {
        await super.on_data_loaded(records, adjust_window);
        try {
            this._applyCanvasView();
        } catch {
            // never break the paint on a compression hiccup
        }
    },

    async _refreshOverlay() {
        await super._refreshOverlay();
        try {
            this._applyCanvasView();
        } catch {
            // non-fatal
        }
    },

    /** Background items for vis — with the §2.2 synergy + a hard safety cap so a
     *  dense Week/Month never freezes the main thread. Overrides the shipped
     *  builder (kept byte-compatible: same id/className) but:
     *   - always keeps 'leave' segments;
     *   - in hidden mode, drops 'off' segments that fall inside a hidden column
     *     (they are invisible anyway — the synergy the handover asked for);
     *   - if 'off' still exceeds OFF_BG_CAP (e.g. off-hours SHOWN on a busy Week,
     *     or staff calendars don't intersect), drops 'off' entirely. */
    _backgroundItems() {
        const bgs = (this._overlay && this._overlay.backgrounds) || [];
        const isMonth = this.mode.data === "month";
        const hidden = !isMonth && offHoursHidden() ? this._hiddenRanges() : [];
        const leaves = [];
        const offs = [];
        for (const bg of bgs) {
            const s = this._sqlToDate(bg.start);
            const e = this._sqlToDate(bg.end);
            const item = {
                id: `bg_${bg.staff_id}_${bg.start}_${bg.kind}`,
                group: bg.staff_id,
                start: s,
                end: e,
                type: "background",
                className: `hf-av hf-av--${bg.kind}`,
            };
            if (bg.kind === "leave") {
                leaves.push(item);
                continue;
            }
            const st = s.getTime();
            const et = e.getTime();
            const insideHidden = hidden.some(
                (h) => h.start.getTime() <= st && et <= h.end.getTime()
            );
            if (!insideHidden) {
                offs.push(item);
            }
        }
        if (offs.length > OFF_BG_CAP) {
            return leaves; // protect the main thread — shading is decorative
        }
        return leaves.concat(offs);
    },

    /** Cached hidden ranges for the current window (recomputed per overlay key). */
    _hiddenRanges() {
        if (this._hiddenCacheKey === this._lastWinKey && this._hiddenCache) {
            return this._hiddenCache;
        }
        this._hiddenCache = this._computeHiddenDates();
        this._hiddenCacheKey = this._lastWinKey;
        return this._hiddenCache;
    },

    /** Apply hiddenDates (day/week, toggle-honoring) + optional month cluster. */
    _applyCanvasView() {
        if (!this.timeline) {
            return;
        }
        const isMonth = this.mode.data === "month";
        let hidden = [];
        if (!isMonth && offHoursHidden()) {
            hidden = this._hiddenRanges();
        }
        try {
            this.timeline.setOptions({hiddenDates: hidden});
        } catch {
            // some vis builds reject an empty array — clear via redraw instead
        }
        if (ENABLE_MONTH_CLUSTER) {
            try {
                this.timeline.setOptions({
                    cluster: isMonth ? {maxItems: 3, fitOnDoubleClick: true} : false,
                });
            } catch {
                // clustering unsupported — ignore
            }
        }
    },

    /** Concrete hidden ranges: time columns that are 'off' for EVERY loaded staff
     *  row and contain NO loaded booking (exemption). Operates purely on the
     *  overlay/item JS-Date basis — no independent tz math (avoids the +7h bug). */
    _computeHiddenDates() {
        const rows = (this._overlay && this._overlay.rows) || [];
        const bgs = (this._overlay && this._overlay.backgrounds) || [];
        if (!rows.length || !bgs.length) {
            return [];
        }
        const staffIds = rows.map((r) => r.id);
        const byStaff = new Map();
        for (const id of staffIds) {
            byStaff.set(id, []);
        }
        for (const b of bgs) {
            if (b.kind !== "off" || !byStaff.has(b.staff_id)) {
                continue;
            }
            const s = this._sqlToDate(b.start).getTime();
            const e = this._sqlToDate(b.end).getTime();
            if (e > s) {
                byStaff.get(b.staff_id).push({s, e});
            }
        }
        // Intersect off-intervals across all staff → the globally-off columns.
        let intersection = null;
        for (const id of staffIds) {
            const segs = mergeIntervals(byStaff.get(id) || []);
            if (!segs.length) {
                return []; // a staff with no 'off' here → nothing globally hidden
            }
            intersection =
                intersection === null ? segs : intersectIntervals(intersection, segs);
            if (!intersection.length) {
                return [];
            }
        }
        if (!intersection || !intersection.length) {
            return [];
        }
        // Exemption: drop any globally-off interval a loaded booking intersects.
        const items = this._loadedItemSpans();
        const result = [];
        for (const iv of intersection) {
            const covered = items.some((it) => it.s < iv.e && it.e > iv.s);
            if (!covered) {
                result.push({start: new Date(iv.s), end: new Date(iv.e)});
            }
        }
        return result;
    },

    /** Foreground (non-background) item spans currently in the vis dataset. */
    _loadedItemSpans() {
        try {
            const data = this.timeline.itemsData.get({
                filter: (it) => it.type !== "background",
            });
            return data.map((it) => ({
                s: new Date(it.start).getTime(),
                e: new Date(it.end || it.start).getTime(),
            }));
        } catch {
            return [];
        }
    },

    _mountOffHoursToggle() {
        const bar = this.rootRef.el?.querySelector(".oe_timeline_buttons");
        if (!bar || this._offToggle) {
            return;
        }
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-sm hf-offhours-toggle";
        const paint = () => {
            const hidden = offHoursHidden();
            btn.classList.toggle("is-hidden", hidden);
            btn.textContent = hidden
                ? _t("Off-hours: hidden")
                : _t("Off-hours: shown");
        };
        paint();
        btn.addEventListener("click", () => {
            try {
                localStorage.setItem(
                    OFFHOURS_KEY,
                    offHoursHidden() ? "shown" : "hidden"
                );
            } catch {
                // ignore storage failures
            }
            paint();
            try {
                // Rebuild the background items in place: hidden→shown must re-add the
                // 'off' segments that the synergy filtered out (and vice-versa). No
                // refetch — reuse the cached overlay.
                if (this.timeline) {
                    const data = this.timeline.itemsData;
                    const old = data
                        .get({filter: (it) => it.type === "background"})
                        .map((it) => it.id);
                    if (old.length) {
                        data.remove(old);
                    }
                    data.add(this._backgroundItems());
                }
                this._applyCanvasView();
            } catch {
                // non-fatal
            }
        });
        bar.appendChild(btn);
        this._offToggle = btn;
    },
});
