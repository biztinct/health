"""Brand known application navigation without renaming stored customer data."""
from copy import deepcopy
from odoo import api, models, _

class Menu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def load_menus(self, debug):
        menus = super().load_menus(debug)
        brand = self.env['ir.http']._tenant_identity()
        if not brand['own']:
            return menus
        menus = deepcopy(menus)
        p = self.env['ir.config_parameter'].sudo()
        icon = p.get_param('tenant.identity.favicon') or p.get_param('tenant.identity.logo') or False
        for menu in menus.values():
            if menu.get('xmlid') == 'health_cms_sidebar.menu_cms_root':
                menu.update(name=brand['name'], web_icon=False, web_icon_data=icon, web_icon_data_mimetype='image/png')
        return menus

class Sidebar(models.Model):
    _inherit = 'cms.sidebar.item'

    @api.model
    def get_sidebar_data(self):
        sections = super().get_sidebar_data()
        brand = self.env['ir.http']._tenant_identity()
        if brand['own']:
            sections = deepcopy(sections)
            def visit(item):
                if item.get('action_xmlid') == 'biz_tenancy.action_biz_tenancy_about':
                    item['name'] = _('About %s', brand['name'])
                for child in item.get('children', []):visit(child)
            for section in sections:
                for item in section.get('items', []):visit(item)
        return sections
