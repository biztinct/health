/** @odoo-module **/
/**
 * A window, said the way a person would say it — IN THE READER'S OWN CLOCK.
 *
 * THE TRAP THIS FILE EXISTS FOR (ledger F17 / F32). The platform stores a
 * window in UTC, because that is the only clock two machines can agree on. The
 * person reading the bar is in Ho Chi Minh City, seven hours ahead. Handing the
 * stored string straight to a renderer moves every window by seven hours with
 * no error anywhere: the owner types "22:00 tonight" and the customer's bar
 * announces maintenance in the middle of their morning.
 *
 * So the conversion is EXPLICIT and it happens here, once, and nothing that
 * draws a time does it any other way. `parseUtc` is the only door in.
 */
import { _t } from "@web/core/l10n/translation";

/**
 * `"2026-09-04 22:00:00"` (UTC, the framework's own spelling) → a Date.
 *
 * Returns null for anything unreadable rather than an Invalid Date, so every
 * caller has one thing to test for. The `Z` is what makes this a conversion at
 * all: without it the browser reads the string as LOCAL time and the whole
 * point is lost.
 */
export function parseUtc(stamp) {
    const s = String(stamp || "").trim();
    if (!s) { return null; }
    const d = new Date(s.replace(" ", "T") + "Z");
    return isNaN(d.getTime()) ? null : d;
}

/** `22:00` in the reader's clock. */
function hhmm(d) {
    return String(d.getHours()).padStart(2, "0") + ":"
         + String(d.getMinutes()).padStart(2, "0");
}

/** Whole days from today to this date, in the reader's clock. */
function dayOffset(d, now) {
    const a = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const b = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((a - b) / 86400000);
}

/** The weekday, in the reader's own language. */
function weekday(d) {
    try { return d.toLocaleDateString(undefined, { weekday: "short" }); }
    catch { return ""; }
}

/**
 * "tonight 22:00–01:00" — the window, in words, in the reader's clock.
 *
 * Returns "" when there is no window at all, so a caller can leave the line out
 * rather than print an empty one.
 */
export function renderRange(startsUtc, endsUtc, now = new Date()) {
    const a = parseUtc(startsUtc);
    const b = parseUtc(endsUtc);
    if (!a && !b) { return ""; }
    if (!a) { return _t("until %(time)s", { time: hhmm(b) }); }
    const day = dayOffset(a, now);
    if (!b) {
        if (day === 0) { return _t("from %(time)s today", { time: hhmm(a) }); }
        if (day === 1) { return _t("from %(time)s tomorrow", { time: hhmm(a) }); }
        return `${weekday(a)} ${hhmm(a)}`;
    }
    // 18:00 is when an office is empty, which is when every window anybody has
    // ever scheduled starts.
    if (day === 0 && a.getHours() >= 18) {
        return _t("tonight %(from)s–%(to)s", { from: hhmm(a), to: hhmm(b) });
    }
    if (day === 0 && dayOffset(b, now) === 0) {
        return _t("today %(from)s–%(to)s", { from: hhmm(a), to: hhmm(b) });
    }
    if (day === 1) {
        return _t("tomorrow %(from)s–%(to)s", { from: hhmm(a), to: hhmm(b) });
    }
    if (a.toDateString() === b.toDateString()) {
        return `${weekday(a)} ${hhmm(a)}–${hhmm(b)}`;
    }
    return `${weekday(a)} ${hhmm(a)} – ${weekday(b)} ${hhmm(b)}`;
}

/** "4 September 2026" — a day, in the reader's locale. */
export function longDate(iso) {
    const s = String(iso || "").trim();
    if (!s) { return ""; }
    const d = new Date(s.length <= 10 ? `${s}T00:00:00` : s.replace(" ", "T"));
    if (isNaN(d.getTime())) { return s; }
    try {
        return d.toLocaleDateString(undefined,
            { day: "numeric", month: "long", year: "numeric" });
    } catch { return s.slice(0, 10); }
}
