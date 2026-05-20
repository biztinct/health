/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const STATE_COLORS = {
    draft: { bg: '#f1f5f9', border: '#94a3b8', text: '#64748b', dot: '#94a3b8' },
    assigned: { bg: '#eff6ff', border: '#3b82f6', text: '#1d4ed8', dot: '#3b82f6' },
    confirmed: { bg: '#eff6ff', border: '#2563eb', text: '#1e40af', dot: '#2563eb' },
    in_progress: { bg: '#fff7ed', border: '#f97316', text: '#c2410c', dot: '#f97316' },
    completed: { bg: '#f0fdf4', border: '#22c55e', text: '#15803d', dot: '#22c55e' },
    completed_pending_invoice: { bg: '#f0fdf4', border: '#22c55e', text: '#15803d', dot: '#22c55e' },
    cancelled: { bg: '#fef2f2', border: '#ef4444', text: '#dc2626', dot: '#ef4444' },
    deferred: { bg: '#fefce8', border: '#eab308', text: '#a16207', dot: '#eab308' },
};

export class BookingTimelineWidget extends Component {
    static template = "health_fieldservice.BookingTimelineWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        const now = new Date();
        this.state = useState({
            bookings: [],
            calendarDots: {},
            calMonth: now.getMonth(),
            calYear: now.getFullYear(),
            highlightDate: null,
            loading: true,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const resId = this.props.record.resId;
        if (!resId) return;
        try {
            const data = await this.orm.call(
                "res.partner", "get_booking_timeline_data", [resId]
            );
            this.state.bookings = data.bookings || [];
            this.state.calendarDots = data.calendar_dots || {};
            this.state.loading = false;
        } catch (e) {
            console.error("Timeline load failed:", e);
            this.state.loading = false;
        }
    }

    get todayStr() {
        return new Date().toISOString().slice(0, 10);
    }

    get groupedBookings() {
        const groups = {};
        for (const b of this.state.bookings) {
            if (!groups[b.date]) {
                groups[b.date] = { date: b.date, display: b.date_display, bookings: [] };
            }
            groups[b.date].bookings.push(b);
        }
        const sorted = Object.values(groups).sort((a, b) => b.date.localeCompare(a.date));

        const today = this.todayStr;
        const hasTodayGroup = sorted.some(g => g.date === today);
        if (!hasTodayGroup && sorted.length > 0) {
            let insertIdx = sorted.length;
            for (let i = 0; i < sorted.length; i++) {
                if (sorted[i].date < today) {
                    insertIdx = i;
                    break;
                }
            }
            sorted.splice(insertIdx, 0, { date: today, isTodayMarker: true, bookings: [] });
        }

        let idx = 0;
        for (const group of sorted) {
            for (const bk of group.bookings) {
                bk.side = idx % 2 === 0 ? 'left' : 'right';
                idx++;
            }
        }
        return sorted;
    }

    stateColor(state, prop) {
        return (STATE_COLORS[state] || STATE_COLORS.draft)[prop];
    }

    formatDuration(hours) {
        if (!hours) return '';
        const h = Math.floor(hours);
        const m = Math.round((hours - h) * 60);
        if (h && m) return `${h}h ${m}m`;
        if (h) return `${h}h`;
        return `${m}m`;
    }

    isToday(dateStr) {
        return dateStr === this.todayStr;
    }

    isFuture(dateStr) {
        return dateStr > this.todayStr;
    }

    openBooking(bookingId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.fieldservice.order',
            res_id: bookingId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    // Calendar methods
    get calMonthLabel() {
        const d = new Date(this.state.calYear, this.state.calMonth, 1);
        return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    }

    get calWeekdays() {
        return ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
    }

    get calDays() {
        const year = this.state.calYear;
        const month = this.state.calMonth;
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        let startDow = firstDay.getDay() - 1;
        if (startDow < 0) startDow = 6;

        const monthKey = `${year}-${String(month + 1).padStart(2, '0')}`;
        const dotsForMonth = this.state.calendarDots[monthKey] || {};

        const today = new Date();
        const isCurrentMonth = today.getFullYear() === year && today.getMonth() === month;

        const days = [];
        for (let i = 0; i < startDow; i++) {
            days.push({ empty: true });
        }
        for (let d = 1; d <= lastDay.getDate(); d++) {
            const dayKey = String(d);
            const states = dotsForMonth[dayKey] || [];
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            days.push({
                day: d,
                dateStr,
                isToday: isCurrentMonth && d === today.getDate(),
                hasDots: states.length > 0,
                dots: [...new Set(states)].slice(0, 3),
                isHighlighted: dateStr === this.state.highlightDate,
            });
        }
        return days;
    }

    prevMonth() {
        if (this.state.calMonth === 0) {
            this.state.calMonth = 11;
            this.state.calYear--;
        } else {
            this.state.calMonth--;
        }
    }

    nextMonth() {
        if (this.state.calMonth === 11) {
            this.state.calMonth = 0;
            this.state.calYear++;
        } else {
            this.state.calMonth++;
        }
    }

    onCalDayClick(dateStr) {
        this.state.highlightDate = dateStr;
        const el = document.querySelector(`[data-timeline-date="${dateStr}"]`);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
}

export const bookingTimelineWidget = {
    component: BookingTimelineWidget,
};
registry.category("view_widgets").add("vu_booking_timeline", bookingTimelineWidget);
