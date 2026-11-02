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

export const formStudioService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        const memo = new Map();

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
