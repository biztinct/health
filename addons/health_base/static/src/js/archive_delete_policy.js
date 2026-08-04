/** @odoo-module **/

/**
 * System-wide record-lifecycle policy (Viet Uc CMS):
 *   1. On lifecycle models (health.lifecycle.mixin), "Delete" is a USER
 *      function: it routes to the mandatory-reason wizard and soft-flags the
 *      record (visible with a DELETED badge, excluded from counts). The
 *      native unlink survives as an owner-only "Delete Permanently", enabled
 *      only when every selected record already carries the Deleted flag.
 *   2. On every guarded business model, "Archive"/"Unarchive" are CUSTODIAN
 *      functions routed through the same wizard (reason mandatory, logged).
 *   3. On other guarded models the physical "Delete" stays hidden for
 *      everyone except the Healthcare Owner group (blocked server-side too).
 *
 * Implemented by patching the List/Form controllers' getStaticActionMenuItems()
 * — the single place both the cog menu and the multi-select bar read their
 * Archive/Unarchive/Delete items from. Fully guarded so any future web-internal
 * change degrades gracefully (worst case: native behaviour returns).
 */
import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

const OWNER_GROUP = "health_base.group_healthcare_owner";
const CUSTODIAN_GROUP = "health_base.group_healthcare_custodian";

// Mirror of soft_delete_guard._health_owner_only_delete_model().
const GUARDED_EXACT = new Set([
    "account.move",
    "account.move.line",
    "account.payment",
    "crm.lead",
    "crm.stage",
    "hr.employee",
    "product.pricelist",
    "product.product",
    "product.template",
    "res.partner",
    "res.users",
    "sale.order",
    "sale.order.line",
]);
const GUARDED_PREFIXES = ["advanced.pricing.", "health.", "misa."];

// Models carrying health.lifecycle.mixin (the soft "Deleted" tier). Keep in
// sync with the server-side mixin applications. Their list/form archs carry
// an invisible `deleted` field so the per-record flag is readable here.
const LIFECYCLE_MODELS = new Set([
    "health.fieldservice.order",
    "res.partner",
    "health.payment.transaction",
    "account.move",
    "crm.lead",
]);

function isGuardedModel(resModel) {
    return (
        GUARDED_EXACT.has(resModel) ||
        GUARDED_PREFIXES.some((p) => resModel.startsWith(p))
    );
}

function applyPolicy(Controller, getTarget, getRecords) {
    patch(Controller.prototype, {
        setup() {
            super.setup(...arguments);
            // Resolve memberships once; default false (least privilege).
            this._hdIsOwner = false;
            this._hdIsCustodian = false;
            Promise.resolve(user.hasGroup(OWNER_GROUP))
                .then((v) => { this._hdIsOwner = v; })
                .catch(() => { this._hdIsOwner = false; });
            Promise.resolve(user.hasGroup(CUSTODIAN_GROUP))
                .then((v) => { this._hdIsCustodian = v; })
                .catch(() => { this._hdIsCustodian = false; });
        },

        _hdOpenLifecycleWizard(actionXmlId) {
            const { resModel, resIds } = getTarget(this);
            if (!resModel || !resIds || !resIds.length) {
                return;
            }
            this.actionService.doAction(actionXmlId, {
                additionalContext: {
                    active_model: resModel,
                    active_ids: resIds,
                },
                onClose: () => this.model.root.load(),
            });
        },

        getStaticActionMenuItems() {
            const items = super.getStaticActionMenuItems();
            try {
                const resModel = this.model.root.resModel;
                if (!isGuardedModel(resModel)) {
                    return items;
                }
                const records = getRecords(this);
                const anyDeleted = records.some((r) => !!(r.data || {}).deleted);
                const allDeleted =
                    records.length > 0 &&
                    records.every((r) => !!(r.data || {}).deleted);

                // Archive/Unarchive: custodian-only, reason-wizard routed.
                if (items.archive) {
                    const orig = items.archive.isAvailable;
                    items.archive.isAvailable = () =>
                        !!this._hdIsCustodian && (orig ? orig() : true);
                    items.archive.callback = () =>
                        this._hdOpenLifecycleWizard(
                            "health_base.action_archive_reason_wizard");
                }
                if (items.unarchive) {
                    const orig = items.unarchive.isAvailable;
                    items.unarchive.isAvailable = () =>
                        !!this._hdIsCustodian && (orig ? orig() : true);
                    items.unarchive.callback = () =>
                        this._hdOpenLifecycleWizard(
                            "health_base.action_lifecycle_unarchive_wizard");
                }

                if (items.delete && LIFECYCLE_MODELS.has(resModel)) {
                    const native = { ...items.delete };
                    // "Delete" = soft-delete request for EVERY user (it is a
                    // write, not an unlink, so it must not depend on the
                    // native item's unlink-ACL availability).
                    items.delete.isAvailable = () => !allDeleted;
                    items.delete.callback = () =>
                        this._hdOpenLifecycleWizard(
                            "health_base.action_lifecycle_delete_wizard");
                    items.lifecycleRestore = {
                        isAvailable: () => !!this._hdIsCustodian && anyDeleted,
                        sequence: (native.sequence || 50) - 2,
                        icon: "fa fa-undo",
                        description: _t("Restore"),
                        callback: () =>
                            this._hdOpenLifecycleWizard(
                                "health_base.action_lifecycle_restore_wizard"),
                    };
                    items.deleteForever = {
                        isAvailable: () =>
                            !!this._hdIsOwner &&
                            allDeleted &&
                            (native.isAvailable ? native.isAvailable() : true),
                        sequence: (native.sequence || 50) + 1,
                        icon: "fa fa-trash",
                        description: _t("Delete Permanently"),
                        class: "text-danger",
                        callback: native.callback,
                    };
                } else if (items.delete) {
                    const orig = items.delete.isAvailable;
                    items.delete.isAvailable = () =>
                        !!this._hdIsOwner && (orig ? orig() : true);
                }
            } catch (err) {
                console.warn("[health archive/delete policy] left native behaviour:", err);
            }
            return items;
        },
    });
}

// List: act on the current selection.
applyPolicy(
    ListController,
    (ctrl) => ({
        resModel: ctrl.model.root.resModel,
        resIds: (ctrl.model.root.selection || []).map((r) => r.resId),
    }),
    (ctrl) => ctrl.model.root.selection || []
);

// Form: act on the current record.
applyPolicy(
    FormController,
    (ctrl) => ({
        resModel: ctrl.model.root.resModel,
        resIds: ctrl.model.root.resId ? [ctrl.model.root.resId] : [],
    }),
    (ctrl) => (ctrl.model.root ? [ctrl.model.root] : [])
);
