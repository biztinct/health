# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime, timedelta
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


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
            # Get current employee for staff name
            current_user = request.env.user
            employee = request.env['hr.employee'].search([
                ('user_id', '=', current_user.id)
            ], limit=1)

            # Parse query parameters
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            team_id = kwargs.get('team_id')
            stage = kwargs.get('stage')
            patient_id = kwargs.get('patient_id')
            date_from = kwargs.get('date_from')
            date_to = kwargs.get('date_to')

            # Build domain
            # Record rules will automatically filter by user assignments
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
            all_orders = request.env['health.fieldservice.order'].search(
                domain, limit=limit, offset=offset, order='scheduled_datetime desc'
            )

            # Filter out completed/cancelled bookings for future dates
            from datetime import datetime as dt
            from odoo import fields as odoo_fields
            now_utc = odoo_fields.Datetime.now()  # Get current time in Odoo's UTC format

            orders = all_orders.filtered(
                lambda fso: (
                    # Include all past/today bookings regardless of stage
                    not fso.scheduled_datetime or fso.scheduled_datetime <= now_utc
                ) or (
                    # For future bookings, exclude completed/cancelled stages
                    fso.scheduled_datetime > now_utc and (
                        not fso.stage_id or (
                            fso.stage_id.state not in ['cancelled', 'completed', 'completed_pending_invoice', 'closed']
                            and fso.stage_id.name.lower() not in ['completed', 'cancelled', 'closed']
                        )
                    )
                )
            )

            total_count = len(orders)

            # Debug logging
            excluded_count = len(all_orders) - len(orders)
            if excluded_count > 0:
                _logger.info(f'PWA FSO List: Excluded {excluded_count} completed future bookings')

            # Get staff name for response
            staff_name = employee.name if employee else current_user.name
            
            orders_data = []
            for order in orders:
                # Format scheduled time
                scheduled_time = ''
                if order.scheduled_datetime:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(order.scheduled_datetime))
                    scheduled_time = dt.strftime('%I:%M %p')

                orders_data.append({
                    'id': order.id,
                    'fso_id': order.id,
                    'fso_name': order.name,
                    'patient_name': order.patient_id.name if order.patient_id else None,
                    'patient_id': order.patient_id.id if order.patient_id else None,
                    'patient_phone': order.patient_phone,
                    'service_type': order._get_service_type_label() if hasattr(order, '_get_service_type_label') else order.service_type,
                    'appointment_type': '',
                    'scheduled_datetime': order.scheduled_datetime,
                    'scheduled_time': scheduled_time,
                    'scheduled_duration': order.scheduled_duration,
                    'status': order.state,
                    'status_display': order.state,
                    'location': order.service_address,
                    'priority': order.priority,
                    'assignment_role': 'staff',
                    'notes': order.symptoms or order.patient_notes or '',
                })
            
            response_data = {
                'orders': orders_data,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count,
                'staff_name': staff_name,
                'staff_id': employee.id if employee else None
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
            
            # Get primary contact from patient relations
            primary_contact = None
            if order.patient_id:
                # Look for emergency contact marked as primary
                contacts = request.env['health.client.relation'].search([
                    ('client_id', '=', order.patient_id.id),
                    ('role', '=', 'emergency_contact'),
                    ('is_primary', '=', True)
                ], limit=1)
                if contacts and contacts[0].representative_id:
                    contact_partner = contacts[0].representative_id
                    primary_contact = {
                        'name': contact_partner.name,
                        'phone': contact_partner.mobile or contact_partner.phone,
                        'relationship': contacts[0].relationship_type or 'Emergency Contact',
                    }

            # Use main patient contact if no primary relation found
            if not primary_contact and order.patient_id:
                primary_contact = {
                    'name': order.patient_id.name,
                    'phone': order.patient_id.mobile or order.patient_id.phone,
                    'relationship': 'Patient',
                }

            # Get service items from quote
            quote_items = []
            if order.sale_order_id:
                for line in order.sale_order_id.order_line:
                    quote_items.append({
                        'id': line.id,
                        'product_name': line.product_id.name if line.product_id else line.name,
                        'quantity': float(line.product_uom_qty),
                        'unit_price': float(line.price_unit),
                        'discount': float(line.discount) if line.discount else 0.0,
                        'discount_reason': line.discount_reason if hasattr(line, 'discount_reason') and line.discount_reason else '',
                    })

            order_data = {
                'id': order.id,
                'name': order.name,
                'state': order.state,
                'actual_start_datetime': order.actual_start_datetime,
                'actual_end_datetime': order.actual_end_datetime if hasattr(order, 'actual_end_datetime') else None,
                'patient': {
                    'id': order.patient_id.id if order.patient_id else None,
                    'name': order.patient_id.name if order.patient_id else None,
                    'patient_code': order.patient_id.patient_code if order.patient_id else None,
                    'phone': order.patient_id.phone or order.patient_id.mobile if order.patient_id else None,
                    'age': order.patient_id.age if order.patient_id else None,
                    'gender': order.patient_id.gender if order.patient_id else None,
                    'allergies': order.patient_id.allergies if order.patient_id else None,
                },
                'primary_contact': primary_contact,
                'stage': order.stage_id.name if order.stage_id else None,
                'stage_color': getattr(order.stage_id, 'color', 0) if order.stage_id else 0,
                'priority': order.priority,
                'scheduled_datetime': order.scheduled_datetime,
                'scheduled_duration': order.scheduled_duration,
                'estimated_end_datetime': order.estimated_end_datetime,
                'estimated_duration': order.estimated_duration,
                'service_type': order._get_service_type_label() if hasattr(order, '_get_service_type_label') else order.service_type,
                'package': {
                    'id': order.package_id.id if order.package_id else None,
                    'name': order.package_id.name if order.package_id else None,
                } if hasattr(order, 'package_id') else None,
                'quote_items': quote_items,
                'team': {
                    'id': order.team_id.id if order.team_id else None,
                    'name': order.team_id.name if order.team_id else None,
                },
                'assigned_user': {
                    'id': order.lead_staff_id.id if order.lead_staff_id else None,
                    'name': order.lead_staff_id.name if order.lead_staff_id else None,
                },
                'address': order.service_address,
                'phone': order.patient_phone,
                'description': order.symptoms or order.patient_notes or '',
                'patient_notes': order.patient_notes,
                'clinical_notes': order.clinical_notes if hasattr(order, 'clinical_notes') else None,
                'diagnosis': order.diagnosis if hasattr(order, 'diagnosis') else None,
                'treatment_performed': order.treatment_performed if hasattr(order, 'treatment_performed') else None,
                'medications_prescribed': order.medications_prescribed if hasattr(order, 'medications_prescribed') else None,
                'vital_signs': order.vital_signs if hasattr(order, 'vital_signs') else None,
                # Intake notes fields
                'referring_doctor_id': order.referring_doctor_id.id if hasattr(order, 'referring_doctor_id') and order.referring_doctor_id else None,
                'referring_doctor_name': order.referring_doctor_id.name if hasattr(order, 'referring_doctor_id') and order.referring_doctor_id else None,
                'referring_doctor_phone': order.referring_doctor_id.mobile or order.referring_doctor_id.phone if hasattr(order, 'referring_doctor_id') and order.referring_doctor_id else None,
                'goal_of_care': order.goal_of_care if hasattr(order, 'goal_of_care') else None,
                'required_equipment': order.required_equipment if hasattr(order, 'required_equipment') else None,
                'intake_notes': order.intake_notes if hasattr(order, 'intake_notes') else None,
                'location': {
                    'lat': order.patient_id.partner_latitude if order.patient_id else None,
                    'lng': order.patient_id.partner_longitude if order.patient_id else None,
                    'gps_coordinates': order.gps_coordinates if hasattr(order, 'gps_coordinates') else None,
                    'travel_distance': order.travel_distance if hasattr(order, 'travel_distance') else None,
                    'travel_time_minutes': order.travel_time_minutes if hasattr(order, 'travel_time_minutes') else None,
                },
                'created_date': order.create_date,
                'updated_date': order.write_date,
            }

            # Add confirmation requirements info
            is_valid, error_msg = order._check_confirmation_requirements()
            order_data['confirmation_requirements'] = {
                'is_valid': is_valid,
                'error_message': error_msg,
                'has_quote_with_items': bool(order.sale_order_id and order.sale_order_id.order_line),
                'has_package': bool(order.package_id),
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

    @http.route('/health_pwa/api/fso/<int:order_id>/start', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_start_service(self, order_id, **kwargs):
        """Start service timer for FSO from mobile app"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            # Check if order is in assigned state
            if order.state not in ['assigned', 'confirmed']:
                return self._prepare_json_response(error=f'Cannot start service in {order.state} state', status_code=400)

            # Start the service
            order.action_start_service()

            return self._prepare_json_response(data={
                'actual_start_datetime': order.actual_start_datetime,
                'state': order.state,
                'message': 'Service started successfully'
            })

        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/complete', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_complete_service(self, order_id, **kwargs):
        """Complete service and stop timer for FSO from mobile app"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            # Check if order is in progress
            if order.state != 'in_progress':
                return self._prepare_json_response(error=f'Cannot complete service in {order.state} state', status_code=400)

            # Get payment option from request body
            import json as json_module
            try:
                data = json_module.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            except:
                data = {}

            # Get payment wizard data
            payment_choice = data.get('payment_choice', 'pay_now')  # 'pay_now' or 'pay_later'
            payment_method = data.get('payment_method', 'cash')  # 'cash', 'bank_transfer', 'credit_card', etc.
            service_notes = data.get('service_notes', '')
            create_invoice_now = data.get('create_invoice_now', True)
            clinical_notes = data.get('clinical_notes', '')

            # Update clinical notes and service notes if provided
            update_vals = {}
            if clinical_notes:
                update_vals['clinical_notes'] = clinical_notes
            if service_notes:
                update_vals['nurse_notes'] = service_notes if hasattr(order, 'nurse_notes') else None
                # If nurse_notes doesn't exist, add to clinical notes
                if service_notes and not hasattr(order, 'nurse_notes'):
                    update_vals['clinical_notes'] = (update_vals.get('clinical_notes', clinical_notes or '') + '\n\nService Notes: ' + service_notes).strip()

            if update_vals:
                order.write(update_vals)

            # Complete the service using the standard method
            order.action_complete_service()

            # Handle invoice creation and payment
            message = 'Service completed successfully'

            # Check if invoice should be created (skip if amount is zero or prepaid)
            should_create_invoice = create_invoice_now and order.sale_order_id
            if should_create_invoice:
                # Check if sale order total is zero - skip invoice if so
                sale_order_total = order.sale_order_id.amount_total or 0.0
                if sale_order_total <= 0.0:
                    should_create_invoice = False
                    message = 'Service completed - No invoice created (zero amount)'
                    _logger.info(f'Skipping invoice creation for FSO {order.name} - Sale order total is zero')

            if should_create_invoice:
                # Confirm the sale order to create invoice
                if order.sale_order_id.state in ['draft', 'sent']:
                    order.sale_order_id.action_confirm()

                # Create invoice from sale order if not exists
                if not order.invoice_id:
                    invoices = order.sale_order_id._create_invoices()
                    if invoices:
                        order.invoice_id = invoices[0] if len(invoices) == 1 else invoices
                        # Post the invoice
                        order.invoice_id.action_post()

            # Process payment based on choice (only if invoice was created)
            if payment_choice == 'pay_now' and payment_method and order.invoice_id:
                # Create payment transaction record
                try:
                    transaction_vals = {
                        'patient_id': order.patient_id.id if order.patient_id else False,
                        'fso_id': order.id,
                        'invoice_id': order.invoice_id.id if order.invoice_id else False,
                        'amount': order.invoice_id.amount_total if order.invoice_id else 0.0,
                        'payment_method': payment_method,
                        'transaction_type': 'immediate',
                        'status': 'collected' if payment_method != 'cash' else 'pending_delivery',
                        'collected_by_id': request.env.user.employee_id.id if request.env.user.employee_id else False,
                        'transaction_notes': service_notes or f'Payment collected on service completion via mobile - {payment_method}',
                    }

                    # Create transaction if model exists
                    if 'health.payment.transaction' in request.env:
                        transaction = request.env['health.payment.transaction'].create(transaction_vals)
                        message = f'Service completed - {payment_method.replace("_", " ").title()} payment collected'
                    else:
                        message = f'Service completed - {payment_method.replace("_", " ").title()} payment noted'

                except Exception as e:
                    _logger.warning(f'Could not create payment transaction: {str(e)}')
                    message = f'Service completed - {payment_method.replace("_", " ").title()} payment noted'
            elif payment_choice == 'pay_later' and order.invoice_id:
                # Pay Later (only if invoice exists)
                message = 'Service completed - Invoice will be sent for later payment'
            elif not order.invoice_id:
                # No invoice created (zero amount or prepaid)
                if 'zero amount' not in message:
                    message = 'Service completed - No payment required'

            return self._prepare_json_response(data={
                'actual_end_datetime': order.actual_end_datetime,
                'adjusted_end_datetime': order.adjusted_end_datetime if hasattr(order, 'adjusted_end_datetime') else None,
                'actual_duration': order.actual_duration if hasattr(order, 'actual_duration') else None,
                'state': order.state,
                'payment_choice': payment_choice,
                'payment_method': payment_method,
                'message': message
            })

        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/complete_without_quote', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_complete_service_without_quote(self, order_id, **kwargs):
        """Complete service without quote - for cases where no invoice is needed"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            # Check if order is in progress
            if order.state != 'in_progress':
                return self._prepare_json_response(error=f'Cannot complete service in {order.state} state', status_code=400)

            # Get service notes from request body if provided
            import json as json_module
            try:
                data = json_module.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            except:
                data = {}

            service_notes = data.get('service_notes', '')

            # Update service notes if provided
            if service_notes:
                update_vals = {}
                if hasattr(order, 'nurse_notes'):
                    update_vals['nurse_notes'] = service_notes
                else:
                    # Add to clinical notes if nurse_notes doesn't exist
                    clinical_notes = order.clinical_notes or ''
                    update_vals['clinical_notes'] = (clinical_notes + '\n\nService Notes: ' + service_notes).strip()

                if update_vals:
                    order.write(update_vals)

            # Complete the service without creating an invoice
            order.action_complete_service()

            return self._prepare_json_response(data={
                'actual_end_datetime': order.actual_end_datetime,
                'adjusted_end_datetime': order.adjusted_end_datetime if hasattr(order, 'adjusted_end_datetime') else None,
                'actual_duration': order.actual_duration if hasattr(order, 'actual_duration') else None,
                'state': order.state,
                'message': 'Service completed successfully without invoice'
            })

        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/clinical_notes', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_save_clinical_notes(self, order_id, **kwargs):
        """Save clinical notes for FSO from mobile app"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            # Get clinical notes from request body
            import json as json_module
            try:
                data = json_module.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            except:
                data = {}

            clinical_notes = data.get('clinical_notes', '')
            diagnosis = data.get('diagnosis', '')
            treatment_performed = data.get('treatment_performed', '')
            medications_prescribed = data.get('medications_prescribed', '')
            vital_signs = data.get('vital_signs', '')

            # Update order
            update_vals = {}
            if clinical_notes:
                update_vals['clinical_notes'] = clinical_notes
            if diagnosis:
                update_vals['diagnosis'] = diagnosis
            if treatment_performed:
                update_vals['treatment_performed'] = treatment_performed
            if medications_prescribed:
                update_vals['medications_prescribed'] = medications_prescribed
            if vital_signs:
                update_vals['vital_signs'] = vital_signs

            if update_vals:
                order.write(update_vals)
                # Mark clinical notes as submitted
                order.write({'clinical_notes_submitted': True})

            return self._prepare_json_response(data={
                'clinical_notes_submitted': order.clinical_notes_submitted,
                'message': 'Clinical notes saved successfully'
            })

        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/intake_notes', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_save_intake_notes(self, order_id, **kwargs):
        """Save intake notes for FSO from mobile app"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            # Get intake notes from request body
            import json as json_module
            try:
                data = json_module.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            except:
                data = {}

            diagnosis = data.get('diagnosis', '')
            referring_doctor_id = data.get('referring_doctor_id')
            goal_of_care = data.get('goal_of_care', '')
            required_equipment = data.get('required_equipment', '')
            intake_notes = data.get('intake_notes', '')

            # Update order
            update_vals = {}
            if diagnosis:
                update_vals['diagnosis'] = diagnosis
            if referring_doctor_id:
                update_vals['referring_doctor_id'] = referring_doctor_id
            if goal_of_care:
                update_vals['goal_of_care'] = goal_of_care
            if required_equipment:
                update_vals['required_equipment'] = required_equipment
            if intake_notes:
                update_vals['intake_notes'] = intake_notes

            if update_vals:
                order.write(update_vals)

            return self._prepare_json_response(success=True, data={
                'message': 'Intake notes saved successfully',
                'order_id': order.id
            })

        except Exception as e:
            _logger.error(f'Error saving intake notes: {str(e)}')
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/upload_image', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_upload_image(self, order_id, **kwargs):
        """Upload clinical image for FSO from mobile app"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            # Get uploaded file
            image_file = request.httprequest.files.get('image')
            if not image_file:
                return self._prepare_json_response(error='No image provided', status_code=400)

            # Read image data
            import base64
            image_data = base64.b64encode(image_file.read())

            # Create attachment for the image
            attachment = request.env['ir.attachment'].create({
                'name': f'Clinical_Image_{order.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg',
                'type': 'binary',
                'datas': image_data,
                'res_model': 'health.fieldservice.order',
                'res_id': order.id,
                'mimetype': image_file.content_type or 'image/jpeg',
            })

            return self._prepare_json_response(data={
                'attachment_id': attachment.id,
                'filename': attachment.name,
                'url': f'/web/content/{attachment.id}'
            })

        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/quote', type='http', auth='user', methods=['GET'], csrf=False)
    def api_fso_get_quote(self, order_id, **kwargs):
        """Get quote/sale order for FSO from mobile app"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            if not order.sale_order_id:
                return self._prepare_json_response(error='No quote found for this order', status_code=404)

            sale_order = order.sale_order_id

            # Prepare quote data
            quote_data = {
                'id': sale_order.id,
                'name': sale_order.name,
                'state': sale_order.state,
                'amount_total': float(sale_order.amount_total),
                'amount_untaxed': float(sale_order.amount_untaxed),
                'amount_tax': float(sale_order.amount_tax),
                'currency': sale_order.currency_id.name if sale_order.currency_id else 'VND',
                'order_lines': [],
            }

            # Add order lines
            for line in sale_order.order_line:
                quote_data['order_lines'].append({
                    'id': line.id,
                    'product_id': line.product_id.id if line.product_id else None,
                    'product_name': line.product_id.name if line.product_id else line.name,
                    'description': line.name,
                    'quantity': float(line.product_uom_qty),
                    'unit_price': float(line.price_unit),
                    'discount': float(line.discount) if hasattr(line, 'discount') else 0.0,
                    'discount_reason': line.discount_reason if hasattr(line, 'discount_reason') else '',
                    'subtotal': float(line.price_subtotal),
                    'total': float(line.price_total),
                })

            return self._prepare_json_response(data=quote_data)

        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/products/catalog', type='http', auth='user', methods=['GET'], csrf=False)
    def api_get_product_catalog(self, **kwargs):
        """Get product catalog for adding to quotes"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            # Parse query parameters
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            search = kwargs.get('search', '')
            category = kwargs.get('category', '')

            # Build domain for product search
            domain = [('sale_ok', '=', True)]

            if search:
                domain.extend([
                    '|',
                    ('name', 'ilike', search),
                    ('default_code', 'ilike', search)
                ])

            if category:
                domain.append(('categ_id.name', '=', category))

            # Get products
            products = request.env['product.product'].search(
                domain, limit=limit, offset=offset, order='name asc'
            )
            total_count = request.env['product.product'].search_count(domain)

            # Prepare product data
            products_data = []
            for product in products:
                products_data.append({
                    'id': product.id,
                    'name': product.name,
                    'code': product.default_code,
                    'description': product.description_sale,
                    'price': float(product.list_price),
                    'currency': product.currency_id.name if product.currency_id else 'VND',
                    'category': product.categ_id.name if product.categ_id else None,
                    'uom': product.uom_id.name if product.uom_id else None,
                    'image_url': f'/web/image/product.product/{product.id}/image_128' if product.image_128 else None,
                })

            response_data = {
                'products': products_data,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count
            }

            return self._prepare_json_response(data=response_data)

        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/quote/update', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_update_quote(self, order_id, **kwargs):
        """Update quote lines for FSO from mobile app"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            if not order.sale_order_id:
                return self._prepare_json_response(error='No quote found for this order', status_code=404)

            sale_order = order.sale_order_id

            # Get update data from request body
            import json as json_module
            try:
                data = json_module.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            except:
                data = {}

            action = data.get('action')  # 'add', 'update', 'remove'
            line_data = data.get('line_data', {})

            if action == 'add':
                # Add new product line
                product_id = line_data.get('product_id')
                quantity = line_data.get('quantity', 1.0)

                if not product_id:
                    return self._prepare_json_response(error='Product ID required', status_code=400)

                product = request.env['product.product'].browse(product_id)
                if not product.exists():
                    return self._prepare_json_response(error='Product not found', status_code=404)

                # Create order line
                request.env['sale.order.line'].create({
                    'order_id': sale_order.id,
                    'product_id': product_id,
                    'product_uom_qty': quantity,
                    'price_unit': product.list_price,
                })

            elif action == 'update':
                # Update existing line
                line_id = line_data.get('line_id')
                quantity = line_data.get('quantity')
                price = line_data.get('price')
                discount = line_data.get('discount')
                discount_reason = line_data.get('discount_reason')

                if not line_id:
                    return self._prepare_json_response(error='Line ID required', status_code=400)

                line = request.env['sale.order.line'].browse(line_id)
                if not line.exists() or line.order_id.id != sale_order.id:
                    return self._prepare_json_response(error='Line not found', status_code=404)

                update_vals = {}
                if quantity is not None:
                    update_vals['product_uom_qty'] = float(quantity)
                if price is not None:
                    update_vals['price_unit'] = float(price)
                if discount is not None:
                    update_vals['discount'] = float(discount)
                if discount_reason is not None:
                    update_vals['discount_reason'] = discount_reason

                if update_vals:
                    line.write(update_vals)

            elif action == 'remove':
                # Remove line
                line_id = line_data.get('line_id')

                if not line_id:
                    return self._prepare_json_response(error='Line ID required', status_code=400)

                line = request.env['sale.order.line'].browse(line_id)
                if not line.exists() or line.order_id.id != sale_order.id:
                    return self._prepare_json_response(error='Line not found', status_code=404)

                line.unlink()

            else:
                return self._prepare_json_response(error='Invalid action', status_code=400)

            # Return updated quote data
            updated_quote = {
                'id': sale_order.id,
                'name': sale_order.name,
                'state': sale_order.state,
                'amount_total': float(sale_order.amount_total),
                'amount_untaxed': float(sale_order.amount_untaxed),
                'amount_tax': float(sale_order.amount_tax),
                'order_lines': [],
            }

            for line in sale_order.order_line:
                updated_quote['order_lines'].append({
                    'id': line.id,
                    'product_id': line.product_id.id if line.product_id else None,
                    'product_name': line.product_id.name if line.product_id else line.name,
                    'description': line.name,
                    'quantity': float(line.product_uom_qty),
                    'unit_price': float(line.price_unit),
                    'discount': float(line.discount) if hasattr(line, 'discount') else 0.0,
                    'discount_reason': line.discount_reason if hasattr(line, 'discount_reason') else '',
                    'subtotal': float(line.price_subtotal),
                    'total': float(line.price_total),
                })

            return self._prepare_json_response(data={
                'quote': updated_quote,
                'message': 'Quote updated successfully'
            })

        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/quote/save', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_save_quote(self, order_id, **kwargs):
        """Save quote with verification comments and sync modified line items from mobile app"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            if not order.sale_order_id:
                return self._prepare_json_response(error='No quote found for this order', status_code=404)

            sale_order = order.sale_order_id

            # Get save data from request body
            import json as json_module
            try:
                data = json_module.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            except:
                data = {}

            comments = data.get('comments', '')
            line_comments = data.get('line_comments', {})
            modified_lines = data.get('modified_lines', [])

            # Process modified line items - update Qty and Discount on sale.order.line
            for line_update in modified_lines:
                line_id = line_update.get('line_id')
                quantity = line_update.get('quantity')
                discount = line_update.get('discount', 0)
                discount_reason = line_update.get('discount_reason', '')
                line_comment = line_update.get('comment', '')

                if line_id:
                    sale_line = request.env['sale.order.line'].browse(line_id)
                    if sale_line.exists() and sale_line.order_id.id == sale_order.id:
                        # Update the quantity and discount on the sale order line
                        update_vals = {}
                        if quantity is not None:
                            update_vals['product_uom_qty'] = float(quantity)
                        if discount is not None:
                            update_vals['discount'] = float(discount)
                        if discount_reason:
                            update_vals['discount_reason'] = discount_reason

                        # Add line comment to the line's internal note field
                        if line_comment:
                            note_text = f"[Line Modification] {line_comment}"
                            if hasattr(sale_line, 'notes') and sale_line.notes:
                                update_vals['notes'] = sale_line.notes + "\n\n" + note_text
                            else:
                                # If notes field doesn't exist, add to sale order notes
                                pass

                        if update_vals:
                            sale_line.write(update_vals)

            # Save general comments to the sale order note
            if comments:
                # Add comments to the internal notes of the quote
                note_text = f"[Invoice Verification] {comments}"
                if sale_order.note:
                    sale_order.note = sale_order.note + "\n\n" + note_text
                else:
                    sale_order.note = note_text

            return self._prepare_json_response(data={
                'quote_id': sale_order.id,
                'quote_name': sale_order.name,
                'comments_saved': bool(comments),
                'modified_lines_count': len(modified_lines),
                'message': 'Invoice verified and saved successfully'
            })

        except Exception as e:
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/assignments/today', type='http', auth='user', methods=['GET'], csrf=False)
    def api_get_today_assignments(self, **kwargs):
        """
        Get field service order bookings for the logged-in nurse/doctor
        Shows all bookings assigned to the current user for a given date (defaults to today)
        Supports optional 'date' query parameter in YYYY-MM-DD format
        """
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            # Get logged-in user
            current_user = request.env.user

            # Get the employee record for the current user (optional)
            # Record rules will handle filtering by assignments
            employee = request.env['hr.employee'].search([
                ('user_id', '=', current_user.id)
            ], limit=1)

            # Parse optional date parameter, default to today
            date_param = kwargs.get('date')
            if date_param:
                try:
                    # Parse YYYY-MM-DD format
                    from datetime import datetime as dt
                    target_date = dt.strptime(date_param, '%Y-%m-%d').date()
                except ValueError:
                    return self._prepare_json_response(
                        error='Invalid date format. Use YYYY-MM-DD',
                        status_code=400
                    )
            else:
                target_date = fields.Date.today()

            # Create timezone-aware datetime range for the target date
            # Convert local date to UTC datetime range for database query
            from datetime import datetime as dt, timedelta
            import pytz

            # Get the user's timezone or use server timezone
            user_tz = pytz.timezone(request.env.user.tz or 'UTC')

            # Create datetime objects for the target date in the user's timezone
            local_start = user_tz.localize(dt.combine(target_date, dt.min.time()))
            local_end = user_tz.localize(dt.combine(target_date, dt.max.time()))

            # Convert to UTC for database query
            utc_start = local_start.astimezone(pytz.UTC)
            utc_end = local_end.astimezone(pytz.UTC)

            # Format as strings for the query (Odoo will handle timezone conversion)
            today_start = utc_start.strftime('%Y-%m-%d %H:%M:%S')
            today_end = utc_end.strftime('%Y-%m-%d %H:%M:%S')

            # Find FSOs scheduled for the target date
            # Record rules will automatically filter by user assignments
            all_fsos = request.env['health.fieldservice.order'].search([
                ('scheduled_datetime', '>=', today_start),
                ('scheduled_datetime', '<=', today_end),
                ('state', 'not in', ['cancelled']),
            ], order='scheduled_datetime asc')

            # Filter out completed bookings for future dates
            from odoo import fields as odoo_fields
            now_utc = odoo_fields.Datetime.now()

            # Check if target date is in the future
            target_datetime_utc = utc_start
            is_future_date = target_datetime_utc.replace(tzinfo=None) > now_utc

            if is_future_date:
                # For future dates, exclude completed/cancelled bookings
                fsos = all_fsos.filtered(
                    lambda fso: not fso.stage_id or (
                        fso.stage_id.state not in ['cancelled', 'completed', 'completed_pending_invoice', 'closed']
                        and fso.stage_id.name.lower() not in ['completed', 'cancelled', 'closed']
                    )
                )
                excluded_count = len(all_fsos) - len(fsos)
                if excluded_count > 0:
                    _logger.info(f'Assignments {target_date}: Excluded {excluded_count} completed bookings')
            else:
                # For past/today, show all bookings including completed ones
                fsos = all_fsos

            # Prepare booking data
            bookings_data = []
            for fso in fsos:
                patient = fso.patient_id

                # Find the assignment record for this staff member (if employee exists)
                assignment = None
                if employee:
                    assignment = fso.assignment_ids.filtered(
                        lambda a: a.staff_id.id == employee.id
                    )
                    assignment = assignment[0] if assignment else None

                # Get service type display name
                service_type_label = 'Service'
                if fso.service_type:
                    service_type_dict = dict(fso._fields['service_type'].selection)
                    service_type_label = service_type_dict.get(fso.service_type, fso.service_type)

                # Get appointment type name if available
                appointment_type = ''
                if fso.appointment_type_id:
                    appointment_type = fso.appointment_type_id.name

                bookings_data.append({
                    'id': fso.id,
                    'fso_id': fso.id,
                    'fso_name': fso.name,
                    'patient_name': patient.name if patient else 'Unknown',
                    'patient_id': patient.id if patient else None,
                    'patient_phone': patient.mobile or patient.phone if patient else None,
                    'service_type': service_type_label,
                    'appointment_type': appointment_type,
                    'scheduled_datetime': fso.scheduled_datetime,
                    'scheduled_time': fso.scheduled_datetime.strftime('%H:%M') if fso.scheduled_datetime else '',
                    'status': fso.state,
                    'status_display': fso.state or 'Unknown',
                    'location': fso.service_location or fso.service_address or '',
                    'priority': fso.priority,
                    'priority_display': dict(fso._fields['priority'].selection).get(fso.priority, '') if 'priority' in fso._fields and hasattr(fso._fields['priority'], 'selection') else '',
                    'scheduled_duration': fso.scheduled_duration if fso.scheduled_duration else 60,
                    'assignment_role': assignment.assignment_role if assignment else 'support',
                    'notes': getattr(fso, 'patient_notes', '') or getattr(fso, 'symptoms', '') or '',
                })

            response_data = {
                'bookings': bookings_data,
                'total_count': len(bookings_data),
                'staff_name': employee.name if employee else current_user.name,
                'staff_id': employee.id if employee else None,
                'date': target_date.isoformat(),
                'requested_date': date_param or target_date.isoformat(),
            }

            return self._prepare_json_response(data=response_data)

        except Exception as e:
            _logger.error(f'Error fetching today bookings: {str(e)}')
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/config/clinic-phone', type='http', auth='user', methods=['GET'], csrf=False)
    def api_get_clinic_phone(self, **kwargs):
        """
        Get clinic phone number and name from PWA configuration
        Used for the Call feature in the mobile app
        """
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            # Get PWA configuration
            pwa_config = request.env['health.pwa.config'].search(
                [('active', '=', True)],
                limit=1
            )

            if not pwa_config:
                # Return default/fallback clinic info from company
                company = request.env.company
                config_data = {
                    'clinic_phone_number': company.phone or '+1-800-CLINIC',
                    'clinic_name': company.name or 'Clinic',
                    'from_config': False
                }
            else:
                config_data = {
                    'clinic_phone_number': pwa_config.clinic_phone_number,
                    'clinic_name': pwa_config.clinic_name,
                    'enable_offline_mode': pwa_config.enable_offline_mode,
                    'enable_gps_tracking': pwa_config.enable_gps_tracking,
                    'enable_photo_capture': pwa_config.enable_photo_capture,
                    'from_config': True
                }

            return self._prepare_json_response(data=config_data)

        except Exception as e:
            _logger.error(f'Error fetching clinic config: {str(e)}')
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/next_visit_status', type='http', auth='user', methods=['GET'], csrf=False)
    def api_fso_next_visit_status(self, order_id, **kwargs):
        """Check if patient has a scheduled next visit"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            if not order.patient_id:
                return self._prepare_json_response(error='No patient associated with this order', status_code=400)

            patient = order.patient_id

            # Search for future FSOs (excluding the current one being completed)
            # This is more reliable than checking patient.next_visit_date field
            next_fso = request.env['health.fieldservice.order'].search([
                ('patient_id', '=', patient.id),
                ('id', '!=', order.id),  # Exclude current order
                ('state', 'in', ['draft', 'assigned', 'confirmed', 'in_progress']),
                ('scheduled_datetime', '!=', False)
            ], order='scheduled_datetime ASC', limit=1)

            # Determine if next visit exists based on actual FSO search
            has_next_visit = bool(next_fso)
            next_visit_date = None

            response_data = {
                'has_next_visit': has_next_visit,
                'patient_name': patient.name,
                'patient_id': patient.id,
                'assignment_notes': patient.assignment_notes or '',
            }

            # If next visit exists, populate FSO details
            if has_next_visit and next_fso:
                next_visit_date = next_fso.scheduled_datetime.isoformat() if next_fso.scheduled_datetime else None
                response_data['next_visit_date'] = next_visit_date
                response_data['next_fso_id'] = next_fso.id

                # Get all assignments for this FSO (excluding template assignments)
                assignments = request.env['health.staff.assignment'].search([
                    ('fso_id', '=', next_fso.id),
                    ('staff_id', '!=', False),  # Only show assignments with actual staff
                    ('state', '!=', 'template'),  # Exclude template assignments
                ], order='assignment_role DESC')  # Lead role first

                assigned_staff = []
                for assignment in assignments:
                    assigned_staff.append({
                        'id': assignment.staff_id.id,
                        'name': assignment.staff_id.name,
                        'role': assignment.assignment_role or 'Staff',
                    })

                response_data['assigned_staff'] = assigned_staff

                # Also keep single assigned_nurse for backward compatibility
                if assignments:
                    response_data['assigned_nurse'] = {
                        'id': assignments[0].staff_id.id,
                        'name': assignments[0].staff_id.name,
                    }
                else:
                    response_data['assigned_nurse'] = {
                        'id': None,
                        'name': None,
                    }

                # Get quote line items
                quote_items = []
                if next_fso.sale_order_id:
                    for line in next_fso.sale_order_id.order_line:
                        quote_items.append({
                            'id': line.id,
                            'product_id': line.product_id.id,
                            'product_name': line.product_id.name if line.product_id else line.name,
                            'quantity': float(line.product_uom_qty),
                            'unit_price': float(line.price_unit),
                        })
                response_data['quote_items'] = quote_items
            else:
                response_data['next_visit_date'] = None

            return self._prepare_json_response(data=response_data)

        except Exception as e:
            _logger.error(f'Error checking next visit status: {str(e)}')
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/no_future_visit', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_no_future_visit(self, order_id, **kwargs):
        """Record that patient doesn't want/need future visits"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            if not order.patient_id:
                return self._prepare_json_response(error='No patient associated with this order', status_code=400)

            # Get request data
            import json as json_module
            try:
                data = json_module.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            except:
                data = {}

            reason = data.get('reason', '')
            other_reason_text = data.get('other_reason_text', '')

            # Build the reason string
            if reason == 'Other':
                reason_note = f"[No Future Visit] {reason}: {other_reason_text}"
            else:
                reason_note = f"[No Future Visit] {reason}"

            patient = order.patient_id

            # Append to assignment_notes
            if patient.assignment_notes:
                patient.write({
                    'assignment_notes': patient.assignment_notes + '\n' + reason_note,
                    'next_visit_date': False  # Clear next visit date
                })
            else:
                patient.write({
                    'assignment_notes': reason_note,
                    'next_visit_date': False  # Clear next visit date
                })

            return self._prepare_json_response(data={
                'message': 'Visit cancellation reason recorded successfully',
                'patient_id': patient.id
            })

        except Exception as e:
            _logger.error(f'Error recording no future visit: {str(e)}')
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/fso/<int:order_id>/schedule_next_visit', type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_schedule_next_visit(self, order_id, **kwargs):
        """Create new FSO or update existing next visit"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            order = request.env['health.fieldservice.order'].browse(order_id)

            if not order.exists():
                return self._prepare_json_response(error='Order not found', status_code=404)

            if not order.patient_id:
                return self._prepare_json_response(error='No patient associated with this order', status_code=400)

            # Get request data
            import json as json_module
            try:
                data = json_module.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            except:
                data = {}

            next_visit_date = data.get('next_visit_date')
            quote_items = data.get('quote_items', [])
            assigned_staff_id = data.get('assigned_staff_id')
            next_fso_id = data.get('next_fso_id')  # From status check

            # Parse ISO format datetime string to Odoo-compatible format
            # Frontend sends: '2025-11-21T14:23:00+00:00' (ISO 8601 with timezone)
            # Odoo expects: '2025-11-21 14:23:00' (without timezone, stored as UTC)
            if next_visit_date:
                try:
                    # Remove timezone suffix and replace 'T' with space
                    # Convert '2025-11-21T14:23:00+00:00' to '2025-11-21 14:23:00'
                    if 'T' in next_visit_date:
                        # Split by 'T' to get date and time parts
                        date_part, time_with_tz = next_visit_date.split('T')
                        # Remove timezone info from time part (everything after +/- or Z)
                        # Handle +00:00, -05:00, Z formats
                        if '+' in time_with_tz:
                            time_part = time_with_tz.split('+')[0]
                        elif time_with_tz.count('-') > 0:
                            # Split only on the last occurrence of '-' (for timezone)
                            # This preserves negative times if any
                            time_part = time_with_tz.rsplit('-', 1)[0]
                        elif 'Z' in time_with_tz:
                            time_part = time_with_tz.split('Z')[0]
                        else:
                            time_part = time_with_tz
                        # Reconstruct as Odoo-compatible format
                        next_visit_date = f'{date_part} {time_part}'
                except Exception as e:
                    _logger.error(f'Error parsing datetime: {next_visit_date}, error: {str(e)}')
                    return self._prepare_json_response(error=f'Invalid datetime format: {str(e)}', status_code=400)

            patient = order.patient_id

            # Determine if we're updating existing FSO or creating new one
            if next_fso_id:
                # Update existing FSO
                next_fso = request.env['health.fieldservice.order'].browse(next_fso_id)
                if next_fso.exists() and next_fso.patient_id.id == patient.id:
                    update_vals = {'scheduled_datetime': next_visit_date}
                    if assigned_staff_id:
                        update_vals['lead_staff_id'] = assigned_staff_id
                    else:
                        update_vals['lead_staff_id'] = False
                    next_fso.write(update_vals)
                else:
                    return self._prepare_json_response(error='Invalid FSO or patient mismatch', status_code=400)
            else:
                # Determine state: 'assigned' if staff assigned, 'confirmed' if unassigned
                # First check if assigned_staff_id is provided and has a user_id
                fso_state = 'draft'
                if assigned_staff_id:
                    # Check if the staff member has a user_id
                    staff = request.env['hr.employee'].browse(assigned_staff_id)
                    if staff.exists() and staff.user_id:
                        fso_state = 'assigned'
                else:
                    # No staff assigned - create in confirmed state
                    fso_state = 'confirmed'

                # Get current user's employee record for booking credit tracking
                current_employee = request.env.user.employee_id

                # Create new FSO
                next_fso = request.env['health.fieldservice.order'].create({
                    'patient_id': patient.id,
                    'customer_id': patient.id,
                    'scheduled_datetime': next_visit_date,
                    'lead_staff_id': assigned_staff_id if assigned_staff_id else False,
                    'state': fso_state,
                    'created_by_employee_id': current_employee.id if current_employee else False,
                })

                # Increment booking credit for the staff member who created this booking
                if current_employee and current_employee.is_healthcare_staff:
                    current_employee.booking_credit += 1
                    _logger.info(f'✅ Booking credit incremented for {current_employee.name}: {current_employee.booking_credit}')

                # Create Assignment records if staff is assigned
                # Pattern: Create template (for adding more staff later) + actual assignment (for lead staff)
                if assigned_staff_id:
                    try:
                        assignment_date = next_fso.scheduled_datetime or request.env['ir.fields.datetime'].now()

                        # 1. Create template assignment (state='template', staff_id=False)
                        # This allows backend forms to add more staff to the same booking
                        try:
                            template_assignment = request.env['health.staff.assignment'].create({
                                'fso_id': next_fso.id,
                                'staff_id': False,  # Empty - template for adding more staff
                                'assignment_date': assignment_date,
                                'state': 'template',
                                'assignment_type': 'clinic_visit',
                                'priority': next_fso.priority or '1',
                            })
                            _logger.info(f'✅ Created template assignment {template_assignment.id} for FSO {next_fso.id}')
                        except Exception as template_error:
                            _logger.error(f'❌ Failed to create template assignment: {str(template_error)}')
                            raise

                        # 2. Create actual assignment (with staff_id - set state='assigned')
                        try:
                            actual_assignment = request.env['health.staff.assignment'].create({
                                'fso_id': next_fso.id,
                                'staff_id': assigned_staff_id,
                                'assignment_date': assignment_date,
                                'assignment_role': 'lead',  # Mark as lead staff
                                'assignment_type': 'clinic_visit',
                                'priority': next_fso.priority or '1',
                                'state': 'assigned',  # Explicitly set default state to assigned
                            })
                            _logger.info(f'✅ Created actual assignment {actual_assignment.id} for FSO {next_fso.id} with staff {assigned_staff_id}')
                        except Exception as actual_error:
                            _logger.error(f'❌ Failed to create actual assignment: {str(actual_error)}')
                            raise
                    except Exception as e:
                        _logger.error(f'❌ Error creating assignment records: {str(e)}', exc_info=True)

            # Create or update quote with line items
            if next_fso.sale_order_id:
                quote = next_fso.sale_order_id
                # Remove existing lines
                quote.order_line.unlink()
            else:
                # Create new quote
                quote = request.env['sale.order'].create({
                    'partner_id': patient.id,
                    'order_line': [],
                })
                next_fso.write({'sale_order_id': quote.id})

            # Add line items to quote
            for item in quote_items:
                request.env['sale.order.line'].create({
                    'order_id': quote.id,
                    'product_id': item.get('product_id'),
                    'product_uom_qty': item.get('quantity', 1),
                    'price_unit': item.get('unit_price', 0),
                })

            # Update patient's next_visit_date
            patient.write({'next_visit_date': next_visit_date})

            return self._prepare_json_response(data={
                'message': 'Next visit scheduled successfully',
                'fso_id': next_fso.id,
                'fso_name': next_fso.name,
                'patient_id': patient.id,
                'next_visit_date': next_visit_date
            })

        except Exception as e:
            _logger.error(f'Error scheduling next visit: {str(e)}')
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/future_bookings', type='http', auth='user', methods=['GET'], csrf=False)
    def api_get_future_bookings(self, **kwargs):
        """Get all future bookings for current user (staff), grouped by date"""
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)

        try:
            user = request.env.user

            # Get employee record for current user
            employee = request.env['hr.employee'].search([
                ('user_id', '=', user.id)
            ], limit=1)

            if not employee:
                return self._prepare_json_response(data={'bookings_by_date': {}})

            # Get current datetime
            from datetime import datetime as dt
            import pytz

            user_tz = pytz.timezone(request.env.user.tz or 'UTC')
            now = dt.now(user_tz)

            # Find all future FSOs
            # Record rules will automatically filter by user assignments
            # First get all future FSOs, then filter out completed/cancelled ones
            all_future_fsos = request.env['health.fieldservice.order'].search([
                ('scheduled_datetime', '>', now.isoformat()),
            ], order='scheduled_datetime asc')

            # Filter out completed/cancelled FSOs based on stage
            fsos = all_future_fsos.filtered(
                lambda fso: not fso.stage_id or (
                    fso.stage_id.state not in ['cancelled', 'completed', 'completed_pending_invoice', 'closed']
                    and fso.stage_id.name.lower() not in ['completed', 'cancelled', 'closed']
                )
            )

            # Debug logging
            excluded_count = len(all_future_fsos) - len(fsos)
            if excluded_count > 0:
                _logger.info(f'Excluded {excluded_count} completed/cancelled future bookings from PWA view')

            # Group bookings by date
            bookings_by_date = {}

            for fso in fsos:
                if fso.scheduled_datetime:
                    # Parse the datetime and convert to user's timezone
                    fso_dt = fso.scheduled_datetime
                    if isinstance(fso_dt, str):
                        fso_dt = dt.fromisoformat(fso_dt.replace('Z', '+00:00'))

                    # Convert to user timezone
                    if fso_dt.tzinfo is None:
                        fso_dt = pytz.UTC.localize(fso_dt)
                    fso_dt_user_tz = fso_dt.astimezone(user_tz)

                    # Format date as YYYY-MM-DD
                    date_str = fso_dt_user_tz.strftime('%Y-%m-%d')
                    date_display = fso_dt_user_tz.strftime('%d %b %Y')  # e.g., "25 Nov 2025"

                    if date_str not in bookings_by_date:
                        bookings_by_date[date_str] = {
                            'date_display': date_display,
                            'bookings': []
                        }

                    # Add booking info
                    bookings_by_date[date_str]['bookings'].append({
                        'id': fso.id,
                        'name': fso.name,
                        'patient_name': fso.patient_id.name if fso.patient_id else 'Unknown',
                        'patient_id': fso.patient_id.id if fso.patient_id else None,
                        'scheduled_time': fso_dt_user_tz.strftime('%H:%M'),
                        'scheduled_datetime': fso.scheduled_datetime,
                        'service_type': fso._get_service_type_label() if hasattr(fso, '_get_service_type_label') else fso.service_type,
                        'state': fso.state,
                        'phone': fso.patient_id.mobile or fso.patient_id.phone if fso.patient_id else '',
                        'address': fso.service_address or '',
                    })

            return self._prepare_json_response(data={'bookings_by_date': bookings_by_date})

        except Exception as e:
            _logger.error(f'Error fetching future bookings: {str(e)}')
            return self._prepare_json_response(error=str(e), status_code=500)

    @http.route('/health_pwa/api/current_user', type='http', auth='user', methods=['GET'], csrf=False)
    def api_get_current_user(self, **kwargs):
        """Get current logged-in user's information"""
        try:
            user = request.env.user

            # Get employee record if exists
            employee = request.env['hr.employee'].search([
                ('user_id', '=', user.id)
            ], limit=1)

            # Check if user is a doctor by checking healthcare_role field
            is_doctor = False
            if employee:
                # Check if healthcare_role field exists and is set to 'doctor'
                if hasattr(employee, 'healthcare_role') and employee.healthcare_role:
                    is_doctor = employee.healthcare_role.lower() == 'doctor'

            user_data = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'employee_id': employee.id if employee else None,
                'employee_name': employee.name if employee else user.name,
                'timezone': user.tz or 'UTC',  # User's timezone for proper datetime handling
                'is_doctor': is_doctor,  # True if user is a doctor
                'booking_credit': employee.booking_credit if employee else 0,  # PWA booking credits
            }

            return self._prepare_json_response(data=user_data)

        except Exception as e:
            _logger.error(f'Error getting current user: {str(e)}')
            return self._prepare_json_response(error=str(e), status_code=500)