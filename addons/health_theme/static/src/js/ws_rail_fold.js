/** @odoo-module */
// =============================================================================
// ws_rail_fold — Workspace kit: a "Summary" head that folds the rail's panels
// away when the rail sits in the page flow (narrower screens, where it moves
// up under the Next step banner — ws_workspace.scss §1).
// -----------------------------------------------------------------------------
// Usage (FIRST child of .ws-rail):   <widget name="ws_rail_fold"/>
//
// Contract:
//  1. Open by default, every time a record is opened — the choice is NOT
//     remembered (owner decision 2026-09-30). Moving to another record opens
//     it again.
//  2. Folding toggles `ws-rail--folded` on the widget's own .ws-rail; CSS hides
//     every panel but this head. On wide screens (rail pinned at the right)
//     the head is hidden by CSS and the class has no effect.
//  3. The folded head names what is folded, read from the panels' own
//     (already translated) .ws-panel__head texts.
// =============================================================================

import { Component, onMounted, onPatched, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const FOLDED = "ws-rail--folded";

export class WsRailFold extends Component {
    static template = "health_theme.WsRailFold";
    static props = { ...standardWidgetProps };

    setup() {
        this.root = useRef("root");
        this.state = useState({ folded: false, names: "" });
        this.resId = this.props.record.resId;
        onMounted(() => this.sync());
        onPatched(() => this.sync());
    }

    get rail() {
        return this.root.el?.closest(".ws-rail") || null;
    }

    sync() {
        // a different record opens unfolded (contract 1)
        if (this.props.record.resId !== this.resId) {
            this.resId = this.props.record.resId;
            if (this.state.folded) {
                this.state.folded = false;
                return;
            }
        }
        const rail = this.rail;
        if (!rail) {
            return;
        }
        rail.classList.toggle(FOLDED, this.state.folded);
        const names = [...rail.querySelectorAll(".ws-panel__head")]
            .map((el) => el.textContent.trim())
            .filter(Boolean)
            .join(" · ");
        if (names !== this.state.names) {
            this.state.names = names;
        }
    }

    toggle() {
        this.state.folded = !this.state.folded;
    }
}

registry.category("view_widgets").add("ws_rail_fold", { component: WsRailFold });
