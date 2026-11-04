# -*- coding: utf-8 -*-
"""The package smart button, made valid on a product VARIANT as well.

WHY THIS FILE EXISTS, AND WHAT IT COST TO FIND.

`product_template.py` adds a smart button to the product form calling
`action_view_package_instances`. Odoo's product VARIANT form
(`product.product`) is an inherit of the product TEMPLATE form, so that button
is inherited onto it too — and a button's action is validated against the model
the view is FOR.

`product.product` declares `_inherits = {'product.template': 'product_tmpl_id'}`,
and that delegation covers FIELDS but never METHODS. So every field the button
reads (`is_healthcare_package`, `healthcare_package_instances_count`) resolves
perfectly on a variant, and the method behind it does not exist — the one part
of the button nothing delegates.

THE SYMPTOM WAS NOWHERE NEAR THE CAUSE. Nothing fails while the view sits in
the database; it fails the next time that view is REBUILT, which happens when
any module that touches the product form is upgraded. On this deployment that
made `sale_project` — a stock module, on the framework's side, that this
repository does not even contain — refuse to load, with

    ParseError: while parsing sale_project/views/product_views.xml
    action_view_package_instances is not a valid action on product.product

and the upgrade died there. The practical consequence was that **no upgrade
which cascades into the product form could be run on this deployment at all**:
`-u account_payment`, `-u sale`, `-u account` all stopped at the same line, and
the traceback named a framework file every time, so it read as a framework
fault.

THE FIX IS TO MAKE THE BUTTON TRUE RATHER THAN TO HIDE IT. Delegating to the
template means a variant's button opens the same list the template's does,
which is what somebody clicking it on a variant expects — the packages belong
to the product, and a variant IS that product. Narrowing the view to exclude
`product.product` would have silenced the error and left a button that lies.
"""

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_view_package_instances(self):
        """Open the client packages of this variant's product.

        `_inherits` gives a variant every field of its template but none of its
        methods, so this hands the call on explicitly. `ensure_one()` matches
        the template's own contract, and is what a smart button always calls
        with.
        """
        self.ensure_one()
        return self.product_tmpl_id.action_view_package_instances()

    def write(self, vals):
        """Archiving a package template must not need stock rights.

        stock's `product.product.write` toggles the variant's restocking rules
        (`orderpoint_ids`) whenever `active` changes, reading them as the
        current user — so an Owner without Inventory rights could not archive a
        package template from Master Data ("not allowed to access Minimum
        Inventory Rule", UAT 2026-11-04). A healthcare package has no stock and
        no restocking rules, so for those variants alone the write runs with
        elevated rights, after checking the user may write them at all.
        """
        if 'active' in vals and 'stock.warehouse.orderpoint' in self.env \
                and not self.env['stock.warehouse.orderpoint'].has_access('read'):
            packages = self.filtered(lambda p: p.type == 'healthcare_package')
            if packages:
                packages.check_access('write')
                super(ProductProduct, packages.sudo()).write(vals)
                rest = self - packages
                return super(ProductProduct, rest).write(vals) if rest else True
        return super().write(vals)
