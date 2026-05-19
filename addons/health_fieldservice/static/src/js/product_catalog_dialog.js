/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class ProductCatalogDialog extends Component {
    static template = "health_fieldservice.ProductCatalogDialog";
    static props = {
        products: { type: Array },
        categories: { type: Array },
        selected: { type: Array },
        close: { type: Function },
        onDone: { type: Function },
    };

    setup() {
        const initial = {};
        for (const item of this.props.selected) {
            initial[item.product_id] = { ...item };
        }
        this.state = useState({
            search: "",
            activeCategoryId: false,
            selections: initial,
        });
    }

    formatPrice(amount) {
        if (!amount && amount !== 0) return "0 đ";
        return amount.toLocaleString("vi-VN") + " đ";
    }

    get filteredProducts() {
        let list = this.props.products;
        if (this.state.activeCategoryId) {
            list = list.filter((p) => p.categ_id === this.state.activeCategoryId);
        }
        const q = (this.state.search || "").toLowerCase().trim();
        if (q) {
            list = list.filter(
                (p) =>
                    (p.name || "").toLowerCase().includes(q) ||
                    (p.default_code || "").toLowerCase().includes(q)
            );
        }
        return list;
    }

    get selectedCount() {
        return Object.keys(this.state.selections).length;
    }

    get selectedTotal() {
        let total = 0;
        for (const item of Object.values(this.state.selections)) {
            total += (item.price || 0) * (item.qty || 1);
        }
        return total;
    }

    isSelected(productId) {
        return productId in this.state.selections;
    }

    getQty(productId) {
        const sel = this.state.selections[productId];
        return sel ? sel.qty : 0;
    }

    setCategory(categId) {
        this.state.activeCategoryId = categId;
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
    }

    addProduct(product) {
        if (this.state.selections[product.id]) {
            this.state.selections[product.id].qty += 1;
        } else {
            this.state.selections[product.id] = {
                product_id: product.id,
                name: product.name,
                price: product.price,
                qty: 1,
            };
        }
    }

    removeProduct(productId) {
        delete this.state.selections[productId];
    }

    decreaseQty(productId) {
        const sel = this.state.selections[productId];
        if (!sel) return;
        if (sel.qty <= 1) {
            delete this.state.selections[productId];
        } else {
            sel.qty -= 1;
        }
    }

    increaseQty(productId) {
        const sel = this.state.selections[productId];
        if (sel) {
            sel.qty += 1;
        }
    }

    onDone() {
        const result = Object.values(this.state.selections).map((s) => ({ ...s }));
        this.props.onDone(result);
        this.props.close();
    }

    onClose() {
        this.props.close();
    }
}
