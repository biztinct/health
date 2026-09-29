/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { runPartnerMethod, shortcutRegistry } from "@health_fieldservice/js/ws_client_panels";
import { PackageWizardDialog } from "./package_wizard_dialog";

/**
 * The client screen's Shortcuts panel (health_fieldservice ws_client_panels,
 * WS-2) is filled from a registry. These are the money entries of the old
 * client sidebar. "Buy a package" opens the rich OWL package dialog (the same
 * one used on the booking screen) in patient mode, and refreshes the client
 * screen once a package has been bought.
 *
 * Before WS-2 this file patched OpsClientProfileFormController.openPackagePurchase();
 * the sidebar button that called it is gone, so the patch became this entry.
 */
shortcutRegistry.add("package", {
    key: "package",
    label: _t("Buy a package"),
    icon: "gift",
    sequence: 40,
    run: (env, partnerId, ctx) => {
        if (!partnerId) {
            return;
        }
        env.services.dialog.add(PackageWizardDialog, {
            patientId: partnerId,
            onDone: () => ctx && ctx.reload && ctx.reload(),
        });
    },
});
shortcutRegistry.add("invoice_new", {
    key: "invoice_new",
    label: _t("Create invoice"),
    icon: "receipt",
    sequence: 50,
    run: (env, partnerId) => runPartnerMethod(env, partnerId, "action_create_standard_invoice"),
});
shortcutRegistry.add("invoices", {
    key: "invoices",
    label: _t("Invoices"),
    icon: "file-text",
    sequence: 60,
    run: (env, partnerId) => runPartnerMethod(env, partnerId, "action_view_invoices"),
});
shortcutRegistry.add("packages", {
    key: "packages",
    label: _t("Packages"),
    icon: "package",
    sequence: 70,
    run: (env, partnerId) => runPartnerMethod(env, partnerId, "action_view_service_packages"),
});
shortcutRegistry.add("payments", {
    key: "payments",
    label: _t("Payments"),
    icon: "wallet",
    sequence: 80,
    run: (env, partnerId) => runPartnerMethod(env, partnerId, "action_view_payment_transactions"),
});
