from odoo import http, fields
from odoo.http import request
import json


class HealthAppointmentAPI(http.Controller):
    """REST API endpoints for appointment management"""
    
    @http.route('/api/appointments', type='json', auth='user', methods=['GET'])
    def get_appointments(self, patient_id=None, date_from=None, date_to=None, **kw):
        """Get appointments for a patient or date range"""
        domain = []
        
        if patient_id:
            domain.append(('patient_id', '=', int(patient_id)))
        
        if date_from:
            domain.append(('appointment_date', '>=', date_from))
            
        if date_to:
            domain.append(('appointment_date', '<=', date_to))
        
        appointments = request.env['health.appointment'].search(domain)
        
        return [{
            'id': apt.id,
            'name': apt.name,
            'patient_name': apt.patient_id.name,
            'appointment_type': apt.appointment_type_id.name,
            'date': apt.appointment_date.isoformat() if apt.appointment_date else None,
            'time': apt.appointment_time,
            'state': apt.state,
            'location_type': apt.location_type,
        } for apt in appointments]
    
    @http.route('/api/appointment-types', type='json', auth='public', methods=['GET'])
    def get_appointment_types(self, **kw):
        """Get available appointment types for booking"""
        appointment_types = request.env['health.service.type'].sudo().search([
            ('allow_online_booking', '=', True),
            ('active', '=', True)
        ])
        
        return [{
            'id': apt_type.id,
            'name': apt_type.name,
            'description': apt_type.description,
            'duration_minutes': apt_type.duration_minutes,
            'base_price': apt_type.base_price,
            'location_type': apt_type.location_type,
            'icon': apt_type.icon,
            'color': apt_type.color,
        } for apt_type in appointment_types]
    
    @http.route('/api/available-slots/<int:appointment_type_id>/<string:date>', 
                type='json', auth='public', methods=['GET'])
    def get_available_slots_api(self, appointment_type_id, date, **kw):
        """Get available time slots for a specific appointment type and date"""
        appointment_type = request.env['health.service.type'].sudo().browse(appointment_type_id)
        
        if not appointment_type.exists():
            return {'error': 'Invalid appointment type'}
        
        try:
            slots = appointment_type.get_available_slots(date)
            return {'slots': slots}
        except Exception as e:
            return {'error': str(e)}