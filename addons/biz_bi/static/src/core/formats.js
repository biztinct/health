/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

/**
 * Value formatting for BI results. Locale-generic: any Odoo language code
 * maps to its Intl locale (vi_VN -> vi-VN, th_TH -> th-TH, ...), so number
 * and date styles follow each user's language automatically.
 */

function localeOf(lang) {
    try {
        return Intl.getCanonicalLocales(
            (lang || "en_US").replace("_", "-"))[0];
    } catch {
        return "en-US";
    }
}

export function formatNumber(value, format = {}, lang = "en_US") {
    if (value === null || value === undefined) {
        return "–";
    }
    if (typeof value !== "number") {
        return String(value);
    }
    const locale = localeOf(lang);
    const currency = format.currency;
    const decimals =
        format.decimals !== undefined ? format.decimals : currency === "VND" ? 0 : guessDecimals(value);
    let text;
    if (Math.abs(value) >= 1_000_000_000) {
        text = (value / 1_000_000_000).toLocaleString(locale, { maximumFractionDigits: 1 }) + "B";
    } else if (Math.abs(value) >= 1_000_000) {
        text = (value / 1_000_000).toLocaleString(locale, { maximumFractionDigits: 1 }) + "M";
    } else {
        text = value.toLocaleString(locale, {
            minimumFractionDigits: 0,
            maximumFractionDigits: decimals,
        });
    }
    if (currency === "VND") {
        text += " ₫";
    } else if (currency) {
        text += " " + currency;
    }
    return (format.prefix || "") + text + (format.suffix || "");
}

export function formatFull(value, format = {}, lang = "en_US") {
    // untruncated variant for tooltips and tables
    if (value === null || value === undefined) {
        return "–";
    }
    if (typeof value !== "number") {
        return String(value);
    }
    const locale = localeOf(lang);
    const decimals = format.decimals !== undefined ? format.decimals : guessDecimals(value);
    let text = value.toLocaleString(locale, { maximumFractionDigits: decimals });
    if (format.currency === "VND") {
        text += " ₫";
    } else if (format.currency) {
        text += " " + format.currency;
    }
    return (format.prefix || "") + text + (format.suffix || "");
}

function guessDecimals(value) {
    return Number.isInteger(value) ? 0 : 2;
}

const GRAIN_FORMATS = {
    year: { year: "numeric" },
    quarter: null, // custom below
    month: { month: "short", year: "numeric" },
    week: { day: "2-digit", month: "short" },
    day: { day: "2-digit", month: "short", year: "2-digit" },
};

const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * True when a column's values are UTC INSTANTS that must be re-read in the
 * viewer's timezone; false for calendar values, which never shift.
 *
 * Mirrors `column_is_instant` in `biz_bi/bi_tz.py` — change one side, change
 * both, or the screen and the spreadsheet part company again. A `date`
 * column and a grain truncation are bucket LABELS, not moments: shifting
 * `2026-04-01 00:00` by an offset renames the April bucket "March".
 */
export function columnIsInstant(column) {
    return (column || {}).type === "datetime" && !(column || {}).grain;
}

/** The IANA zone the viewer reads in: their Odoo preference, else the
 *  browser's. The server exports in `env.user.tz`, so the screen has to use
 *  the same one or the two disagree for anyone whose browser has travelled. */
function viewerTimeZone() {
    try {
        return user.tz || undefined;
    } catch {
        return undefined;
    }
}

/**
 * The engine emits naive values: `2026-04-27T02:30:00` for a datetime
 * (UTC, always) and `2026-04-27` for a date. `new Date()` treats the FIRST
 * as browser-local — relabelling a UTC wall clock — and the SECOND as UTC
 * midnight, which is a day early for every negative offset. Both are wrong
 * in different directions, so neither goes through the bare constructor.
 *
 * Returns `{date, timeZone}` — the instant plus the zone to render it in —
 * or null when the value is not a date at all.
 */
function parseEngineDate(value, column) {
    const instant = columnIsInstant(column);
    if (value instanceof Date) {
        return isNaN(value) ? null : { date: value, timeZone: instant ? viewerTimeZone() : "UTC" };
    }
    if (typeof value !== "string") {
        return null;
    }
    const text = value.trim();
    if (DATE_ONLY_RE.test(text)) {
        // a calendar date: pin it to UTC midnight and READ it in UTC, so it
        // renders as the very day it says, in every zone on earth
        const date = new Date(text + "T00:00:00Z");
        return isNaN(date) ? null : { date, timeZone: "UTC" };
    }
    const iso = text.replace(" ", "T");
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(iso)) {
        return null;
    }
    const date = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    if (isNaN(date)) {
        return null;
    }
    return { date, timeZone: instant ? viewerTimeZone() : "UTC" };
}

/** Calendar fields of `date` as seen in `timeZone` (never the browser's). */
function calendarPartsIn(date, timeZone) {
    const parts = {};
    for (const part of new Intl.DateTimeFormat("en-US", {
        timeZone,
        year: "numeric",
        month: "numeric",
        day: "numeric",
    }).formatToParts(date)) {
        parts[part.type] = part.value;
    }
    return { year: Number(parts.year), month: Number(parts.month), day: Number(parts.day) };
}

export function formatDimensionValue(value, column, lang = "en_US") {
    if (value === null || value === undefined || value === false) {
        return "–";
    }
    if (value === "__bi_others__") {
        return _t("Others");
    }
    // value_labels: many2one ids resolved to record names server-side, per
    // reader. selection_labels: baked at scan time. Same lookup contract.
    const labels = column.value_labels || column.selection_labels || {};
    if (labels[value] !== undefined) {
        return labels[value];
    }
    if (column.type === "date" || column.type === "datetime" || column.grain) {
        const parsed = parseEngineDate(value, column);
        if (parsed) {
            const { date, timeZone } = parsed;
            const locale = lang.startsWith("en") ? "en-GB" : localeOf(lang);
            if (column.grain === "quarter") {
                const { year, month } = calendarPartsIn(date, timeZone);
                return "Q" + (Math.floor((month - 1) / 3) + 1) + " " + year;
            }
            const options = GRAIN_FORMATS[column.grain] || {
                day: "2-digit",
                month: "short",
                year: "2-digit",
            };
            const text = date.toLocaleDateString(locale, { ...options, timeZone });
            if (!column.grain && columnIsInstant(column)) {
                // a Records-mode timestamp: the export writes the clock, so
                // the screen shows it too — a bare date cannot be checked
                // against anything, and it is the half that used to be wrong
                return (
                    text +
                    " " +
                    date.toLocaleTimeString(locale, {
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: false,
                        timeZone,
                    })
                );
            }
            return text;
        }
    }
    if (typeof value === "boolean") {
        return value ? "✓" : "✗";
    }
    return String(value);
}
