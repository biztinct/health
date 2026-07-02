/** @odoo-module **/

/**
 * Value formatting for BI results. Vietnamese number style uses '.' for
 * thousands and ',' for decimals; VND has no decimal places.
 */

export function formatNumber(value, format = {}, lang = "en_US") {
    if (value === null || value === undefined) {
        return "–";
    }
    if (typeof value !== "number") {
        return String(value);
    }
    const locale = lang.startsWith("vi") ? "vi-VN" : "en-US";
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
    const locale = lang.startsWith("vi") ? "vi-VN" : "en-US";
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
        return lang.startsWith("vi") ? "Khác" : "Others";
    }
    const labels = column.selection_labels || {};
    if (labels[value] !== undefined) {
        return labels[value];
    }
    if (column.type === "date" || column.type === "datetime" || column.grain) {
        const date = new Date(value);
        if (!isNaN(date)) {
            const locale = lang.startsWith("vi") ? "vi-VN" : "en-GB";
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
