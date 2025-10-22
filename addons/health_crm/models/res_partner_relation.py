from odoo import models, fields, api, _


class ResPartnerRelation(models.Model):
    """Extend res.partner with relationship dashboard fields (Section 2.2)"""
    _inherit = 'res.partner'

    # ========================================================================
    # RELATIONSHIP FIELDS (Section 2.2)
    # ========================================================================

    # One2many fields to health.client.relation
    patient_relation_ids = fields.One2many(
        'health.client.relation',
        'client_id',
        string='My Representatives',
        help='client'
    )
    representative_relation_ids = fields.One2many(
        'health.client.relation',
        'representative_id',
        string='My Patients',
        help='clients for whom I am a representative'
    )

    # Many2many shortcuts (computed from health.client.relation)
    caregiver_ids = fields.Many2many(
        'res.partner',
        compute='_compute_relationship_shortcuts',
        string='All Caregivers',
        help='client (primary + additional)'
    )
    payer_ids = fields.Many2many(
        'res.partner',
        compute='_compute_relationship_shortcuts',
        string='All Payers',
        help='client (primary + additional)'
    )
    referrer_ids = fields.Many2many(
        'res.partner',
        compute='_compute_relationship_shortcuts',
        string='All Referrers',
        help='client'
    )
    emergency_contact_ids = fields.Many2many(
        'res.partner',
        compute='_compute_relationship_shortcuts',
        string='All Emergency Contacts',
        help='client'
    )
    legal_guardian_ids = fields.Many2many(
        'res.partner',
        compute='_compute_relationship_shortcuts',
        string='All Legal Guardians',
        help='client'
    )

    # Computed count fields for smart buttons
    total_caregivers = fields.Integer(
        'Total Caregivers',
        compute='_compute_relationship_counts_extended',
        help='client'
    )
    total_payers = fields.Integer(
        'Total Payers',
        compute='_compute_relationship_counts_extended',
        help='client'
    )
    total_referrers = fields.Integer(
        'Total Referrers',
        compute='_compute_relationship_counts_extended',
        help='client'
    )
    total_emergency_contacts = fields.Integer(
        'Total Emergency Contacts',
        compute='_compute_relationship_counts_extended',
        help='client'
    )
    total_legal_guardians = fields.Integer(
        'Total Legal Guardians',
        compute='_compute_relationship_counts_extended',
        help='client'
    )
    relationship_total_count = fields.Integer(
        'Total Relationships',
        compute='_compute_relationship_counts_extended',
        help='Total number of all relationships for this person'
    )

    # ========================================================================
    # COMPUTE METHODS
    # ========================================================================

    @api.depends('patient_relation_ids', 'patient_relation_ids.role', 'patient_relation_ids.representative_id')
    def _compute_relationship_shortcuts(self):
        """Compute Many2many shortcut fields for all relationship types"""
        for partner in self:
            # Extract representatives by role from patient_relation_ids
            partner.caregiver_ids = partner.patient_relation_ids.filtered(
                lambda r: r.role == 'caregiver'
            ).mapped('representative_id')

            partner.payer_ids = partner.patient_relation_ids.filtered(
                lambda r: r.role == 'payer'
            ).mapped('representative_id')

            partner.referrer_ids = partner.patient_relation_ids.filtered(
                lambda r: r.role == 'referrer'
            ).mapped('representative_id')

            partner.emergency_contact_ids = partner.patient_relation_ids.filtered(
                lambda r: r.role == 'emergency_contact'
            ).mapped('representative_id')

            partner.legal_guardian_ids = partner.patient_relation_ids.filtered(
                lambda r: r.role == 'legal_guardian'
            ).mapped('representative_id')

    @api.depends('patient_relation_ids', 'patient_relation_ids.role',
                 'representative_relation_ids', 'representative_relation_ids.role')
    def _compute_relationship_counts_extended(self):
        """Compute healthcare relationship counts for smart buttons"""
        for partner in self:
            # Patient Side: Count MY caregivers, payers, etc.
            partner.total_caregivers = len(partner.patient_relation_ids.filtered(
                lambda r: r.role == 'caregiver'
            ))
            partner.total_payers = len(partner.patient_relation_ids.filtered(
                lambda r: r.role == 'payer'
            ))
            partner.total_referrers = len(partner.patient_relation_ids.filtered(
                lambda r: r.role == 'referrer'
            ))
            partner.total_emergency_contacts = len(partner.patient_relation_ids.filtered(
                lambda r: r.role == 'emergency_contact'
            ))
            partner.total_legal_guardians = len(partner.patient_relation_ids.filtered(
                lambda r: r.role == 'legal_guardian'
            ))

            # Total relationships (both sides)
            partner.relationship_total_count = len(partner.patient_relation_ids) + len(partner.representative_relation_ids)

    # ========================================================================
    # ACTION METHODS (Section 2.2)
    # ========================================================================

    def action_view_all_relationships(self):
        """View all relationships (both patient and representative sides)"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'All Relationships - {self.name}',
            'res_model': 'health.client.relation',
            'view_mode': 'kanban,list,form,graph,pivot,calendar',
            'target': 'current',
            'domain': ['|', ('client_id', '=', self.id), ('representative_id', '=', self.id)],
            'context': {
                'default_client_id': self.id if self.is_patient else False,
                'default_representative_id': self.id if not self.is_patient else False,
            }
        }

    def action_view_my_caregivers(self):
        """View all caregivers for this patient"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Caregivers - {self.name}',
            'res_model': 'health.client.relation',
            'view_mode': 'kanban,list,form',
            'target': 'current',
            'domain': [('client_id', '=', self.id), ('role', '=', 'caregiver')],
            'context': {
                'default_client_id': self.id,
                'default_role': 'caregiver',
            }
        }

    def action_view_my_payers(self):
        """View all payers for this patient"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Payers - {self.name}',
            'res_model': 'health.client.relation',
            'view_mode': 'kanban,list,form',
            'target': 'current',
            'domain': [('client_id', '=', self.id), ('role', '=', 'payer')],
            'context': {
                'default_client_id': self.id,
                'default_role': 'payer',
            }
        }

    def action_view_my_referrers(self):
        """View all referrers for this patient"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Referrers - {self.name}',
            'res_model': 'health.client.relation',
            'view_mode': 'kanban,list,form',
            'target': 'current',
            'domain': [('client_id', '=', self.id), ('role', '=', 'referrer')],
            'context': {
                'default_client_id': self.id,
                'default_role': 'referrer',
            }
        }

    def action_view_my_emergency_contacts(self):
        """View all emergency contacts for this patient"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Emergency Contacts - {self.name}',
            'res_model': 'health.client.relation',
            'view_mode': 'kanban,list,form',
            'target': 'current',
            'domain': [('client_id', '=', self.id), ('role', '=', 'emergency_contact')],
            'context': {
                'default_client_id': self.id,
                'default_role': 'emergency_contact',
            }
        }

    def action_view_my_legal_guardians(self):
        """View all legal guardians for this patient"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Legal Guardians - {self.name}',
            'res_model': 'health.client.relation',
            'view_mode': 'kanban,list,form',
            'target': 'current',
            'domain': [('client_id', '=', self.id), ('role', '=', 'legal_guardian')],
            'context': {
                'default_client_id': self.id,
                'default_role': 'legal_guardian',
            }
        }
