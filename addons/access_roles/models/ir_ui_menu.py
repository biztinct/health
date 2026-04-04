# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models, tools


class IrUiMenu(models.Model):
    """Extend ir.ui.menu to apply role-based UI restrictions."""
    _inherit = 'ir.ui.menu'

    root_menu_name = fields.Char(
        string='Root Menu',
        compute='_compute_root_menu_name',
        store=True,
    )

    @api.depends('parent_path')
    def _compute_root_menu_name(self):
        for menu in self:
            if menu.parent_path:
                root_id = int(menu.parent_path.split('/')[0])
                root_menu = self.sudo().browse(root_id)
                menu.root_menu_name = root_menu.name if root_menu.exists() else menu.name
            else:
                menu.root_menu_name = menu.name

    @api.model
    def _visible_menu_ids(self, debug=False):
        """Override to dynamically hide menus based on role management."""
        visible_menu_ids = super()._visible_menu_ids(debug=debug)
        role = self.env.user.access_role_id
        hidden_menu_ids = set()
        if role.role_management_id and role.role_management_id.menu_ids:
            hidden_menu_ids.update(role.role_management_id.menu_ids.ids)
        return visible_menu_ids - hidden_menu_ids

    @api.model
    def _invalidate_menu_cache(self):
        """Clear both _visible_menu_ids and load_menus caches.
        Call this when role management menus or user role assignments change."""
        self.env.registry.clear_cache()
