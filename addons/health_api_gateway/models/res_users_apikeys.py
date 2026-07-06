# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsersApikeys(models.Model):
    """Gateway metadata on Odoo core API keys (spec B.2.2).

    Keys authenticate as their owning service user; record rules of that user
    then apply naturally. Odoo 19 core apikeys already carry
    ``expiration_date`` — consumed defensively via getattr in the auth helper,
    never duplicated here.
    """
    _inherit = 'res.users.apikeys'

    scope_ids = fields.Many2many(
        'api.key.scope', 'res_users_apikeys_scope_rel',
        'apikey_id', 'scope_id', string='Granted Scopes')
    facility_ids = fields.Many2many(
        'health.facility', 'res_users_apikeys_facility_rel',
        'apikey_id', 'facility_id', string='Facilities',
        help='Empty = all facilities the service user can see.')
    ip_allowlist = fields.Char(
        string='IP Allowlist',
        help='Comma-separated CIDRs (e.g. 10.0.0.0/8, 203.0.113.7/32). Empty = any IP.')
    gateway_active = fields.Boolean(
        string='Gateway Active', default=True,
        help='Kill-switch for gateway access without deleting the key.')
