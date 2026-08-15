from odoo import fields, models


class CmsSidebarSection(models.Model):
    _name = 'cms.sidebar.section'
    _description = 'CMS Sidebar Section'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    technical_key = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(string='Icon Class')
    active = fields.Boolean(default=True)
    color = fields.Char(string='Accent Color')
    item_ids = fields.One2many('cms.sidebar.item', 'section_id', string='Menu Items')
    role_ids = fields.Many2many(
        'access.role', 'cms_sidebar_section_role_rel', 'section_id', 'role_id',
        string='Allowed Roles',
        help='Roles allowed to see this whole section. Every item in the '
             'section inherits these — an item with no roles of its own '
             'becomes visible to exactly these roles, and an item that lists '
             'its own roles is visible to those AS WELL AS these. Leave empty '
             'to gate item by item.',
    )
