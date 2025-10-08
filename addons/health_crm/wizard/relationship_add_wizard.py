# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RelationshipAddWizard(models.TransientModel):
    """Wizard to add a new relationship to a client/patient"""
    _name = 'health.relationship.add.wizard'
    _description = 'Add Relationship Wizard'

    # Pre-filled from context (readonly)
    client_id = fields.Many2one(
        'res.partner',
        string='Client/Patient',
        required=True,
        readonly=True,
        help='The patient receiving this relationship'
    )

    role = fields.Selection([
        ('caregiver', 'Caregiver'),
        ('payer', 'Payer'),
        ('referrer', 'Referrer'),
        ('emergency_contact', 'Emergency Contact'),
        ('legal_guardian', 'Legal Guardian'),
        ('client_representative', 'Client Representative'),
    ], string='Role', required=True, readonly=True,
       help='The role this representative will play')

    # Main selection field - Many2one with search and create
    representative_id = fields.Many2one(
        'res.partner',
        string='Representative',
        required=True,
        help='Select existing partner or create new one'
    )

    # Relationship details
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
       help='The personal or professional relationship type')

    is_primary = fields.Boolean(
        string='Primary for this Role',
        default=False,
        help='Mark as the primary contact for this role'
    )

    # Healthcare permissions
    can_make_medical_decisions = fields.Boolean(
        string='Can Make Medical Decisions',
        default=False,
        help='Authorized to make medical decisions for the patient'
    )

    can_receive_medical_info = fields.Boolean(
        string='Can Receive Medical Information',
        default=False,
        help='Authorized to receive patient medical information'
    )

    can_schedule_appointments = fields.Boolean(
        string='Can Schedule Appointments',
        default=False,
        help='Can schedule appointments on behalf of the patient'
    )

    # Financial responsibility
    financial_responsibility = fields.Float(
        string='Financial Responsibility %',
        default=0.0,
        help='Percentage of financial responsibility (0-100%)'
    )

    # Computed display fields
    client_name = fields.Char(
        string='Client Name',
        related='client_id.name',
        readonly=True
    )

    role_label = fields.Char(
        string='Role',
        compute='_compute_role_label',
        readonly=True
    )

    @api.depends('role')
    def _compute_role_label(self):
        """Get human-readable role label"""
        for record in self:
            if record.role:
                record.role_label = dict(record._fields['role'].selection).get(record.role, record.role)
            else:
                record.role_label = ''

    @api.model
    def default_get(self, fields_list):
        """Set defaults from context"""
        res = super().default_get(fields_list)

        # Get values from context
        if 'default_client_id' in self.env.context:
            res['client_id'] = self.env.context['default_client_id']

        if 'default_role' in self.env.context:
            res['role'] = self.env.context['default_role']

            # Auto-populate permissions based on role
            role = self.env.context['default_role']
            if role == 'legal_guardian':
                res['can_make_medical_decisions'] = True
                res['can_receive_medical_info'] = True
                res['can_schedule_appointments'] = True
            elif role in ['emergency_contact', 'caregiver']:
                res['can_receive_medical_info'] = True
                if role == 'caregiver':
                    res['can_schedule_appointments'] = True
            elif role == 'payer':
                res['financial_responsibility'] = 100.0

        return res

    @api.onchange('role')
    def _onchange_role_set_defaults(self):
        """Update permission defaults when role changes"""
        if self.role == 'legal_guardian':
            self.can_make_medical_decisions = True
            self.can_receive_medical_info = True
            self.can_schedule_appointments = True
        elif self.role in ['emergency_contact', 'caregiver']:
            self.can_receive_medical_info = True
            if self.role == 'caregiver':
                self.can_schedule_appointments = True
        elif self.role == 'payer':
            self.financial_responsibility = 100.0

    def action_create_relationship(self):
        """Create the relationship record"""
        self.ensure_one()

        if not self.representative_id:
            raise ValidationError(_('Please select a representative.'))

        if self.client_id.id == self.representative_id.id:
            raise ValidationError(_('A person cannot be their own representative.'))

        # Check for existing relationship
        existing = self.env['health.client.relation'].search([
            ('client_id', '=', self.client_id.id),
            ('representative_id', '=', self.representative_id.id),
            ('role', '=', self.role),
            ('active', '=', True),
        ])

        if existing:
            raise ValidationError(_(
                'A relationship already exists between %s and %s for role %s.'
            ) % (self.client_id.name, self.representative_id.name, self.role_label))

        # Ensure representative has is_representative flag
        if not self.representative_id.is_representative:
            self.representative_id.write({'is_representative': True})

        # Create the relationship
        relation_vals = {
            'client_id': self.client_id.id,
            'representative_id': self.representative_id.id,
            'role': self.role,
            'relationship_type': self.relationship_type,
            'is_primary': self.is_primary,
            'can_make_medical_decisions': self.can_make_medical_decisions,
            'can_receive_medical_info': self.can_receive_medical_info,
            'can_schedule_appointments': self.can_schedule_appointments,
            'financial_responsibility': self.financial_responsibility,
        }

        self.env['health.client.relation'].create(relation_vals)

        # Show notification and close wizard
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Relationship Added'),
                'message': _('%s added as %s for %s') % (
                    self.representative_id.name,
                    self.role_label,
                    self.client_id.name
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
