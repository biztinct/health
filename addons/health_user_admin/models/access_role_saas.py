# -*- coding: utf-8 -*-
"""
SaaS Access Control for Access Roles
=====================================

Prevents tenant admins from seeing or assigning dangerous system groups
in the Access Role form.

Two protections work together:
1. get_view() — strips hidden group <field> elements from the arch AND
   removes the field names from the models dict, so the client never
   receives them. This runs AFTER Odoo's internal validation, avoiding
   "field does not exist" errors.
2. write()/create() — server-side validation blocks forbidden group
   assignment even via direct RPC/API calls.

NOTE: We intentionally do NOT override fields_get(). Odoo validates the
view arch against fields_get() results inside _get_view_cache() (which
runs BEFORE get_view). If fields_get strips a field but the cached arch
still references it, validation fails. Instead, we keep fields_get intact
and only strip the arch/models after validation completes.
"""

import logging
from lxml import etree
from odoo import api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# Group xml ids that tenant admins must NEVER be allowed to assign
FORBIDDEN_GROUP_XMLIDS = [
    'base.group_system',           # Administration / Settings
    'base.group_erp_manager',      # Access Rights
    'base.group_no_one',           # Technical Features
]

# Privilege names whose groups SHOULD be shown to tenant admins.
# NOTE: 'Inventory' removed (duplicate of Purchase under Supply Chain)
#       'Attendances' removed (duplicate of Employees under Human Resources)
ALLOWED_PRIVILEGE_NAMES = {
    'Sales',
    'Productivity',
    'Marketing',
    'Healthcare',
    'Healthcare Invoicing',
    'Accounting',
    'Employee Development',
    'AI Performance Coaching',
    'Access Role',
    'Employees',
    'Website',
    'Project',
    'Purchase',
    'Timesheets',
    'Contact',
    'Products',
    'Export',
    'Canned Responses',
    'Bank',
    'Dashboard',
    'eLearning',
}


def _is_direct_system_admin(env):
    """Check if the current user has base.group_system DIRECTLY assigned."""
    group_system = env.ref('base.group_system', raise_if_not_found=False)
    if not group_system:
        return False
    env.cr.execute("""
        SELECT 1 FROM res_groups_users_rel
        WHERE uid = %s AND gid = %s
        LIMIT 1
    """, (env.uid, group_system.id))
    return bool(env.cr.fetchone())


def _get_hidden_group_ids(env):
    """Return set of res.groups IDs that should be hidden from tenant admins."""
    hidden_ids = set()

    for xmlid in FORBIDDEN_GROUP_XMLIDS:
        grp = env.ref(xmlid, raise_if_not_found=False)
        if grp:
            hidden_ids.add(grp.id)

    allowed_priv_ids = set()
    for priv_name in ALLOWED_PRIVILEGE_NAMES:
        privs = env['res.groups.privilege'].sudo().search([
            ('name', '=', priv_name)
        ])
        allowed_priv_ids.update(privs.ids)

    all_groups = env['res.groups'].sudo().search([])
    for group in all_groups:
        if not group.privilege_id or group.privilege_id.id not in allowed_priv_ids:
            hidden_ids.add(group.id)

    return hidden_ids


def _should_field_be_hidden(fname, hidden_ids):
    """Check if a reified group field should be hidden."""
    if fname.startswith('in_group_'):
        try:
            gid = int(fname[9:])
            return gid in hidden_ids
        except (ValueError, IndexError):
            return False
    elif fname.startswith('sel_groups_'):
        try:
            gids = [int(v) for v in fname[11:].split('_')]
            return any(gid in hidden_ids for gid in gids)
        except (ValueError, IndexError):
            return False
    return False


