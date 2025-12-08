# Odoo 18 → 19 Migration Notes (Health modules)

Practical deltas observed while porting the health_* stack to Odoo 19:

- **Search views**: Odoo 19 rejects dynamic `filter_domain` expressions using `self`, `datetime`/`timedelta`/`relativedelta`, or complex inline logic. Keep search filters simple (plain domains, basic `context_today()` comparisons) or remove them.
- **Widgets/kanban templates**: Custom widget names must exist in the `view_widgets` registry. Remove unregistered widgets or provide JS + registry entry. OWL kanban requires a `card` template; add `<t t-name="card"><t t-call="kanban-box"/></t>` to templates.
- **Core field changes**:
  - `res.partner.mobile` is gone; use `phone` (or add your own `mobile`).
  - `res.groups.category_id` removed; do not set it.
  - Direct writes to `res.users.groups_id` removed; grant access via `implied_ids` between groups instead.
  - `mail_message.record_name` removed; use `subject` if you need a label.
- **Menu/action load order**: Parent menus/actions must be loaded before menuitems referencing them. Adjust manifest order accordingly.
- **Hooks**: Avoid calling `_auto_init()` or other registry internals in `post_init_hook`; keep hooks lightweight (data seeding, simple SQL) and align any audit-log SQL with new columns (e.g., `subject` instead of `record_name`).
- **Search/group-by filters**: Some group_by or date filters that worked in 18 need trimming in 19; stick to basic group_by contexts and simple domains.
- **Search filter fixes process**: When a search view breaks, first replace complex/dynamic filters with simple literal domains on existing fields (avoid `context_today()` math, Python objects, or `self`). Only remove filters entirely if a simple version is not possible.
- **Group/privilege changes**: `res.groups.category_id` is removed; if you need categories, use `res.groups.privilege` (via `privilege_id`). Avoid referencing `groups_id` in views/menus; use `group_ids`.
- **Routes**: HTTP routes with `type="json"` are now `type="jsonrpc"`.
- **Registry imports**: Use `from odoo.modules.registry import Registry` instead of `from odoo import registry`.
- **UoM changes**: `product_uom` → `product_uom_id`; `tax_id` → `tax_ids`; `factor_inv` → `relative_factor`; use `relative_uom_id` instead of `category_id`/`uom_type`.
- **Removed models/fields**: `res.partner.mobile` is gone (use `phone` or add your own); `res.partner.title` removed.
- **Views**: OWL kanban needs `<card>` templates; legacy `<kanban-box>` should be replaced. `group` tags in search views no longer support `expand="0" string="Group By"` (keep them simple).
- **Server actions**: Don’t mix `sudo` with `group_ids` in `ir.actions.server`.
- **Misc API cleanups**: Use `self.env.context` instead of `self._context`; `self.env.uid` instead of `self._uid`; avoid direct `_apply_ir_rules`; prefer `_search(domain, bypass_access=True)` if needed.
- **Comodel sanity**: Odoo 19 fails registry setup if a `Many2one` points to a non-existent model. Remove/relocate such fields to the module that actually defines the target model (e.g., insurance-claim links belong in the invoicing layer, not in the base fieldservice module).

Use this checklist when migrating other modules to reduce iteration.***
