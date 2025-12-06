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

Use this checklist when migrating other modules to reduce iteration.***
