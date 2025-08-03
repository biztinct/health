import json
from datetime import datetime, timedelta
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class HealthBookingPortal(CustomerPortal):
    """State-of-the-art appointment booking portal controller"""
    
    def _prepare_home_portal_values(self, counters):
        """Add appointment counts to portal home"""
        values = super()._prepare_home_portal_values(counters)
        if 'appointment_count' in counters:
            appointment_count = request.env['health.appointment'].search_count([
                ('partner_id', '=', request.env.user.partner_id.id)
            ]) if request.env.user.partner_id else 0
            values['appointment_count'] = appointment_count
        return values
    
    @http.route(['/my/appointments', '/my/appointments/page/<int:page>'], 
                type='http', auth="user", website=True)
    def portal_my_appointments(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        """Patient's appointment dashboard - inspired by Epic MyChart"""
        values = self._prepare_portal_layout_values()
        
        # Search domain
        domain = [('partner_id', '=', request.env.user.partner_id.id)]
        
        # Date filtering
        if date_begin and date_end:
            domain += [('appointment_date', '>=', date_begin), ('appointment_date', '<=', date_end)]
        
        # Sorting options
        searchbar_sortings = {
            'date': {'label': _('Appointment Date'), 'order': 'appointment_date desc'},
            'name': {'label': _('Reference'), 'order': 'name'},
            'state': {'label': _('Status'), 'order': 'state'},
        }
        
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Count and pagination
        appointment_count = request.env['health.appointment'].search_count(domain)
        pager = portal_pager(
            url="/my/appointments",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=appointment_count,
            page=page,
            step=self._items_per_page
        )
        
        # Fetch appointments
        appointments = request.env['health.appointment'].search(domain, order=order, 
                                                              limit=self._items_per_page, 
                                                              offset=pager['offset'])
        
        values.update({
            'appointments': appointments,
            'page_name': 'appointment',
            'pager': pager,
            'default_url': '/my/appointments',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'date_begin': date_begin,
            'date_end': date_end,
        })
        
        return request.render("health_calendar.portal_my_appointments", values)
    
    @http.route(['/my/appointments/<int:appointment_id>'], 
                type='http', auth="user", website=True)
    def portal_appointment_detail(self, appointment_id, access_token=None, **kw):
        """Detailed appointment view"""
        try:
            appointment_sudo = self._document_check_access('health.appointment', appointment_id, access_token)
        except Exception:
            return request.redirect('/my')
        
        values = {
            'appointment': appointment_sudo,
            'page_name': 'appointment_detail',
        }
        return request.render("health_calendar.portal_appointment_detail", values)
    
    @http.route('/book-appointment', type='http', auth="public", website=True)
    def appointment_booking_portal(self, **kw):
        """Main booking portal - Calendly-inspired interface"""
        values = {
            'page_name': 'book_appointment',
            'appointment_types': request.env['health.service.type'].sudo().search([
                ('allow_online_booking', '=', True),
                ('active', '=', True)
            ]),
            'facilities': request.env['health.facility'].sudo().search([
                ('active', '=', True)
            ]),
        }
        return request.render("health_calendar.booking_portal_main", values)
    
    @http.route('/book-appointment/step2', type='http', auth="public", website=True, csrf=False)
    def booking_step2_select_datetime(self, appointment_type_id=None, **kw):
        """Step 2: Select date and time - Calendly-style calendar"""
        if not appointment_type_id:
            return request.redirect('/book-appointment')
        
        appointment_type = request.env['health.service.type'].sudo().browse(int(appointment_type_id))
        if not appointment_type.exists():
            return request.redirect('/book-appointment')
        
        values = {
            'page_name': 'book_appointment_step2',
            'appointment_type': appointment_type,
            'today': fields.Date.today(),
            'max_date': fields.Date.today() + timedelta(days=appointment_type.advance_booking_days),
        }
        return request.render("health_calendar.booking_portal_step2", values)
    
    @http.route('/book-appointment/step3', type='http', auth="public", website=True, csrf=False)
    def booking_step3_patient_info(self, appointment_type_id=None, selected_date=None, 
                                  selected_time=None, **kw):
        """Step 3: Enter patient information"""
        if not all([appointment_type_id, selected_date, selected_time]):
            return request.redirect('/book-appointment')
        
        appointment_type = request.env['health.service.type'].sudo().browse(int(appointment_type_id))
        
        values = {
            'page_name': 'book_appointment_step3',
            'appointment_type': appointment_type,
            'selected_date': selected_date,
            'selected_time': float(selected_time),
            'selected_time_str': self._float_to_time_string(float(selected_time)),
            'booking_config': appointment_type.get_booking_form_config(),
            'countries': request.env['res.country'].sudo().search([]),
            'states': request.env['res.country.state'].sudo().search([('country_id.code', '=', 'VN')]),
        }
        return request.render("health_calendar.booking_portal_step3", values)
    
    @http.route('/book-appointment/confirm', type='http', auth="public", website=True, 
                methods=['POST'], csrf=False)
    def booking_confirm(self, **post):
        """Final step: Confirm appointment booking"""
        try:
            # Validate required fields
            required_fields = ['appointment_type_id', 'selected_date', 'selected_time', 
                             'patient_name', 'patient_phone', 'patient_email']
            for field in required_fields:
                if not post.get(field):
                    return request.render("health_calendar.booking_error", {
                        'error': _('Missing required field: %s') % field
                    })
            
            # Find or create patient
            patient = self._find_or_create_patient(post)
            
            # Create appointment
            appointment_vals = {
                'patient_id': patient.id,
                'appointment_type_id': int(post['appointment_type_id']),
                'appointment_date': post['selected_date'],
                'appointment_time': float(post['selected_time']),
                'state': 'requested',
                'booking_source': 'portal',
                'symptoms': post.get('symptoms', ''),
                'patient_notes': post.get('patient_notes', ''),
                'special_requirements': post.get('special_requirements', ''),
                'urgency_level': post.get('urgency_level', 'routine'),
            }
            
            # Handle location-specific data
            appointment_type = request.env['health.service.type'].sudo().browse(int(post['appointment_type_id']))
            if appointment_type.location_type == 'home':
                appointment_vals.update({
                    'visit_address': post.get('visit_address', ''),
                    'travel_fee': appointment_type.travel_fee,
                })
            elif appointment_type.location_type == 'clinic':
                if post.get('facility_id'):
                    appointment_vals['facility_id'] = int(post['facility_id'])
            
            appointment = request.env['health.appointment'].sudo().create(appointment_vals)
            
            # Send confirmation email
            self._send_booking_confirmation(appointment)
            
            return request.render("health_calendar.booking_success", {
                'appointment': appointment,
                'page_name': 'booking_success',
            })
            
        except Exception as e:
            return request.render("health_calendar.booking_error", {
                'error': _('An error occurred while processing your booking: %s') % str(e)
            })
    
    def _find_or_create_patient(self, post):
        """Find existing patient or create new one"""
        # Try to find existing patient by email or phone
        existing_patient = request.env['health.patient'].sudo().search([
            '|', ('email', '=', post['patient_email']), 
                 ('mobile', '=', post['patient_phone'])
        ], limit=1)
        
        if existing_patient:
            return existing_patient
        
        # Create new patient
        patient_vals = {
            'name': post['patient_name'],
            'first_name': post.get('patient_first_name', ''),
            'last_name': post.get('patient_last_name', ''),
            'email': post['patient_email'],
            'mobile': post['patient_phone'],
            'phone': post['patient_phone'],
            'birth_date': post.get('birth_date') if post.get('birth_date') else None,
            'gender': post.get('gender', ''),
            'national_id': post.get('national_id', ''),
            'patient_status': 'new',
            'source_type': 'website',
            'source_details': 'Online appointment booking',
        }
        
        # Address information
        if post.get('street'):
            patient_vals.update({
                'street': post.get('street', ''),
                'street2': post.get('street2', ''),
                'city': post.get('city', ''),
                'state_id': int(post['state_id']) if post.get('state_id') else None,
                'zip': post.get('zip', ''),
                'country_id': int(post['country_id']) if post.get('country_id') else None,
            })
        
        return request.env['health.patient'].sudo().create(patient_vals)
    
    def _send_booking_confirmation(self, appointment):
        """Send booking confirmation email"""
        template = request.env.ref('health_calendar.email_template_booking_confirmation', False)
        if template:
            template.sudo().send_mail(appointment.id, force_send=True)
    
    def _float_to_time_string(self, float_time):
        """Convert float time to string format"""
        hours = int(float_time)
        minutes = int((float_time - hours) * 60)
        return f'{hours:02d}:{minutes:02d}'
    
    # AJAX endpoints for dynamic booking
    @http.route('/book-appointment/api/available-slots', type='json', auth="public")
    def get_available_slots(self, appointment_type_id, date, facility_id=None):
        """Get available time slots for a specific date"""
        try:
            appointment_type = request.env['health.service.type'].sudo().browse(appointment_type_id)
            if not appointment_type.exists():
                return {'error': 'Invalid appointment type'}
            
            # Get basic slots from appointment type
            slots = appointment_type.get_available_slots(date, facility_id)
            
            # Filter out booked slots
            existing_appointments = request.env['health.appointment'].sudo().search([
                ('appointment_date', '=', date),
                ('appointment_type_id', '=', appointment_type_id),
                ('state', 'in', ['confirmed', 'in_progress']),
            ])
            
            booked_times = [apt.appointment_time for apt in existing_appointments]
            
            # Mark unavailable slots
            for slot in slots:
                if slot['time'] in booked_times:
                    slot['available'] = False
            
            return {'slots': slots}
            
        except Exception as e:
            return {'error': f'Server error: {str(e)}'}
    
    # Alternative simple HTTP endpoint for fallback
    @http.route('/book-appointment/api/slots/<int:appointment_type_id>/<string:date>', 
                type='http', auth="public", methods=['GET'], csrf=False)
    def get_available_slots_simple(self, appointment_type_id, date, **kw):
        """Simple HTTP GET endpoint for available slots"""
        import json
        
        try:
            appointment_type = request.env['health.service.type'].sudo().browse(appointment_type_id)
            if not appointment_type.exists():
                return json.dumps({'error': 'Invalid appointment type'})
            
            slots = appointment_type.get_available_slots(date, None)
            return json.dumps({'slots': slots})
            
        except Exception as e:
            return json.dumps({'error': f'Server error: {str(e)}'})
    
    @http.route('/book-appointment/api/validate-slot', type='json', auth="public")
    def validate_time_slot(self, appointment_type_id, date, time):
        """Validate if a time slot is still available"""
        # Double-check availability before booking
        existing = request.env['health.appointment'].sudo().search_count([
            ('appointment_date', '=', date),
            ('appointment_time', '=', float(time)),
            ('appointment_type_id', '=', appointment_type_id),
            ('state', 'in', ['confirmed', 'in_progress']),
        ])
        
        return {'available': existing == 0}