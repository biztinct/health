# -*- coding: utf-8 -*-
"""Keep the Analytics group current for new and re-roled users.

Phase 1 granted ``biz_bi.group_bi_creator`` to every user holding one of the
four Analytics roles, once, from ``post_init_hook``. Its own browser QA then
measured the gap that leaves: a user created **after** the install came back
``HAS_CREATOR: False`` — the sidebar leaf drew for them and the hub answered
"no analytics access". A sweep that only runs at install/upgrade time is a
snapshot of the workforce on the day it ran.

So the same decision is now taken per record, at the moment
``access_role_id`` is set:

* **add-only** — ``Command.link``, never ``Command.set``, never an unlink.
  Losing an Analytics role does NOT take the BI group away, for exactly the
  reason ``access_roles`` gives for not removing groups on role change: we
  cannot tell which groups the role granted from which the administrator
  granted by hand. Revocation stays a deliberate act.
* **the role list is not re-typed** — ``hooks.gated_role_ids`` /
  ``hooks.grant_creator_to_users`` are the single source, shared with the
  install hook and the migration.
* **idempotent** — the closure check (``all_group_ids``, §5.114) means a user
  who already reaches the group through ``group_bi_admin`` gains no redundant
  direct row, and re-assigning the same role writes nothing.

Ordering note: ``access_roles.res.users`` overrides both ``create`` and
``write`` to link the role's own ``groups_ids``. Both of ours run AFTER
``super()``, so they see the final role assignment; and because the recursive
``self.write({'group_ids': …})`` those overrides perform carries no
``access_role_id`` key, this hook cannot re-enter through them.
"""
from odoo import api, models

from ..hooks import gated_role_ids, grant_creator_to_users


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _biz_bi_cms_sync_creator_group(self):
        """Grant the Analytics group to whichever of ``self`` now qualifies.

        ``access_role_id`` belongs to the ``access_roles`` addon, which this
        module does not depend on — the guard keeps a deployment without it
        from losing the ability to create users at all.
        """
        if 'access_role_id' not in self._fields:
            return 0
        candidates = self.sudo().filtered(
            lambda u: u.access_role_id and not u.share and u.active)
        if not candidates:
            return 0
        role_ids = gated_role_ids(self.env)
        if not role_ids:
            return 0
        eligible = candidates.filtered(
            lambda u: u.access_role_id.id in role_ids)
        return grant_creator_to_users(self.env, eligible)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._biz_bi_cms_sync_creator_group()
        return users

    def write(self, vals):
        result = super().write(vals)
        if vals.get('access_role_id'):
            self._biz_bi_cms_sync_creator_group()
        return result
