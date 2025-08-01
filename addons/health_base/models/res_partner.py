from odoo import models, fields, api


class ResPartner(models.Model):
    """Extend res.partner for healthcare functionality"""
    _inherit = 'res.partner'

    # Healthcare-specific fields
    is_patient = fields.Boolean('Is Patient', default=False)
    is_healthcare_staff = fields.Boolean('Is Healthcare Staff', default=False)
    is_healthcare_facility = fields.Boolean('Is Healthcare Facility', default=False)
    
    # Patient relationship
    patient_id = fields.Many2one('health.patient', string='Patient Record', 
                                 help='Linked patient record if this contact is a patient')
    
    # Healthcare facility relationship
    facility_id = fields.Many2one('health.facility', string='Facility Record',
                                  help='Linked facility record if this contact is a healthcare facility')
    
    # Medical specialties for healthcare staff
    medical_specialties = fields.Many2many('health.medical.specialty', 
                                          string='Medical Specialties')
    
    # Professional details for healthcare staff
    license_number = fields.Char('Professional License Number')
    license_expiry = fields.Date('License Expiry Date')
    
    # Emergency contact flag
    is_emergency_contact = fields.Boolean('Is Emergency Contact', default=False)
    
    # Vietnamese specific fields
    vietnamese_name = fields.Char('Vietnamese Name')
    national_id = fields.Char('National ID (CCCD/CMND)')
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set healthcare flags based on categories"""
        partners = super().create(vals_list)
        
        # Get healthcare category references
        patient_category = self.env.ref('health_base.patient_category', raise_if_not_found=False)
        staff_category = self.env.ref('health_base.staff_category', raise_if_not_found=False)
        facility_category = self.env.ref('health_base.facility_category', raise_if_not_found=False)
        
        for partner in partners:
            # Set healthcare flags based on categories
            if patient_category and patient_category in partner.category_id:
                partner.is_patient = True
            if staff_category and staff_category in partner.category_id:
                partner.is_healthcare_staff = True
            if facility_category and facility_category in partner.category_id:
                partner.is_healthcare_facility = True
                
        return partners
    
    def action_create_patient_record(self):
        """Create a patient record for this contact"""
        if self.is_patient and not self.patient_id:
            patient_vals = {
                'name': self.name,
                'partner_id': self.id,
                'phone': self.phone,
                'mobile': self.mobile,
                'email': self.email,
                'street': self.street,
                'street2': self.street2,
                'city': self.city,
                'state_id': self.state_id.id,
                'zip': self.zip,
                'country_id': self.country_id.id,
                'vietnamese_name': self.vietnamese_name,
                'national_id': self.national_id,
            }
            patient = self.env['health.patient'].create(patient_vals)
            self.patient_id = patient.id
            
            return {
                'type': 'ir.actions.act_window',
                'name': 'Patient Record',
                'res_model': 'health.patient',
                'res_id': patient.id,
                'view_mode': 'form',
                'target': 'current'
            }
    
    def action_view_patient_record(self):
        """View the linked patient record"""
        if self.patient_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Patient Record',
                'res_model': 'health.patient',
                'res_id': self.patient_id.id,
                'view_mode': 'form',
                'target': 'current'
            }
    
    def action_view_facility_record(self):
        """View the linked facility record"""
        if self.facility_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Facility Record',
                'res_model': 'health.facility',
                'res_id': self.facility_id.id,
                'view_mode': 'form',
                'target': 'current'
            }