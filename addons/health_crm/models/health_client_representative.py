# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HealthClientRepresentative(models.Model):
    """
    Client Representative Table (FROM EXCEL REQUIREMENTS)
    Person making contact on behalf of client
    """
    _name = 'health.client.representative'
    _description = 'Healthcare Client Representative'
    _rec_name = 'representative_name'
    _order = 'contact_id, representative_name'

    # Core fields from Excel
    contact_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        help='Links to contact (from Excel: contact_id [Compulsory])'
    )

    representative_name = fields.Char(
        'Representative Name',
        help='From Excel: Representative Name [Optional]'
    )

    kinship_title = fields.Char(
        'Kinship Title',
        help='From Excel: Kinship Title [Optional] - Vietnamese honorific'
    )

    preferred_name = fields.Char(
        'Preferred Name',
        help='From Excel: Preferred Name [Optional]'
    )

    relationship = fields.Selection([
        ('is_client', 'Is Client'),
        ('relative', 'Relative'),
        ('friend', 'Friend'),
        ('other', 'Other')
    ], string='Relationship', help='From Excel: Relationship [Optional]')

    # Contact information from Excel
    representative_phone_1 = fields.Char(
        'Representative Phone No 1',
        help='From Excel: Representative Phone No 1 [Optional]'
    )

    representative_phone_2 = fields.Char(
        'Representative Phone No 2', 
        help='From Excel: Representative Phone No 2 [Optional]'
    )

    email = fields.Char(
        'Email',
        help='From Excel: email [Optional]'
    )

    zalo = fields.Char(
        'Zalo',
        help='From Excel: Zalo [Optional] - Vietnamese messaging app'
    )

    # Status tracking from Excel
    details_complete = fields.Boolean(
        'Details Complete',
        help='From Excel: Details Complete [Optional] - Triggers follow-up if No',
        default=False
    )

    # Additional fields for functionality
    is_primary = fields.Boolean(
        'Primary Representative',
        help='Is this the primary representative for the contact?',
        default=False
    )

    notes = fields.Text(
        'Notes',
        help='Additional notes about this representative'
    )

    active = fields.Boolean(
        'Active',
        default=True,
        help='Is this representative relationship active?'
    )

    @api.constrains('contact_id', 'is_primary')
    def _check_single_primary_representative(self):
        """Ensure only one primary representative per contact"""
        for record in self:
            if record.is_primary:
                primary_count = self.search_count([
                    ('contact_id', '=', record.contact_id.id),
                    ('is_primary', '=', True),
                    ('id', '!=', record.id),
                    ('active', '=', True)
                ])
                if primary_count > 0:
                    raise ValidationError(_(
                        'Contact %s already has a primary representative. '
                        'Please uncheck the other primary representative first.'
                    ) % record.contact_id.name)

    @api.model
    def create(self, vals):
        """Auto-calculate details_complete based on required fields"""
        record = super().create(vals)
        record._compute_details_complete()
        return record

    def write(self, vals):
        """Re-calculate details_complete when fields change"""
        result = super().write(vals)
        if any(field in vals for field in ['representative_name', 'representative_phone_1', 'email', 'relationship']):
            for record in self:
                record._compute_details_complete()
        return result

    def _compute_details_complete(self):
        """Calculate if representative details are complete (triggers follow-up if No)"""
        for record in self:
            # Basic completeness check - customize based on business rules
            required_fields = [
                record.representative_name,
                record.relationship,
                record.representative_phone_1 or record.email  # At least one contact method
            ]
            record.details_complete = all(required_fields)

    def action_set_as_primary(self):
        """Set this representative as primary for the contact"""
        self.ensure_one()
        
        # Remove primary flag from other representatives of same contact
        other_primaries = self.search([
            ('contact_id', '=', self.contact_id.id),
            ('id', '!=', self.id),
            ('is_primary', '=', True)
        ])
        other_primaries.write({'is_primary': False})
        
        # Set this as primary
        self.write({'is_primary': True})

    def action_create_followup_activity(self):
        """Create follow-up activity for incomplete details"""
        self.ensure_one()
        
        if self.details_complete:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Representative details are already complete.'),
                    'type': 'info',
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Complete Representative Details'),
            'res_model': 'mail.activity',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_id': self.contact_id.id,
                'default_res_model': 'res.partner',
                'default_summary': f'Complete details for representative: {self.representative_name or "Unnamed"}',
                'default_note': f'Representative details incomplete. Missing: {self._get_missing_details()}',
                'default_date_deadline': fields.Date.today(),
            }
        }

    def _get_missing_details(self):
        """Get list of missing details for follow-up"""
        missing = []
        if not self.representative_name:
            missing.append('Name')
        if not self.relationship:
            missing.append('Relationship')
        if not self.representative_phone_1 and not self.email:
            missing.append('Contact information (phone or email)')
        return ', '.join(missing)


class ResPartnerRepresentativeExtension(models.Model):
    """
    Extension to res.partner to link with representatives
    """
    _inherit = 'res.partner'

    # Client Representative relationship (FROM EXCEL)
    client_representative_ids = fields.One2many(
        'health.client.representative',
        'contact_id',
        string='Client Representatives',
        help='People who can represent this contact (from Excel Client Representative table)'
    )

    # Primary representative (FROM EXCEL: client_representative_id [Compulsory])
    primary_representative_id = fields.Many2one(
        'health.client.representative',
        string='Primary Representative',
        help='From Excel: client_representative_id [Compulsory]',
        compute='_compute_primary_representative',
        store=True
    )

    @api.depends('client_representative_ids.is_primary')
    def _compute_primary_representative(self):
        """Compute primary representative"""
        for partner in self:
            primary = partner.client_representative_ids.filtered(
                lambda r: r.is_primary and r.active
            )
            partner.primary_representative_id = primary[0] if primary else False

    def action_create_representative(self):
        """Create a new representative for this contact"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Client Representative'),
            'res_model': 'health.client.representative',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contact_id': self.id,
                'default_is_primary': not self.client_representative_ids,  # First rep is primary
            }
        }