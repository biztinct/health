/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const HOUR_HEIGHT = 60;
const START_HOUR = 7;
const END_HOUR = 19;
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const EVENT_CLASS = {
    home_visit: 'ev-hv',
    clinic_visit: 'ev-cv',
    consultation: 'ev-consult',
    follow_up: 'ev-fu',
    emergency: 'ev-emergency',
    telemedicine: 'ev-tm',
    preventive: 'ev-fu',
    rehabilitation: 'ev-consult',
    vaccination: 'ev-cv',
    diagnostic: 'ev-hv',
};

class OpsCalendar extends Component {
    static template = "health_fieldservice.OpsCalendar";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");


        const today = new Date();
        this.state = useState({
            isLoading: true,
            viewMode: 'week',
            currentDate: new Date(today),
            staffFilter: '',
            serviceFilter: '',
            events: [],
            staffList: [],
            needsStaffCount: 0,
        });

        this.hourSlots = [];
        for (let h = START_HOUR; h < END_HOUR; h++) {
            this.hourSlots.push({
                hour: h,
                label: `${String(h).padStart(2, '0')}:00`,
            });
        }

        this._nowInterval = null;

        onWillStart(async () => {
            await this.loadCalendarData();
            await this.loadNeedsStaffCount();
        });

        onMounted(() => {
            this._nowInterval = setInterval(() => {
                this.state.currentDate = new Date(this.state.currentDate);
            }, 60000);
            const body = document.querySelector('.cal-body');
            if (body) {
                const now = new Date();
                const scrollTo = Math.max(0, (now.getHours() - START_HOUR - 1) * HOUR_HEIGHT);
                body.scrollTop = scrollTo;
            }
        });

