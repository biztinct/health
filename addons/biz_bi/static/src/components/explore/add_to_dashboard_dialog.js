/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class AddToDashboardDialog extends Component {
    static template = "biz_bi.AddToDashboardDialog";
    static components = { Dialog };
    static props = {
        dashboards: { type: Array },
        onConfirm: { type: Function },
        close: { type: Function },
    };

    setup() {
        this.state = useState({
            selectedId: this.props.dashboards.length
                ? this.props.dashboards[0].id
                : 0,
            newName: "",
        });
    }

    select(dashboardId) {
        this.state.selectedId = dashboardId;
    }

    confirm() {
        const choice =
            this.state.selectedId === 0
                ? { newName: this.state.newName.trim() }
                : { dashboardId: this.state.selectedId };
        if (this.state.selectedId === 0 && !choice.newName) {
            return;
        }
        this.props.onConfirm(choice);
        this.props.close();
    }
}
