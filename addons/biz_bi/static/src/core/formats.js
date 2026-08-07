/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

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
        const date = new Date(value);
        if (!isNaN(date)) {
            const locale = lang.startsWith("en") ? "en-GB" : localeOf(lang);
            if (column.grain === "quarter") {
                return "Q" + (Math.floor(date.getMonth() / 3) + 1) + " " + date.getFullYear();
            }
            const options = GRAIN_FORMATS[column.grain] || {
                day: "2-digit",
                month: "short",
                year: "2-digit",
            };
            return date.toLocaleDateString(locale, options);
        }
    }
    if (typeof value === "boolean") {
        return value ? "✓" : "✗";
    }
    return String(value);
}
