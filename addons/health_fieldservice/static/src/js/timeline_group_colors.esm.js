/**
 * Extension for web_timeline to apply group colors as item borders
 * and handle week/month full-day width
 */
import {TimelineRenderer} from "@web_timeline/views/timeline/timeline_renderer.esm";
import {patch} from "@web/core/utils/patch";

const {DateTime} = luxon;

patch(TimelineRenderer.prototype, {
    /**
     * Override on_data_loaded to handle week/month width after timeline renders
     */
    async on_data_loaded(records, adjust_window) {
        await super.on_data_loaded(records, adjust_window);

        // Only handle week/month width adjustments
        setTimeout(() => {
            this._handleWeekMonthFullDayWidth();
        }, 100);
    },

    /**
     * In week/month view, extend items to span full day for better visibility
     */
    _handleWeekMonthFullDayWidth() {
        if (!this.timeline || !this.mode.data) return;

        // Only apply in week or month view
        if (this.mode.data !== 'week' && this.mode.data !== 'month') return;

        const itemsData = this.timeline.itemsData;
        if (!itemsData) return;

        const items = itemsData.get();
        const updatedItems = [];

        items.forEach(item => {
            if (item.start) {
                const startDate = DateTime.fromJSDate(item.start);

                // In week/month view: span entire day (start of day to end of day)
                const startOfDay = startDate.startOf('day').toJSDate();
                const endOfDay = startDate.endOf('day').toJSDate();

                updatedItems.push({
                    ...item,
                    start: startOfDay,
                    end: endOfDay
                });
            }
        });

        if (updatedItems.length > 0) {
            // Update items to span full day
            itemsData.update(updatedItems);

            // For month view, add left/right positioning classes
            if (this.mode.data === 'month') {
                setTimeout(() => this._applyMonthPositioning(), 50);
            }
        }
    },

    /**
     * Apply left/right positioning for month view (2-day cells)
     */
    _applyMonthPositioning() {
        if (!this.timeline || this.mode.data !== 'month') return;

        const items = this.rootRef.el?.querySelectorAll('.vis-item.vis-range');
        if (!items) return;

        const itemsData = this.timeline.itemsData;

        items.forEach(item => {
            const itemId = item.getAttribute('data-id');
            if (!itemId) return;

            const itemData = itemsData?.get(parseInt(itemId));
            if (!itemData || !itemData.start) return;

            const startDate = DateTime.fromJSDate(itemData.start);
            const dayOfMonth = startDate.day;

            // Remove existing classes
            item.classList.remove('month-day-left', 'month-day-right');

            // In month view, cells show 2 days each
            // Position left for odd days, right for even days
            if (dayOfMonth % 2 === 1) {
                item.classList.add('month-day-left');
            } else {
                item.classList.add('month-day-right');
            }
        });
    },

    /**
     * Override _computeMode to handle week/month full-day width
     */
    _computeMode() {
        super._computeMode();

        // Add data attribute to root element for CSS targeting
        if (this.rootRef.el && this.mode.data) {
            this.rootRef.el.setAttribute('data-timeline-mode', this.mode.data);
        }

        // Apply full-day width when switching modes
        setTimeout(() => {
            this._handleWeekMonthFullDayWidth();
        }, 150);
    },

    /**
     * Override mode change methods to update data attribute and handle width
     */
    _onScaleDayClicked() {
        super._onScaleDayClicked();
        if (this.rootRef.el) {
            this.rootRef.el.setAttribute('data-timeline-mode', 'day');
        }
        // Restore original item durations in day view
        this._restoreOriginalDurations();
    },

    _onScaleWeekClicked() {
        super._onScaleWeekClicked();
        if (this.rootRef.el) {
            this.rootRef.el.setAttribute('data-timeline-mode', 'week');
        }
        setTimeout(() => this._handleWeekMonthFullDayWidth(), 150);
    },

    _onScaleMonthClicked() {
        super._onScaleMonthClicked();
        if (this.rootRef.el) {
            this.rootRef.el.setAttribute('data-timeline-mode', 'month');
        }
        setTimeout(() => {
            this._handleWeekMonthFullDayWidth();
            this._applyMonthPositioning();
        }, 150);
    },

    /**
     * Restore original item durations (when switching back to day view)
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
    }
});
