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

const {DateTime} = luxon;

// How many days are visible at once in month view. The full month is still
// loaded; the rest is reached by horizontal scroll / drag. Fewer days here =>
// wider, more readable cards.
const MONTH_VISIBLE_DAYS = 10;

patch(TimelineRenderer.prototype, {
    /**
     * Override on_data_loaded to handle week/month width after timeline renders.
     */
    async on_data_loaded(records, adjust_window) {
        await super.on_data_loaded(records, adjust_window);

        setTimeout(() => this._handleWeekMonthFullDayWidth(), 100);
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
    },

    _onScaleDayClicked() {
        super._onScaleDayClicked();
        this._setTimelineModeAttr("day");
        this.timeline?.setOptions({horizontalScroll: false});
        // Restore original item durations in day view
        this._restoreOriginalDurations();
    },

    _onScaleWeekClicked() {
        super._onScaleWeekClicked();
        this._setTimelineModeAttr("week");
        this.timeline?.setOptions({horizontalScroll: false});
        setTimeout(() => this._handleWeekMonthFullDayWidth(), 150);
    },

    _onScaleMonthClicked() {
        super._onScaleMonthClicked();
        this._setTimelineModeAttr("month");
        setTimeout(() => this._handleWeekMonthFullDayWidth(), 150);
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
