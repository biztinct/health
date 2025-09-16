# -*- coding: utf-8 -*-

import json
from datetime import datetime, timedelta
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError, UserError


class HealthPWAAPIController(http.Controller):
    """RESTful API endpoints for PWA frontend"""
    
    def _check_api_access(self):
        """Check if user has API access to health modules"""
        if not request.env.user or request.env.user.id == request.env.ref('base.public_user').id:
            return False
        
        try:
            # Check if user can access health models
            request.env['res.partner'].check_access_rights('read')
            return True
        except:
            return False
    
    def _prepare_json_response(self, data=None, error=None, status_code=200):
        """Prepare standardized JSON response"""
        response_data = {
            'success': error is None,
            'timestamp': fields.Datetime.now().isoformat(),
        }
        
        if error:
            response_data['error'] = error
        else:
            response_data['data'] = data
        
        return request.make_response(
            json.dumps(response_data, default=str, ensure_ascii=False, indent=2),
            headers=[
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With'),
            ],
            status=status_code
        )
    
    @http.route('/health_pwa/api/patients', type='http', auth='user', methods=['GET'], csrf=False)
    def api_patients_list(self, **kwargs):
        """Get list of patients with pagination and filtering"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)
        
        try:
            # Parse query parameters
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            search = kwargs.get('search', '')
            status_filter = kwargs.get('status', '')
            
            # Build domain for patient search
            domain = [('is_patient', '=', True)]
            
            if search:
                domain.extend([
                    '|', '|', '|',
                    ('name', 'ilike', search),
                    ('patient_code', 'ilike', search),
                    ('phone', 'ilike', search),
                    ('mobile', 'ilike', search)
                ])
            
            if status_filter:
                domain.append(('patient_status', '=', status_filter))
            
            # Get patients with count
            patients = request.env['res.partner'].search(
                domain, limit=limit, offset=offset, order='name asc'
            )
            total_count = request.env['res.partner'].search_count(domain)
            
            # Prepare patient data for PWA
            patients_data = []
            for patient in patients:
                patients_data.append({
                    'id': patient.id,
                    'name': patient.name,
                    'patient_code': patient.patient_code,
                    'phone': patient.phone or patient.mobile,
                    'email': patient.email,
                    'age': patient.age,
                    'gender': patient.gender,
                    'blood_group': patient.blood_group,
                    'patient_status': patient.patient_status,
                    'last_visit_date': patient.last_visit_date,
                    'next_visit_date': patient.next_visit_date,
                    'address': patient.contact_address,
                    'image_url': f'/web/image/res.partner/{patient.id}/image_128' if patient.image_128 else None,
                    'visit_count': patient.visit_count,
                    'primary_facility': patient.primary_facility_id.name if patient.primary_facility_id else None,
                })
            
            response_data = {
                'patients': patients_data,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count
            }
            
            return self._prepare_json_response(data=response_data)
            
        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)
    
    @http.route('/health_pwa/api/patients/<int:patient_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def api_patient_detail(self, patient_id, **kwargs):
        """Get detailed patient information"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)
        
        try:
            patient = request.env['res.partner'].browse(patient_id)
            
            if not patient.exists() or not patient.is_patient:
                return self._prepare_json_response(error='Patient not found', status_code=404)
            
            # Get recent field service orders
            recent_orders = request.env['health.fieldservice.order'].search([
                ('patient_id', '=', patient.id)
            ], limit=10, order='scheduled_datetime desc')
            
            orders_data = []
            for order in recent_orders:
                orders_data.append({
                    'id': order.id,
                    'name': order.name,
                    'stage': order.stage_id.name if order.stage_id else None,
                    'scheduled_datetime': order.scheduled_datetime,
                    'address': order.service_address,
                    'service_type': order.service_type_id.name if order.service_type_id else None,
                    'team': order.team_id.name if order.team_id else None,
                    'priority': order.priority,
                })
            
            patient_data = {
                'id': patient.id,
                'name': patient.name,
                'patient_code': patient.patient_code,
                'first_name': patient.first_name,
                'last_name': patient.last_name,
                'birth_date': patient.birth_date,
                'age': patient.age,
                'gender': patient.gender,
                'blood_group': patient.blood_group,
                'phone': patient.phone,
                'mobile': patient.mobile,
                'email': patient.email,
                'street': patient.street,
                'city': patient.city,
                'country': patient.country_id.name if patient.country_id else None,
                'patient_status': patient.patient_status,
                'allergies': patient.allergies,
                'medical_history': patient.medical_history,
                'emergency_contact_name': patient.emergency_contact_name,
                'emergency_contact_phone': patient.emergency_contact_phone,
                'emergency_contact_relation': patient.emergency_contact_relation,
                'insurance_provider': patient.insurance_provider,
                'insurance_number': patient.insurance_number,
                'last_visit_date': patient.last_visit_date,
                'next_visit_date': patient.next_visit_date,
                'visit_count': patient.visit_count,
                'primary_facility': patient.primary_facility_id.name if patient.primary_facility_id else None,
                'primary_caregiver': patient.primary_caregiver_id.name if patient.primary_caregiver_id else None,
                'image_url': f'/web/image/res.partner/{patient.id}/image_256' if patient.image_256 else None,
                'recent_orders': orders_data,
            }
            
            return self._prepare_json_response(data=patient_data)
            
        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)
    
    @http.route('/health_pwa/api/fso', type='http', auth='user', methods=['GET'], csrf=False)
    def api_fso_list(self, **kwargs):
        """Get field service orders with filtering"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)
        
        try:
            # Parse query parameters
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            team_id = kwargs.get('team_id')
            stage = kwargs.get('stage')
            patient_id = kwargs.get('patient_id')
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')
            
            # Build domain
            domain = []
            
            if team_id:
                domain.append(('team_id', '=', int(team_id)))
                
            if stage:
                domain.append(('stage_id.name', '=', stage))
                
            if patient_id:
                domain.append(('patient_id', '=', int(patient_id)))
            
            if date_from:
                domain.append(('scheduled_datetime', '>=', date_from))
                
            if date_to:
                domain.append(('scheduled_datetime', '<=', date_to))
            
            # Get field service orders
            orders = request.env['health.fieldservice.order'].search(
                domain, limit=limit, offset=offset, order='scheduled_datetime desc'
            )
            total_count = request.env['health.fieldservice.order'].search_count(domain)
            
            orders_data = []
            for order in orders:
                orders_data.append({
                    'id': order.id,
                    'name': order.name,
                    'patient_name': order.patient_id.name if order.patient_id else None,
                    'patient_code': order.patient_id.patient_code if order.patient_id else None,
                    'stage': order.stage_id.name if order.stage_id else None,
                    'stage_color': getattr(order.stage_id, 'color', 0) if order.stage_id else 0,
                    'priority': order.priority,
                    'scheduled_datetime': order.scheduled_datetime,
                    'estimated_end_datetime': order.estimated_end_datetime,
                    'estimated_duration': order.estimated_duration,
                    'duration_minutes': order.duration_minutes,
                    'service_type': order.service_type_id.name if order.service_type_id else None,
                    'team': order.team_id.name if order.team_id else None,
                    'assigned_user': order.user_id.name if order.user_id else None,
                    'address': order.service_address,
                    'phone': order.patient_phone,
                    'description': order.description,
                    'location_lat': order.service_lat,
                    'location_lng': order.service_lng,
                })
            
            response_data = {
                'orders': orders_data,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count
            }
            
            return self._prepare_json_response(data=response_data)
            
        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)
    
    @http.route('/health_pwa/api/fso/<int:order_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def api_fso_detail(self, order_id, **kwargs):
        """Get detailed field service order information"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)
        
        try:
            order = request.env['health.fieldservice.order'].browse(order_id)
            
            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)
            
            order_data = {
                'id': order.id,
                'name': order.name,
                'patient': {
                    'id': order.patient_id.id if order.patient_id else None,
                    'name': order.patient_id.name if order.patient_id else None,
                    'patient_code': order.patient_id.patient_code if order.patient_id else None,
                    'phone': order.patient_id.phone or order.patient_id.mobile if order.patient_id else None,
                    'age': order.patient_id.age if order.patient_id else None,
                    'gender': order.patient_id.gender if order.patient_id else None,
                    'allergies': order.patient_id.allergies if order.patient_id else None,
                },
                'stage': order.stage_id.name if order.stage_id else None,
                'stage_color': getattr(order.stage_id, 'color', 0) if order.stage_id else 0,
                'priority': order.priority,
                'scheduled_datetime': order.scheduled_datetime,
                'estimated_end_datetime': order.estimated_end_datetime,
                'estimated_duration': order.estimated_duration,
                'duration_minutes': order.duration_minutes,
                'service_type': {
                    'id': order.service_type_id.id if order.service_type_id else None,
                    'name': order.service_type_id.name if order.service_type_id else None,
                },
                'team': {
                    'id': order.team_id.id if order.team_id else None,
                    'name': order.team_id.name if order.team_id else None,
                },
                'assigned_user': {
                    'id': order.user_id.id if order.user_id else None,
                    'name': order.user_id.name if order.user_id else None,
                },
                'address': order.service_address,
                'phone': order.patient_phone,
                'description': order.description,
                'patient_notes': order.patient_notes,
                'location': {
                    'lat': order.service_lat,
                    'lng': order.service_lng,
                },
                'created_date': order.create_date,
                'updated_date': order.write_date,
            }
            
            return self._prepare_json_response(data=order_data)
            
        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)
    
    @http.route('/health_pwa/api/fso/<int:order_id>/update', type='json', auth='user', methods=['POST'], csrf=False)
    def api_fso_update(self, order_id, **kwargs):
        """Update field service order from mobile app"""
        if not self._check_api_access():
            return {'success': False, 'error': 'Access denied'}
        
        try:
            order = request.env['health.fieldservice.order'].browse(order_id)
            
            if not order.exists():
                return {'success': False, 'error': 'Order not found'}
            
            # Parse update data
            data = request.jsonrequest
            update_vals = {}
            
            # Allow updating specific fields from mobile
            allowed_fields = [
                'patient_notes', 'stage_id', 'duration_actual',
                'service_lat', 'service_lng', 'completion_notes'
            ]
            
            for field in allowed_fields:
                if field in data:
                    update_vals[field] = data[field]
            
            # Update order
            order.write(update_vals)
            
            return {'success': True, 'message': 'Order updated successfully'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @http.route('/health_pwa/api/teams', type='http', auth='user', methods=['GET'], csrf=False)
    def api_teams_list(self, **kwargs):
        """Get list of field service teams"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)
        
        try:
            teams = request.env['health.fieldservice.team'].search([])
            
            teams_data = []
            for team in teams:
                teams_data.append({
                    'id': team.id,
                    'name': team.name,
                    'description': team.description,
                    'active_orders_count': len([o for o in team.order_ids if o.stage_id.name not in ['Completed', 'Cancelled']]),
                    'members': [{'id': u.id, 'name': u.name} for u in team.member_ids],
                })
            
            return self._prepare_json_response(data={'teams': teams_data})
            
        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)
    
    @http.route('/health_pwa/api/user/profile', type='http', auth='user', methods=['GET'], csrf=False)
    def api_user_profile(self, **kwargs):
        """Get current user profile information"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)
        
        try:
            user = request.env.user
            
            # Get user's team assignments if any
            user_teams = request.env['health.fieldservice.team'].search([
                ('member_ids', 'in', [user.id])
            ])
            
            user_data = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'mobile': user.mobile,
                'image_url': f'/web/image/res.users/{user.id}/image_128' if user.image_128 else None,
                'company': user.company_id.name,
                'teams': [{'id': t.id, 'name': t.name} for t in user_teams],
                'timezone': user.tz or 'UTC',
            }
            
            return self._prepare_json_response(data=user_data)
            
        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)
    
    @http.route('/health_pwa/api/stats/dashboard', type='http', auth='user', methods=['GET'], csrf=False)
    def api_dashboard_stats(self, **kwargs):
        """Get dashboard statistics for mobile app"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)
        
        try:
            # Get current user's teams
            user_teams = request.env['health.fieldservice.team'].search([
                ('member_ids', 'in', [request.env.user.id])
            ])
            
            team_domain = [('team_id', 'in', user_teams.ids)] if user_teams else []
            
            # Today's orders
            today = fields.Date.today()
            today_orders = request.env['health.fieldservice.order'].search_count(
                team_domain + [('scheduled_datetime', '>=', today), ('scheduled_datetime', '<', today + timedelta(days=1))]
            )
            
            # Pending orders
            pending_orders = request.env['health.fieldservice.order'].search_count(
                team_domain + [('stage_id.name', 'not in', ['Completed', 'Cancelled'])]
            )
            
            # Active patients count
            active_patients = request.env['res.partner'].search_count([
                ('is_patient', '=', True),
                ('patient_status', '=', 'active')
            ])
            
            # This week's completed orders
            week_start = today - timedelta(days=today.weekday())
            completed_this_week = request.env['health.fieldservice.order'].search_count(
                team_domain + [
                    ('stage_id.name', '=', 'Completed'),
                    ('scheduled_datetime', '>=', week_start)
                ]
            )
            
            stats_data = {
                'today_orders': today_orders,
                'pending_orders': pending_orders,
                'active_patients': active_patients,
                'completed_this_week': completed_this_week,
                'user_teams_count': len(user_teams),
                'last_updated': fields.Datetime.now().isoformat(),
            }
            
            return self._prepare_json_response(data=stats_data)
            
        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)