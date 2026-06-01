/**
 * Extension for web_timeline: a "jump to date" calendar button.
 *
 * Adds a calendar icon button to the timeline toolbar (after the Year button,
 * injected via timeline_jump_date.xml). Clicking it opens the standard Odoo
 * date-picker popover; selecting a date re-positions the timeline onto that date
 * while keeping the currently-active scale (Day -> that day, Week -> that week,
 * Month -> that month).
 *
 * All records are loaded client-side regardless of the visible window (the model
 * search_reads on the action domain only, no date-range filter), so jumping is a
 * pure client-side setWindow() — no reload needed. We reuse the existing
 * (already-patched) scale handlers so the jumped-to date renders identically to
 * clicking a scale button (wide-window, CSS mode attr, duration restore).
 */
import {TimelineRenderer} from "@web_timeline/views/timeline/timeline_renderer.esm";
import {patch} from "@web/core/utils/patch";
import {usePopover} from "@web/core/popover/popover_hook";
import {DateTimePickerPopover} from "@web/core/datetime/datetime_picker_popover";

const {DateTime} = luxon;

patch(TimelineRenderer.prototype, {
    setup() {
        super.setup();
        // usePopover must be called during setup() — the patched setup runs at
        // component construction, so the hook registers correctly.
        this.jumpDatePopover = usePopover(DateTimePickerPopover, {position: "bottom"});
    },

    /**
     * Open the date-picker popover anchored to the calendar button.
     */
    _onJumpDateClicked(ev) {
        // Seed the picker with the currently-focused date (window start), else now.
        let value = DateTime.now();
        if (this.timeline) {
            value = DateTime.fromJSDate(this.timeline.getWindow().start);
        }
        this.jumpDatePopover.open(ev.currentTarget, {
            pickerProps: {
                type: "date",
                value,
                onSelect: (date) => {
                    if (date) {
                        this._jumpToDate(date);
                        this.jumpDatePopover.close();
                    }
                },
            },
        });
    },

    /**
     * Re-position the timeline onto `date`, preserving the current scale.
     * Strategy: anchor the window start at the chosen date, then invoke the
     * existing (already-patched) scale handler so the wide-window / CSS-mode /
     * duration logic runs exactly as if the scale button were clicked.
     *
     * @param {DateTime} date Luxon DateTime chosen in the picker.
     */
    _jumpToDate(date) {
        if (!this.timeline) return;
        const mode = this.mode.data;
        let unit = "day";
        if (mode === "week") unit = "week";
        else if (mode === "month") unit = "month";
        else if (mode === "year") unit = "year";
        // "today" / "fit" / unknown -> treated as day.

        const anchor = date.startOf(unit);
        // Park the window at the anchor so _scaleCurrentWindow() scales from there.
        this.timeline.setWindow(
            anchor.toJSDate(),
            anchor.plus({hours: 1}).toJSDate(),
            {animation: false}
        );

        switch (mode) {
            case "week":
                this._onScaleWeekClicked();
                break;
            case "month":
                this._onScaleMonthClicked();
                break;
            case "year":
                this._onScaleYearClicked();
                break;
            default:
                this._onScaleDayClicked(); // day / today / fit
        }
    },
});
