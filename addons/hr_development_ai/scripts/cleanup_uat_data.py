# -*- coding: utf-8 -*-
"""
Cleanup duplicate/test BFSI coaching data on UAT.

Run inside odoo shell:
    sudo -u odoo odoo-bin shell -d vietuat -c /etc/odoo/odoo.conf < cleanup_uat_data.py

Set DRY_RUN = False to actually apply the changes.
Targets (from the June 2026 UX audit):
  * duplicate action plans (same employee + commitment_date, keep newest)
  * duplicate same-day coaching strategies (same banker + snapshot date, keep newest)
  * "in use" strategies with 0% confidence and no analysis -> archived
  * test branches with zero bankers (e.g. "BranEast") -> archived
"""

DRY_RUN = True

env = env  # noqa: F821 — provided by odoo shell
log = print

# ── 1. duplicate action plans ────────────────────────────────────────
Plan = env['bfsi.action.plan'].sudo()
seen = {}
dupes = Plan.browse()
for plan in Plan.search([], order='create_date desc'):
    key = (plan.employee_id.id, str(plan.commitment_date), plan.state)
    if key in seen:
        dupes |= plan
    else:
        seen[key] = plan.id
log('Duplicate action plans: %s' % dupes.mapped('name'))
if not DRY_RUN and dupes:
    dupes.write({'state': 'cancelled'})

# ── 2. duplicate strategies (same banker + snapshot date) ────────────
Strategy = env['bfsi.coaching.strategy'].sudo()
seen = {}
dupes = Strategy.browse()
for st in Strategy.search([], order='create_date desc'):
    key = (st.banker_id.id, str(st.kpi_snapshot_date))
    if key in seen:
        dupes |= st
    else:
        seen[key] = st.id
log('Duplicate strategies: %s' % dupes.mapped('name'))
if not DRY_RUN and dupes:
    dupes.write({'state': 'archived'})

# ── 3. empty "in use" strategies ─────────────────────────────────────
empty = Strategy.search([
    ('state', '=', 'in_use'),
    ('ai_confidence', '=', 0),
    ('root_cause_analysis', '=', False),
])
log('Empty in-use strategies: %s' % empty.mapped('name'))
if not DRY_RUN and empty:
    empty.write({'state': 'archived'})

# ── 4. test branches with no bankers ─────────────────────────────────
Branch = env['bfsi.branch'].sudo()
ghost = Branch.search([]).filtered(
    lambda b: not b.banker_ids.filtered(lambda e: e.active))
log('Branches with zero active bankers: %s' % ghost.mapped('name'))
if not DRY_RUN and ghost:
    ghost.write({'active': False})

if not DRY_RUN:
    env.cr.commit()
    log('COMMITTED.')
else:
    log('DRY RUN — nothing written. Set DRY_RUN = False to apply.')
