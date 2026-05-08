/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";

patch(ListController.prototype, {
    async createRecord({ group } = {}) {
        if (this.props.context && this.props.context.open_create_wizard) {
            const action = await this.env.services.orm.call(
                "res.users",
                "action_open_create_user_wizard",
                [],
            );
            await this.env.services.action.doAction(action, {
                onClose: async () => {
                    await this.model.root.load();
                },
            });
            return;
        }
        return super.createRecord({ group });
    },
});
