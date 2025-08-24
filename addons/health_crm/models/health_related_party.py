# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HealthRelatedParty(models.Model):
    """
    Healthcare Related Party Management
    Links patients with caregivers, payers, and referrers
    """
    _name = 'health.related.party'
    _description = 'Healthcare Related Party'
    _rec_name = 'display_name'
    _order = 'client_id, relationship_type, partner_id'

    # Core relationship
    client_id = fields.Many2one(
        'res.partner',
        string='Client/Patient',
        required=True,
        help='The patient or client'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Related Person',
        required=True,
        help='The caregiver, payer, or referrer'
    )

    relationship_type = fields.Selection([
        ('caregiver', 'Caregiver'),
        ('payer', 'Payer'),
        ('referrer', 'Referrer'),
        ('emergency_contact', 'Emergency Contact'),
        ('family_member', 'Family Member'),
        ('legal_guardian', 'Legal Guardian'),
    ], string='Relationship Type', required=True)

    # Caregiver-specific fields
    caregiver_id = fields.Many2one(
        'res.partner',
        string='Caregiver',
        compute='_compute_relationship_partners',
        store=True,
        help='Caregiver partner (computed)'
    )

    caregiver_relationship = fields.Selection([
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('sibling', 'Sibling'),
        ('relative', 'Other Relative'),
        ('friend', 'Friend'),
        ('professional', 'Professional Caregiver'),
        ('volunteer', 'Volunteer'),
    ], string='Caregiver Relationship')

    caregiver_availability = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('on_call', 'On Call'),
        ('emergency_only', 'Emergency Only'),
    ], string='Caregiver Availability')

    caregiver_notes = fields.Text('Caregiver Notes')

    # Payer-specific fields
    payer_id = fields.Many2one(
        'res.partner',
        string='Payer',
        compute='_compute_relationship_partners',
        store=True,
        help='Payer partner (computed)'
    )

    payer_relationship = fields.Selection([
        ('self', 'Self Pay'),
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('insurance', 'Insurance'),
        ('government', 'Government'),
        ('employer', 'Employer'),
        ('other', 'Other'),
    ], string='Payer Relationship')

    payment_responsibility = fields.Selection([
        ('primary', 'Primary Payer'),
        ('secondary', 'Secondary Payer'),
        ('emergency', 'Emergency Payer'),
    ], string='Payment Responsibility', default='primary')

    tax_id_number = fields.Char('Tax ID Number')
    insurance_policy_number = fields.Char('Insurance Policy Number')
    payer_notes = fields.Text('Payer Notes')

    # Referrer-specific fields
    referrer_id = fields.Many2one(
        'res.partner',
        string='Referrer',
        compute='_compute_relationship_partners',
        store=True,
        help='Referrer partner (computed)'
    )

    referrer_type = fields.Selection([
        ('patient', 'Existing Patient'),
        ('family', 'Family Member'),
        ('friend', 'Friend'),
        ('doctor', 'Doctor/Medical Professional'),
        ('clinic', 'Clinic/Hospital'),
        ('community', 'Community Leader'),
        ('online', 'Online Review/Social Media'),
    ], string='Referrer Type')

    referral_date = fields.Date('Referral Date', default=fields.Date.today)
    commission_rate = fields.Float('Commission Rate (%)', help='Commission percentage for referrals')
    referral_notes = fields.Text('Referral Notes')

    # Status and validity
    is_active = fields.Boolean('Active', default=True)
    start_date = fields.Date('Start Date', default=fields.Date.today)
    end_date = fields.Date('End Date')

    # Contact information override
    alternative_phone = fields.Char('Alternative Phone')
    alternative_email = fields.Char('Alternative Email')
    contact_notes = fields.Text('Contact Notes')

    # Display name
    display_name = fields.Char(
        'Display Name',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('relationship_type', 'partner_id')
    def _compute_relationship_partners(self):
        """Compute specific relationship partner fields"""
        for record in self:
            # Reset all relationship fields
            record.caregiver_id = False
            record.payer_id = False
            record.referrer_id = False
            
            # Set the appropriate field based on relationship type
            if record.relationship_type == 'caregiver':
                record.caregiver_id = record.partner_id.id
            elif record.relationship_type == 'payer':
                record.payer_id = record.partner_id.id
            elif record.relationship_type == 'referrer':
                record.referrer_id = record.partner_id.id

    @api.depends('client_id', 'partner_id', 'relationship_type')
    def _compute_display_name(self):
        """Compute display name for the relationship"""
        for record in self:
            if record.client_id and record.partner_id and record.relationship_type:
                record.display_name = f"{record.partner_id.name} ({record.relationship_type}) → {record.client_id.name}"
            else:
                record.display_name = 'New Healthcare Relationship'

    @api.constrains('client_id', 'partner_id')
    def _check_different_partners(self):
        """Ensure client and related person are different"""
        for record in self:
            if record.client_id == record.partner_id:
                raise ValidationError(_('Client and related person must be different contacts.'))

    @api.constrains('client_id', 'partner_id', 'relationship_type')
    def _check_unique_relationship(self):
        """Ensure unique relationships per client-partner-type combination"""
        for record in self:
            domain = [
                ('client_id', '=', record.client_id.id),
                ('partner_id', '=', record.partner_id.id),
                ('relationship_type', '=', record.relationship_type),
                ('id', '!=', record.id),
            ]
            if self.search(domain):
                raise ValidationError(_(
                    'A %s relationship already exists between %s and %s.'
                ) % (record.relationship_type, record.partner_id.name, record.client_id.name))

    @api.model
    def create(self, vals):
        """Override create to update partner flags"""
        record = super().create(vals)
        record._update_partner_flags()
        return record

    def write(self, vals):
        """Override write to update partner flags"""
        result = super().write(vals)
        if 'relationship_type' in vals or 'partner_id' in vals:
            for record in self:
                record._update_partner_flags()
        return result

    def unlink(self):
        """Override unlink to update partner flags"""
        partners_to_update = self.mapped('partner_id')
        result = super().unlink()
        for partner in partners_to_update:
            partner._update_healthcare_flags()
        return result

    def _update_partner_flags(self):
        """Update healthcare flags on the related partner"""
        self.ensure_one()
        if self.partner_id:
            self.partner_id._update_healthcare_flags()

    def action_view_client_appointments(self):
        """View appointments for this client"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Client Appointments'),
            'res_model': 'health.appointment',
            'view_mode': 'tree,form',
            'domain': [('patient_id.partner_id', '=', self.client_id.id)],
            'context': {'default_patient_id': self.client_id.id},
        }

    def action_view_client_invoices(self):
        """View invoices for this client"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Client Invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [
                ('partner_id', '=', self.client_id.id),
                ('move_type', 'in', ['out_invoice', 'out_refund'])
            ],
            'context': {'default_partner_id': self.client_id.id},
        }


class ResPartnerHealthcareFlags(models.Model):
    """
    Extension to res.partner to update healthcare flags
    """
    _inherit = 'res.partner'

    def _update_healthcare_flags(self):
        """Update healthcare relationship flags based on related party records"""
        for partner in self:
            # Check if this partner is a caregiver for anyone
            partner.is_caregiver = bool(self.env['health.related.party'].search([
                ('partner_id', '=', partner.id),
                ('relationship_type', '=', 'caregiver'),
                ('is_active', '=', True)
            ], limit=1))
            
            # Check if this partner is a payer for anyone
            partner.is_payer = bool(self.env['health.related.party'].search([
                ('partner_id', '=', partner.id),
                ('relationship_type', '=', 'payer'),
                ('is_active', '=', True)
            ], limit=1))
            
            # Check if this partner is a referrer for anyone
            partner.is_referrer = bool(self.env['health.related.party'].search([
                ('partner_id', '=', partner.id),
                ('relationship_type', '=', 'referrer'),
                ('is_active', '=', True)
            ], limit=1))