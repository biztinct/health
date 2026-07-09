/** @odoo-module **/
/**
 * Reschedule-by-drag — route the staff-schedule timeline's assignment move
 * through the ops-gated server gate `reschedule_from_drag`.
 *
 * This PATCHES the shipped StaffScheduleController._onMove (no addon-file edit).
 * The shipped flow (validate_timeline_change / apply_timeline_change) lacked the
 * ops guard, state guard, same-facility guard, duration immunity, matrix
 * consistency and the patient ZNS — the server gate adds all of them, so the
 * controller only orchestrates UX: refused → snap back + danger toast;
 * needs_confirm → confirm dialog then re-call confirmed; ok → success toast +
 * reload (never trust the local item write — the FSO resync moves every sibling
 * block, so we always reload the model). The unassigned side-rail drop path is
 * untouched.
 */
import {patch} from "@web/core/utils/patch";
import {StaffScheduleController} from "@health_fieldservice/js/staff_schedule_timeline.esm";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {_t} from "@web/core/l10n/translation";

const {DateTime} = luxon;

/** vis JS Date (real-UTC instant) → real-UTC wall-clock string. The timeline
 *  items live on the real-UTC basis; the server parses these as UTC. */
function toUtcStr(d) {
    return DateTime.fromJSDate(d, {zone: "utc"}).toFormat("yyyy-MM-dd HH:mm:ss");
}

patch(StaffScheduleController.prototype, {
    async _onMove(item, callback) {
        const staffId = item.group && item.group !== -1 ? item.group : false;
        if (!staffId) {
            this.notification.add(_t("Drop the assignment on a staff member's row."), {
                type: "warning",
            });
            callback(null);
            return;
        }
        const mode = this._timelineMode();
        const id = Number(item.id) || item.id;
        const startIso = toUtcStr(item.start);
        const endIso = item.end ? toUtcStr(item.end) : startIso;

        const call = (confirmed) =>
            this.orm.call("health.staff.assignment", "reschedule_from_drag", [
                id,
                startIso,
                endIso,
                staffId,
                confirmed,
                mode,
            ]);

        let res;
        try {
            res = await call(false);
        } catch {
            res = {status: "refused", message: _t("Could not reschedule the booking.")};
        }

        if (res.status === "refused") {
            this.notification.add(res.message || _t("That change isn't allowed."), {
                type: "danger",
                title: _t("Blocked"),
            });
            callback(null);
            return;
        }
        if (res.status === "noop") {
            callback(item); // dropped back where it was — nothing to do
            return;
        }

        // Snap the block back optimistically, then let the reload paint the
        // server truth (siblings move too — never trust the local write).
        const finish = async (toast, type) => {
            callback(null);
            if (toast) {
                this.notification.add(toast, {type: type || "success"});
            }
            await this._reloadTimeline();
        };

        if (res.status === "needs_confirm") {
            this.dialogService.add(ConfirmationDialog, {
                title: _t("Confirm reschedule"),
                body: res.message || _t("Reschedule this booking?"),
                confirmLabel: _t("Confirm"),
                cancelLabel: _t("Cancel"),
                confirm: async () => {
                    let r;
                    try {
                        r = await call(true);
                    } catch {
                        r = {status: "refused", message: _t("Could not save the change.")};
                    }
                    if (r.status === "ok") {
                        await finish(r.message || _t("Rescheduled."), "success");
                    } else {
                        await finish(
                            r.message || _t("Could not reschedule the booking."),
                            "warning"
                        );
                    }
                },
                cancel: () => callback(null),
            });
            return;
        }

        // status === "ok": the confirmed=false call already applied it.
        await finish(res.message || _t("Rescheduled."), "success");
    },
});
