/** @odoo-module **/

/**
 * Chart.js loader — serves the locally bundled build (no CDN dependency)
 * and keeps a registry of live charts so screens can destroy them cleanly.
 */

let loading = null;

export async function ensureChartJS() {
    if (typeof globalThis.Chart !== "undefined") {
        return true;
    }
    if (!loading) {
        loading = new Promise((resolve) => {
            const script = document.createElement("script");
            script.src = "/hr_development_ai/static/src/lib/chart.umd.min.js";
            script.onload = () => resolve(true);
            script.onerror = () => {
                console.error("Chart.js bundle failed to load");
                resolve(false);
            };
            document.head.appendChild(script);
        });
    }
    return loading;
}

/** Destroy-safe chart factory: kills any previous chart on the canvas. */
export function renderChart(canvas, config) {
    if (!canvas || typeof globalThis.Chart === "undefined") {
        return null;
    }
    const prev = globalThis.Chart.getChart(canvas);
    if (prev) {
        prev.destroy();
    }
    return new globalThis.Chart(canvas, config);
}

export const CHART_COLORS = {
    primary: "#2563EB",
    accent: "#1E40AF",
    ok: "#10B981",
    warn: "#F59E0B",
    danger: "#EF4444",
    info: "#3B82F6",
    muted: "#9CA3AF",
};
