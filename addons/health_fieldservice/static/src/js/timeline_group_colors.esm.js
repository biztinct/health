/**
 * Extension for web_timeline:
 *  - apply group colors as item left-borders (handled in CSS via the
 *    data-timeline-mode hook set below)
 *  - week/month: span items to the full day so cards fill the day column
 *  - month: use a wide, horizontally-scrollable window so cards stay readable
 *    instead of squeezing 30 days into the viewport (~50px/day, unreadable)
 */
import {TimelineRenderer} from "@web_timeline/views/timeline/timeline_renderer.esm";
import {patch} from "@web/core/utils/patch";
import {useState} from "@odoo/owl";

const {DateTime} = luxon;

// How many days are visible at once in month view. The full month is still
// loaded; the rest is reached by horizontal scroll / drag. Fewer days here =>
// wider, more readable cards.
const MONTH_VISIBLE_DAYS = 10;

// Day-view time-scale options. The full day is always loaded; the rest is
// reached by horizontal scroll / drag. `visibleHours` sets the window span, which
// (against a fixed canvas width) determines the column width — and therefore the
// appointment-card width, since vis renders items as proportional ranges. Fewer
// visible hours => wider columns/cards. `timeAxis` sets the gridline granularity.
// Each scale shows ~12 columns across the viewport.
const DAY_SCALES = {
    "15min": {visibleHours: 3, timeAxis: {scale: "minute", step: 15}},
    "30min": {visibleHours: 6, timeAxis: {scale: "minute", step: 30}},
    "1hr": {visibleHours: 12, timeAxis: {scale: "hour", step: 1}},
};
const DEFAULT_DAY_SCALE = "30min";
// Where the visible window starts (24h clock) when the displayed day is not
// today. On "today" we center on the current hour instead.
const DAY_WINDOW_START_HOUR = 7;

