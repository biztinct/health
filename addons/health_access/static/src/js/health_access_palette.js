/** @odoo-module **/
/**
 * The two things the browser half of the Access home has to be told about this
 * clinic — and both are REGISTRATIONS rather than imports, because the
 * dependency only ever runs one way: this module knows about the Access home,
 * and the Access home knows nothing about clinics.
 *
 *   1. **Where "Back" goes.** The kit's back chip returns to whatever screen a
 *      product has named as its home. Without one it goes back a page, which is
 *      a door but not the right one: somebody who reached the Access home from
 *      the left menu should land back on the clinic's own admin dashboard, not
 *      wherever their history happens to point.
 *
 *   2. **Who may change a gate.** The Access home's own access team is one
 *      permission; this clinic's administrators are another, and they are the
 *      people who have always added colleagues and said who does what. The same
 *      registration is made on the server (`register_manager_groups`), and the
 *      two have to agree — a browser gate that is narrower than the server's
 *      produces a screen the people it was built for cannot find, and one that
 *      is wider produces a button that only ever shows them a refusal.
 *
 * `base.group_system` is deliberately NOT added to anything here. It stays with
 * the one account that owns the box.
 */
import { registerHome } from "@biz_kit/js/kit_registries";
import { registerAccessManagerGroups } from "@biz_access/js/access_palette";

registerHome("health_landing.action_admin_dashboard");

registerAccessManagerGroups("health_access.group_clinic_admin");
