# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HealthClientRelation(models.Model):
    """
    Healthcare Client ↔ Representative Relationship Model
    
    Models the relationships between patients (clients) and their representatives
    (caregivers, payers, referrers, emergency contacts, etc.) in a flexible M:N structure.
    
    Based on Odoo best practices for relationship modeling using association tables.
    """
    _name = "health.client.relation"
    _inherit = ['health.lifecycle.mixin']
    _description = "Healthcare Client ↔ Representative Relationship"
    _rec_name = "display_name"
    _order = "client_id, role, is_primary desc, id"

    # Core relationship fields
    client_id = fields.Many2one(
        "res.partner",
        string="Client/Patient",
        required=True,
        domain=[("is_patient", "=", True)],
        ondelete="cascade",
        help='Client/client in this relationship'
    )
    
    representative_id = fields.Many2one(
        "res.partner",
        string="Representative",
        required=True,
        domain=[("is_representative", "=", True)],
        ondelete="restrict",
        help="The person representing or supporting the client"
    )

    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Area',
        compute='_compute_catchment_province_id',
        store=True,
        readonly=True,
        help='Catchment area used for filtering and access control'
    )

    @api.depends('client_id.catchment_province_id', 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for relation in self:
            relation.catchment_province_id = (
                relation.client_id._get_health_catchment_province()
                if relation.client_id
                else False
            )
    
    # Healthcare role classification - Limited to 6 essential roles
    role = fields.Selection([
        ('caregiver', 'Caregiver'),
        ('payer', 'Payer'),
        ('referrer', 'Referrer'),
        ('emergency_contact', 'Emergency Contact'),
        ('legal_guardian', 'Legal Guardian'),
        ('client_representative', 'Client Representative'),
    ], string="Role", required=True, default='client_representative',
       help="The role this representative plays for the client")
    
    # Relationship type (family/professional relationship)
    relationship_type = fields.Selection([
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('sibling', 'Sibling'),
        ('grandparent', 'Grandparent'),
        ('grandchild', 'Grandchild'),
        ('relative', 'Other Relative'),
        ('professional', 'Professional Service Provider'),
        ('friend', 'Friend'),
        ('neighbor', 'Neighbor'),
        ('other', 'Other'),
    ], string='Relationship Type', 
       help="The personal or professional relationship type")
    
    # Primary contact designation
    is_primary = fields.Boolean(
        string="Primary for this Role",
        default=False,
        help="Is this the primary contact for this specific role?"
    )
    
    # Date range for relationship validity
    start_date = fields.Date(
        string="Start Date",
        default=fields.Date.today,
        help="When this relationship started"
    )
    
    end_date = fields.Date(
        string="End Date",
        help="When this relationship ended (if applicable)"
    )
    
    # Healthcare-specific permissions
    can_make_medical_decisions = fields.Boolean(
        string="Can Make Medical Decisions",
        default=False,
        help='Can make medical decisions for the client'
    )
    
    can_receive_medical_info = fields.Boolean(
        string="Can Receive Medical Information",
        default=False,
        help='Can receive medical information about the client'
    )
    
    can_schedule_appointments = fields.Boolean(
        string="Can Schedule Appointments",
        default=False,
        help='Can schedule appointments for the client'
    )
    
    # Financial responsibility
    financial_responsibility = fields.Float(
        string="Financial Responsibility %",
        default=0.0,
        help="Percentage of financial responsibility (0-100%)"
    )
    
    # Contact priority
    priority_order = fields.Integer(
        string="Contact Priority Order",
        default=10,
        help="Contact priority order (1=highest priority)"
    )
    
    # Vietnamese healthcare compliance fields
    legal_document_type = fields.Selection([
        ('family_book', 'Family Registration Book (Sổ hộ khẩu)'),
        ('birth_certificate', 'Birth Certificate (Giấy khai sinh)'),
        ('marriage_certificate', 'Marriage Certificate (Giấy đăng ký kết hôn)'),
        ('power_of_attorney', 'Power of Attorney (Giấy ủy quyền)'),
        ('guardianship_order', 'Guardianship Order (Lệnh giám hộ)'),
        ('id_card', 'National ID Card (CCCD/CMND)'),
        ('other', 'Other Legal Document'),
    ], string='Legal Document Type',
       help="Type of legal document establishing this relationship")
    
    legal_document_number = fields.Char(
        string="Legal Document Number",
        help="Document number or reference"
    )
    
    issued_by = fields.Char(
        string="Issued By",
        help="Authority that issued the legal document"
    )
    
    issued_date = fields.Date(
        string="Document Issue Date",
        help="Date the legal document was issued"
    )
    
    # Additional notes
    notes = fields.Text(
        string="Notes",
        help="Additional notes about this relationship"
    )
    
    # Computed display name
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=False,
        help="Computed display name for this relationship"
    )
    
    # Status tracking
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Is this relationship currently active?"
    )

    # SQL constraints
    _sql_constraints = [
        ('check_financial_responsibility', 
         'CHECK(financial_responsibility >= 0 AND financial_responsibility <= 100)',
         'Financial responsibility must be between 0 and 100%.'),
        ('check_priority_positive',
         'CHECK(priority_order > 0)',
         'Priority order must be a positive number.'),
        ('check_different_partners',
         'CHECK(client_id != representative_id)',
         'A person cannot be their own representative.'),
    ]

    @api.depends("client_id", "representative_id", "role", "relationship_type")
    def _compute_display_name(self):
        """Compute a meaningful display name for the relationship"""
        for record in self:
            client_name = record.client_id.name or "Unknown Client"
            rep_name = record.representative_id.name or "Unknown Representative" 
            role_label = dict(record._fields['role'].selection).get(record.role, record.role)
            
            if record.relationship_type:
                rel_type_label = dict(record._fields['relationship_type'].selection).get(
                    record.relationship_type, record.relationship_type)
                record.display_name = f"{client_name} ↔ {rep_name} ({role_label} - {rel_type_label})"
            else:
                record.display_name = f"{client_name} ↔ {rep_name} ({role_label})"

    @api.constrains('client_id', 'representative_id', 'role', 'is_primary', 'active')
    def _check_unique_primary_per_role(self):
        """Ensure only one primary representative per role per client"""
        for record in self:
            if record.is_primary and record.active:
                existing_primary = self.search([
                    ('client_id', '=', record.client_id.id),
                    ('role', '=', record.role),
                    ('is_primary', '=', True),
                    ('active', '=', True),
                    ('id', '!=', record.id),
                ])
                if existing_primary:
                    raise ValidationError(_(
                        'Only one primary %s is allowed per client. '
                        'Please remove the primary designation from %s first.'
                    ) % (
                        dict(record._fields['role'].selection).get(record.role, record.role),
                        existing_primary[0].representative_id.name
                    ))

    @api.constrains('start_date', 'end_date')
    def _check_date_consistency(self):
        """Ensure end date is after start date"""
        for record in self:
            if record.start_date and record.end_date:
                if record.end_date < record.start_date:
                    raise ValidationError(_('End date cannot be before start date.'))

    @api.onchange('role')
    def _onchange_role_set_defaults(self):
        """Set default permissions based on role"""
        if self.role == 'legal_guardian':
            self.can_make_medical_decisions = True
            self.can_receive_medical_info = True
            self.can_schedule_appointments = True
        elif self.role == 'healthcare_proxy':
            self.can_make_medical_decisions = True
            self.can_receive_medical_info = True
        elif self.role == 'emergency_contact':
            self.can_receive_medical_info = True
        elif self.role == 'payer':
            self.financial_responsibility = 100.0
            
    @api.model
    def get_primary_contact_by_role(self, client_id, role):
        """Get the primary contact for a specific role and client"""
        return self.search([
            ('client_id', '=', client_id),
            ('role', '=', role),
            ('is_primary', '=', True),
            ('active', '=', True),
        ], limit=1)
    
    def action_set_as_primary(self):
        """Set this relationship as primary for its role"""
        self.ensure_one()
        # First remove primary from other relationships of same role
        other_primary = self.search([
            ('client_id', '=', self.client_id.id),
            ('role', '=', self.role),
            ('is_primary', '=', True),
            ('active', '=', True),
            ('id', '!=', self.id),
        ])
        other_primary.write({'is_primary': False})
        
        # Set this one as primary
        self.is_primary = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%s is now the primary %s for %s') % (
                    self.representative_id.name,
                    dict(self._fields['role'].selection).get(self.role, self.role),
                    self.client_id.name
                ),
                'type': 'success',
            }
        }
