# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)

# Groups that tenant admins must NEVER be able to assign — checked
# TRANSITIVELY: containing a group that merely IMPLIES one of these is just
# as dangerous as containing it directly (E1: the Owner-role escalation rode
# a DB-only implied_ids row into base.group_system).
PROTECTED_GROUP_XMLIDS = [
    'base.group_system',           # Administration / Settings
    'base.group_erp_manager',      # Access Rights (implied by group_system)
    # The access_roles module's own admin group: grants the Access Role menus,
    # full write on access.role/role.management (ring 0 ACL) and the CMS
    # sidebar-gating bypass. Assigning it IS becoming platform admin (E2).
    'access_roles.access_role_group_administrator',
]

# Checked on DIRECT containment only. group_no_one exposes technical UI but
# grants no model rights — and on this database base.group_user itself
# implies it, so a transitive check would damn every role in the system.
PROTECTED_DIRECT_GROUP_XMLIDS = [
    'base.group_no_one',           # Technical / Extra Rights
]


def _browse_xmlids(env, xmlids):
    groups = env['res.groups'].sudo().browse()
    for xmlid in xmlids:
        grp = env.ref(xmlid, raise_if_not_found=False)
        if grp:
            groups |= grp
    return groups


def _dangerous_subset(env, groups):
    """The part of `groups` a tenant admin must never hand out: any group
    granting-or-implying a protected group, plus direct-only offenders."""
    groups = groups.sudo()
    transitive = _browse_xmlids(env, PROTECTED_GROUP_XMLIDS)
    direct = _browse_xmlids(env, PROTECTED_DIRECT_GROUP_XMLIDS)
    return ((groups | groups.all_implied_ids) & transitive) | (groups & direct)


