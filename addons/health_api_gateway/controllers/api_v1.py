# -*- coding: utf-8 -*-
"""/api/v1 wrapped business endpoints (spec B.5, Phase-1 surface).

Each handler is a thin mirror of the corresponding health_pwa endpoint —
same ORM logic, same `data` payload — running as the authenticated service
user (record rules apply). The legacy /health_pwa/api/* routes are untouched.
"""
import logging
from datetime import datetime as dt

import pytz

from odoo import _, fields, http
from odoo.http import request

from .. import schemas
from .gateway import ApiError, _audit_touch, api_route

_logger = logging.getLogger(__name__)


def _selection_labels(record, field_name):
    return dict(record._fields[field_name]._description_selection(record.env))


class HealthApiV1Controller(http.Controller):

    # ------------------------------------------------------------------
    # Shared serializers (mirrors of the health_pwa private helpers)
    # ------------------------------------------------------------------
    def _get_order_or_404(self, order_id):
        order = request.env['health.fieldservice.order'].browse(order_id)
        if not order.exists():
            raise ApiError(_('Order not found'), 404)
        _audit_touch(model='health.fieldservice.order',
                     record_ids=[order.id],
                     patient_ids=[order.patient_id.id] if order.patient_id else None)
        return order

    def _serialize_patient_summary(self, patient):
        return {
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
            'image_url': f'/web/image/res.partner/{patient.id}/image_128'
                         if patient.image_128 else None,
            'visit_count': patient.visit_count,
            'primary_facility': patient.primary_facility_id.name
                                if patient.primary_facility_id else None,
        }

    def _serialize_booking_summary(self, order):
        scheduled_time = ''
        if order.scheduled_datetime:
            scheduled_time = dt.fromisoformat(
                str(order.scheduled_datetime)).strftime('%I:%M %p')
        return {
            'id': order.id,
            'fso_id': order.id,
            'fso_name': order.name,
            'patient_name': order.patient_id.name if order.patient_id else None,
            'patient_id': order.patient_id.id if order.patient_id else None,
            'patient_code': order.patient_id.patient_code if order.patient_id else None,
            'patient_phone': order.patient_phone,
            'service_type': order._get_service_type_label()
                            if hasattr(order, '_get_service_type_label')
                            else order.service_type,
            'appointment_type': '',
            'scheduled_datetime': order.scheduled_datetime,
            'scheduled_time': scheduled_time,
            'scheduled_duration': order.scheduled_duration,
            'status': order.state,
            'status_display': order.state,
            'location': order.service_address,
            'priority': order.priority,
            'lead_staff_name': order.lead_staff_id.sudo().name
                               if order.lead_staff_id else None,
            'assignment_role': 'staff',
            'notes': order.symptoms or order.patient_notes or '',
        }

    def _serialize_clinical_notes(self, order):
        # Mirror of health_pwa _serialize_clinical_notes (api.py:105)
        notes = []
        if hasattr(order, 'clinical_note_ids'):
            for note in order.clinical_note_ids:
                notes.append({
                    'id': note.id,
                    'author': note.author_id.name if note.author_id else 'Unknown',
                    'author_role': note.author_role or 'Staff',
                    'date': note.create_date.isoformat() if note.create_date else None,
                    'clinical_notes': note.clinical_notes or '',
                    'diagnosis': note.diagnosis or '',
                    'treatment_performed': note.treatment_performed or '',
                    'medications_prescribed': note.medications_prescribed or '',
                    'vital_signs': note.vital_signs or '',
                    'patient_condition_before': note.patient_condition_before or '',
                    'patient_condition_after': note.patient_condition_after or '',
                    'injection_count': note.injection_count,
                    'medication_count': note.medication_count,
                    'wound_count': note.wound_count,
                    'iv_fluid_count': note.iv_fluid_count,
                    'images': [
                        {'id': att.id, 'filename': att.name,
                         'url': f'/web/content/{att.id}'}
                        for att in note.image_ids
                    ],
                })
        return notes

    @staticmethod
    def _is_open_stage(fso):
        return not fso.stage_id or (
            fso.stage_id.state not in ('cancelled', 'completed',
                                       'completed_pending_invoice', 'closed')
            and fso.stage_id.name.lower() not in ('completed', 'cancelled', 'closed'))

    # ==================================================================
    # Patients
    # ==================================================================
    @api_route('/api/v1/patients', methods=('GET',), scopes=('patient.read',),
               summary='List patients with pagination and filtering',
               response_model=schemas.PatientListResponse, tags=('patients',))
    def v1_patients_list(self, **kwargs):
        limit = int(kwargs.get('limit', 50))
        offset = int(kwargs.get('offset', 0))
        search = kwargs.get('search', '')
        status_filter = kwargs.get('status', '')

        domain = [('is_patient', '=', True)]
        if search:
            domain.extend([
                '|', '|', '|',
                ('name', 'ilike', search),
                ('patient_code', 'ilike', search),
                ('phone', 'ilike', search),
                ('mobile', 'ilike', search),
            ])
        if status_filter:
            domain.append(('patient_status', '=', status_filter))

        patients = request.env['res.partner'].search(
            domain, limit=limit, offset=offset, order='name asc')
        total_count = request.env['res.partner'].search_count(domain)
        _audit_touch(model='res.partner', record_ids=patients.ids,
                     patient_ids=patients.ids)
        return {
            'patients': [self._serialize_patient_summary(p) for p in patients],
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total_count,
        }

    @api_route('/api/v1/patients/<int:patient_id>', methods=('GET',),
               scopes=('patient.read',), summary='Patient detail',
               response_model=schemas.PatientDetailResponse, tags=('patients',))
    def v1_patient_detail(self, patient_id, **kwargs):
        patient = request.env['res.partner'].browse(patient_id)
        if not patient.exists() or not patient.is_patient:
            raise ApiError(_('Patient not found'), 404)
        _audit_touch(model='res.partner', record_ids=[patient.id],
                     patient_ids=[patient.id])

        recent_orders = request.env['health.fieldservice.order'].search(
            [('patient_id', '=', patient.id)],
            limit=10, order='scheduled_datetime desc')
        orders_data = [{
            'id': order.id,
            'name': order.name,
            'stage': order.stage_id.name if order.stage_id else None,
            'scheduled_datetime': order.scheduled_datetime,
            'address': order.service_address,
            'service_type': order.service_type_id.name
                            if getattr(order, 'service_type_id', False) else None,
            'team': order.team_id.name if getattr(order, 'team_id', False) else None,
            'priority': order.priority,
        } for order in recent_orders]

        return {
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
            'primary_facility': patient.primary_facility_id.name
                                if patient.primary_facility_id else None,
            'primary_caregiver': patient.primary_caregiver_id.name
                                 if patient.primary_caregiver_id else None,
            'image_url': f'/web/image/res.partner/{patient.id}/image_256'
                         if patient.image_256 else None,
            'recent_orders': orders_data,
        }

    # ==================================================================
    # Bookings
    # ==================================================================
    @api_route('/api/v1/bookings', methods=('GET',), scopes=('booking.read',),
               summary='List bookings (field service orders) with filters',
               response_model=schemas.BookingListResponse, tags=('bookings',))
    def v1_bookings_list(self, **kwargs):
        limit = int(kwargs.get('limit', 50))
        offset = int(kwargs.get('offset', 0))

        domain = []
        if kwargs.get('team_id'):
            domain.append(('team_id', '=', int(kwargs['team_id'])))
        if kwargs.get('stage'):
            domain.append(('stage_id.name', '=', kwargs['stage']))
        if kwargs.get('state'):
            domain.append(('state', '=', kwargs['state']))
        if kwargs.get('patient_id'):
            domain.append(('patient_id', '=', int(kwargs['patient_id'])))
        if kwargs.get('date_from'):
            domain.append(('scheduled_datetime', '>=', kwargs['date_from']))
        if kwargs.get('date_to'):
            domain.append(('scheduled_datetime', '<=', kwargs['date_to']))

        all_orders = request.env['health.fieldservice.order'].search(
            domain, limit=limit, offset=offset, order='scheduled_datetime desc')

        # Same rule as PWA: hide completed/cancelled bookings in the future.
        now_utc = fields.Datetime.now()
        orders = all_orders.filtered(
            lambda fso: (not fso.scheduled_datetime
                         or fso.scheduled_datetime <= now_utc)
            or (fso.scheduled_datetime > now_utc and self._is_open_stage(fso)))

        _audit_touch(model='health.fieldservice.order', record_ids=orders.ids,
                     patient_ids=orders.mapped('patient_id').ids)
        total_count = len(orders)
        return {
            'orders': [self._serialize_booking_summary(o) for o in orders],
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total_count,
        }

    @api_route('/api/v1/bookings/<int:order_id>', methods=('GET',),
               scopes=('booking.read',), summary='Booking detail',
               response_model=schemas.BookingDetailResponse, tags=('bookings',))
    def v1_booking_detail(self, order_id, **kwargs):
        order = self._get_order_or_404(order_id)

        primary_contact = None
        if order.patient_id:
            contacts = request.env['health.client.relation'].search([
                ('client_id', '=', order.patient_id.id),
                ('role', '=', 'emergency_contact'),
                ('is_primary', '=', True),
            ], limit=1)
            if contacts and contacts[0].representative_id:
                contact_partner = contacts[0].representative_id
                primary_contact = {
                    'name': contact_partner.name,
                    'phone': contact_partner.mobile or contact_partner.phone,
                    'relationship': contacts[0].relationship_type
                                    or 'Emergency Contact',
                }
            if not primary_contact:
                primary_contact = {
                    'name': order.patient_id.name,
                    'phone': order.patient_id.mobile or order.patient_id.phone,
                    'relationship': 'Patient',
                }

        quote_items = []
        if order.sale_order_id:
            for line in order.sale_order_id.order_line:
                quote_items.append({
                    'id': line.id,
                    'product_name': line.product_id.name
                                    if line.product_id else line.name,
                    'quantity': float(line.product_uom_qty),
                    'unit_price': float(line.price_unit),
                    'discount': float(line.discount) if line.discount else 0.0,
                    'discount_reason': line.discount_reason
                        if hasattr(line, 'discount_reason') and line.discount_reason
                        else '',
                })

        patient = order.patient_id
        return {
            'id': order.id,
            'name': order.name,
            'state': order.state,
            'stage': order.stage_id.name if order.stage_id else None,
            'priority': order.priority,
            'scheduled_datetime': order.scheduled_datetime,
            'scheduled_duration': order.scheduled_duration,
            'estimated_end_datetime': order.estimated_end_datetime,
            'actual_start_datetime': order.actual_start_datetime,
            'actual_end_datetime': order.actual_end_datetime
                if hasattr(order, 'actual_end_datetime') else None,
            'service_type': order._get_service_type_label()
                            if hasattr(order, '_get_service_type_label')
                            else order.service_type,
            'location': order.service_address,
            'patient': {
                'id': patient.id if patient else None,
                'name': patient.name if patient else None,
                'patient_code': patient.patient_code if patient else None,
                'phone': (patient.phone or patient.mobile) if patient else None,
                'age': patient.age if patient else None,
                'gender': patient.gender if patient else None,
                'allergies': patient.allergies if patient else None,
            },
            'primary_contact': primary_contact,
            'quote_items': quote_items,
            'clinical_notes_submitted': order.clinical_notes_submitted
                if hasattr(order, 'clinical_notes_submitted') else False,
            'clinical_notes': self._serialize_clinical_notes(order),
        }

    @api_route('/api/v1/bookings/<int:order_id>/start', methods=('POST',),
               scopes=('booking.write',), summary='Start service (timer on)',
               request_model=schemas.BookingStartRequest,
               response_model=schemas.BookingStartResponse, tags=('bookings',))
    def v1_booking_start(self, order_id, payload=None, **kwargs):
        order = self._get_order_or_404(order_id)
        if order.state not in ('assigned', 'confirmed'):
            if order.state == 'draft':
                raise ApiError(_(
                    'Service cannot be started because the booking is still in '
                    'Draft status. Please confirm or assign the booking before '
                    'starting service.'), 400)
            raise ApiError(_(
                'Service cannot be started in the current booking status. '
                'Please check the booking before starting service.'), 400)
        order.action_start_service()
        return {
            'actual_start_datetime': order.actual_start_datetime,
            'state': order.state,
            'message': _('Service started successfully'),
        }

    @api_route('/api/v1/bookings/<int:order_id>/complete', methods=('POST',),
               scopes=('booking.write',),
               summary='Complete service (payment_choice/payment_method passthrough)',
               request_model=schemas.BookingCompleteRequest,
               response_model=schemas.BookingCompleteResponse, tags=('bookings',))
    def v1_booking_complete(self, order_id, payload=None, **kwargs):
        order = self._get_order_or_404(order_id)
        data = payload or {}
        if order.state != 'in_progress':
            raise ApiError(
                _('Cannot complete service in %s state') % order.state, 400)

        payment_choice = data.get('payment_choice', 'pay_now')
        payment_method = data.get('payment_method', 'cash')
        service_notes = data.get('service_notes', '')
        create_invoice_now = data.get('create_invoice_now', True)

        if service_notes:
            if hasattr(order, 'nurse_notes'):
                order.write({'nurse_notes': service_notes})
            else:
                request.env['health.clinical.note'].create({
                    'order_id': order.id,
                    'clinical_notes': f'Service Notes: {service_notes}',
                })

        order.action_complete_service()

        message = _('Service completed successfully')
        should_create_invoice = create_invoice_now and order.sale_order_id
        if should_create_invoice:
            sale_order_total = order.sale_order_id.amount_total or 0.0
            if sale_order_total <= 0.0:
                should_create_invoice = False
                message = _('Service completed - No invoice created (zero amount)')

        if should_create_invoice:
            if order.sale_order_id.state in ('draft', 'sent'):
                order.sale_order_id.action_confirm()
            if not order.invoice_id:
                invoices = order.sale_order_id._create_invoices()
                if invoices:
                    order.invoice_id = invoices[0] if len(invoices) == 1 else invoices
                    order.invoice_id.action_post()

        if payment_choice == 'pay_now' and payment_method and order.invoice_id:
            try:
                transaction_vals = {
                    'patient_id': order.patient_id.id if order.patient_id else False,
                    'fso_id': order.id,
                    'invoice_id': order.invoice_id.id if order.invoice_id else False,
                    'amount': order.invoice_id.amount_total
                              if order.invoice_id else 0.0,
                    'payment_method': payment_method,
                    'transaction_type': 'immediate',
                    'status': 'collected' if payment_method != 'cash'
                              else 'pending_delivery',
                    'collected_by_id': request.env.user.employee_id.id
                                       if request.env.user.employee_id else False,
                    'transaction_notes': service_notes
                        or f'Payment collected on service completion via API - {payment_method}',
                }
                if 'health.payment.transaction' in request.env:
                    request.env['health.payment.transaction'].create(
                        transaction_vals)
                    message = _('Service completed - %s payment collected') \
                        % payment_method.replace('_', ' ').title()
                else:
                    message = _('Service completed - %s payment noted') \
                        % payment_method.replace('_', ' ').title()
            except Exception as exc:
                _logger.warning('Could not create payment transaction: %s', exc)
                message = _('Service completed - %s payment noted') \
                    % payment_method.replace('_', ' ').title()
        elif payment_choice == 'pay_later' and order.invoice_id:
            message = _('Service completed - Invoice will be sent for later payment')
        elif not order.invoice_id:
            if 'zero amount' not in message:
                message = _('Service completed - No payment required')

        return {
            'actual_end_datetime': order.actual_end_datetime,
            'adjusted_end_datetime': order.adjusted_end_datetime
                if hasattr(order, 'adjusted_end_datetime') else None,
            'actual_duration': order.actual_duration
                if hasattr(order, 'actual_duration') else None,
            'state': order.state,
            'payment_choice': payment_choice,
            'payment_method': payment_method,
            'message': message,
        }

    @api_route('/api/v1/bookings/<int:order_id>/cancel', methods=('POST',),
               scopes=('booking.write',), summary='Cancel booking with reason',
               request_model=schemas.BookingCancelRequest,
               response_model=schemas.BookingCancelResponse, tags=('bookings',))
    def v1_booking_cancel(self, order_id, payload=None, **kwargs):
        order = self._get_order_or_404(order_id)
        data = payload or {}
        if order.state in ('completed', 'cancelled', 'closed'):
            raise ApiError(
                _('Cannot cancel service in %s state') % order.state, 400)

        cancellation_reason_id = data.get('cancellation_reason_id')
        cancellation_notes = data.get('cancellation_notes', '')
        reason_record = request.env['health.booking.cancellation.reason'].browse(
            int(cancellation_reason_id))
        if not reason_record.exists():
            raise ApiError(_('Invalid cancellation reason'), 400)

        cancellation_note = f'Visit Cancelled/Refused: {reason_record.name}'
        if cancellation_notes:
            cancellation_note += f' - {cancellation_notes}'
        request.env['health.clinical.note'].create({
            'order_id': order.id,
            'clinical_notes': cancellation_note,
        })
        order.cancel_with_reason(reason_record.id, cancellation_notes)
        return {
            'state': order.state,
            'message': _('Visit cancelled successfully'),
            'cancellation_reason': reason_record.name,
        }

    @api_route('/api/v1/bookings/<int:order_id>/clinical-notes', methods=('POST',),
               scopes=('booking.write',), summary='Create a clinical note',
               request_model=schemas.ClinicalNoteRequest,
               response_model=schemas.ClinicalNoteResponse, tags=('bookings',))
    def v1_booking_clinical_notes(self, order_id, payload=None, **kwargs):
        order = self._get_order_or_404(order_id)
        data = payload or {}

        note_vals = {'order_id': order.id}
        for field_name in ('clinical_notes', 'diagnosis', 'treatment_performed',
                           'medications_prescribed', 'vital_signs',
                           'patient_condition_before', 'patient_condition_after'):
            val = data.get(field_name, '')
            if val:
                note_vals[field_name] = val
        for count_field in ('injection_count', 'medication_count',
                            'wound_count', 'iv_fluid_count'):
            if count_field in data and data[count_field] is not None:
                try:
                    note_vals[count_field] = int(data[count_field])
                except (ValueError, TypeError):
                    pass

        note = request.env['health.clinical.note'].create(note_vals)
        return {
            'note_id': note.id,
            'clinical_notes_submitted': order.clinical_notes_submitted,
            'clinical_note_count': order.clinical_note_count,
            'message': _('Clinical note created successfully'),
        }

    @api_route('/api/v1/bookings/<int:order_id>/quote', methods=('GET',),
               scopes=('booking.read',), summary='Quote/sale order for a booking',
               response_model=schemas.QuoteResponse, tags=('bookings',))
    def v1_booking_quote(self, order_id, **kwargs):
        order = self._get_order_or_404(order_id)
        if not order.sale_order_id:
            raise ApiError(_('No quote found for this order'), 404)
        sale_order = order.sale_order_id
        quote_data = {
            'id': sale_order.id,
            'name': sale_order.name,
            'state': sale_order.state,
            'amount_total': float(sale_order.amount_total),
            'amount_untaxed': float(sale_order.amount_untaxed),
            'amount_tax': float(sale_order.amount_tax),
            'currency': sale_order.currency_id.name
                        if sale_order.currency_id else 'VND',
            'order_lines': [],
        }
        for line in sale_order.order_line:
            quote_data['order_lines'].append({
                'id': line.id,
                'product_id': line.product_id.id if line.product_id else None,
                'product_name': line.product_id.name
                                if line.product_id else line.name,
                'description': line.name,
                'quantity': float(line.product_uom_qty),
                'unit_price': float(line.price_unit),
                'discount': float(line.discount)
                            if hasattr(line, 'discount') else 0.0,
                'discount_reason': line.discount_reason
                                   if hasattr(line, 'discount_reason') else '',
                'subtotal': float(line.price_subtotal),
                'total': float(line.price_total),
            })
        return quote_data

    # ==================================================================
    # Assignments / catalog / future bookings
    # ==================================================================
    @api_route('/api/v1/assignments/today', methods=('GET',),
               scopes=('booking.read',),
               summary="Bookings assigned to the service user for a date (default today)",
               response_model=schemas.AssignmentsTodayResponse, tags=('assignments',))
    def v1_assignments_today(self, **kwargs):
        current_user = request.env.user
        employee = request.env['hr.employee'].search(
            [('user_id', '=', current_user.id)], limit=1)

        date_param = kwargs.get('date')
        if date_param:
            try:
                target_date = dt.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                raise ApiError(_('Invalid date format. Use YYYY-MM-DD'), 400)
        else:
            target_date = fields.Date.today()

        user_tz = pytz.timezone(current_user.tz or 'UTC')
        local_start = user_tz.localize(dt.combine(target_date, dt.min.time()))
        local_end = user_tz.localize(dt.combine(target_date, dt.max.time()))
        utc_start = local_start.astimezone(pytz.UTC)
        utc_end = local_end.astimezone(pytz.UTC)

        all_fsos = request.env['health.fieldservice.order'].search([
            ('scheduled_datetime', '>=', utc_start.strftime('%Y-%m-%d %H:%M:%S')),
            ('scheduled_datetime', '<=', utc_end.strftime('%Y-%m-%d %H:%M:%S')),
            ('state', 'not in', ['cancelled']),
        ], order='scheduled_datetime asc')

        now_utc = fields.Datetime.now()
        is_future_date = utc_start.replace(tzinfo=None) > now_utc
        fsos = all_fsos.filtered(self._is_open_stage) if is_future_date else all_fsos

        _audit_touch(model='health.fieldservice.order', record_ids=fsos.ids,
                     patient_ids=fsos.mapped('patient_id').ids)

        bookings_data = []
        for fso in fsos:
            patient = fso.patient_id
            assignment = None
            if employee:
                matched = fso.assignment_ids.filtered(
                    lambda a: a.staff_id.id == employee.id)
                assignment = matched[0] if matched else None

            service_type_label = 'Service'
            if fso.service_type:
                service_type_label = _selection_labels(
                    fso, 'service_type').get(fso.service_type, fso.service_type)

            appointment_type = ''
            if getattr(fso, 'appointment_type_id', False):
                appointment_type = fso.appointment_type_id.name

            bookings_data.append({
                'id': fso.id,
                'fso_id': fso.id,
                'fso_name': fso.name,
                'patient_name': patient.name if patient else 'Unknown',
                'patient_id': patient.id if patient else None,
                'patient_code': patient.patient_code if patient else None,
                'patient_phone': (patient.mobile or patient.phone)
                                 if patient else None,
                'service_type': service_type_label,
                'appointment_type': appointment_type,
                'scheduled_datetime': fso.scheduled_datetime,
                'scheduled_time': fso.scheduled_datetime.strftime('%H:%M')
                                  if fso.scheduled_datetime else '',
                'status': fso.state,
                'status_display': fso.state or 'Unknown',
                'location': fso.service_location or fso.service_address or '',
                'priority': fso.priority,
                'priority_display': _selection_labels(fso, 'priority').get(
                    fso.priority, '') if 'priority' in fso._fields else '',
                'lead_staff_name': fso.lead_staff_id.sudo().name
                                   if fso.lead_staff_id else None,
                'scheduled_duration': fso.scheduled_duration or 60,
                'assignment_role': assignment.assignment_role
                                   if assignment else 'support',
                'notes': getattr(fso, 'patient_notes', '')
                         or getattr(fso, 'symptoms', '') or '',
            })

        return {
            'bookings': bookings_data,
            'total_count': len(bookings_data),
            'staff_name': employee.sudo().name if employee else current_user.name,
            'staff_id': employee.id if employee else None,
            'date': target_date.isoformat(),
            'requested_date': date_param or target_date.isoformat(),
        }

    @api_route('/api/v1/products/catalog', methods=('GET',),
               scopes=('booking.read',), summary='Sellable product catalog',
               response_model=schemas.ProductCatalogResponse, tags=('catalog',))
    def v1_products_catalog(self, **kwargs):
        limit = int(kwargs.get('limit', 50))
        offset = int(kwargs.get('offset', 0))
        search = kwargs.get('search', '')
        category = kwargs.get('category', '')

        domain = [('sale_ok', '=', True)]
        if search:
            domain.extend(['|', ('name', 'ilike', search),
                           ('default_code', 'ilike', search)])
        if category:
            domain.append(('categ_id.name', '=', category))

        products = request.env['product.product'].search(
            domain, limit=limit, offset=offset, order='name asc')
        total_count = request.env['product.product'].search_count(domain)
        _audit_touch(model='product.product', record_ids=products.ids)

        products_data = [{
            'id': product.id,
            'name': product.name,
            'code': product.default_code,
            'description': product.description_sale,
            'price': float(product.list_price),
            'currency': product.currency_id.name if product.currency_id else 'VND',
            'category': product.categ_id.name if product.categ_id else None,
            'uom': product.uom_id.name if product.uom_id else None,
            'image_url': f'/web/image/product.product/{product.id}/image_128'
                         if product.image_128 else None,
        } for product in products]

        return {
            'products': products_data,
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total_count,
        }

    @api_route('/api/v1/future-bookings', methods=('GET',),
               scopes=('booking.read',),
               summary='Future bookings for the service user, grouped by date',
               response_model=schemas.FutureBookingsResponse, tags=('bookings',))
    def v1_future_bookings(self, **kwargs):
        user = request.env.user
        employee = request.env['hr.employee'].search(
            [('user_id', '=', user.id)], limit=1)
        if not employee:
            return {'bookings_by_date': {}}

        user_tz = pytz.timezone(user.tz or 'UTC')
        now = dt.now(user_tz)

        all_future_fsos = request.env['health.fieldservice.order'].search(
            [('scheduled_datetime', '>', now.isoformat())],
            order='scheduled_datetime asc')
        fsos = all_future_fsos.filtered(self._is_open_stage)
        _audit_touch(model='health.fieldservice.order', record_ids=fsos.ids,
                     patient_ids=fsos.mapped('patient_id').ids)

        bookings_by_date = {}
        for fso in fsos:
            if not fso.scheduled_datetime:
                continue
            fso_dt = fso.scheduled_datetime
            if isinstance(fso_dt, str):
                fso_dt = dt.fromisoformat(fso_dt.replace('Z', '+00:00'))
            if fso_dt.tzinfo is None:
                fso_dt = pytz.UTC.localize(fso_dt)
            fso_dt_user_tz = fso_dt.astimezone(user_tz)

            date_str = fso_dt_user_tz.strftime('%Y-%m-%d')
            if date_str not in bookings_by_date:
                bookings_by_date[date_str] = {
                    'date_display': fso_dt_user_tz.strftime('%d %b %Y'),
                    'bookings': [],
                }
            bookings_by_date[date_str]['bookings'].append({
                'id': fso.id,
                'name': fso.name,
                'patient_name': fso.patient_id.name if fso.patient_id else 'Unknown',
                'patient_id': fso.patient_id.id if fso.patient_id else None,
                'patient_code': fso.patient_id.patient_code
                                if fso.patient_id else None,
                'scheduled_time': fso_dt_user_tz.strftime('%H:%M'),
                'scheduled_datetime': fso.scheduled_datetime,
                'service_type': fso._get_service_type_label()
                                if hasattr(fso, '_get_service_type_label')
                                else fso.service_type,
                'state': fso.state,
                'phone': (fso.patient_id.mobile or fso.patient_id.phone)
                         if fso.patient_id else '',
                'address': fso.service_address or '',
                'lead_staff_name': fso.lead_staff_id.name
                                   if fso.lead_staff_id else None,
            })

        return {'bookings_by_date': bookings_by_date}
