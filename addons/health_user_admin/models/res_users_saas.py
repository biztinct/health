# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError

# Groups that tenant admins must NEVER be able to assign
PROTECTED_GROUP_XMLIDS = [
    'base.group_system',           # Administration / Settings
    'base.group_erp_manager',      # Access Rights (implied by group_system)
    'base.group_no_one',           # Technical / Extra Rights
]


class ResUsersSaaS(models.Model):
    """
    Extends res.users with SaaS-safe user management methods.
    
    Tenant admins (group_health_user_admin) can manage users through
    these methods WITHOUT having base.group_system. All writes to
    res.users are done via sudo() but with strict validation.
    """
    _inherit = 'res.users'

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
        """Ensure a role doesn't contain any protected system groups."""
        role = self.env['access.role'].sudo().browse(role_id)
        if not role.exists():
            raise UserError(_("Invalid access role."))
        
        protected_groups = self.env['res.groups']
        for xmlid in PROTECTED_GROUP_XMLIDS:
            try:
                grp = self.env.ref(xmlid, raise_if_not_found=False)
                if grp:
                    protected_groups |= grp
            except Exception:
                pass

        dangerous = role.groups_ids & protected_groups
        if dangerous:
            raise UserError(_(
                "Access role '%s' contains restricted system groups: %s. "
                "These groups cannot be assigned through the tenant interface.",
                role.name, ', '.join(dangerous.mapped('full_name'))
            ))

    def write(self, vals):
        """Override write to block system group assignment by tenant admins."""
        if 'group_ids' in vals and not self.env.is_superuser():
            # If the caller is a tenant admin (not system admin), 
            # check that no protected groups are being added
            if self.env.user.has_group('health_user_admin.group_health_user_admin') \
                    and not self.env.user.has_group('base.group_system'):
                self._guard_protected_groups(vals.get('group_ids', []))
        return super().write(vals)

    def _guard_protected_groups(self, group_commands):
        """Prevent tenant admins from adding protected groups via write."""
        protected_ids = set()
        for xmlid in PROTECTED_GROUP_XMLIDS:
            try:
                grp = self.env.ref(xmlid, raise_if_not_found=False)
                if grp:
                    protected_ids.add(grp.id)
            except Exception:
                pass

        if not protected_ids:
            return

        for cmd in (group_commands or []):
            if isinstance(cmd, (list, tuple)):
                if cmd[0] == 4 and cmd[1] in protected_ids:  # Link
                    raise AccessError(_(
                        "You cannot assign system administration groups."
                    ))
                elif cmd[0] == 6:  # Replace
                    if protected_ids & set(cmd[2] or []):
                        raise AccessError(_(
                            "You cannot assign system administration groups."
                        ))
