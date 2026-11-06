/** @odoo-module **/
/**
 * `form_studio` — "may this person open Studio on this screen?", asked once.
 *
 * The answer is remembered per (record type, form) for the life of the page,
 * so opening ten records of the same kind costs one question. The question
 * itself (`fs.studio.probe`) never raises on the server, and is asked through
 * the silent ORM here, so even a network failure answers "no" rather than an
 * error dialog on a screen that otherwise works (ledger §5.127).
 */
import { registry } from "@web/core/registry";
import { rpcBus } from "@web/core/network/rpc";

export const formStudioService = {
    dependencies: ["orm", "bus_service"],
    start(env, { orm, bus_service }) {
        const memo = new Map();

        // A layout was published or a Studio field deleted somewhere (UAT
        // round 11): this tab's cached screens may name a field that no
        // longer exists, so read them again on the next open.
        bus_service.subscribe("biz_form_studio/changed", () => {
            rpcBus.trigger("CLEAR-CACHES", "get_views");
            memo.clear();
        });

        function canEdit(model, viewId) {
            if (!model || !viewId) {
                return Promise.resolve(false);
            }
            const key = `${model}|${viewId}`;
            if (!memo.has(key)) {
                memo.set(
                    key,
                    orm.silent
                        .call("fs.studio", "probe", [model, viewId])
                        .then((res) => Boolean(res && res.host && res.can_edit))
                        .catch(() => false)
                );
            }
            return memo.get(key);
        }

        function forget() {
            memo.clear();
        }

        return { canEdit, forget };
    },
};

registry.category("services").add("form_studio", formStudioService);
