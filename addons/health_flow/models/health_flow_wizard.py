# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HealthFlowWizard(models.TransientModel):
    """
    Interactive circular workflow wizard for healthcare operations.
    Provides a modern, animated interface for accessing various healthcare functions.
    """
    _name = 'health.flow.wizard'
    _description = 'Health Flow Dashboard'

    name = fields.Char(
        string='Flow Dashboard',
        default=lambda self: self._default_name(),
        readonly=True
    )

    # ==========================================
    # Action Resolution Methods
    # ==========================================

    @api.model
    def get_action(self, key):
        """
        Return a full action dict for a panel tile or primary circle.
        Uses server-side xmlid resolution so the client can simply do-action.
        """
        # Handle special actions with custom domains/contexts
        if key in ['crm-initial', 'crm-activities', 'crm-calendar']:
            return self._get_crm_action(key)
        elif key in ['booking-draft', 'booking-assigned', 'booking-scheduled']:
            return self._get_booking_action(key)

        # Map keys to action xmlid
        mapping = {
            # Center Circle
            'client': ('health_base.action_health_patient', _('Patient Registry')),

            # Primary Circles - Direct Actions
            'analytics': ('synconics_bi_dashboard.action_bi_dashboard', _('BI Dashboard')),
            'audit': ('health_base.action_health_audit_log', _('Audit Log')),

            # CRM Panel
            'crm-search': ('health_crm.action_healthcare_opportunities', _('CRM Search')),

            # Booking Panel
            'booking-calendar': ('health_fieldservice.action_assignment_scheduler_grid', _('Booking Calendar')),
            'booking-staff': ('health_fieldservice.action_staff_workload_dashboard', _('Staff Assignment')),

            # Invoicing Panel
            'invoicing-ar': ('health_invoicing.action_healthcare_ar_dashboard', _('AR Dashboard')),
            'invoicing-payments': ('health_invoicing.action_health_payment_transaction', _('Payment Transactions')),
            'invoicing-invoices': ('health_invoicing.action_healthcare_invoices', _('Invoices')),

            # Admin Panel (Configuration)
            'admin-pricing-engines': ('advanced_pricing.action_advanced_pricing_engines', _('Pricing Engines')),
            'admin-package-products': ('health_invoicing.action_healthcare_package_products', _('Package Products')),
            'admin-pricing-rules': ('advanced_pricing.action_pricing_rules_with_visual', _('Pricing Rules')),
            'admin-quick-edit-rules': ('advanced_pricing.action_pricing_rules_quick_edit', _('Quick Edit Rules')),
            'admin-portable-equipment': ('health_fieldservice.action_health_portable_equipment', _('Portable Equipment')),
            'admin-facilities': ('health_base.action_health_facility', _('Healthcare Facilities')),
            'admin-patient-categories': ('health_base.action_health_patient_category', _('Patient Categories')),
            'admin-service-types': ('health_base.action_health_service_type', _('Service Types')),
            'admin-symptoms': ('health_base.action_health_symptom', _('Symptoms')),
            'admin-referral-sources': ('health_base.action_health_referral_source', _('Referral Sources')),
            'admin-insurance': ('health_base.action_health_insurance_provider', _('Insurance Providers')),
            'admin-urgency-levels': ('health_base.action_health_urgency_level', _('Urgency Levels')),
        }

        action_xmlid, action_name = mapping.get(key, (False, False))
        if not action_xmlid:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Action Not Found'),
                    'message': _('The requested action "%s" is not configured.', key),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        try:
            action = self.env['ir.actions.actions']._for_xml_id(action_xmlid)
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Action Error'),
                    'message': _('Failed to load action: %s', str(e)),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Open full-screen so breadcrumbs and full controls show
        action['target'] = 'current'
        action.setdefault('context', {})
        action.setdefault('name', action_name)

        return action

    @api.model
    def _get_crm_action(self, key):
        """Get CRM actions with specific filters"""
        try:
            action = self.env['ir.actions.actions']._for_xml_id(
                'health_crm.action_healthcare_opportunities'
            )
            action['target'] = 'current'

            if key == 'crm-initial':
                # Filter for initial contact stage
                action['name'] = _('Initial Contact')
                action['domain'] = [('type', '=', 'opportunity'), ('stage_id.sequence', '<=', 1)]
                action['context'] = {'default_type': 'opportunity'}
            elif key == 'crm-activities':
                # Filter for opportunities with planned activities
                action['name'] = _('Planned Activities')
                action['domain'] = [('type', '=', 'opportunity'), ('activity_ids', '!=', False)]
                action['context'] = {'default_type': 'opportunity'}
            elif key == 'crm-calendar':
                # Open calendar view
                action['name'] = _('CRM Calendar')
                action['view_mode'] = 'calendar,tree,form'
                action['context'] = {'default_type': 'opportunity'}

            return action
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('CRM Action Error'),
                    'message': _('Failed to load CRM action: %s', str(e)),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    @api.model
    def _get_booking_action(self, key):
        """Get Booking actions with calendar view and filters"""
        try:
            action = self.env['ir.actions.actions']._for_xml_id(
                'health_fieldservice.action_health_fieldservice_order'
            )
            action['target'] = 'current'
            # Open calendar view first for Draft/Assigned/Scheduled
            action['view_mode'] = 'calendar,tree,form'

            if key == 'booking-draft':
                action['name'] = _('Draft Bookings Calendar')
                action['domain'] = [('stage_id.is_draft', '=', True)]
                action['context'] = {
                    'default_stage_id': self.env.ref('health_fieldservice.health_fso_stage_draft', False).id if self.env.ref('health_fieldservice.health_fso_stage_draft', False) else False,
                    'search_default_filter_draft': 1,
                }
            elif key == 'booking-assigned':
                action['name'] = _('Assigned Bookings Calendar')
                action['domain'] = [('stage_id.is_assigned', '=', True)]
                action['context'] = {
                    'search_default_filter_assigned': 1,
                }
            elif key == 'booking-scheduled':
                action['name'] = _('Scheduled Bookings Calendar')
                action['domain'] = [('stage_id.is_scheduled', '=', True)]
                action['context'] = {
                    'search_default_filter_scheduled': 1,
                }

            return action
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Booking Action Error'),
                    'message': _('Failed to load Booking action: %s', str(e)),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    @api.model
    def get_booking_counts(self):
        """Get counts for Draft, Assigned, Scheduled bookings"""
        try:
            FSO = self.env['health.fieldservice.order']
            counts = {
                'draft': FSO.search_count([('stage_id.is_draft', '=', True)]),
                'assigned': FSO.search_count([('stage_id.is_assigned', '=', True)]),
                'scheduled': FSO.search_count([('stage_id.is_scheduled', '=', True)]),
            }
            return counts
        except Exception:
            return {'draft': 0, 'assigned': 0, 'scheduled': 0}

    @api.model
    def search_bookings(self, query):
        """Search bookings by client name, phone, or booking reference"""
        try:
            FSO = self.env['health.fieldservice.order']
            domain = [
                '|', '|', '|',
                ('name', 'ilike', query),
                ('patient_id.name', 'ilike', query),
                ('patient_id.mobile', 'ilike', query),
                ('patient_id.phone', 'ilike', query),
            ]
            bookings = FSO.search(domain, limit=20, order='appointment_date desc')

            results = []
            for booking in bookings:
                # Determine status
                status = 'draft'
                if booking.stage_id.is_scheduled:
                    status = 'scheduled'
                elif booking.stage_id.is_assigned:
                    status = 'assigned'
                elif booking.stage_id.is_completed:
                    status = 'completed'

                results.append({
                    'id': booking.id,
                    'client_name': booking.patient_id.name or 'Unknown',
                    'lead_nurse': booking.lead_staff_id.name if booking.lead_staff_id else 'Unassigned',
                    'status': status,
                    'appointment_date': booking.appointment_date.strftime('%Y-%m-%d %H:%M') if booking.appointment_date else 'Not Set',
                })

            return results
        except Exception as e:
            return []

    @api.model
    def get_booking_form_action(self, booking_id):
        """Open booking form view"""
        try:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Booking'),
                'res_model': 'health.fieldservice.order',
                'res_id': booking_id,
                'view_mode': 'form',
                'target': 'current',
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to open booking'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    # ==========================================
    # Defaults / Helpers
    # ==========================================

    @api.model
    def _default_name(self):
        """Ensure the control panel title is always meaningful (no 'New')."""
        return _('Health Flow Dashboard')

    @api.model
    def default_get(self, fields_list):
        """Guarantee name is set even if context/defaults are missing."""
        res = super().default_get(fields_list)
        if 'name' in fields_list:
            res.setdefault('name', self._default_name())
        return res
