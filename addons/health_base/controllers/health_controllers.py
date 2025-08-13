from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class HealthcareController(http.Controller):
    """Base Healthcare API Controller for VAFHS"""

    @http.route('/api/health/patient/search', type='json', auth='user', methods=['POST'])
    def search_patients(self, **kwargs):
        """Search patients with healthcare-specific filters"""
        try:
            domain = []
            limit = kwargs.get('limit', 20)
            offset = kwargs.get('offset', 0)
            
            # Search filters
            if kwargs.get('name'):
                domain.append(['name', 'ilike', kwargs['name']])
            if kwargs.get('patient_code'):
                domain.append(['patient_code', 'ilike', kwargs['patient_code']])
            if kwargs.get('phone'):
                domain.append(['|', ['phone', 'ilike', kwargs['phone']], ['mobile', 'ilike', kwargs['phone']]])
            if kwargs.get('national_id'):
                domain.append(['national_id', 'ilike', kwargs['national_id']])
            if kwargs.get('facility_id'):
                domain.append(['primary_facility_id', '=', kwargs['facility_id']])
            if kwargs.get('category_id'):
                domain.append(['patient_category_id', '=', kwargs['category_id']])
            if kwargs.get('status'):
                domain.append(['patient_status', '=', kwargs['status']])

            # Add patient filter to domain
            domain.append(('is_patient', '=', True))
            patients = request.env['res.partner'].search(
                domain, limit=limit, offset=offset, order='name asc'
            )
            
            patient_data = []
            for patient in patients:
                patient_data.append({
                    'id': patient.id,
                    'patient_code': patient.patient_code,
                    'name': patient.name,
                    'age_display': patient.age_display,
                    'gender': patient.gender,
                    'phone': patient.phone,
                    'mobile': patient.mobile,
                    'email': patient.email,
                    'patient_status': patient.patient_status,
                    'category': patient.patient_category_id.name if patient.patient_category_id else '',
                    'facility': patient.primary_facility_id.name if patient.primary_facility_id else '',
                    'last_visit': patient.last_visit_date.strftime('%Y-%m-%d') if patient.last_visit_date else '',
                    'next_visit': patient.next_visit_date.strftime('%Y-%m-%d') if patient.next_visit_date else '',
                    'source_type': patient.source_type,
                })

            return {
                'success': True,
                'data': patient_data,
                'total': len(patient_data)
            }
            
        except Exception as e:
            _logger.error(f"Patient search error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/health/patient/<int:patient_id>', type='json', auth='user', methods=['GET'])
    def get_patient_details(self, patient_id, **kwargs):
        """Get detailed patient information"""
        try:
            patient = request.env['res.partner'].browse(patient_id)
            if not patient.is_patient:
                return request.not_found()
            if not patient.exists():
                return {
                    'success': False,
                    'error': 'Patient not found'
                }

            return {
                'success': True,
                'data': {
                    'id': patient.id,
                    'patient_code': patient.patient_code,
                    'name': patient.name,
                    'vietnamese_name': patient.vietnamese_name,
                    'first_name': patient.first_name,
                    'last_name': patient.last_name,
                    'gender': patient.gender,
                    'birth_date': patient.birth_date.strftime('%Y-%m-%d') if patient.birth_date else '',
                    'age': patient.age,
                    'age_display': patient.age_display,
                    'phone': patient.phone,
                    'mobile': patient.mobile,
                    'email': patient.email,
                    'national_id': patient.national_id,
                    'address': {
                        'street': patient.street,
                        'street2': patient.street2,
                        'city': patient.city,
                        'state': patient.state_id.name if patient.state_id else '',
                        'zip': patient.zip,
                        'country': patient.country_id.name if patient.country_id else ''
                    },
                    'medical_info': {
                        'blood_group': patient.blood_group,
                        'allergies': patient.allergies,
                        'medical_history': patient.medical_history
                    },
                    'category': {
                        'id': patient.patient_category_id.id if patient.patient_category_id else None,
                        'name': patient.patient_category_id.name if patient.patient_category_id else ''
                    },
                    'facility': {
                        'id': patient.primary_facility_id.id if patient.primary_facility_id else None,
                        'name': patient.primary_facility_id.name if patient.primary_facility_id else ''
                    },
                    'emergency_contact': {
                        'name': patient.emergency_contact_name,
                        'phone': patient.emergency_contact_phone,
                        'relation': patient.emergency_contact_relation
                    },
                    'insurance': {
                        'provider': patient.insurance_provider,
                        'number': patient.insurance_number,
                        'expiry': patient.insurance_expiry.strftime('%Y-%m-%d') if patient.insurance_expiry else ''
                    },
                    'status': patient.patient_status,
                    'source': {
                        'type': patient.source_type,
                        'details': patient.source_details,
                        'referral': patient.referral_source
                    },
                    'dates': {
                        'registration': patient.registration_date.strftime('%Y-%m-%d %H:%M') if patient.registration_date else '',
                        'last_visit': patient.last_visit_date.strftime('%Y-%m-%d') if patient.last_visit_date else '',
                        'next_visit': patient.next_visit_date.strftime('%Y-%m-%d') if patient.next_visit_date else ''
                    },
                    'visit_count': patient.visit_count
                }
            }
            
        except Exception as e:
            _logger.error(f"Get patient details error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/health/facilities', type='json', auth='user', methods=['GET'])
    def get_facilities(self, **kwargs):
        """Get healthcare facilities list"""
        try:
            domain = [('active', '=', True)]
            
            if kwargs.get('facility_type'):
                domain.append(['facility_type', '=', kwargs['facility_type']])
            if kwargs.get('home_visits_only'):
                domain.append(['covers_home_visits', '=', True])
            if kwargs.get('city'):
                domain.append(['city', 'ilike', kwargs['city']])

            facilities = request.env['health.facility'].search(domain, order='name asc')
            
            facility_data = []
            for facility in facilities:
                facility_data.append({
                    'id': facility.id,
                    'name': facility.name,
                    'code': facility.code,
                    'type': facility.facility_type,
                    'status': facility.facility_status,
                    'address': f"{facility.street}, {facility.city}",
                    'phone': facility.phone,
                    'email': facility.email,
                    'home_visits': facility.covers_home_visits,
                    'home_visit_radius': facility.home_visit_radius_km,
                    'max_patients': facility.max_daily_patients,
                    'total_beds': facility.total_beds,
                    'available_beds': facility.available_beds
                })

            return {
                'success': True,
                'data': facility_data
            }
            
        except Exception as e:
            _logger.error(f"Get facilities error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/health/lookup/<string:model>', type='json', auth='user', methods=['GET'])
    def get_lookup_data(self, model, **kwargs):
        """Get lookup data for healthcare dropdowns"""
        try:
            lookup_models = {
                'patient_categories': 'health.patient.category',
                'service_types': 'health.service.type',
                'medical_specialties': 'health.medical.specialty',
                'symptoms': 'health.symptom',
                'urgency_levels': 'health.urgency.level',
                'referral_sources': 'health.referral.source',
                'insurance_providers': 'health.insurance.provider',
                'districts': 'health.vietnamese.district'
            }
            
            if model not in lookup_models:
                return {
                    'success': False,
                    'error': 'Invalid lookup model'
                }

            records = request.env[lookup_models[model]].search([('active', '=', True)], order='name asc')
            
            data = []
            for record in records:
                item = {
                    'id': record.id,
                    'name': record.name
                }
                
                # Add model-specific fields
                if model == 'patient_categories':
                    item.update({
                        'description': record.description,
                        'price_multiplier': record.price_multiplier,
                        'color': record.color
                    })
                elif model == 'service_types':
                    item.update({
                        'code': record.code,
                        'category': record.category,
                        'base_price': record.base_price,
                        'duration': record.duration_minutes,
                        'home_available': record.available_home,
                        'clinic_available': record.available_clinic,
                        'telemedicine_available': record.available_telemedicine
                    })
                elif model == 'urgency_levels':
                    item.update({
                        'code': record.code,
                        'priority_score': record.priority_score,
                        'response_time': record.response_time_hours,
                        'color': record.color
                    })
                elif model == 'districts':
                    item.update({
                        'province': record.province_name,
                        'region': record.region,
                        'travel_zone': record.travel_zone,
                        'travel_fee': record.base_travel_fee,
                        'travel_time': record.average_travel_time
                    })
                
                data.append(item)

            return {
                'success': True,
                'data': data
            }
            
        except Exception as e:
            _logger.error(f"Get lookup data error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/health/validate/vietnamese-phone', type='json', auth='public', methods=['POST'])
    def validate_vietnamese_phone(self, **kwargs):
        """Validate Vietnamese phone number format"""
        try:
            phone = kwargs.get('phone', '').strip()
            if not phone:
                return {'success': False, 'error': 'Phone number is required'}

            # Remove all non-digits
            digits = ''.join(filter(str.isdigit, phone))
            
            # Vietnamese phone number patterns
            # Mobile: 03x, 05x, 07x, 08x, 09x (10 digits total starting with 0)
            # Or international format: +84 3x, 5x, 7x, 8x, 9x (12 digits total)
            
            is_valid = False
            formatted_phone = phone
            
            if len(digits) == 10 and digits.startswith('0') and digits[1] in ['3', '5', '7', '8', '9']:
                is_valid = True
                formatted_phone = f"{digits[:4]} {digits[4:7]} {digits[7:]}"
            elif len(digits) == 11 and digits.startswith('84') and digits[2] in ['3', '5', '7', '8', '9']:
                is_valid = True
                formatted_phone = f"+{digits[:2]} {digits[2:5]} {digits[5:8]} {digits[8:]}"
            elif phone.startswith('+84') and len(digits) == 11 and digits[2] in ['3', '5', '7', '8', '9']:
                is_valid = True
                formatted_phone = f"+{digits[:2]} {digits[2:5]} {digits[5:8]} {digits[8:]}"

            return {
                'success': True,
                'valid': is_valid,
                'formatted': formatted_phone if is_valid else phone,
                'message': 'Valid Vietnamese phone number' if is_valid else 'Invalid phone number format'
            }
            
        except Exception as e:
            _logger.error(f"Phone validation error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/health/validate/national-id', type='json', auth='public', methods=['POST'])
    def validate_national_id(self, **kwargs):
        """Validate Vietnamese National ID (CCCD/CMND) format"""
        try:
            national_id = kwargs.get('national_id', '').strip()
            if not national_id:
                return {'success': False, 'error': 'National ID is required'}

            # Remove all non-digits
            digits = ''.join(filter(str.isdigit, national_id))
            
            # Vietnamese National ID patterns
            # CMND: 9-12 digits
            # CCCD: 12 digits
            
            is_valid = len(digits) >= 9 and len(digits) <= 12
            id_type = ''
            
            if len(digits) == 12:
                id_type = 'CCCD (Citizen Identity Card)'
            elif len(digits) >= 9 and len(digits) <= 11:
                id_type = 'CMND (Identity Card)'
            
            return {
                'success': True,
                'valid': is_valid,
                'type': id_type if is_valid else '',
                'message': f'Valid {id_type}' if is_valid else 'Invalid National ID format (must be 9-12 digits)'
            }
            
        except Exception as e:
            _logger.error(f"National ID validation error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/health/dashboard', type='http', auth='user', website=True)
    def healthcare_dashboard(self, **kwargs):
        """Healthcare dashboard page"""
        try:
            # Get dashboard statistics
            patient_count = request.env['res.partner'].search_count([('is_patient', '=', True), ('active', '=', True)])
            facility_count = request.env['health.facility'].search_count([('active', '=', True)])
            
            # Today's appointments (placeholder - will be implemented in health_calendar)
            today_appointments = 0
            
            # Recent patients
            recent_patients = request.env['res.partner'].search([
                ('is_patient', '=', True),
                ('active', '=', True)
            ], limit=5, order='registration_date desc')

            values = {
                'patient_count': patient_count,
                'facility_count': facility_count,
                'today_appointments': today_appointments,
                'recent_patients': recent_patients,
                'page_name': 'healthcare_dashboard'
            }

            return request.render('health_base.health_dashboard_template', values)
            
        except Exception as e:
            _logger.error(f"Dashboard error: {str(e)}")
            return request.render('web.http_error', {
                'status_code': 500,
                'status_message': 'Internal Server Error',
                'exception': str(e)
            })

    @http.route('/health/patient/portal', type='http', auth='user', website=True)
    def patient_portal(self, **kwargs):
        """Patient portal access"""
        try:
            user = request.env.user
            
            # Check if user is linked to a patient record
            patient = request.env['res.partner'].search([
                ('is_patient', '=', True),
                ('partner_id.user_ids', 'in', [user.id])
            ], limit=1)

            if not patient:
                return request.render('health_base.patient_portal_no_access', {
                    'page_name': 'patient_portal'
                })

            values = {
                'patient': patient,
                'page_name': 'patient_portal'
            }

            return request.render('health_base.patient_portal_template', values)
            
        except Exception as e:
            _logger.error(f"Patient portal error: {str(e)}")
            return request.render('web.http_error', {
                'status_code': 500,
                'status_message': 'Internal Server Error',
                'exception': str(e)
            })

    @http.route('/api/health/stats/dashboard', type='json', auth='user', methods=['GET'])
    def get_dashboard_stats(self, **kwargs):
        """Get dashboard statistics for AJAX updates"""
        try:
            stats = {
                'patients': {
                    'total': request.env['res.partner'].search_count([('is_patient', '=', True), ('active', '=', True)]),
                    'new_this_month': request.env['res.partner'].search_count([
                        ('is_patient', '=', True),
                        ('active', '=', True),
                        ('registration_date', '>=', kwargs.get('month_start', '2024-01-01'))
                    ]),
                    'vip': request.env['res.partner'].search_count([
                        ('is_patient', '=', True),
                        ('active', '=', True),
                        ('patient_category_id.name', '=', 'VIP Patient')
                    ])
                },
                'facilities': {
                    'total': request.env['health.facility'].search_count([('active', '=', True)]),
                    'operational': request.env['health.facility'].search_count([
                        ('active', '=', True),
                        ('facility_status', '=', 'operational')
                    ]),
                    'home_visit_capable': request.env['health.facility'].search_count([
                        ('active', '=', True),
                        ('covers_home_visits', '=', True)
                    ])
                }
                # Additional stats will be added when other modules are implemented
            }

            return {
                'success': True,
                'data': stats
            }
            
        except Exception as e:
            _logger.error(f"Dashboard stats error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }