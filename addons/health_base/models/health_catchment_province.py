# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HealthCatchmentProvince(models.Model):
    """
    Healthcare Catchment Province
    
    A catchment province represents a geographic service area for healthcare operations.
    Multiple healthcare facilities can belong to one catchment province.
    This model is used for:
    - User assignment (which catchment area a user serves)
    - Client/Patient assignment (which catchment area a patient belongs to)
    - Contact wizard (initial contact province selection)
    """
    _name = "health.catchment.province"
    _description = "Healthcare Catchment Province"
    _order = "sequence, name"
    
    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
        help="Name of the catchment province/area"
    )
    
    description = fields.Text(
        string="Description",
        translate=True,
        help="Description of this catchment province/area"
    )
    
    code = fields.Char(
        string="Province Code",
        size=10,
        help="Short code for the province (e.g., HCM, HN, DN). Used for patient ID generation."
    )
    
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Sequence for ordering provinces"
    )
    
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Is this catchment province currently active?"
    )

    timezone = fields.Selection(
        '_get_timezone_list',
        string="Timezone",
        default='Asia/Ho_Chi_Minh',
        help="Default timezone for this catchment province. "
             "Copied to facilities when they select this province."
    )

    @api.model
    def _get_timezone_list(self):
        """Get timezone list for the region"""
        return [
            ('Asia/Ho_Chi_Minh', 'Ho Chi Minh City (GMT+7)'),
            ('Asia/Hanoi', 'Hanoi (GMT+7)'),
            ('Asia/Bangkok', 'Bangkok (GMT+7)'),
            ('UTC', 'UTC (GMT+0)'),
        ]
    
    # Relationship to facilities
    facility_ids = fields.One2many(
        'health.facility',
        'catchment_province_id',
        string='Facilities',
        help='Healthcare facilities in this catchment province'
    )
    
    facility_count = fields.Integer(
        string="Facility Count",
        compute="_compute_facility_count",
        help="Number of facilities in this catchment province"
    )
    
    # Usage tracking
    user_count = fields.Integer(
        string="User Count",
        compute="_compute_usage_counts",
        help="Number of users assigned to this catchment province"
    )
    
    client_count = fields.Integer(
        string="Client Count",
        compute="_compute_usage_counts",
        help="Number of clients/patients in this catchment province"
    )
    
    @api.depends('facility_ids')
    def _compute_facility_count(self):
        """Compute number of facilities in this catchment province"""
        for record in self:
            record.facility_count = len(record.facility_ids)
    
    @api.depends()
    def _compute_usage_counts(self):
        """Compute usage counts from users and clients"""
        for record in self:
            # Count users assigned to this catchment province
            user_count = self.env['res.users'].search_count([
                ('catchment_province_id', '=', record.id)
            ])
            record.user_count = user_count
            
            # Count clients/patients in this catchment province
            client_count = self.env['res.partner'].search_count([
                ('catchment_province_id', '=', record.id),
                ('is_patient', '=', True)
            ])
            record.client_count = client_count
    
    def name_get(self):
        """Custom name_get to show code if available"""
        result = []
        for record in self:
            if record.code:
                name = f"[{record.code}] {record.name}"
            else:
                name = record.name
            result.append((record.id, name))
        return result
    
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Catchment province name must be unique!'),
        ('code_unique', 'UNIQUE(code)', 'Catchment province code must be unique!'),
    ]