class ResUsersSaaS(models.Model):
    """
    Extends res.users with SaaS-safe user management methods.
    
    Tenant admins (group_health_user_admin) can manage users through
    these methods WITHOUT having base.group_system. All writes to
    res.users are done via sudo() but with strict validation.
    """
    _inherit = 'res.users'

    @api.model
    def _register_hook(self):
        """Watchdog: the two-ring design depends on base.group_user being
        READ-ONLY on access.role. If a re-imported access_roles update ever
        reverts its CSV, scream in the log rather than fail silently open."""
        res = super()._register_hook()
        acl = self.env.ref('access_roles.access_access_role',
                           raise_if_not_found=False)
        if acl and (acl.perm_write or acl.perm_create or acl.perm_unlink):
            _logger.critical(
                "SECURITY: access_roles.access_access_role grants write on "
                "access.role to base.group_user again — the ring ACL lockdown "
                "has been reverted (likely an upstream access_roles update). "
                "Re-apply the read-only CSV immediately.")
        return res

    @api.model
    def action_open_create_user_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create User'),
            'res_model': 'health.create.user.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

    @api.model
    def action_saas_create_user(self, vals):
        """Create a user from the simplified SaaS form.
        
        Called by tenant admins who don't have base.group_system.
        Only allows safe fields and forces role-based group assignment.
        
        :param vals: dict with keys: name, login, access_role_id, 
                     password (optional), phone (optional)
        :returns: dict with created user info
        """
        self._check_user_admin_access()
        
        # Whitelist allowed fields
        safe_vals = {}
        allowed_fields = {'name', 'login', 'password', 'phone', 'access_role_id',
                          'company_id', 'company_ids', 'lang', 'tz',
                          'is_duty_doctor', 'is_head_nurse', 'catchment_province_id'}
        for key in vals:
            if key in allowed_fields:
                safe_vals[key] = vals[key]

        if not safe_vals.get('name') or not safe_vals.get('login'):
            raise UserError(_("Name and Email are required to create a user."))

        # Validate the role doesn't contain protected groups
        if safe_vals.get('access_role_id'):
            self._validate_role_safe(safe_vals['access_role_id'])

        # Create user via sudo
        new_user = self.sudo().create(safe_vals)
        return {
            'id': new_user.id,
            'name': new_user.name,
            'login': new_user.login,
        }

    def action_saas_deactivate(self):
        """Deactivate a user (SaaS-safe: no delete, just archive)."""
        self._check_user_admin_access()
        for user in self:
            if user.has_group('base.group_system'):
                raise UserError(_(
                    "Cannot deactivate system administrator '%s'. "
                    "Contact your system administrator.", user.name
                ))
            if user.id == self.env.uid:
                raise UserError(_("You cannot deactivate your own account."))
        self.sudo().write({'active': False})

    def action_saas_activate(self):
        """Re-activate a deactivated user."""
        self._check_user_admin_access()
        self.sudo().with_context(active_test=False).write({'active': True})

    def action_saas_assign_role(self, role_id):
        """Assign an access role to users (SaaS-safe)."""
        self._check_user_admin_access()
        if role_id:
            self._validate_role_safe(role_id)
        self.sudo().write({'access_role_id': role_id})

    def action_saas_reset_password(self):
        """Send password reset email to selected users."""
        self._check_user_admin_access()
        for user in self:
            if user.has_group('base.group_system') and user.id != self.env.uid:
                raise UserError(_(
                    "Cannot reset password for system administrator '%s'.", user.name
                ))
        self.sudo().action_reset_password()

    def action_open_staff_details(self):
        self.ensure_one()
        employee = self.get_employee_record()
        if not employee:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Employee Record'),
                    'message': _('No employee record found for this user.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Staff Details'),
            'res_model': 'hr.employee',
            'res_id': employee.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_fieldservice.view_healthcare_staff_form').id,
            'target': 'current',
        }

    def _check_user_admin_access(self):
        """Verify the current user has the Healthcare User Admin group or is a system admin."""
        if not (self.env.user.has_group('health_user_admin.group_health_user_admin')
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_(
                "You do not have permission to manage users. "
                "Contact your administrator."
            ))

    def _validate_role_safe(self, role_id):
        """Ensure a role doesn't contain — or transitively IMPLY — any
        protected system group. Direct containment alone is not enough:
        the Owner role escalated to base.group_system through an implied_ids
        row on one of its ordinary-looking groups (E1)."""
        role = self.env['access.role'].sudo().browse(role_id)
        if not role.exists():
            raise UserError(_("Invalid access role."))

        dangerous = _dangerous_subset(self.env, role.groups_ids)
        if dangerous:
            raise UserError(_(
                "Access role '%s' contains or implies restricted system groups: %s. "
                "These groups cannot be assigned through the tenant interface.",
                role.name, ', '.join(dangerous.mapped('full_name'))
            ))

    def write(self, vals):
        """Override write to block system group assignment by tenant admins."""
        if not self.env.is_superuser() \
                and self.env.user.has_group('health_user_admin.group_health_user_admin') \
                and not self.env.user.has_group('base.group_system'):
            # check that no protected groups are being added
            if 'group_ids' in vals:
                self._guard_protected_groups(vals.get('group_ids', []))
            # a privileged role assignment is refused before its group sync
            # can fire (the access_roles write override links role groups)
            if vals.get('access_role_id'):
                self._validate_role_safe(vals['access_role_id'])
        return super().write(vals)

    def _guard_protected_groups(self, group_commands):
        """Prevent tenant admins from adding protected groups via write.

        Implication-aware (E1): a linked group is refused when it IS a
        protected group or when it transitively implies one — otherwise a
        harmless-looking wrapper group smuggles in base.group_system."""
        added_ids = set()
        for cmd in (group_commands or []):
            if isinstance(cmd, (list, tuple)):
                if cmd[0] == 4:            # Link
                    added_ids.add(cmd[1])
                elif cmd[0] == 6:          # Replace
                    added_ids.update(cmd[2] or [])

        if not added_ids:
            return
        added = self.env['res.groups'].sudo().browse(list(added_ids))
        if _dangerous_subset(self.env, added):
            raise AccessError(_(
                "You cannot assign system administration groups."
            ))
