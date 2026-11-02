/** @odoo-module **/
/**
 * The Studio button on a form's top bar, beside the cog.
 *
 * WHY THE CONTROLLER AND NOT THE STATUS BAR. The status bar belongs to the
 * renderer, a product theme may lift it somewhere else entirely, and a form
 * with no `<header>` has none. The control panel is drawn by the controller
 * on every full-page form, so that is where the door lives.
 *
 * THE QUESTION NEVER BLOCKS THE FORM. The probe is fired, not awaited: the
 * form renders at once and the button appears when the answer arrives (once
 * per screen per page — the service remembers). Never in a dialog, and never
 * on a form the client did not load by id.
 */
import { onWillStart, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { FormController } from "@web/views/form/form_controller";
import { ic } from "@biz_kit/js/kit_icons";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.formStudio = useState({ canEdit: false });
        const viewId = this.env.config && this.env.config.viewId;
        if (this.env.inDialog || !viewId) {
            return;
        }
        const studio = useService("form_studio");
        const model = this.props.resModel;
        onWillStart(() => {
            studio
                .canEdit(model, viewId)
                .then((ok) => {
                    this.formStudio.canEdit = ok;
                })
                .catch(() => {});
        });
    },

    get fsCanEdit() {
        return Boolean(this.formStudio && this.formStudio.canEdit && !this.env.inDialog);
    },

    get fsIcon() {
        return ic("wandSparkles", 15);
    },

    // Leaving the form saves it first (the action service asks the form to
    // `beforeLeave`), exactly as any other navigation away from it does.
    async openFormStudio() {
        const root = this.model.root;
        await this.actionService.doAction({
            type: "ir.actions.client",
            tag: "biz_form_studio.studio",
            name: _t("Form Studio"),
            params: {
                model: this.props.resModel,
                view_id: this.env.config.viewId,
                res_id: (root && root.resId) || false,
            },
        });
    },
});
