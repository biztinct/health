/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";

const STATUS_COLORS = {
    active: "#1565C0",
    booking: "#2E7D32",
    lead: "#F57F17",
    lost_booking: "#C62828",
    spam: "#757575",
};

const STATUS_LABELS = {
    active: _t("Initial Contact"),
    booking: _t("Booking"),
    lead: _t("Lead"),
    lost_booking: _t("Lost Booking"),
    spam: _t("Spam Call"),
};

const CHANNEL_COLORS = [
    "#1A237E", "#3949AB", "#5C6BC0", "#7986CB", "#9FA8DA",
    "#FF6F00", "#FFA726", "#CE93D8", "#80CBC4",
];

const KPI_DEFS = [
    { key: "contacts_today", label: _t("Contacts Today"), icon: "fa-phone", format: "number" },
    { key: "pending_followups", label: _t("Pending Follow-ups"), icon: "fa-clock-o", format: "number" },
    { key: "active_leads", label: _t("Active Leads"), icon: "fa-bullseye", format: "number" },
    { key: "bookings_this_week", label: _t("Bookings This Week"), icon: "fa-calendar-check-o", format: "number" },
    { key: "conversion_rate", label: _t("Conversion Rate"), icon: "fa-line-chart", format: "percent" },
    { key: "spam_rate", label: _t("Spam Rate"), icon: "fa-ban", format: "percent" },
];

