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

    client_phone = fields.Char(
        related='client_id.phone', string='Client Phone', readonly=True)
    client_email = fields.Char(
        related='client_id.email', string='Client Email', readonly=True)
    representative_phone = fields.Char(
        related='representative_id.phone', string='Representative Phone',
        readonly=True)
    representative_email = fields.Char(
        related='representative_id.email', string='Representative Email',
        readonly=True)
    
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
    relationship_type_id = fields.Many2one(
        'health.lookup.value',
        string='Relationship Type',
        domain="[('category_code', '=', 'relationship_type'), ('active', '=', True)]",
        ondelete='restrict',
        help='The personal or professional relationship type')
    # Companion for view expressions and domains: an Odoo view attribute
    # (invisible=, decoration-, domain=) cannot traverse a many2one, and
    # this keeps every existing comparison a one-word change.
    relationship_type_code = fields.Char(
        related='relationship_type_id.code', string='Relationship Type Code', readonly=True)
    
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

    relationship_status = fields.Selection([
        ('active', 'Active'),
        ('scheduled', 'Scheduled'),
        ('ended', 'Ended'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ], string='Status', compute='_compute_relationship_status')
    authority_summary = fields.Char(
        string='Delegated Authority', compute='_compute_authority_summary')

    @api.depends('active', 'deleted', 'start_date', 'end_date')
    def _compute_relationship_status(self):
        today = fields.Date.context_today(self)
        for relation in self:
            if relation.deleted:
                relation.relationship_status = 'deleted'
            elif not relation.active:
                relation.relationship_status = 'archived'
            elif relation.end_date and relation.end_date < today:
                relation.relationship_status = 'ended'
            elif relation.start_date and relation.start_date > today:
                relation.relationship_status = 'scheduled'
            else:
                relation.relationship_status = 'active'

    @api.depends(
        'can_make_medical_decisions', 'can_receive_medical_info',
        'can_schedule_appointments', 'financial_responsibility')
    def _compute_authority_summary(self):
        for relation in self:
            labels = []
            if relation.can_make_medical_decisions:
                labels.append(_('Medical decisions'))
            if relation.can_receive_medical_info:
                labels.append(_('Medical information'))
            if relation.can_schedule_appointments:
                labels.append(_('Scheduling'))
            if relation.financial_responsibility:
                labels.append(_(
                    '%s%% financial', '%g' % relation.financial_responsibility))
            relation.authority_summary = ' · '.join(labels) or _('No delegated authority')

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

    @api.depends("client_id", "representative_id", "role", "relationship_type_id")
    def _compute_display_name(self):
        """Compute a meaningful display name for the relationship"""
        for record in self:
            client_name = record.client_id.name or "Unknown Client"
            rep_name = record.representative_id.name or "Unknown Representative" 
            role_label = dict(record._fields['role'].selection).get(record.role, record.role)
            
            if record.relationship_type_id:
                rel_type_label = record.relationship_type_id.name or ''
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
