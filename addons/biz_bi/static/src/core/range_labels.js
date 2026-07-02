/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/** Relative date ranges: [engine value, translated label]. */
export const RELATIVE_RANGES = [
    ["today", _t("Today")],
    ["yesterday", _t("Yesterday")],
    ["last_7_days", _t("Last 7 days")],
    ["last_30_days", _t("Last 30 days")],
    ["this_week", _t("This week")],
    ["this_month", _t("This month")],
    ["last_month", _t("Last month")],
    ["this_quarter", _t("This quarter")],
    ["last_6_months", _t("Last 6 months")],
    ["last_12_months", _t("Last 12 months")],
    ["this_year", _t("This year")],
    ["last_year", _t("Last year")],
];
