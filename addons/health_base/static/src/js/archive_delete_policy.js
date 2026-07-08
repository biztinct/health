/** @odoo-module **/

/**
 * System-wide record-management policy (Viet Uc CMS):
 *   1. Hide the physical "Delete" action for everyone except the Healthcare
 *      Owner group (hard delete is already blocked server-side for others).
 *   2. Route "Archive" through a mandatory-reason wizard
 *      (health.archive.reason.wizard) instead of the plain confirm dialog.
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

const OWNER_GROUP = "health_base.group_healthcare_owner";

function applyPolicy(Controller, getTarget) {
    patch(Controller.prototype, {
        setup() {
            super.setup(...arguments);
            // Resolve owner membership once; default false (hide delete).
            this._hdIsOwner = false;
            Promise.resolve(user.hasGroup(OWNER_GROUP))
                .then((v) => { this._hdIsOwner = v; })
                .catch(() => { this._hdIsOwner = false; });
        },

        getStaticActionMenuItems() {
            const items = super.getStaticActionMenuItems();
            try {
                // (1) Delete visible only to Healthcare Owner.
                if (items.delete) {
                    const orig = items.delete.isAvailable;
                    items.delete.isAvailable = () =>
                        !!this._hdIsOwner && (orig ? orig() : true);
                }
                // (2) Archive -> mandatory-reason wizard.
                if (items.archive) {
                    items.archive.callback = () => {
                        const { resModel, resIds } = getTarget(this);
                        if (!resModel || !resIds || !resIds.length) {
                            return;
                        }
                        this.actionService.doAction(
                            "health_base.action_archive_reason_wizard",
                            {
                                additionalContext: {
                                    active_model: resModel,
                                    active_ids: resIds,
                                },
                                onClose: () => this.model.root.load(),
                            }
                        );
                    };
                }
            } catch (err) {
                console.warn("[health archive/delete policy] left native behaviour:", err);
            }
            return items;
        },
    });
}

// List: act on the current selection.
applyPolicy(ListController, (ctrl) => ({
    resModel: ctrl.model.root.resModel,
    resIds: (ctrl.model.root.selection || []).map((r) => r.resId),
}));

// Form: act on the current record.
applyPolicy(FormController, (ctrl) => ({
    resModel: ctrl.model.root.resModel,
    resIds: ctrl.model.root.resId ? [ctrl.model.root.resId] : [],
}));
