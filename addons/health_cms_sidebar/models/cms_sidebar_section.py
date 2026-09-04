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
    # Who sees a whole block is `health_access`'s question to answer, on
    # `biz_role_ids`. See the note on `cms.sidebar.item`.
