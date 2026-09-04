/** @odoo-module **/
/**
 * The bar under the top of every page, when the platform has something to say.
 *
 * TWO COMPONENTS, ON PURPOSE.
 *
 *   <BizTenancyBar/>     draws ONE message, from a prop. It knows nothing about
 *                        where the message came from and nothing about closing.
 *   <BizTenancyBanner/>  the one mounted in the web client: asks the service
 *                        whether there is a message this person has not closed,
 *                        and draws the bar if so.
 *
 * The split is what lets the platform's own composer show a preview that IS the
 * bar rather than a drawing of it — same component, same styles, same
 * time-phrase renderer, so the sentence the owner approves is exactly the
 * sentence the customer reads.
 *
 * A BAR, NEVER A DIALOG. Somebody halfway through a visit note must not be
 * interrupted by a box they have to dismiss before they can carry on typing.
 * The bar takes a strip, says its piece, and has an x.
 */
import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { WebClient } from "@web/webclient/webclient";
import { ic } from "@biz_kit/js/kit_icons";
import { _t } from "@web/core/l10n/translation";
import { noticeKey } from "./tenancy_service";
import { renderRange } from "./tenancy_range";

/** One message, drawn. No state, no service, no decision about visibility. */
export class BizTenancyBar extends Component {
    static template = "biz_tenancy.Bar";
    static props = {
        // { id, kind, text, starts_at, ends_at, live }
        notice: { type: Object },
        // Absent in a preview: there is nothing to close there.
        onDismiss: { type: Function, optional: true },
        // "preview" softens the shadow so the bar can sit inside a card.
        preview: { type: Boolean, optional: true },
    };

    ic(name, size = 16) { return ic(name, size); }

    get kind() {
        return this.props.notice.kind === "maintenance" ? "maintenance" : "info";
    }

    get icon() {
        return this.kind === "maintenance" ? "wrench" : "info";
    }

    /** "tonight 22:00–01:00", in THIS reader's clock (ledger F17/F32). */
    get range() {
        const n = this.props.notice;
        return renderRange(n.starts_at, n.ends_at);
    }

    /** The little word in front. It is the whole difference between the two
     *  states this bar has: a warning about something planned, and an
     *  explanation for something happening right now. */
    get label() {
        if (this.props.notice.live) { return _t("Happening now"); }
        return this.kind === "maintenance"
            ? _t("Planned update") : _t("Worth knowing");
    }

    /**
     * An update that is happening RIGHT NOW cannot be hidden.
     *
     * Every other message here is something the reader may take or leave. This
     * one is the explanation for a pause they are about to sit through, so
     * somebody who closes it is left looking at a fault instead of a notice. It
     * comes down on its own the moment the window ends.
     */
    get dismissable() {
        return !!this.props.onDismiss && !this.props.notice.live;
    }
}

/** The one mounted in the web client. */
export class BizTenancyBanner extends Component {
    static template = "biz_tenancy.Banner";
    static components = { BizTenancyBar };
    static props = {};

    setup() {
        this.tenancy = useService("biz_tenancy");
        // `useState` AND NOT `this.tenancy.state`, and the difference is the
        // whole feature (ledger F47). A service's reactive object only
        // re-renders components that have SUBSCRIBED to it, and `useService`
        // subscribes to nothing — so a bar reading the service object directly
        // renders once at mount and never again. The poll would fetch the new
        // message every minute and the screen would sit there.
        this.state = useState(this.tenancy.state);
    }

    /**
     * The message to show, or null.
     *
     * Read off `this.state` rather than delegated to the service, for the same
     * reason: every property this getter touches has to be touched THROUGH the
     * component's own subscription, or the render is not re-run when it moves.
     */
    get notice() {
        const n = this.state.notice;
        if (!n || !n.text) { return null; }
        return noticeKey(n) === this.state.dismissed ? null : n;
    }

    /** A CLICK handler. */
    dismiss() { this.tenancy.dismiss(); }
}

// The mount point is declared in `webclient_patch.xml`; this registers the
// component so the template can name it.
patch(WebClient, {
    components: { ...WebClient.components, BizTenancyBanner },
});
