# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HealthLeadReason(models.Model):
    """
    Healthcare Lead Reason Model
    
    Lookup table for lead reasons used in CRM opportunities.
    Different from contact_reason - this is for opportunity-specific reasons.
    Based on Excel requirements for lead_reason field.
    """
    _name = "health.lead.reason"
    _description = "Healthcare Lead Reason"
    _order = "sequence, name"
    
    name = fields.Char(
        string="Reason Name",
        required=True,
        help="Name of the lead reason"
    )
    
    code = fields.Char(
        string="Reason Code",
        help="Short code for the lead reason"
    )
    
    description = fields.Text(
        string="Description",
        help="Detailed description of when to use this reason"
    )
    
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Sequence for ordering reasons"
    )
    
    category = fields.Selection([
        ('service_interest', 'Service Interest'),
        ('referral', 'Referral'),
        ('marketing', 'Marketing Campaign'),
        ('website', 'Website Inquiry'),
        ('social_media', 'Social Media'),
        ('event', 'Health Event/Fair'),
        ('emergency', 'Emergency Need'),
        ('follow_up', 'Follow-up Opportunity'),
        ('other', 'Other'),
    ], string='Category', default='service_interest',
       help='Category of lead reason for reporting purposes')
    
    lead_type = fields.Selection([
        ('lead', 'Lead'),
        ('opportunity', 'Opportunity'), 
        ('both', 'Both'),
    ], string='Applicable To', default='both',
       help='Whether this reason applies to leads, opportunities, or both')
    
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Is this reason currently active?"
    )
    
    # Vietnamese specific fields
    name_vietnamese = fields.Char(
        string="Vietnamese Name",
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
                ('lead_reason_id', '=', reason.id)
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