        onWillUnmount(() => {
            if (this._nowInterval) clearInterval(this._nowInterval);
        });
    }

    // ===== DATE HELPERS =====

    getMonday(d) {
        const date = new Date(d);
        const day = date.getDay();
        const diff = date.getDate() - day + (day === 0 ? -6 : 1);
        date.setDate(diff);
        date.setHours(0, 0, 0, 0);
        return date;
    }

    formatDateISO(d) {
        return d.toISOString().split('T')[0];
    }

    get weekStart() {
        return this.getMonday(this.state.currentDate);
    }

    get weekDays() {
        const monday = this.weekStart;
        const days = [];
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        for (let i = 0; i < 7; i++) {
            const d = new Date(monday);
            d.setDate(monday.getDate() + i);
            days.push({
                date: new Date(d),
                dayName: DAY_NAMES[d.getDay()],
                dayNum: d.getDate(),
                isToday: d.getTime() === today.getTime(),
                isWeekend: d.getDay() === 0 || d.getDay() === 6,
                dateISO: this.formatDateISO(d),
            });
        }
        return days;
    }

    get dateRangeLabel() {
        if (this.state.viewMode === 'day') {
            const d = this.state.currentDate;
            return d.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
        }
        if (this.state.viewMode === 'month') {
            const d = this.state.currentDate;
            return `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`;
        }
        const ws = this.weekStart;
        const we = new Date(ws);
        we.setDate(ws.getDate() + 6);
        const sameMonth = ws.getMonth() === we.getMonth();
        if (sameMonth) {
            return `${MONTH_NAMES[ws.getMonth()]} ${ws.getDate()} — ${we.getDate()}, ${ws.getFullYear()}`;
        }
        return `${MONTH_NAMES[ws.getMonth()].substring(0, 3)} ${ws.getDate()} — ${MONTH_NAMES[we.getMonth()].substring(0, 3)} ${we.getDate()}, ${we.getFullYear()}`;
    }

    // ===== DATE RANGE FOR DATA =====

    get dataRange() {
        if (this.state.viewMode === 'day') {
            const d = new Date(this.state.currentDate);
            const start = new Date(d); start.setHours(0, 0, 0, 0);
            const end = new Date(d); end.setHours(23, 59, 59, 999);
            return { start, end };
        }
        if (this.state.viewMode === 'month') {
            const d = this.state.currentDate;
            const start = new Date(d.getFullYear(), d.getMonth(), 1);
            const end = new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59);
            return { start, end };
        }
        const ws = this.weekStart;
        const we = new Date(ws);
        we.setDate(ws.getDate() + 6);
        we.setHours(23, 59, 59, 999);
        return { start: ws, end: we };
    }

    // ===== NAVIGATION =====

    prevPeriod() {
        const d = new Date(this.state.currentDate);
        if (this.state.viewMode === 'day') d.setDate(d.getDate() - 1);
        else if (this.state.viewMode === 'week') d.setDate(d.getDate() - 7);
        else d.setMonth(d.getMonth() - 1);
        this.state.currentDate = d;
        this.loadCalendarData();
    }

    nextPeriod() {
        const d = new Date(this.state.currentDate);
        if (this.state.viewMode === 'day') d.setDate(d.getDate() + 1);
        else if (this.state.viewMode === 'week') d.setDate(d.getDate() + 7);
        else d.setMonth(d.getMonth() + 1);
        this.state.currentDate = d;
        this.loadCalendarData();
    }

    goToday() {
        this.state.currentDate = new Date();
        this.loadCalendarData();
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
        this.loadCalendarData();
    }

    onStaffFilterChange(ev) {
        this.state.staffFilter = ev.target.value;
        this.loadCalendarData();
    }

    onServiceFilterChange(ev) {
        this.state.serviceFilter = ev.target.value;
        this.loadCalendarData();
    }

    // ===== DATA LOADING =====

    async loadCalendarData() {
        this.state.isLoading = true;
        try {
            const range = this.dataRange;
            const startStr = range.start.toISOString().replace('T', ' ').substring(0, 19);
            const endStr = range.end.toISOString().replace('T', ' ').substring(0, 19);
            const data = await this.orm.call(
                "health.fieldservice.order",
                "get_ops_calendar_data",
                [startStr, endStr, this.state.staffFilter || false, this.state.serviceFilter || false]
            );
            this.state.events = data.events || [];
            this.state.staffList = data.staff || [];
        } catch (e) {
            console.error('Failed to load calendar data:', e);
            this.notification.add(_t("Error loading calendar"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    async loadNeedsStaffCount() {
        try {
            const count = await this.orm.searchCount("health.fieldservice.order", [
                ['has_staff_assigned', '=', false],
                ['state', 'in', ['draft', 'confirmed']],
            ]);
            this.state.needsStaffCount = count;
        } catch (e) { /* ignore */ }
    }

    // ===== EVENT HELPERS =====

    getEventsForDay(dateISO) {
        return this.state.events.filter(ev => {
            if (!ev.start_dt) return false;
            const evDate = new Date(ev.start_dt.replace(' ', 'T') + 'Z');
            return this.formatDateISO(evDate) === dateISO;
        });
    }

    getEventStyle(ev) {
        if (!ev.start_dt) return '';
        const dt = new Date(ev.start_dt.replace(' ', 'T') + 'Z');
        const hours = dt.getHours();
        const minutes = dt.getMinutes();
        const top = Math.max(0, (hours - START_HOUR) * HOUR_HEIGHT + minutes);
        const height = Math.max(20, ev.duration);
        return `top:${top}px;height:${height}px;`;
    }

    getEventClass(ev) {
        if (ev.state === 'in_progress') return 'cal-event ev-active';
        if (!ev.has_staff) return 'cal-event ev-unassigned';
        return 'cal-event ' + (EVENT_CLASS[ev.service_type] || 'ev-hv');
    }

    getEventTimeLabel(ev) {
        if (!ev.start_dt) return '';
        const dt = new Date(ev.start_dt.replace(' ', 'T') + 'Z');
        const startH = String(dt.getHours()).padStart(2, '0');
        const startM = String(dt.getMinutes()).padStart(2, '0');
        const endDt = new Date(dt.getTime() + ev.duration * 60000);
        const endH = String(endDt.getHours()).padStart(2, '0');
        const endM = String(endDt.getMinutes()).padStart(2, '0');
        return `${startH}:${startM}-${endH}:${endM}`;
    }

    getEventStaffLabel(ev) {
        if (!ev.has_staff) return 'Unassigned!';
        return ev.staff_name || '';
    }

    // ===== NOW LINE =====

    get nowLineStyle() {
        const now = new Date();
        const today = this.formatDateISO(now);
        const todayCol = this.weekDays.findIndex(d => d.dateISO === today);
        if (todayCol < 0) return 'display:none';
        const top = (now.getHours() - START_HOUR) * HOUR_HEIGHT + now.getMinutes();
        if (top < 0 || top > (END_HOUR - START_HOUR) * HOUR_HEIGHT) return 'display:none';
        return `top:${top}px;`;
    }

    isTodayColumn(dateISO) {
        return dateISO === this.formatDateISO(new Date());
    }

    get nowLineTop() {
        const now = new Date();
        const top = (now.getHours() - START_HOUR) * HOUR_HEIGHT + now.getMinutes();
        return top;
    }

    // ===== MONTH VIEW =====

    get monthWeeks() {
        const d = this.state.currentDate;
        const firstDay = new Date(d.getFullYear(), d.getMonth(), 1);
        const lastDay = new Date(d.getFullYear(), d.getMonth() + 1, 0);
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const startDay = this.getMonday(firstDay);
        const weeks = [];
        let current = new Date(startDay);

        for (let w = 0; w < 6; w++) {
            const week = [];
            for (let i = 0; i < 7; i++) {
                const dayDate = new Date(current);
                const dateISO = this.formatDateISO(dayDate);
                const eventsForDay = this.getEventsForDay(dateISO);
                week.push({
                    date: dayDate,
                    dayNum: dayDate.getDate(),
                    isCurrentMonth: dayDate.getMonth() === d.getMonth(),
                    isToday: dayDate.getTime() === today.getTime(),
                    dateISO,
                    eventCount: eventsForDay.length,
                    events: eventsForDay.slice(0, 3),
                });
                current.setDate(current.getDate() + 1);
            }
            weeks.push(week);
            if (current.getMonth() > d.getMonth() && current.getDate() > 7) break;
        }
        return weeks;
    }

    // ===== DAY VIEW =====

    get dayDateISO() {
        return this.formatDateISO(this.state.currentDate);
    }

    get dayEvents() {
        return this.getEventsForDay(this.dayDateISO);
    }

    get dayLabel() {
        const d = this.state.currentDate;
        return `${DAY_NAMES[d.getDay()]} ${d.getDate()}`;
    }

    get isDayToday() {
        return this.dayDateISO === this.formatDateISO(new Date());
    }

    // ===== ACTIONS =====

    openBooking(bookingId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.fieldservice.order',
            res_id: bookingId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    openCreateBooking() {
        this.action.doAction('health_fieldservice.action_ops_booking_wizard', { clearBreadcrumbs: true });
    }

    // ===== SIDEBAR =====

}

registry.category("actions").add("ops_calendar", OpsCalendar);

export default OpsCalendar;
