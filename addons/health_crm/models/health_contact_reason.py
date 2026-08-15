# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HealthContactReason(models.Model):
    """
    Healthcare Contact Reason Model
    
    Lookup table for contact reasons used in CRM leads for Sales/OM purposes.
    Based on Excel requirements for contact_reason field.
    """
    _name = "health.contact.reason"
    _description = "Healthcare Contact Reason"
    _inherit = ["health.vi.alias.mixin"]
    _vi_alias_field = "name_vietnamese"
    _order = "sequence, name"
    
    name = fields.Char(
        string="Reason Name",
        required=True,
        translate=True,
        help="Name of the contact reason"
    )
    
    code = fields.Char(
        string="Reason Code",
        help="Short code for the contact reason"
    )
    
    description = fields.Text(
        string="Description",
        translate=True,
        help="Detailed description of when to use this reason"
    )
    
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Sequence for ordering reasons"
    )
    
    category_id = fields.Many2one(
        'health.lookup.value',
        string='Category',
        domain="[('category_code', '=', 'contact_reason_category'), ('active', '=', True)]",
        ondelete='restrict',
        default=lambda self: self.env['health.lookup.value']._default_for('contact_reason_category', 'sales'),
        help='Category of contact reason for reporting purposes')
    
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Is this reason currently active?"
    )
    
    # Vietnamese specific fields
    #
    # Not a column any more: this mirrors the vi_VN translation of `name`, so
    # the value shows up in every many2one dropdown instead of sitting in a
    # field nothing renders. See health.vi.alias.mixin.
    name_vietnamese = fields.Char(
        string="Vietnamese Name",
        compute="_compute_vi_alias",
        inverse="_inverse_vi_alias",
        store=False,
        help="Vietnamese translation of the reason name"
    )
    
    # Usage tracking
    usage_count = fields.Integer(
        string="Usage Count",
        compute="_compute_usage_count",
        help="Number of times this reason has been used"
    )
    
    @api.depends()
    def _compute_usage_count(self):
        """Compute usage count from CRM leads"""
        for reason in self:
            count = self.env['crm.lead'].search_count([
                ('contact_reason_id', '=', reason.id)
            ])
            reason.usage_count = count
    
    def name_get(self):
        """Custom name_get to show code and name"""
        result = []
        for record in self:
            if record.code:
                name = f"[{record.code}] {record.name}"
            else:
                name = record.name
            result.append((record.id, name))
        return result