patch(TimelineRenderer.prototype, {
    setup() {
        super.setup();
        // Reactive day-view time scale (15min / 30min / 1hr). Drives both the
        // toolbar button highlighting and the window span in _applyDayWideWindow.
        this.dayScale = useState({value: DEFAULT_DAY_SCALE});
    },

    /**
     * After the base timeline is built, allow a single press-drag on a card to
     * move it directly (no pre-click): itemsAlwaysDraggable.item makes an
     * unselected item start dragging immediately (and vis stopPropagation then
     * suppresses the range pan, so a press-drag on empty background still pans).
     * editable.updateTime=false locks the time so a drag only reassigns staff
     * (vertical / group), never reschedules. Set once here; the per-view
     * setOptions calls below never touch editable / itemsAlwaysDraggable, so it
     * persists across Day/Week/Month.
     */
    init_timeline() {
        super.init_timeline();
        this.timeline?.setOptions({
            itemsAlwaysDraggable: {item: true, range: false},
            editable: {updateTime: false},
        });
    },

    /**
     * Override on_data_loaded to handle day/week/month width after timeline renders.
     */
    async on_data_loaded(records, adjust_window) {
        await super.on_data_loaded(records, adjust_window);

        setTimeout(() => this._handleWeekMonthFullDayWidth(), 100);
        if (this.mode.data === "day") {
            setTimeout(() => this._applyDayWideWindow(), 100);
        }
    },

    /**
     * Day view: show a narrow slice of the day at a wide hour-column scale and
     * let the user scroll/drag horizontally through the rest of the day. Without
     * this the whole 24h is squeezed into the viewport (~22px/hour) and short
     * appointments collapse to a sliver too narrow to show their card content.
     * Item durations are left untouched, so card width stays proportional.
     */
    _applyDayWideWindow() {
        if (!this.timeline || this.mode.data !== "day") return;

        const cfg = DAY_SCALES[this.dayScale?.value || DEFAULT_DAY_SCALE];
        const win = this.timeline.getWindow();
        const dayStart = DateTime.fromJSDate(win.start).startOf("day");
        const now = DateTime.now();

        // Center on the current hour when viewing today, otherwise start at the
        // business hour. The rest of the day is reached by horizontal scroll.
        let start = dayStart.plus({hours: DAY_WINDOW_START_HOUR});
        if (now >= dayStart && now < dayStart.plus({days: 1})) {
            start = now.minus({hours: 1}).startOf("hour");
        }
        const end = start.plus({hours: cfg.visibleHours});

        this.timeline.setOptions({
            horizontalScroll: true,
            zoomKey: "ctrlKey",
            moveable: true,
            timeAxis: cfg.timeAxis,
        });
        this.timeline.setWindow(start.toJSDate(), end.toJSDate(), {animation: false});
    },

    /**
     * Day view: change the time-column scale (15min / 30min / 1hr). Re-windows in
     * place, anchored on the current window start so the user's scroll position is
     * preserved (unlike _applyDayWideWindow which re-anchors on the business hour).
     */
    _onDayScaleClicked(scale) {
        if (!DAY_SCALES[scale]) return;
        this.dayScale.value = scale;
        if (this.mode.data !== "day" || !this.timeline) return;

        const cfg = DAY_SCALES[scale];
        const start = DateTime.fromJSDate(this.timeline.getWindow().start);
        this.timeline.setOptions({
            horizontalScroll: true,
            zoomKey: "ctrlKey",
            moveable: true,
            timeAxis: cfg.timeAxis,
        });
        this.timeline.setWindow(
            start.toJSDate(),
            start.plus({hours: cfg.visibleHours}).toJSDate(),
            {animation: false}
        );
    },

    /**
     * In week/month view, extend items to span the full day for better visibility.
     */
    _handleWeekMonthFullDayWidth() {
        if (!this.timeline || !this.mode.data) return;
        if (this.mode.data !== "week" && this.mode.data !== "month") return;

        const itemsData = this.timeline.itemsData;
        if (!itemsData) return;

        const updatedItems = [];
        for (const item of itemsData.get()) {
            if (!item.start) continue;
            const startDate = DateTime.fromJSDate(item.start);
            updatedItems.push({
                ...item,
                start: startDate.startOf("day").toJSDate(),
                end: startDate.endOf("day").toJSDate(),
            });
        }

        if (updatedItems.length) {
            itemsData.update(updatedItems);
        }

        if (this.mode.data === "month") {
            setTimeout(() => this._applyMonthWideWindow(), 50);
        }
    },

    /**
     * Month view: show a narrow slice of the month at a readable column width and
     * let the user scroll/drag horizontally through the rest. Without this the
     * whole month is squeezed into the viewport and cards become unreadable.
     */
    _applyMonthWideWindow() {
        if (!this.timeline || this.mode.data !== "month") return;

        const win = this.timeline.getWindow();
        const monthStart = DateTime.fromJSDate(win.start).startOf("month");
        const now = DateTime.now();

        // Land on "today" when the displayed month is the current one, otherwise
        // start at the beginning of that month. The rest of the month is reached
        // by horizontal scroll / drag.
        let start = monthStart;
        if (now >= monthStart && now < monthStart.plus({months: 1})) {
            start = now.startOf("day");
        }
        const end = start.plus({days: MONTH_VISIBLE_DAYS});

        this.timeline.setOptions({
            horizontalScroll: true,
            zoomKey: "ctrlKey",
            moveable: true,
        });
        this.timeline.setWindow(start.toJSDate(), end.toJSDate(), {animation: false});
    },

    /**
     * Set the CSS hook attribute on the view root (.o_timeline_view) so the
     * [data-timeline-mode] rules in web_timeline_card.css actually match. The
     * renderer root is .oe_timeline_view (nested inside .o_timeline_view), hence
     * the closest() lookup.
     */
    _setTimelineModeAttr(mode) {
        const el = this.rootRef.el;
        if (!el) return;
        const target = el.closest(".o_timeline_view") || el;
        target.setAttribute("data-timeline-mode", mode);
    },

    /**
     * Override _computeMode to set the mode attribute and handle week/month width.
     */
    _computeMode() {
        super._computeMode();

        if (this.mode.data) {
            this._setTimelineModeAttr(this.mode.data);
        }

        setTimeout(() => this._handleWeekMonthFullDayWidth(), 150);
        if (this.mode.data === "day") {
            setTimeout(() => this._applyDayWideWindow(), 150);
        }
    },

    _onScaleDayClicked() {
        super._onScaleDayClicked();
        this._setTimelineModeAttr("day");
        // Restore original item durations, then widen the hour columns so short
        // appointments stay readable (horizontal scroll covers the rest of the day).
        this._restoreOriginalDurations();
        setTimeout(() => this._applyDayWideWindow(), 50);
    },

    _onScaleWeekClicked() {
        super._onScaleWeekClicked();
        this._setTimelineModeAttr("week");
        // Drop the day-view minute gridlines (revert to vis auto-scaling).
        this.timeline?.setOptions({
            horizontalScroll: false,
            timeAxis: {scale: undefined, step: undefined},
        });
        setTimeout(() => this._handleWeekMonthFullDayWidth(), 150);
    },

    _onScaleMonthClicked() {
        super._onScaleMonthClicked();
        this._setTimelineModeAttr("month");
        // Drop the day-view minute gridlines (revert to vis auto-scaling).
        this.timeline?.setOptions({timeAxis: {scale: undefined, step: undefined}});
        setTimeout(() => this._handleWeekMonthFullDayWidth(), 150);
    },

    _onScaleYearClicked() {
        super._onScaleYearClicked();
        this._setTimelineModeAttr("year");
        // Drop the day-view minute gridlines (revert to vis auto-scaling).
        this.timeline?.setOptions({timeAxis: {scale: undefined, step: undefined}});
    },

    _onTodayClicked() {
        super._onTodayClicked();
        // "Today" leaves the day scale at a 24h window; drop the minute gridlines.
        this.timeline?.setOptions({timeAxis: {scale: undefined, step: undefined}});
    },

    /**
     * Restore original item durations (when switching back to day view).
     */
    _restoreOriginalDurations() {
        if (!this.timeline) return;

        const itemsData = this.timeline.itemsData;
        if (!itemsData) return;

        // Reload data from model to restore original durations
        if (this.model && this.model.data) {
            const data = [];
            for (const record of this.model.data) {
                if (record[this.date_start]) {
                    data.push(this.model._event_data_transform(record));
                }
            }
            itemsData.clear();
            itemsData.add(data);
        }
    },
});