function animateCounter(el, target, format) {
    const duration = 800;
    const start = performance.now();
    const numVal = parseFloat(target) || 0;

    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = numVal * eased;

        if (format === "percent") {
            el.textContent = current.toFixed(1) + "%";
        } else if (format === "currency_m") {
            el.textContent = (current / 1000000).toFixed(1) + "M";
        } else if (numVal >= 1000000) {
            el.textContent = (current / 1000000).toFixed(1) + "M";
        } else if (numVal >= 1000) {
            el.textContent = Math.round(current).toLocaleString();
        } else {
            el.textContent = Math.round(current);
        }
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

class CrmDashboard extends Component {
    static template = "health_crm.CrmDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            isLoading: true,
            period: "month",
            customFrom: "",
            customTo: "",
            kpis: {},
            trends: {},
            sparklines: {},
            statusBreakdown: [],
            channelBreakdown: [],
            recentContacts: [],
            upcomingBookings: [],
            monthlySummary: {},
        });

        this.charts = {};
        this.donutRef = useRef("donutCanvas");
        this.barRef = useRef("barCanvas");
        this.rootRef = useRef("dashboardRoot");

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadDashboardData();
        });

        onMounted(() => {
            this._renderChartsWhenReady();
            this.animateCounters();
        });

        onWillUnmount(() => {
            this.destroyAllCharts();
        });
    }

    get kpiCards() {
        return KPI_DEFS;
    }

    get hasPipelineData() {
        return (this.state.statusBreakdown || []).some((s) => s.count > 0);
    }

    get hasChannelData() {
        return (this.state.channelBreakdown || []).length > 0;
    }

    // ===== DATA =====

    async loadDashboardData() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "crm.lead", "get_crm_dashboard_data",
                [this.state.period, this.state.customFrom || false, this.state.customTo || false]
            );
            this.state.kpis = data.kpis || {};
            this.state.trends = data.trends || {};
            this.state.sparklines = data.sparklines || {};
            this.state.statusBreakdown = data.status_breakdown || [];
            this.state.channelBreakdown = data.channel_breakdown || [];
            this.state.recentContacts = data.recent_contacts || [];
            this.state.upcomingBookings = data.upcoming_bookings || [];
            this.state.monthlySummary = data.monthly_summary || {};
        } catch (e) {
            console.error("CRM dashboard load failed:", e);
            this.notification.add(_t("Error loading dashboard"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    // ===== CHARTS =====

    destroyAllCharts() {
        Object.values(this.charts).forEach((c) => c && c.destroy());
        this.charts = {};
    }

    _renderChartsWhenReady(attempt = 0) {
        // On SPA navigation the dashboard can mount before its grid columns are
        // measured (canvas clientWidth == 0); Chart.js (responsive) then draws at
        // 0px and stays blank until a manual refresh. Wait for the canvas to have a
        // real width AND Chart.js to be loaded before drawing, with a ~1s safety cap.
        const el = this.donutRef.el || this.barRef.el;
        const ready = el && el.clientWidth > 0 && window.Chart;
        if (ready || attempt >= 60) {
            this.renderAllCharts();
            return;
        }
        requestAnimationFrame(() => this._renderChartsWhenReady(attempt + 1));
    }

    renderAllCharts() {
        this.destroyAllCharts();
        this.renderDonutChart();
        this.renderBarChart();
        this.renderSparklines();
    }

    renderDonutChart() {
        const el = this.donutRef.el;
        if (!el || !window.Chart) return;
        const bd = this.state.statusBreakdown.filter((s) => s.count > 0);
        if (!bd.length) return;

        const total = bd.reduce((s, v) => s + v.count, 0);

        this.charts.donut = new Chart(el.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: bd.map((s) => this.getStatusLabel(s.status)),
                datasets: [{
                    data: bd.map((s) => s.count),
                    backgroundColor: bd.map((s) => STATUS_COLORS[s.status] || "#9E9E9E"),
                    borderWidth: 2,
                    borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "65%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { usePointStyle: true, padding: 14, font: { size: 11, weight: "500" } },
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const pct = total ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                return ` ${ctx.label}: ${ctx.raw} (${pct}%)`;
                            },
                        },
                    },
                },
                onClick: (_evt, elements) => {
                    if (elements.length) {
                        const seg = bd[elements[0].index];
                        this.action.doAction({
                            type: "ir.actions.act_window",
                            name: seg.label || seg.status,
                            res_model: "crm.lead",
                            views: [[false, "list"], [false, "form"]],
                            domain: [["contact_status", "=", seg.status]],
                            target: "current",
                        });
                    }
                },
            },
            plugins: [{
                id: "centerText",
                afterDraw(chart) {
                    const { ctx, chartArea: { width, height, top, left } } = chart;
                    ctx.save();
                    ctx.font = "bold 22px sans-serif";
                    ctx.fillStyle = "#263238";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillText(total, left + width / 2, top + height / 2 - 8);
                    ctx.font = "500 11px sans-serif";
                    ctx.fillStyle = "#90A4AE";
                    ctx.fillText(_t("Total"), left + width / 2, top + height / 2 + 12);
                    ctx.restore();
                },
            }],
        });
    }

    renderBarChart() {
        const el = this.barRef.el;
        if (!el || !window.Chart) return;
        const bd = this.state.channelBreakdown;
        if (!bd.length) return;

        this.charts.bar = new Chart(el.getContext("2d"), {
            type: "bar",
            data: {
                labels: bd.map((c) => c.label),
                datasets: [{
                    data: bd.map((c) => c.count),
                    backgroundColor: bd.map((_, i) => CHANNEL_COLORS[i % CHANNEL_COLORS.length]),
                    borderRadius: 6,
                    borderSkipped: false,
                    barThickness: 22,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ` ${ctx.raw} contacts`,
                        },
                    },
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { display: false },
                        ticks: { font: { size: 11 } },
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: { size: 11, weight: "500" } },
                    },
                },
                onClick: (_evt, elements) => {
                    if (elements.length) {
                        const ch = bd[elements[0].index];
                        this.action.doAction({
                            type: "ir.actions.act_window",
                            name: ch.label,
                            res_model: "crm.lead",
                            views: [[false, "list"], [false, "form"]],
                            domain: [["vietnamese_channel", "=", ch.channel]],
                            target: "current",
                        });
                    }
                },
            },
        });
    }

    renderSparklines() {
        const root = this.rootRef.el;
        if (!root || !window.Chart) return;
        for (const kpi of KPI_DEFS) {
            const canvas = root.querySelector(`canvas[data-spark-key="${kpi.key}"]`);
            if (!canvas) continue;
            const data = this.state.sparklines[kpi.key];
            if (!data || !data.length) continue;

            canvas.width = 60;
            canvas.height = 28;
            this.charts["spark_" + kpi.key] = new Chart(canvas.getContext("2d"), {
                type: "line",
                data: {
                    labels: data.map(() => ""),
                    datasets: [{
                        data,
                        borderColor: "#1A237E",
                        borderWidth: 1.5,
                        fill: true,
                        backgroundColor: "rgba(26, 35, 126, 0.12)",
                        pointRadius: 0,
                        tension: 0.4,
                    }],
                },
                options: {
                    responsive: false,
                    plugins: { legend: { display: false }, tooltip: { enabled: false } },
                    scales: { x: { display: false }, y: { display: false } },
                    animation: { duration: 600 },
                },
            });
        }
    }

    animateCounters() {
        for (const kpi of KPI_DEFS) {
            const el = this.__owl__.bdom?.parentEl?.querySelector?.(
                `[data-kpi-key="${kpi.key}"] .cd-kpi-value`
            );
            if (el) {
                const val = this.state.kpis[kpi.key] ?? 0;
                animateCounter(el, val, kpi.format);
            }
        }
    }

    // ===== FORMATTING =====

    formatKpiValue(key, format) {
        const val = this.state.kpis[key];
        if (val === undefined || val === null) return "0";
        if (format === "percent") return val.toFixed(1) + "%";
        if (val >= 1000000) return (val / 1000000).toFixed(1) + "M";
        if (val >= 1000) return Math.round(val).toLocaleString();
        return String(Math.round(val));
    }

    getTrendClass(key) {
        const val = this.state.trends[key] || 0;
        if (val > 0) return "up";
        if (val < 0) return "down";
        return "flat";
    }

    getTrendIcon(key) {
        const val = this.state.trends[key] || 0;
        if (val > 0) return "fa-arrow-up";
        if (val < 0) return "fa-arrow-down";
        return "fa-minus";
    }

    getTrendValue(key) {
        return Math.abs(this.state.trends[key] || 0).toFixed(1) + "%";
    }

    getStatusColor(status) {
        return STATUS_COLORS[status] || "#9E9E9E";
    }

    getStatusLabel(status) {
        return STATUS_LABELS[status] || status;
    }

    // ===== ACTIONS =====

    async onPeriodChange(period) {
        this.state.period = period;
        // "custom" only reloads once both dates are picked (handled in onCustomDateChange)
        if (period === "custom" && !(this.state.customFrom && this.state.customTo)) {
            return;
        }
        await this.loadDashboardData();
        this.renderAllCharts();
        this.animateCounters();
    }

    async onCustomDateChange(which, value) {
        if (which === "from") {
            this.state.customFrom = value;
        } else {
            this.state.customTo = value;
        }
        this.state.period = "custom";
        if (this.state.customFrom && this.state.customTo) {
            await this.loadDashboardData();
            this.renderAllCharts();
            this.animateCounters();
        }
    }

    async onRefresh() {
        await this.loadDashboardData();
        this.renderAllCharts();
        this.animateCounters();
        this.notification.add(_t("Dashboard refreshed"), { type: "success" });
    }

    onKpiClick(key) {
        const today = new Date();
        const todayStr = today.toISOString().slice(0, 10) + " 00:00:00";
        const tomorrow = new Date(today);
        tomorrow.setDate(today.getDate() + 1);
        const tomorrowStr = tomorrow.toISOString().slice(0, 10) + " 00:00:00";
        const weekStart = new Date(today);
        weekStart.setDate(today.getDate() - today.getDay() + 1);
        const weekStr = weekStart.toISOString().slice(0, 10) + " 00:00:00";
        const monthStr = today.toISOString().slice(0, 8) + "01 00:00:00";

        const map = {
            contacts_today: {
                name: _t("Contacts Today"),
                domain: [["create_date", ">=", todayStr]],
            },
            pending_followups: {
                name: _t("Pending Follow-ups"),
                domain: [["contact_status", "=", "lead"],
                         ["next_follow_up_date", "!=", false],
                         ["next_follow_up_date", "<", tomorrowStr]],
            },
            active_leads: {
                name: _t("Active Leads"),
                domain: [["contact_status", "=", "lead"]],
            },
            bookings_this_week: {
                name: _t("Bookings This Week"),
                domain: [["contact_status", "=", "booking"], ["create_date", ">=", weekStr]],
            },
            conversion_rate: {
                name: _t("Bookings This Month"),
                domain: [["contact_status", "=", "booking"], ["create_date", ">=", monthStr]],
            },
            spam_rate: {
                name: _t("Spam This Month"),
                domain: [["contact_status", "=", "spam"], ["create_date", ">=", monthStr]],
            },
        };

        const cfg = map[key];
        if (!cfg) return;

        this.action.doAction({
            type: "ir.actions.act_window",
            name: cfg.name,
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: cfg.domain,
            target: "current",
        });
    }

    onFeedItemClick(contactId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            res_id: contactId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openNewContact() {
        this.action.doAction("health_crm.action_crm_new_contact", { clearBreadcrumbs: true });
    }

    openContacts() {
        this.action.doAction("health_crm.action_crm_contact_list_native", { clearBreadcrumbs: true });
    }

    openCalendar() {
        this.action.doAction("health_crm.action_crm_followup_calendar", { clearBreadcrumbs: true });
    }

    openActivities() {
        this.action.doAction("health_crm.action_crm_activity_list", { clearBreadcrumbs: true });
    }

    openBookings() {
        this.action.doAction("health_crm.action_crm_bookings_calendar", { clearBreadcrumbs: true });
    }

    onBookingClick(item) {
        // Open the actual booking record (not the contact hub) when linked.
        if (item.booking_id) {
            this.action.doAction({
                type: "ir.actions.client",
                tag: "ops_booking_detail",
                name: _t("Booking"),
                target: "current",
                context: { active_id: item.booking_id },
            });
            return;
        }
        this.onFeedItemClick(item.id);
    }
}

registry.category("actions").add("crm_dashboard", CrmDashboard);

export default CrmDashboard;