def _strip_hidden_fields_from_arch(arch_str, env):
    """Strip hidden group field elements from the view arch XML."""
    try:
        tree = etree.fromstring(arch_str)
    except etree.XMLSyntaxError:
        return arch_str

    hidden_ids = _get_hidden_group_ids(env)
    modified = False

    for field_el in list(tree.iter('field')):
        fname = field_el.get('name', '')
        if _should_field_be_hidden(fname, hidden_ids):
            parent = field_el.getparent()
            if parent is not None:
                parent.remove(field_el)
                modified = True

    if not modified:
        return arch_str

    # Clean up empty groups iteratively
    changed = True
    while changed:
        changed = False
        for group_el in list(tree.iter('group')):
            real_children = [c for c in group_el
                           if not isinstance(c, etree._Comment)
                           and c.tag != 'newline']
            if len(real_children) == 0:
                parent = group_el.getparent()
                if parent is not None:
                    parent.remove(group_el)
                    changed = True

    # Clean up separators with empty adjacent groups
    for sep in list(tree.iter('separator')):
        if sep.get('string'):
            parent = sep.getparent()
            if parent is not None:
                next_el = sep.getnext()
                has_content = False
                temp = next_el
                while temp is not None and temp.tag == 'group':
                    if len(list(temp)) > 0:
                        has_content = True
                        break
                    temp = temp.getnext()
                if not has_content and next_el is not None and next_el.tag == 'group':
                    temp = next_el
                    while temp is not None and temp.tag == 'group' and len(list(temp)) == 0:
                        next_temp = temp.getnext()
                        parent.remove(temp)
                        temp = next_temp
                    parent.remove(sep)

    return etree.tostring(tree, encoding='unicode')


class AccessRoleSaaS(models.Model):
    """
    Extends access.role with:
    - get_view() to strip hidden group fields from the view arch and
      models dict AFTER Odoo's internal validation completes
    - write()/create() to block forbidden group assignment at DB level
    """
    _inherit = 'access.role'

    def _should_filter_groups(self):
        return not _is_direct_system_admin(self.env)

    # ---- Protection 1: Strip fields from view arch + models dict ----

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """Strip hidden group fields from view arch AND models dict.
        
        Runs AFTER _get_view_cache() (which validates the arch against
        fields_get), so validation passes with all fields intact.
        Then we strip the hidden fields from the arch and the models dict
        before sending to the client.
        """
        result = super().get_view(view_id=view_id, view_type=view_type, **options)

        if not self._should_filter_groups():
            return result

        hidden_ids = _get_hidden_group_ids(self.env)

        # Strip hidden fields from arch
        arch = result.get('arch', '')
        if arch:
            result['arch'] = _strip_hidden_fields_from_arch(arch, self.env)

        # Strip hidden fields from models dict
        # Values may be tuples (from _get_view_cache frozendict), rebuild
        if 'models' in result:
            new_models = {}
            for model_name, field_names in result['models'].items():
                filtered = tuple(
                    f for f in field_names
                    if not _should_field_be_hidden(f, hidden_ids)
                )
                new_models[model_name] = filtered
            result['models'] = new_models

        return result

    # ---- Protection 2: Block forbidden group assignment ----

    def _validate_groups_safe(self, values):
        """Block forbidden group assignment for non-system-admins."""
        if _is_direct_system_admin(self.env):
            return

        forbidden = set()
        for xmlid in FORBIDDEN_GROUP_XMLIDS:
            grp = self.env.ref(xmlid, raise_if_not_found=False)
            if grp:
                forbidden.add(grp.id)

        for key, val in values.items():
            if key.startswith('in_group_') and val:
                try:
                    gid = int(key[9:])
                    if gid in forbidden:
                        group = self.env['res.groups'].sudo().browse(gid)
                        raise AccessError(
                            "You are not allowed to assign the '%s' group. "
                            "Contact your system administrator." % group.name
                        )
                except (ValueError, IndexError):
                    pass

        if 'groups_ids' in values:
            cmds = values['groups_ids']
            if isinstance(cmds, list):
                for cmd in cmds:
                    if isinstance(cmd, (list, tuple)):
                        if cmd[0] == 4 and cmd[1] in forbidden:
                            group = self.env['res.groups'].sudo().browse(cmd[1])
                            raise AccessError(
                                "You are not allowed to assign the '%s' group. "
                                "Contact your system administrator." % group.name
                            )
                        elif cmd[0] == 6 and cmd[2]:
                            bad = set(cmd[2]) & forbidden
                            if bad:
                                groups = self.env['res.groups'].sudo().browse(list(bad))
                                raise AccessError(
                                    "You are not allowed to assign these groups: %s. "
                                    "Contact your system administrator."
                                    % ', '.join(groups.mapped('name'))
                                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._validate_groups_safe(vals)
        return super().create(vals_list)

    def write(self, values):
        self._validate_groups_safe(values)
        return super().write(values)
