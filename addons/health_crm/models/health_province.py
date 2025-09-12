# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HealthProvince(models.Model):
    """
    Vietnamese Province Lookup Table
    
    Lookup table for Vietnamese provinces/cities used in CRM leads.
    Supports both Vietnamese and English names for provinces.
    """
    _name = "health.province"
    _description = "Vietnamese Province/City"
    _order = "sequence, name"
    
    name = fields.Char(
        string="Province Name",
        required=True,
        help="English name of the province/city"
    )
    
    name_vietnamese = fields.Char(
        string="Vietnamese Name",
        required=True,
        help="Vietnamese name of the province/city"
    )
    
    code = fields.Char(
        string="Province Code",
        required=True,
        help="Short code for the province (e.g., HCM, HN, DN)"
    )
    
    region = fields.Selection([
        ('north', 'Northern Vietnam'),
        ('central', 'Central Vietnam'), 
        ('south', 'Southern Vietnam'),
    ], string='Region', required=True, default='south',
       help='Geographic region of Vietnam')
    
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Sequence for ordering provinces"
    )
    
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Is this province currently active?"
    )
    
    # Usage tracking
    usage_count = fields.Integer(
        string="Usage Count",
        compute="_compute_usage_count",
        help="Number of leads using this province"
    )
    
    @api.depends()
    def _compute_usage_count(self):
        """Compute usage count from CRM leads"""
        for province in self:
            count = self.env['crm.lead'].search_count([
                ('province_code', '=', province.id)
            ])
            province.usage_count = count
    
    def name_get(self):
        """Custom name_get to show code and both names"""
        result = []
        for record in self:
            if record.code:
                name = f"[{record.code}] {record.name} ({record.name_vietnamese})"
            else:
                name = f"{record.name} ({record.name_vietnamese})"
            result.append((record.id, name))
        return result
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Province code must be unique!'),
        ('name_unique', 'UNIQUE(name)', 'Province name must be unique!'),
    ]