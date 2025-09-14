# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ClientSelectionWizard(models.TransientModel):
    """Wizard to select client when multiple patients have the same name"""
    _name = 'health.client.selection.wizard'
    _description = 'Client Selection Wizard'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead',
        required=True,
        readonly=True
    )
    
    client_name = fields.Char(
        string='Client Name',
        readonly=True
    )
    
    selected_patient_id = fields.Many2one(
        'res.partner',
        string='Select Client',
        required=True,
        domain="[('id', 'in', patient_ids)]"
    )
    
    patient_ids = fields.Many2many(
        'res.partner',
        string='Matching Patients',
        readonly=True
    )
    
    @api.model
    def default_get(self, fields):
        """Set default values"""
        result = super().default_get(fields)
        
        # Get lead from context
        lead_id = self.env.context.get('active_id')
        if lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            result['lead_id'] = lead_id
            result['client_name'] = lead.client_name
            
            # Find matching patients
            matching_patients = self.env['res.partner'].search([
                ('name', '=', lead.client_name),
                ('is_patient', '=', True)
            ])
            result['patient_ids'] = [(6, 0, matching_patients.ids)]
        
        return result
    
    def action_select_client(self):
        """Process client selection and continue relationship creation"""
        self.ensure_one()
        
        if not self.selected_patient_id:
            return
        
        # Update lead with selected patient
        self.lead_id.patient_id = self.selected_patient_id.id
        
        # Continue with representative creation if needed
        if self.lead_id.contact_relationship_type != 'client':
            # Create representative record
            representative = self.lead_id._create_representative()
            
            # Create relationship
            self.lead_id._create_health_relationship(self.selected_patient_id, representative)
            
            # Populate appropriate relationship field
            self.lead_id._populate_relationship_field(representative)
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_create_new_client(self):
        """Create new client with same name"""
        self.ensure_one()
        
        # Create new patient with same name but different details
        patient = self.lead_id._get_or_create_patient(self.client_name)
        
        # Update lead with new patient
        self.lead_id.patient_id = patient.id
        
        # Continue with representative creation if needed
        if self.lead_id.contact_relationship_type != 'client':
            # Create representative record
            representative = self.lead_id._create_representative()
            
            # Create relationship
            self.lead_id._create_health_relationship(patient, representative)
            
            # Populate appropriate relationship field
            self.lead_id._populate_relationship_field(representative)
        
        return {'type': 'ir.actions.act_window_close'}