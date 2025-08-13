from odoo import api, fields, models, _


class ResPartnerCalendar(models.Model):
    """Extend res.partner with appointment-specific functionality for patients"""
    _inherit = 'res.partner'
    
    # Appointment-specific fields
    appointment_ids = fields.One2many('health.appointment', 'patient_id', 'Appointments')
    appointment_count = fields.Integer('Appointment Count', compute='_compute_appointment_count')
    
    @api.depends('appointment_ids')
    def _compute_appointment_count(self):
        """Count all appointments for this patient"""
        for patient in self:
            patient.appointment_count = len(patient.appointment_ids)
    
    @api.depends('appointment_ids.state')
    def _compute_visit_count(self):
        """Override base visit count to use actual appointment data"""
        for partner in self:
            if partner.is_patient:
                partner.visit_count = len(partner.appointment_ids.filtered(lambda a: a.state == 'completed'))
            else:
                super(ResPartnerCalendar, partner)._compute_visit_count()
    
    def action_view_appointments(self):
        """View patient appointments (override base method)"""
        if not self.is_patient:
            return super().action_view_appointments()
            
        return {
            'name': _('Patient Appointments'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.appointment',
            'view_mode': 'list,form,calendar',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }
    
    def _get_portal_return_url(self):
        """Return URL for portal access"""
        return '/my/patient/%s' % self.id
    
    def action_activate_portal_access(self):
        """Activate portal access for this patient"""
        if not self.is_patient:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('This contact is not a patient.'),
                    'type': 'warning'
                }
            }
            
        # Ensure partner has portal access
        self.signup_prepare()
        
        # Update patient status to active if it's new
        if self.patient_status == 'new':
            self.patient_status = 'active'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Activated'),
                'message': _('Portal access has been activated for %s. They can now book appointments online.') % self.name,
                'type': 'success'
            }
        }