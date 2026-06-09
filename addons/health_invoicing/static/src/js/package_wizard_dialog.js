/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class PackageWizardDialog extends Component {
    static template = "health_invoicing.PackageWizardDialog";
    static props = {
        // Booking mode passes fsoId (assign existing + purchase);
        // client mode passes patientId (purchase only).
        fsoId: { type: Number, optional: true },
        patientId: { type: Number, optional: true },
        close: { type: Function },
        onDone: { type: Function, optional: true },
    };

    get isPatientMode() {
        return !this.props.fsoId;
    }

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            isLoading: true,
            patientName: "",
            bookingName: "",
            existingPackages: [],
            availableProducts: [],
            selectedPackageIds: {},
            selectedProductId: false,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.isLoading = true;
        try {
            const data = this.props.fsoId
                ? await this.orm.call(
                      "health.fieldservice.order",
                      "get_package_dialog_data",
                      [this.props.fsoId]
                  )
                : await this.orm.call(
                      "res.partner",
                      "get_package_dialog_data",
                      [this.props.patientId]
                  );
            this.state.patientName = data.patient_name;
            this.state.bookingName = data.booking_name;
            this.state.existingPackages = data.existing_packages || [];
            this.state.availableProducts = data.available_products || [];
            const sel = {};
            for (const pkg of this.state.existingPackages) {
                if (pkg.selected) sel[pkg.id] = true;
            }
            this.state.selectedPackageIds = sel;
        } catch (e) {
            console.error("Failed to load package data:", e);
        }
        this.state.isLoading = false;
    }

    formatCurrency(amount) {
        if (!amount && amount !== 0) return "0 đ";
        return Math.round(amount).toLocaleString("vi-VN") + " đ";
    }

    get hasExisting() {
        return this.state.existingPackages.length > 0;
    }

    get selectedCount() {
        return Object.keys(this.state.selectedPackageIds).length;
    }

    isPackageSelected(pkgId) {
        return !!this.state.selectedPackageIds[pkgId];
    }

    togglePackage(pkgId) {
        const pkg = this.state.existingPackages.find(p => p.id === pkgId);
        if (!pkg || !pkg.selectable) return;
        if (this.state.selectedPackageIds[pkgId]) {
            delete this.state.selectedPackageIds[pkgId];
        } else {
            this.state.selectedPackageIds[pkgId] = true;
        }
    }

    isProductSelected(productId) {
        return this.state.selectedProductId === productId;
    }

    selectProduct(productId) {
        this.state.selectedProductId =
            this.state.selectedProductId === productId ? false : productId;
    }

    remainingPercent(pkg) {
        if (!pkg.total_services) return 0;
        return Math.round((pkg.remaining_services / pkg.total_services) * 100);
    }

    remainingClass(pkg) {
        if (pkg.remaining_services === 0) return "pw-gauge--empty";
        if (pkg.remaining_services <= 3) return "pw-gauge--low";
        return "pw-gauge--ok";
    }

    donutOffset(pkg) {
        const circumference = 2 * Math.PI * 42;
        const pct = pkg.total_services ? pkg.remaining_services / pkg.total_services : 0;
        return circumference * (1 - pct);
    }

    donutCircumference() {
        return 2 * Math.PI * 42;
    }

    donutColor(pkg) {
        if (pkg.remaining_services === 0) return '#EF5350';
        const pct = pkg.remaining_services / pkg.total_services;
        if (pct <= 0.25) return '#EF5350';
        if (pct <= 0.5) return '#FB8C00';
        return '#43A047';
    }

    usedPercent(pkg) {
        if (!pkg.total_services) return 0;
        return Math.round((pkg.consumed_services / pkg.total_services) * 100);
    }

    async onConfirmExisting() {
        if (!this.props.fsoId) return;   // assigning needs a booking
        const ids = Object.keys(this.state.selectedPackageIds).map(Number);
        if (!ids.length) {
            this.notification.add(_t("Select at least one package"), { type: "warning" });
            return;
        }
        try {
            await this.orm.call(
                "health.fieldservice.order",
                "action_assign_packages_owl",
                [this.props.fsoId, ids]
            );
            this.notification.add(
                _t("%s package(s) assigned", ids.length),
                { type: "success" }
            );
            if (this.props.onDone) this.props.onDone();
            this.props.close();
        } catch (e) {
            this.notification.add(_t("Failed to assign packages"), { type: "danger" });
        }
    }

    async onPurchase() {
        if (!this.state.selectedProductId) {
            this.notification.add(_t("Select a package to purchase"), { type: "warning" });
            return;
        }
        const onDone = this.props.onDone;
        try {
            const result = this.props.fsoId
                ? await this.orm.call(
                      "health.fieldservice.order",
                      "action_purchase_package_owl",
                      [this.props.fsoId, this.state.selectedProductId]
                  )
                : await this.orm.call(
                      "res.partner",
                      "action_purchase_package_owl",
                      [this.props.patientId, this.state.selectedProductId]
                  );
            this.props.close();
            // Reload the underlying form once the checkout wizard is closed, so the
            // newly-purchased package shows up without a manual page refresh.
            this.action.doAction(result, {
                onClose: () => { if (onDone) onDone(); },
            });
        } catch (e) {
            this.notification.add(_t("Failed to open purchase wizard"), { type: "danger" });
        }
    }

    onClose() {
        this.props.close();
    }
}
