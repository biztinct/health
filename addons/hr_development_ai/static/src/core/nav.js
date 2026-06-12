/** @odoo-module **/

/**
 * Route stack for the coaching workspace SPA.
 * Gives the shell real in-app Back behaviour and survives a refresh via
 * sessionStorage (Odoo owns the URL, so we don't touch location.hash).
 *
 * A route is { screen: string, params: object }.
 */

const STORE_KEY = "bfsi.workspace.routes";

export function loadRoutes(defaultRoute) {
    try {
        const saved = JSON.parse(sessionStorage.getItem(STORE_KEY) || "null");
        if (Array.isArray(saved) && saved.length && saved[0].screen) {
            return saved;
        }
    } catch { /* corrupted store — fall through */ }
    return [defaultRoute];
}

export function persistRoutes(routes) {
    try {
        sessionStorage.setItem(STORE_KEY, JSON.stringify(routes));
    } catch { /* storage full / private mode — non-fatal */ }
}

export function clearRoutes() {
    try { sessionStorage.removeItem(STORE_KEY); } catch { /* ignore */ }
}
