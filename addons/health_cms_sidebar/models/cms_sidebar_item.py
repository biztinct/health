from odoo import api, fields, models


class CmsSidebarItem(models.Model):
    _name = 'cms.sidebar.item'
    _description = 'CMS Sidebar Menu Item'
    _order = 'section_id, sequence, id'

    name = fields.Char(required=True, translate=True)
    section_id = fields.Many2one(
        'cms.sidebar.section', required=True, ondelete='cascade', string='Section',
    )
    parent_id = fields.Many2one(
        'cms.sidebar.item', string='Parent Item', ondelete='cascade',
        help='When set, this item is a sub-menu shown under its parent.',
    )
    sequence = fields.Integer(default=10)
    icon = fields.Char(string='Icon Class', default='fa fa-circle-o')
    action_xmlid = fields.Char(
        string='Action XML ID',
        help='XML ID of the action to execute on click, e.g. health_crm.action_crm_dashboard',
    )
    action_tag = fields.Char(
        string='Client Action Tag',
        help='Tag for OWL client actions, e.g. crm_dashboard',
    )
    role_ids = fields.Many2many('access.role', string='Allowed Roles')
    active = fields.Boolean(default=True)
    match_action_tags = fields.Char(
        string='Match Action Tags',
        help='Comma-separated client action tags that highlight this item',
    )
    match_action_xmlids = fields.Char(
        string='Match Action XML IDs',
        help='Comma-separated action XML IDs that highlight this item',
    )
    match_models = fields.Char(
        string='Match Models',
        help='Comma-separated model names that highlight this item',
    )

    @api.model
    def get_sidebar_data(self):
        user = self.env.user
        user_role = user.access_role_id
        # Users with the "Access Role: Administrator" privilege always see the full
        # sidebar, without needing a business access.role assigned. (That privilege
        # is separate from the access.role the items are gated by, and includes the
        # superuser + base admin via the group's user_ids.) Note: base.group_system
        # is intentionally NOT used here — many staff users carry it in this DB, so
        # it would defeat per-role filtering.
        is_admin = user.has_group('access_roles.access_role_group_administrator')

        sections = self.env['cms.sidebar.section'].search(
            [('active', '=', True)], order='sequence, id',
        )
        all_items = self.search(
            [('active', '=', True)], order='section_id, sequence, id',
        )

        if is_admin:
            visible_items = all_items
        elif user_role:
            visible_items = all_items.filtered(
                lambda i: not i.role_ids or user_role in i.role_ids
            )
        else:
            visible_items = all_items.filtered(lambda i: not i.role_ids)

        def _split(val):
            return [v.strip() for v in (val or '').split(',') if v.strip()]

        def _item_dict(item):
            return {
                'id': item.id,
                'name': item.name,
                'icon': item.icon,
                'action_xmlid': item.action_xmlid,
                'action_tag': item.action_tag,
                'match_action_tags': _split(item.match_action_tags),
                'match_action_xmlids': _split(item.match_action_xmlids),
                'match_models': _split(item.match_models),
                'children': [],
            }

        result = []
        for section in sections:
            sec_items = visible_items.filtered(lambda i, s=section: i.section_id == s)
            tops = sec_items.filtered(lambda i: not i.parent_id).sorted(lambda i: (i.sequence, i.id))
            items = []
            for top in tops:
                d = _item_dict(top)
                kids = sec_items.filtered(lambda c, p=top: c.parent_id == p).sorted(
                    lambda c: (c.sequence, c.id))
                d['children'] = [_item_dict(k) for k in kids]
                items.append(d)
            if not items:
                continue
            result.append({
                'id': section.id,
                'name': section.name,
                'key': section.technical_key,
                'icon': section.icon or False,
                'color': section.color or False,
                'items': items,
            })
        return result
