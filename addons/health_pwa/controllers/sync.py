# -*- coding: utf-8 -*-

import json
from datetime import datetime, timedelta
from odoo import http, fields
from odoo.http import request


class HealthPWASyncController(http.Controller):
    """Data synchronization endpoints for offline PWA functionality"""
    
    def _check_sync_access(self):
        """Check if user has sync access to health modules"""
        if not request.env.user or request.env.user.id == request.env.ref('base.public_user').id:
            return False
        
        try:
            request.env['res.partner'].check_access_rights('read')
            return True
        except:
            return False
    
    def _prepare_sync_response(self, data=None, error=None, status_code=200):
        """Prepare standardized sync response"""
        response_data = {
            'success': error is None,
            'timestamp': fields.Datetime.now().isoformat(),
            'server_time': fields.Datetime.now().isoformat(),
        }
        
        if error:
            response_data['error'] = error
        else:
            response_data.update(data or {})
        
        return request.make_response(
            json.dumps(response_data, default=str, ensure_ascii=False),
            headers=[
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With'),
            ],
            status=status_code
        )
    
    @http.route('/health_pwa/sync/debug', type='http', auth='user', methods=['GET'], csrf=False)
    def sync_debug_info(self, **kwargs):
        """Debug endpoint to check what data is available for sync"""
        if not self._check_sync_access():
            return self._prepare_sync_response(error='Access denied', status_code=403)
        
        try:
            # Check total counts
            total_patients = request.env['res.partner'].search_count([('is_patient', '=', True)])
            total_orders = request.env['health.fieldservice.order'].search_count([])
            total_teams = request.env['health.fieldservice.team'].search_count([])
            
            # Check user's teams
            user_teams = request.env['health.fieldservice.team'].search([
                ('member_ids', 'in', [request.env.user.id])
            ])
            
            # Get recent patients (last 30 days)
            since_30_days = fields.Datetime.now() - timedelta(days=30)
            recent_patients = request.env['res.partner'].search_count([
                ('is_patient', '=', True),
                '|',
                ('write_date', '>=', since_30_days),
                ('create_date', '>=', since_30_days),
            ])
            
            # Get recent orders (last 30 days)
            recent_orders = request.env['health.fieldservice.order'].search_count([
                '|',
                ('write_date', '>=', since_30_days),
                ('create_date', '>=', since_30_days),
            ])
            
            debug_info = {
                'current_user': request.env.user.name,
                'user_id': request.env.user.id,
                'total_patients': total_patients,
                'total_orders': total_orders,
                'total_teams': total_teams,
                'user_teams': [{'id': t.id, 'name': t.name} for t in user_teams],
                'recent_patients_30d': recent_patients,
                'recent_orders_30d': recent_orders,
                'server_time': fields.Datetime.now().isoformat(),
                'since_30d_filter': since_30_days.isoformat(),
            }
            
            return self._prepare_sync_response(data=debug_info)
            
        except Exception as e:
            return self._prepare_sync_response(error=str(e), status_code=500)

    @http.route('/health_pwa/sync/changes', type='http', auth='user', methods=['GET'], csrf=False)
    def sync_get_changes(self, **kwargs):
        """Get changes since last sync timestamp for offline synchronization"""
        if not self._check_sync_access():
            return self._prepare_sync_response(error='Access denied', status_code=403)
        
        try:
            # Check if this is a forced full sync
            force_full = kwargs.get('force_full', False)
            
            # TEMPORARY DEBUG: Always use 30 days ago for sync to ensure we get data
            last_sync = fields.Datetime.now() - timedelta(days=30)
            
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"Sync: Using sync timestamp: {last_sync} (force_full={force_full})")
            
            # Parse sync timestamp - last time client synced
            # last_sync = kwargs.get('since')
            # if last_sync and not force_full:
            #     try:
            #         # Handle ISO format with Z suffix from JavaScript
            #         if last_sync.endswith('Z'):
            #             last_sync = last_sync[:-1] + '+00:00'
            #         last_sync = fields.Datetime.from_string(last_sync.replace('T', ' ').split('+')[0].split('.')[0])
            #     except:
            #         # Fallback to 30 days ago if parsing fails
            #         last_sync = fields.Datetime.now() - timedelta(days=30)
            # else:
            #     # If no timestamp provided or forced full sync, sync last 30 days
            #     last_sync = fields.Datetime.now() - timedelta(days=30)
            
            # Get user's teams for filtering relevant data
            user_teams = request.env['health.fieldservice.team'].search([
                ('member_ids', 'in', [request.env.user.id])
            ])
            
            changes = {
                'patients': self._get_patient_changes(last_sync),
                'field_service_orders': self._get_fso_changes(last_sync, user_teams),
                'teams': self._get_team_changes(last_sync, user_teams),
                'service_types': self._get_service_type_changes(last_sync),
                'facilities': self._get_facility_changes(last_sync),
            }
            
            # Calculate total changes count
            total_changes = sum(len(changes[key]['records']) for key in changes)
            
            # Add debug info to sync response
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"Sync Summary: {total_changes} total changes - Patients: {len(changes['patients']['records'])}, Orders: {len(changes['field_service_orders']['records'])}")
            
            sync_data = {
                'changes': changes,
                'total_changes': total_changes,
                'last_sync': last_sync.isoformat(),
                'current_time': fields.Datetime.now().isoformat(),
                'debug_info': {
                    'since_datetime': last_sync.isoformat(),
                    'force_full': kwargs.get('force_full', False),
                    'patients_found': len(changes['patients']['records']),
                    'orders_found': len(changes['field_service_orders']['records']),
                    'teams_found': len(changes['teams']['records']),
                }
            }
            
            return self._prepare_sync_response(data=sync_data)
            
        except Exception as e:
            return self._prepare_sync_response(error=str(e), status_code=500)
    
    def _get_patient_changes(self, since_datetime):
        """Get patient changes since last sync"""
        # First check if any patients exist at all
        all_patients = request.env['res.partner'].search([('is_patient', '=', True)], limit=1)
        if not all_patients:
            # No patients exist, return empty
            return {
                'model': 'res.partner',
                'count': 0,
                'records': [],
            }
        
        # For debugging: log the datetime filter being used
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"Sync: Looking for patients modified since {since_datetime}")
        
        domain = [
            ('is_patient', '=', True),
            '|',
            ('write_date', '>=', since_datetime),
            ('create_date', '>=', since_datetime),
        ]
        
        patients = request.env['res.partner'].search(domain, limit=500)
        _logger.info(f"Sync: Found {len(patients)} patients matching date filter")
        
        patient_records = []
        for patient in patients:
            patient_records.append({
                'id': patient.id,
                'name': patient.name,
                'patient_code': patient.patient_code,
                'first_name': patient.first_name,
                'last_name': patient.last_name,
                'phone': patient.phone,
                'mobile': patient.mobile,
                'email': patient.email,
                'birth_date': patient.birth_date,
                'age': patient.age,
                'gender': patient.gender,
                'blood_group': patient.blood_group,
                'patient_status': patient.patient_status,
                'allergies': patient.allergies,
                'medical_history': patient.medical_history,
                'street': patient.street,
                'city': patient.city,
                'country': patient.country_id.name if patient.country_id else None,
                'emergency_contact_name': patient.emergency_contact_name,
                'emergency_contact_phone': patient.emergency_contact_phone,
                'last_visit_date': patient.last_visit_date,
                'next_visit_date': patient.next_visit_date,
                'created_date': patient.create_date,
                'updated_date': patient.write_date,
                'is_deleted': False,  # For future soft deletion support
            })
        
        return {
            'model': 'res.partner',
            'count': len(patient_records),
            'records': patient_records,
        }
    
    def _get_fso_changes(self, since_datetime, user_teams):
        """Get field service order changes since last sync"""
        # First check if any FSOs exist at all
        all_orders = request.env['health.fieldservice.order'].search([], limit=1)
        if not all_orders:
            # No orders exist, return empty
            return {
                'model': 'health.fieldservice.order',
                'count': 0,
                'records': [],
            }
        
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"Sync: Looking for FSOs modified since {since_datetime}")
        
        domain = [
            '|',
            ('write_date', '>=', since_datetime),
            ('create_date', '>=', since_datetime),
        ]
        
        # TEMPORARILY DISABLED: Filter by user's teams for debugging
        # if user_teams:
        #     _logger.info(f"Sync: Filtering by user teams: {user_teams.mapped('name')}")
        #     domain.append(('team_id', 'in', user_teams.ids))
        # else:
        _logger.info("Sync: Including all FSOs (team filtering disabled for debugging)")
        
        orders = request.env['health.fieldservice.order'].search(domain, limit=500)
        _logger.info(f"Sync: Found {len(orders)} FSOs matching criteria")
        
        order_records = []
        for order in orders:
            order_records.append({
                'id': order.id,
                'name': order.name,
                'patient_id': order.patient_id.id if order.patient_id else None,
                'patient_name': order.patient_id.name if order.patient_id else None,
                'patient_code': order.patient_id.patient_code if order.patient_id else None,
                'stage_id': order.stage_id.id if order.stage_id else None,
                'stage_name': order.stage_id.name if order.stage_id else None,
                'priority': order.priority,
                'scheduled_datetime': order.scheduled_datetime,
                'estimated_end_datetime': order.estimated_end_datetime,
                'estimated_duration': order.estimated_duration,
                'duration_minutes': order.duration_minutes,
                'service_type': order.service_type,
                'service_type_name': dict(order._fields['service_type'].selection).get(order.service_type, ''),
                'team_id': order.team_id.id if order.team_id else None,
                'team_name': order.team_id.name if order.team_id else None,
                'booking_user_id': order.booking_user_id.id if order.booking_user_id else None,
                'booking_user_name': order.booking_user_id.name if order.booking_user_id else None,
                'service_address': order.service_address,
                'patient_phone': order.patient_phone,
                'symptoms': order.symptoms,
                'patient_notes': order.patient_notes,
                'gps_coordinates': order.gps_coordinates,
                'state': order.state,
                'actual_start_datetime': order.actual_start_datetime if hasattr(order, 'actual_start_datetime') else None,
                'actual_end_datetime': order.actual_end_datetime if hasattr(order, 'actual_end_datetime') else None,
                'actual_duration': order.actual_duration if hasattr(order, 'actual_duration') else None,
                'address': order.service_address,  # Add duplicate for compatibility
                'created_date': order.create_date,
                'updated_date': order.write_date,
                'is_deleted': False,
            })
        
        return {
            'model': 'health.fieldservice.order',
            'count': len(order_records),
            'records': order_records,
        }
    
    def _get_team_changes(self, since_datetime, user_teams):
        """Get team changes since last sync"""
        domain = [
            '|',
            ('write_date', '>=', since_datetime),
            ('create_date', '>=', since_datetime),
        ]
        
        # Only sync teams user is member of
        if user_teams:
            domain.append(('id', 'in', user_teams.ids))
        
        teams = request.env['health.fieldservice.team'].search(domain)
        
        team_records = []
        for team in teams:
            team_records.append({
                'id': team.id,
                'name': team.name,
                'description': team.description,
                'active': team.active,
                'member_ids': team.member_ids.ids,
                'member_names': [m.name for m in team.member_ids],
                'created_date': team.create_date,
                'updated_date': team.write_date,
                'is_deleted': False,
            })
        
        return {
            'model': 'health.fieldservice.team',
            'count': len(team_records),
            'records': team_records,
        }
    
    def _get_service_type_changes(self, since_datetime):
        """Get service type changes since last sync"""
        domain = [
            '|',
            ('write_date', '>=', since_datetime),
            ('create_date', '>=', since_datetime),
        ]
        
        service_types = request.env['health.service.type'].search(domain)
        
        service_type_records = []
        for stype in service_types:
            service_type_records.append({
                'id': stype.id,
                'name': stype.name,
                'code': stype.code,
                'description': stype.description,
                'duration_minutes': stype.duration_minutes,
                'base_price': stype.base_price,
                'category': stype.category,
                'active': stype.active,
                'available_home': stype.available_home,
                'available_clinic': stype.available_clinic,
                'available_telemedicine': stype.available_telemedicine,
                'requires_doctor': stype.requires_doctor,
                'requires_nurse': stype.requires_nurse,
                'staff_count': stype.staff_count,
                'created_date': stype.create_date,
                'updated_date': stype.write_date,
                'is_deleted': False,
            })
        
        return {
            'model': 'health.service.type',
            'count': len(service_type_records),
            'records': service_type_records,
        }
    
    def _get_facility_changes(self, since_datetime):
        """Get facility changes since last sync"""
        domain = [
            '|',
            ('write_date', '>=', since_datetime),
            ('create_date', '>=', since_datetime),
        ]
        
        facilities = request.env['health.facility'].search(domain)
        
        facility_records = []
        for facility in facilities:
            facility_records.append({
                'id': facility.id,
                'name': facility.name,
                'code': facility.code,
                'facility_type': facility.facility_type,
                'street': facility.street,
                'street2': facility.street2,
                'city': facility.city,
                'state_id': facility.state_id.id if facility.state_id else None,
                'state_name': facility.state_id.name if facility.state_id else None,
                'zip': facility.zip,
                'country_id': facility.country_id.id if facility.country_id else None,
                'country_name': facility.country_id.name if facility.country_id else None,
                'phone': facility.phone,
                'email': facility.email,
                'website': facility.website,
                'operating_hours': facility.operating_hours,
                'active': facility.active,
                'created_date': facility.create_date,
                'updated_date': facility.write_date,
                'is_deleted': False,
            })
        
        return {
            'model': 'health.facility',
            'count': len(facility_records),
            'records': facility_records,
        }
    
    @http.route('/health_pwa/sync/push', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_push_changes(self, **kwargs):
        """Push changes from mobile device back to server"""
        if not self._check_sync_access():
            return {'success': False, 'error': 'Access denied'}
        
        try:
            data = request.jsonrequest
            changes = data.get('changes', {})
            results = []
            
            # Process FSO updates
            if 'field_service_orders' in changes:
                fso_results = self._process_fso_updates(changes['field_service_orders'])
                results.extend(fso_results)
            
            # Process patient updates (limited fields for mobile users)
            if 'patients' in changes:
                patient_results = self._process_patient_updates(changes['patients'])
                results.extend(patient_results)
            
            # Calculate statistics
            successful_updates = len([r for r in results if r['success']])
            failed_updates = len([r for r in results if not r['success']])
            
            return {
                'success': True,
                'results': results,
                'statistics': {
                    'total_processed': len(results),
                    'successful_updates': successful_updates,
                    'failed_updates': failed_updates,
                },
                'server_time': fields.Datetime.now().isoformat(),
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _process_fso_updates(self, fso_changes):
        """Process field service order updates from mobile"""
        results = []
        
        for change in fso_changes:
            try:
                order_id = change.get('id')
                if not order_id:
                    results.append({
                        'type': 'field_service_order',
                        'id': None,
                        'success': False,
                        'error': 'Missing order ID'
                    })
                    continue
                
                order = request.env['health.fieldservice.order'].browse(order_id)
                if not order.exists():
                    results.append({
                        'type': 'field_service_order',
                        'id': order_id,
                        'success': False,
                        'error': 'Order not found'
                    })
                    continue
                
                # Only allow updating specific fields from mobile
                allowed_fields = {
                    'patient_notes': 'patient_notes',
                    'completion_notes': 'completion_notes',
                    'duration_actual': 'duration_actual',
                    'service_lat': 'service_lat',
                    'service_lng': 'service_lng',
                    'stage_id': 'stage_id',
                }
                
                update_vals = {}
                for mobile_field, odoo_field in allowed_fields.items():
                    if mobile_field in change:
                        update_vals[odoo_field] = change[mobile_field]
                
                # Update the order
                if update_vals:
                    order.write(update_vals)
                
                results.append({
                    'type': 'field_service_order',
                    'id': order_id,
                    'success': True,
                    'updated_fields': list(update_vals.keys())
                })
                
            except Exception as e:
                results.append({
                    'type': 'field_service_order',
                    'id': change.get('id'),
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def _process_patient_updates(self, patient_changes):
        """Process patient updates from mobile (limited fields)"""
        results = []
        
        for change in patient_changes:
            try:
                patient_id = change.get('id')
                if not patient_id:
                    results.append({
                        'type': 'patient',
                        'id': None,
                        'success': False,
                        'error': 'Missing patient ID'
                    })
                    continue
                
                patient = request.env['res.partner'].browse(patient_id)
                if not patient.exists() or not patient.is_patient:
                    results.append({
                        'type': 'patient',
                        'id': patient_id,
                        'success': False,
                        'error': 'Patient not found'
                    })
                    continue
                
                # Only allow updating limited fields from mobile for security
                allowed_fields = {
                    'phone': 'phone',
                    'mobile': 'mobile',
                    'next_visit_date': 'next_visit_date',
                }
                
                update_vals = {}
                for mobile_field, odoo_field in allowed_fields.items():
                    if mobile_field in change:
                        update_vals[odoo_field] = change[mobile_field]
                
                if update_vals:
                    patient.write(update_vals)
                
                results.append({
                    'type': 'patient',
                    'id': patient_id,
                    'success': True,
                    'updated_fields': list(update_vals.keys())
                })
                
            except Exception as e:
                results.append({
                    'type': 'patient',
                    'id': change.get('id'),
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    @http.route('/health_pwa/sync/status', type='http', auth='user', methods=['GET'], csrf=False)
    def sync_status(self, **kwargs):
        """Get sync status and server information"""
        if not self._check_sync_access():
            return self._prepare_sync_response(error='Access denied', status_code=403)
        
        try:
            # Get user's teams
            user_teams = request.env['health.fieldservice.team'].search([
                ('member_ids', 'in', [request.env.user.id])
            ])
            
            # Get recent activity counts
            today = fields.Date.today()
            recent_patients = request.env['res.partner'].search_count([
                ('is_patient', '=', True),
                ('write_date', '>=', today - timedelta(days=7))
            ])
            
            recent_orders = request.env['health.fieldservice.order'].search_count([
                ('write_date', '>=', today - timedelta(days=7))
            ])
            
            status_data = {
                'server_time': fields.Datetime.now().isoformat(),
                'user_id': request.env.user.id,
                'user_name': request.env.user.name,
                'user_teams': [{'id': t.id, 'name': t.name} for t in user_teams],
                'sync_enabled': True,
                'recent_activity': {
                    'patients_updated_last_7_days': recent_patients,
                    'orders_updated_last_7_days': recent_orders,
                },
                'server_version': '18.0',
                'pwa_version': '1.0.0',
            }
            
            return self._prepare_sync_response(data=status_data)
            
        except Exception as e:
            return self._prepare_sync_response(error=str(e), status_code=500)
    
    @http.route('/health_pwa/sync/reset', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_reset_client(self, **kwargs):
        """Reset client sync state - force full resync"""
        if not self._check_sync_access():
            return {'success': False, 'error': 'Access denied'}
        
        try:
            # Return server time to reset client sync timestamp
            reset_data = {
                'success': True,
                'message': 'Client reset requested - perform full sync',
                'reset_timestamp': fields.Datetime.now().isoformat(),
                'server_time': fields.Datetime.now().isoformat(),
            }
            
            return reset_data
            
        except Exception as e:
            return {'success': False, 'error': str(e)}