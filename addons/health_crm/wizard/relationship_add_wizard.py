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
        help='client receiving this relationship'
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
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Alternative Telephone')
    zalo_number = fields.Char(string='Zalo Number')
    vat = fields.Char(string='Tax Number')
    invoice_legal_name = fields.Char(string='Legal Name for Invoice')
    bank_number = fields.Char(string='Bank Number')
    account_number = fields.Char(string='Account Number')
    payer_code = fields.Char(string='Payer ID')
    referrer_code = fields.Char(string='Referrer ID')
    contract_number = fields.Char(string='Contract Number')
    referral_commission = fields.Float(string='Referral Commission')
    availability_notes = fields.Text(string='Availability Notes')
    representative_vietnamese_address = fields.Text(
        string='Home Address',
        related='representative_id.vietnamese_address',
        readonly=True,
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
        help='client'
    )

    can_receive_medical_info = fields.Boolean(
        string='Can Receive Medical Information',
        default=False,
        help='client medical information'
    )

    can_schedule_appointments = fields.Boolean(
        string='Can Schedule Appointments',
        default=False,
        help='client'
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

    @api.onchange('representative_id')
    def _onchange_representative_id(self):
        if not self.representative_id:
            self.phone = False
            self.mobile = False
            self.zalo_number = False
            self.vat = False
            self.invoice_legal_name = False
            self.bank_number = False
            self.account_number = False
            self.payer_code = False
            self.referrer_code = False
            self.contract_number = False
            self.referral_commission = 0.0
            self.availability_notes = False
            return

        partner = self.representative_id
        self.phone = partner.phone
        self.mobile = partner.mobile
        self.zalo_number = partner.zalo_number
        self.vat = partner.vat
        self.invoice_legal_name = partner.invoice_legal_name
        self.bank_number = partner.bank_number
        self.account_number = partner.account_number
        self.payer_code = partner.payer_code
        self.referrer_code = partner.referrer_code
        self.contract_number = partner.contract_number
        self.referral_commission = partner.referral_commission
        self.availability_notes = partner.availability_notes

    @api.onchange('role', 'representative_id')
    def _onchange_role_generate_codes(self):
        self._ensure_representative_codes()

    def _ensure_representative_codes(self):
        if not self.representative_id or not self.role:
            return

        if self.role in ['caregiver', 'payer', 'referrer'] and not self.representative_id.payer_code:
            self.representative_id.payer_code = self._next_sequence(
                code='health_crm.payer_code',
                name='Payer ID',
                prefix='PAY-',
            )

        if self.role == 'referrer' and not self.representative_id.referrer_code:
            self.representative_id.referrer_code = self._next_sequence(
                code='health_crm.referrer_code',
                name='Referrer ID',
                prefix='REF-',
            )

        self.payer_code = self.representative_id.payer_code
        self.referrer_code = self.representative_id.referrer_code

    def _next_sequence(self, code, name, prefix):
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', code)
        ], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': name,
                'code': code,
                'implementation': 'standard',
                'prefix': prefix,
                'padding': 5,
                'number_increment': 1,
                'number_next': 1,
            })
        return sequence.next_by_id()

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

    def action_edit_representative_address(self):
        self.ensure_one()
        if not self.representative_id:
            raise ValidationError(_('Please select a representative first.'))
        return self.representative_id.action_edit_vietnamese_address()

    def _get_representative_update_vals(self):
        if self.role in ['caregiver', 'payer', 'referrer']:
            vals = {
                'phone': self.phone,
                'zalo_number': self.zalo_number,
                'vat': self.vat,
                'invoice_legal_name': self.invoice_legal_name,
                'bank_number': self.bank_number,
                'account_number': self.account_number,
                'payer_code': self.payer_code,
            }
            if self.role == 'referrer':
                vals.update({
                    'referrer_code': self.referrer_code,
                    'contract_number': self.contract_number,
                    'referral_commission': self.referral_commission,
                })
            return vals

        if self.role in ['emergency_contact', 'legal_guardian', 'client_representative']:
            return {
                'phone': self.phone,
                'zalo_number': self.zalo_number,
                'mobile': self.mobile,
                'availability_notes': self.availability_notes,
            }

        return {}

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

        self._ensure_representative_codes()
        update_vals = self._get_representative_update_vals()
        if update_vals:
            self.representative_id.write(update_vals)

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
