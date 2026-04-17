# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


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

    def _ensure_action_name(self, action, fallback_name=None):
        """Ensure action has a non-empty name for breadcrumbs."""
        if not action:
            return action
        name = action.get('name')
        if not name:
            name = fallback_name or action.get('display_name') or action.get('res_model') or _('Action')
            action['name'] = name
        action.setdefault('display_name', action['name'])
        return action

    def _apply_flow_context(self, action):
        """Attach Health Flow menu context so breadcrumbs show the app name."""
        if not action:
            return action
        context = action.get('context', {})
        if isinstance(context, str):
            context = eval(context)
        menu = self.env.ref('health_flow.menu_health_flow_root', raise_if_not_found=False)
        if menu:
            context.setdefault('menu_id', menu.id)
            context.setdefault('health_flow_origin', True)
            params = context.get('params', {})
            if not isinstance(params, dict):
                params = {}
            params.setdefault('menu_id', menu.id)
            params.setdefault('health_flow_origin', True)
            context['params'] = params
            action.setdefault('menu_id', menu.id)
            action_params = action.get('params', {})
            if not isinstance(action_params, dict):
                action_params = {}
            action_params.setdefault('menu_id', menu.id)
            action_params.setdefault('health_flow_origin', True)
            action['params'] = action_params
        action['context'] = context
        return action

    @api.model
    def get_action(self, key):
        """
        Return a full action dict for a panel tile or primary circle.
        Uses server-side xmlid resolution so the client can simply do-action.
        """
        # Handle Contact-First Flow actions
        if key == 'crm-contacts':
            # Open Initial Contact Wizard popup
            return self._get_initial_contact_action()
        elif key == 'crm-followup':
            # Open Follow-up Activities view
            return self._get_followup_activities_action()
        elif key == 'crm-all-contacts':
            # Open All Contacts list grouped by status
            return self._get_all_contacts_grouped_action()
        elif key == 'crm-all-clients':
            # Open All Clients list
            return self._get_all_clients_action()
        
        # Handle legacy CRM actions (keep for backwards compatibility)
        if key in ['crm-add-lead', 'crm-all', 'crm-initial', 'crm-activities', 'crm-calendar', 'crm-continue-followup', 'crm-client-acquired', 'crm-booking-lost']:
            return self._get_crm_action(key)
        elif key in ['booking-calendar', 'booking-all', 'booking-draft', 'booking-assigned', 'booking-scheduled', 'booking-in-progress', 'booking-completed']:
            return self._get_booking_action(key)
        elif key == 'client':
            return self._get_client_action()
        elif key == 'client-new':
            return self._get_client_new_action()
        elif key == 'analytics':
            # Open My Dashboard directly using the dashboard_amcharts client action
            return self._get_my_dashboard_action()
        elif key == 'invoicing-add-invoice':
            # Open account.move form in create mode for manual invoice
            action = {
                'type': 'ir.actions.act_window',
                'name': _('New Invoice'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
                'context': {'default_move_type': 'out_invoice'},
            }
            action = self._ensure_action_name(action, _('New Invoice'))
            return self._apply_flow_context(action)
        elif key == 'ar-account-payment':
            # AR Management (a): Unpaid invoices for payment registration
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Account Payment'),
                'res_model': 'account.move',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
                'domain': [
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                ],
                'context': {'default_move_type': 'out_invoice'},
            }
            action = self._ensure_action_name(action, _('Account Payment'))
            return self._apply_flow_context(action)
        elif key == 'ar-cash-in-transit':
            # AR Management (b): Cash transactions pending delivery to HO
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Cash In Transit Transfers'),
                'res_model': 'health.payment.transaction',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
                'domain': [
                    ('payment_method', '=', 'cash'),
                    ('status', 'in', ['pending_delivery', 'collected']),
                ],
            }
            action = self._ensure_action_name(action, _('Cash In Transit Transfers'))
            return self._apply_flow_context(action)
        elif key == 'ar-refund-credit':
            # AR Management (c): Credit notes and refunds
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Refund / Credit'),
                'res_model': 'account.move',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
                'domain': [
                    ('move_type', '=', 'out_refund'),
                    ('state', '=', 'posted'),
                ],
                'context': {'default_move_type': 'out_refund'},
            }
            action = self._ensure_action_name(action, _('Refund / Credit'))
            return self._apply_flow_context(action)
        elif key == 'admin-pricelist':
            # Open product.product with the catalog search view which has a searchpanel
            # providing a left sidebar with category/subcategory navigation
            search_view = self.env.ref(
                'product.product_view_search_catalog', raise_if_not_found=False
            )
            kanban_view = self.env.ref(
                'product.product_kanban_view', raise_if_not_found=False
            )
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Pricelist'),
                'res_model': 'product.product',
                'view_mode': 'kanban,list,form',
                'views': [
                    (kanban_view.id if kanban_view else False, 'kanban'),
                    (False, 'list'),
                    (False, 'form'),
                ],
                'target': 'current',
                'context': {
                    'default_type': 'service',
                    'default_sale_ok': True,
                },
            }
            if search_view:
                action['search_view_id'] = [search_view.id, search_view.name]
            action = self._ensure_action_name(action, _('Pricelist'))
            return self._apply_flow_context(action)

        # Map keys to action xmlid
        mapping = {
            # Primary Circles - Direct Actions (analytics handled above)
            'audit': ('health_base.action_health_audit_log', _('Audit Log')),

            # CRM Panel
            'crm-search': ('health_crm.action_healthcare_opportunities', _('CRM Search')),

            # Booking Panel
            'booking-staff': ('health_fieldservice.action_staff_workload_dashboard', _('Staff Workload')),
            'booking-staff-assignment': ('health_fieldservice.action_assignment_web_timeline_view', _('Staff Assignment Timeline')),

            # Invoicing / Finance Panel
            'invoicing-ar': ('health_invoicing.action_healthcare_ar_dashboard', _('Accounts Receivable')),
            'invoicing-payments': ('health_invoicing.action_health_payment_transaction', _('Payment Transactions')),
            'invoicing-invoices': ('health_invoicing.action_healthcare_invoices', _('Invoices')),
            'invoicing-vat-log': ('health_invoicing.action_healthcare_vat_invoice_log', _('VAT Invoices Log')),
            'invoicing-ar-log': ('health_invoicing.action_healthcare_ar_transaction_log', _('AR Transactions Log')),

            # Admin Panel (Configuration)
            'admin-user-list': ('health_user_admin.action_healthcare_users', _('Users')),
            'admin-access-roles': ('health_user_admin.action_healthcare_access_roles', _('Access Roles')),
            'admin-role-management': ('health_user_admin.action_healthcare_role_management', _('Role Management')),
            'admin-package-products': ('health_invoicing.action_healthcare_package_products', _('Package Products')),
            'admin-pricing-rules': ('advanced_pricing.action_pricing_rules_with_visual', _('Pricing Rules')),
            'admin-portable-equipment': ('health_fieldservice.action_health_portable_equipment', _('Portable Equipment')),
            'admin-healthcare-staff': ('health_fieldservice.action_healthcare_staff', _('Healthcare Staff')),
            'admin-facilities': ('health_base.action_health_facility', _('Healthcare Facilities')),
            'admin-catchment-provinces': ('health_base.action_health_catchment_province', _('Catchment Provinces')),
            'admin-patient-categories': ('health_base.action_health_patient_category', _('Patient Categories')),
            'admin-field-requirements': ('health_field_requirements.action_field_requirements_dashboard', _('Field Requirements')),
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
        action = self._ensure_action_name(action, action_name)
        return self._apply_flow_context(action)

    # =========================================================================
    # CONTACT-FIRST FLOW ACTIONS
    # =========================================================================

    @api.model
    def _get_initial_contact_action(self):
        """
        Open the Initial Contact Wizard popup.
        This is the entry point for the Contact-First CRM flow.
        """
        try:
            action = self.env['ir.actions.actions']._for_xml_id(
                'health_crm.action_initial_contact_wizard'
            )
            action['target'] = 'new'  # Open as popup
            return self._ensure_action_name(action, _('New Contact'))
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Contact Wizard Error'),
                    'message': _('Failed to open contact wizard: %s', str(e)),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    @api.model
    def _get_followup_activities_action(self):
        """
        Open the Follow-up Activities wizard.
        This wizard provides menu options for managing leads and activities.
        """
        try:
            action = self.env['ir.actions.actions']._for_xml_id(
                'health_crm.action_followup_wizard'
            )
            action['target'] = 'new'
            return action
        except Exception as e:
            # Fallback to activity view if wizard not found
            try:
                action = self.env['ir.actions.actions']._for_xml_id(
                    'health_crm.action_healthcare_opportunities'
                )
                action['target'] = 'current'
                
                # Get form view reference
                form_view = self.env.ref('health_crm.view_healthcare_opportunity_form', raise_if_not_found=False)
                form_view_id = form_view.id if form_view else False
                
                # Filter for leads with pending follow-up or activities
                action['name'] = _('Follow-up Activities')
                action['domain'] = [
                    ('type', '=', 'opportunity'),
                    '|',
                    ('contact_status', '=', 'lead'),
                    ('activity_ids', '!=', False),
                ]
                
                # Use activity view as the primary view
                action.pop('view_ids', None)
                action.pop('views', None)
                action['view_mode'] = 'activity,list,kanban,calendar,form'
                action['views'] = [
                    (False, 'activity'),
                    (False, 'list'),
                    (False, 'kanban'),
                    (False, 'calendar'),
                    (form_view_id, 'form'),
                ]
                
                action['context'] = {
                    'default_type': 'opportunity',
                    'default_contact_status': 'lead',
                    'search_default_my_activities': 1,
                }
                
                action = self._ensure_action_name(action, _('Follow-up Activities'))
                return self._apply_flow_context(action)
            except Exception as e2:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Follow-up Activities Error'),
                        'message': _('Failed to load follow-up activities: %s', str(e2)),
                        'type': 'warning',
                        'sticky': False,
                    }
                }


    @api.model
    def _get_all_contacts_grouped_action(self):
        """
        Open All Contacts list view grouped by contact status.
        """
        try:
            action = self.env['ir.actions.actions']._for_xml_id(
                'health_crm.action_all_contacts_grouped'
            )
            action['target'] = 'current'
            return action
        except Exception as e:
            # Fallback if action not found
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('All Contacts Error'),
                    'message': _('Failed to load all contacts: %s', str(e)),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    @api.model
    def _get_all_clients_action(self):
        """
        Open All Clients list view sorted by creation date descending.
        """
        try:
            action = self.env['ir.actions.actions']._for_xml_id(
                'health_crm.action_all_clients_list'
            )
            action['target'] = 'current'
            return action
        except Exception as e:
            # Fallback if action not found
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('All Clients Error'),
                    'message': _('Failed to load all clients: %s', str(e)),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    @api.model
    def _get_crm_action(self, key):
        """Get CRM actions with specific filters"""
        try:
            # Use dedicated activities calendar action when requested, otherwise default CRM opportunities
            action_xmlid = 'health_flow.action_health_flow_crm_activity_calendar' if key == 'crm-calendar' else 'health_crm.action_healthcare_opportunities'
            action = self.env['ir.actions.actions']._for_xml_id(action_xmlid)
            action['target'] = 'current'

            # Preserve original context and merge with new values
            original_context = action.get('context', {})
            if isinstance(original_context, str):
                original_context = eval(original_context)
            form_view = self.env.ref('health_crm.view_healthcare_opportunity_form', raise_if_not_found=False)
            form_view_id = form_view.id if form_view else False

            if key == 'crm-add-lead':
                quick_form = self.env.ref('health_crm.view_healthcare_crm_lead_quick_create', raise_if_not_found=False)
                action = {
                    'type': 'ir.actions.act_window',
                    'name': _('New Lead'),
                    'res_model': 'crm.lead',
                    'view_mode': 'form',
                    'target': 'new',
                    'views': [(quick_form.id, 'form')] if quick_form else [(False, 'form')],
                    'context': dict(original_context, **{
                        'default_type': 'opportunity',
                    }),
                }
                return self._apply_flow_context(self._ensure_action_name(action, _('New Lead')))
            elif key == 'crm-all':
                action['name'] = _('All Leads')
                action['domain'] = [('type', '=', 'opportunity')]
                action.pop('view_ids', None)
                action.pop('views', None)
                action['view_mode'] = 'kanban,list,activity,calendar,pivot,graph,form'
                action['views'] = [
                    (False, 'kanban'),
                    (False, 'list'),
                    (False, 'activity'),
                    (False, 'calendar'),
                    (False, 'pivot'),
                    (False, 'graph'),
                    (form_view_id, 'form'),
                ]
                action['context'] = dict(original_context, **{'default_type': 'opportunity'})
            elif key == 'crm-initial':
                # Filter for initial contact stage
                action['name'] = _('Initial Contact')
                action['domain'] = [('type', '=', 'opportunity'), ('stage_id.sequence', '<=', 1)]
                action.pop('view_ids', None)  # Remove view_ids so view_mode takes precedence
                action.pop('views', None)  # Remove views as well
                action['view_mode'] = 'list,kanban,activity,calendar,pivot,graph,form'
                action['views'] = [
                    (False, 'list'),
                    (False, 'kanban'),
                    (False, 'activity'),
                    (False, 'calendar'),
                    (False, 'pivot'),
                    (False, 'graph'),
                    (form_view_id, 'form'),
                ]
                action['context'] = dict(original_context, **{'default_type': 'opportunity'})
            elif key == 'crm-activities':
                # Show opportunities with their activities in activity view
                action['name'] = _('Planned Activities')
                action.pop('view_ids', None)  # Remove view_ids so view_mode takes precedence
                action.pop('views', None)  # Remove views as well
                action['view_mode'] = 'activity,list,form'
                action['views'] = [(False, 'activity'), (False, 'list'), (False, 'form')]
                # Show all opportunities - user can see their activities
                action['context'] = dict(original_context, **{
                    'default_type': 'opportunity',
                })
            elif key == 'crm-calendar':
                # Open calendar view
                action['name'] = _('CRM Calendar')
                action['context'] = dict(original_context, **{
                    'default_res_model': 'crm.lead',
                })
            elif key == 'crm-continue-followup':
                # Filter for opportunities pending follow-up
                action['name'] = _('Continue Follow-up')
                action['domain'] = [
                    ('type', '=', 'opportunity'),
                    '|', '|',
                    ('contact_outcome', '=', 'pending_follow_up'),
                    ('health_contact_outcome', '=', 'pending_follow_up'),
                    ('stage_id.name', 'ilike', 'Continue Follow-up'),
                ]
                action.pop('view_ids', None)  # Remove view_ids so view_mode takes precedence
                action.pop('views', None)  # Remove views as well
                action['view_mode'] = 'list,kanban,activity,calendar,pivot,graph,form'
                action['views'] = [
                    (False, 'list'),
                    (False, 'kanban'),
                    (False, 'activity'),
                    (False, 'calendar'),
                    (False, 'pivot'),
                    (False, 'graph'),
                    (form_view_id, 'form'),
                ]
                action['help'] = _('No leads found for this filter.')
                action['context'] = dict(original_context, **{'default_type': 'opportunity'})
            elif key == 'crm-client-acquired':
                # Filter for service booked opportunities
                action['name'] = _('Client Acquired')
                action['domain'] = [
                    ('type', '=', 'opportunity'),
                    '|', '|', '|',
                    ('contact_outcome', '=', 'service_booked'),
                    ('health_contact_outcome', '=', 'service_booked'),
                    ('stage_id.is_won', '=', True),
                    ('stage_id.name', 'ilike', 'Client Acquired'),
                ]
                action.pop('view_ids', None)  # Remove view_ids so view_mode takes precedence
                action.pop('views', None)  # Remove views as well
                action['view_mode'] = 'list,kanban,activity,calendar,pivot,graph,form'
                action['views'] = [
                    (False, 'list'),
                    (False, 'kanban'),
                    (False, 'activity'),
                    (False, 'calendar'),
                    (False, 'pivot'),
                    (False, 'graph'),
                    (form_view_id, 'form'),
                ]
                action['help'] = _('No leads found for this filter.')
                action['context'] = dict(original_context, **{'default_type': 'opportunity'})
            elif key == 'crm-booking-lost':
                # Filter for booking lost opportunities
                action['name'] = _('Booking Lost')
                action['domain'] = [
                    ('type', '=', 'opportunity'),
                    '|', '|',
                    ('contact_outcome', '=', 'booking_lost'),
                    ('health_contact_outcome', '=', 'booking_lost'),
                    ('stage_id.name', 'in', ['Booking Lost', 'Opportunity Lost']),
                ]
                action.pop('view_ids', None)  # Remove view_ids so view_mode takes precedence
                action.pop('views', None)  # Remove views as well
                action['view_mode'] = 'list,kanban,activity,calendar,pivot,graph,form'
                action['views'] = [
                    (False, 'list'),
                    (False, 'kanban'),
                    (False, 'activity'),
                    (False, 'calendar'),
                    (False, 'pivot'),
                    (False, 'graph'),
                    (form_view_id, 'form'),
                ]
                action['help'] = _('No leads found for this filter.')
                action['context'] = dict(original_context, **{'default_type': 'opportunity'})

            action = self._ensure_action_name(action, action.get('name') or _('CRM'))
            return self._apply_flow_context(action)
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
    def _get_client_action(self):
        """Open client registry without menu-bound breadcrumbs"""
        try:
            base_action = self.env['ir.actions.actions']._for_xml_id(
                'health_base.action_health_patient'
            )
            original_context = base_action.get('context', {})
            if isinstance(original_context, str):
                original_context = eval(original_context)

            list_view = self.env.ref('health_base.view_health_patient_tree', raise_if_not_found=False)
            kanban_view = self.env.ref('health_base.view_health_patient_kanban', raise_if_not_found=False)
            form_view = self.env.ref('health_base.view_health_patient_form', raise_if_not_found=False)
            search_view = self.env.ref('health_base.view_health_patient_search', raise_if_not_found=False)

            action = {
                'type': 'ir.actions.act_window',
                'name': _('Client'),
                'res_model': 'res.partner',
                'view_mode': 'list,kanban,form',
                'views': [
                    (list_view.id, 'list') if list_view else (False, 'list'),
                    (kanban_view.id, 'kanban') if kanban_view else (False, 'kanban'),
                    (form_view.id, 'form') if form_view else (False, 'form'),
                ],
                'search_view_id': search_view.id if search_view else False,
                'domain': [('is_patient', '=', True)],
                'context': dict(original_context),
                'target': 'current',
            }
            menu = self.env.ref('health_flow.menu_health_flow_root', raise_if_not_found=False)
            if menu:
                action['context']['health_flow_menu_id'] = menu.id
                action['context']['health_flow_origin'] = True
            if base_action.get('help'):
                action['help'] = base_action['help']
            action = self._ensure_action_name(action, _('Client'))
            return self._apply_flow_context(action)
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Client Action Error'),
                    'message': _('Failed to load client registry: %s', str(e)),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    @api.model
    def _get_client_new_action(self):
        """Open client form in create mode (full-page, Option A)."""
        form_view = self.env.ref('health_base.view_health_patient_form', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window',
            'name': _('New Client'),
            'res_model': 'res.partner',
            'view_mode': 'form',
            'views': [(form_view.id if form_view else False, 'form')],
            'target': 'current',
            'context': {'default_is_patient': True},
        }
        action = self._ensure_action_name(action, _('New Client'))
        return self._apply_flow_context(action)

    @api.model
    def _get_my_dashboard_action(self):
        """Open My Dashboard directly using the dashboard_amcharts client action."""
        try:
            # Get the My Dashboard record
            dashboard = self.env.ref(
                'synconics_bi_dashboard.my_dashboard_default',
                raise_if_not_found=False
            )
            if not dashboard:
                # Fallback: try to find any dashboard named "My Dashboard"
                dashboard = self.env['dashboard.dashboard'].search(
                    [('name', 'ilike', 'My Dashboard')],
                    limit=1
                )
            
            if not dashboard:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Dashboard Not Found'),
                        'message': _('My Dashboard has not been configured yet.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            
            # Return client action to open the dashboard
            action = {
                'type': 'ir.actions.client',
                'tag': 'dashboard_amcharts',
                'name': dashboard.name,
                'display_name': dashboard.name,
                'params': {
                    'record': dashboard.id,
                    'menu_name': dashboard.name,
                    'dashboard_name': dashboard.name,
                },
                'target': 'current',
            }
            return self._apply_flow_context(action)
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Dashboard Error'),
                    'message': _('Failed to load My Dashboard: %s', str(e)),
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
            # Open calendar view first for status filters
            action['view_mode'] = 'calendar,list,form'

            # Preserve original context and merge with new values
            original_context = action.get('context', {})
            if isinstance(original_context, str):
                original_context = eval(original_context)

            calendar_view = self.env.ref('health_fieldservice.view_health_fieldservice_order_calendar', raise_if_not_found=False)
            list_view = self.env.ref('health_fieldservice.view_health_fieldservice_order_list', raise_if_not_found=False)
            form_view = self.env.ref('health_fieldservice.view_health_fieldservice_order_form', raise_if_not_found=False)
            calendar_views = [
                (calendar_view.id, 'calendar') if calendar_view else (False, 'calendar'),
                (list_view.id, 'list') if list_view else (False, 'list'),
                (form_view.id, 'form') if form_view else (False, 'form'),
            ]

            if key == 'booking-all':
                action['name'] = _('All Bookings')
                action['view_mode'] = 'list,form'
                action['views'] = [
                    (list_view.id, 'list') if list_view else (False, 'list'),
                    (form_view.id, 'form') if form_view else (False, 'form'),
                ]
                action['context'] = dict(original_context, **{
                    'group_by': 'scheduled_datetime:month',
                })
            elif key == 'booking-calendar':
                action['name'] = _('Booking Calendar')
                action['views'] = calendar_views
                action['context'] = dict(original_context)
            if key == 'booking-draft':
                action['name'] = _('Draft Bookings Calendar')
                action['domain'] = [('state', '=', 'draft')]
                action['views'] = calendar_views
                action['context'] = dict(original_context, **{
                    'search_default_filter_draft': 1,
                })
            elif key == 'booking-assigned':
                action['name'] = _('Assigned Bookings Calendar')
                action['domain'] = [('state', '=', 'assigned')]
                action['views'] = calendar_views
                action['context'] = dict(original_context, **{
                    'search_default_filter_assigned': 1,
                })
            elif key == 'booking-scheduled':
                action['name'] = _('Scheduled Bookings Calendar')
                action['domain'] = [('state', '=', 'confirmed')]
                action['views'] = calendar_views
                action['context'] = dict(original_context, **{
                    'search_default_filter_scheduled': 1,
                })
            elif key == 'booking-in-progress':
                action['name'] = _('In Progress Bookings Calendar')
                action['domain'] = [('stage_id.name', '=', 'In Progress')]
                action['views'] = calendar_views
                action['context'] = dict(original_context, **{
                    'search_default_filter_in_progress': 1,
                })
            elif key == 'booking-completed':
                action['name'] = _('Completed Bookings Calendar')
                action['domain'] = [('stage_id.name', '=', 'Completed')]
                action['views'] = calendar_views
                action['context'] = dict(original_context, **{
                    'search_default_filter_completed': 1,
                })

            action = self._ensure_action_name(action, _('Bookings'))
            return self._apply_flow_context(action)
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
        """Get counts for Draft, Assigned, Scheduled, In Progress, Completed bookings"""
        try:
            FSO = self.env['health.fieldservice.order']
            counts = {
                'draft': FSO.search_count([('state', '=', 'draft')]),
                'assigned': FSO.search_count([('state', '=', 'assigned')]),
                'scheduled': FSO.search_count([('state', '=', 'confirmed')]),
                'in_progress': FSO.search_count([('stage_id.name', '=', 'In Progress')]),
                'completed': FSO.search_count([('stage_id.name', '=', 'Completed')]),
            }
            return counts
        except Exception:
            return {'draft': 0, 'assigned': 0, 'scheduled': 0, 'in_progress': 0, 'completed': 0}

    @api.model
    def get_crm_counts(self):
        """Get counts for CRM tiles."""
        try:
            Lead = self.env['crm.lead']
            base_domain = [('type', '=', 'opportunity')]
            counts = {
                'all': Lead.search_count(base_domain),
                'initial': Lead.search_count(base_domain + [('stage_id.sequence', '<=', 1)]),
                'continue_followup': Lead.search_count(base_domain + [
                    '|', '|',
                    ('contact_outcome', '=', 'pending_follow_up'),
                    ('health_contact_outcome', '=', 'pending_follow_up'),
                    ('stage_id.name', 'ilike', 'Continue Follow-up'),
                ]),
                'client_acquired': Lead.search_count(base_domain + [
                    '|', '|', '|',
                    ('contact_outcome', '=', 'service_booked'),
                    ('health_contact_outcome', '=', 'service_booked'),
                    ('stage_id.is_won', '=', True),
                    ('stage_id.name', 'ilike', 'Client Acquired'),
                ]),
                'booking_lost': Lead.search_count(base_domain + [
                    '|', '|',
                    ('contact_outcome', '=', 'booking_lost'),
                    ('health_contact_outcome', '=', 'booking_lost'),
                    ('stage_id.name', 'in', ['Booking Lost', 'Opportunity Lost']),
                ]),
                'planned_activities': Lead.search_count(base_domain + [('activity_ids', '!=', False)]),
            }
            counts['calendar'] = counts['planned_activities']
            return counts
        except Exception:
            return {
                'all': 0,
                'initial': 0,
                'continue_followup': 0,
                'client_acquired': 0,
                'booking_lost': 0,
                'planned_activities': 0,
                'calendar': 0,
            }

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
            if query.isdigit():
                domain = ['|', ('id', '=', int(query))] + domain

            bookings = FSO.search(domain, limit=20, order='scheduled_datetime desc')

            results = []
            for booking in bookings:
                # Determine status
                status = 'draft'
                if booking.state == 'confirmed':
                    status = 'scheduled'
                elif booking.state == 'assigned':
                    status = 'assigned'
                elif booking.state == 'in_progress':
                    status = 'in_progress'
                elif booking.state == 'completed':
                    status = 'completed'

                results.append({
                    'id': booking.id,
                    'client_name': booking.patient_id.name or 'Unknown',
                    'lead_nurse': booking.lead_staff_id.name if booking.lead_staff_id else 'Unassigned',
                    'status': status,
                    'appointment_date': booking.scheduled_datetime.strftime('%Y-%m-%d %H:%M') if booking.scheduled_datetime else 'Not Set',
                })

            return results
        except Exception as e:
            return []

    @api.model
    def search_crm_leads(self, query):
        """Search CRM clients and leads by name, phone, or email"""
        try:
            Partner = self.env['res.partner']
            Lead = self.env['crm.lead']

            client_domain = [
                ('is_patient', '=', True),
                '|', '|', '|', '|',
                ('name', 'ilike', query),
                ('phone', 'ilike', query),
                ('mobile', 'ilike', query),
                ('email', 'ilike', query),
                ('patient_code', 'ilike', query),
            ]
            clients = Partner.search(client_domain, limit=20, order='name')

            lead_domain = [
                ('type', '=', 'opportunity'),
                ('stage_id.name', '!=', 'Client Acquired'),
                '|', '|',
                ('name', 'ilike', query),
                ('phone', 'ilike', query),
                ('email_from', 'ilike', query),
            ]
            leads = Lead.search(lead_domain, limit=20, order='create_date desc')

            client_results = []
            for client in clients:
                client_results.append({
                    'id': client.id,
                    'name': client.name or 'Unknown',
                    'phone': client.phone or client.mobile or 'N/A',
                    'email': client.email or 'N/A',
                    'patient_code': client.patient_code or 'Client',
                })

            lead_results = []
            for lead in leads:
                stage_name = lead.stage_id.name if lead.stage_id else 'New'
                lead_results.append({
                    'id': lead.id,
                    'name': lead.name or 'Unknown',
                    'contact_name': lead.contact_name or '',
                    'phone': lead.phone or 'N/A',
                    'email': lead.email_from or 'N/A',
                    'stage': stage_name,
                    'contact_outcome': lead.contact_outcome or 'pending',
                })

            return {
                'clients': client_results,
                'leads': lead_results,
            }
        except Exception as e:
            return {
                'clients': [],
                'leads': [],
            }

    @api.model
    def get_booking_form_action(self, booking_id):
        """Open booking hub/spoke dashboard"""
        try:
            booking = self.env['health.fieldservice.order'].browse(booking_id).exists()
            if not booking:
                raise UserError(_('Booking not found.'))

            if hasattr(booking, 'action_open_fso_dashboard'):
                action = booking.action_open_fso_dashboard()
                menu = self.env.ref('health_flow.menu_health_flow_root', raise_if_not_found=False)
                if menu:
                    action.setdefault('params', {})
                    action['params']['menu_id'] = menu.id
                    action['params']['health_flow_origin'] = True
                action.setdefault('target', 'current')
                return self._ensure_action_name(action, _('Booking Dashboard'))

            view = self.env.ref('health_fieldservice.view_health_fieldservice_order_form', raise_if_not_found=False)
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Booking'),
                'res_model': 'health.fieldservice.order',
                'res_id': booking_id,
                'view_mode': 'form',
                'target': 'current',
            }
            action['views'] = [(view.id, 'form')] if view else [(False, 'form')]
            return self._ensure_action_name(action, _('Booking'))
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

    @api.model
    def get_client_form_action(self, client_id):
        """Open client hub view"""
        try:
            partner = self.env['res.partner'].browse(client_id).exists()
            if not partner:
                raise UserError(_('Client not found.'))

            if hasattr(partner, 'action_open_hub_spoke'):
                action = partner.action_open_hub_spoke()
                menu = self.env.ref('health_flow.menu_health_flow_root', raise_if_not_found=False)
                if menu:
                    action.setdefault('params', {})
                    action['params']['menu_id'] = menu.id
                    action['params']['health_flow_origin'] = True
                action.setdefault('target', 'current')
                return self._ensure_action_name(action, _('Client Dashboard'))

            view = self.env.ref('health_base.view_health_patient_form', raise_if_not_found=False)
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Client'),
                'res_model': 'res.partner',
                'res_id': client_id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_is_patient': True},
            }
            action['views'] = [(view.id, 'form')] if view else [(False, 'form')]
            return self._ensure_action_name(action, _('Client'))
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to open client'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    # ==========================================
    # Defaults / Helpers
    # ==========================================

    @api.model
    def get_crm_lead_form_action(self, lead_id):
        """Open CRM lead hub view."""
        try:
            lead = self.env['crm.lead'].browse(lead_id).exists()
            if lead and hasattr(lead, 'action_open_lead_hub'):
                action = lead.action_open_lead_hub()
                return self._ensure_action_name(action, _('Lead Dashboard'))

            view = self.env.ref('health_crm.view_healthcare_opportunity_form', raise_if_not_found=False)
            action = {
                'type': 'ir.actions.act_window',
                'name': _('CRM Contact'),
                'res_model': 'crm.lead',
                'res_id': lead_id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_type': 'opportunity'},
            }
            action['views'] = [(view.id, 'form')] if view else [(False, 'form')]
            return self._ensure_action_name(action, _('CRM Contact'))
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to open lead'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

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

    @api.model
    def create_crm_lead(self, values):
        """Create a simple CRM lead/opportunity from the modal."""
        name = (values or {}).get('name')
        if not name:
            raise UserError(_('Contact Name is required.'))

        facility_id = values.get('facility_id')
        facility_name = values.get('facility_name')
        if not facility_id and facility_name:
            facility = self.env['health.facility'].search([('name', 'ilike', facility_name)], limit=1)
            facility_id = facility.id if facility else False

        lead_vals = {
            'name': name,
            'type': 'opportunity',
            'email_from': values.get('email'),
            'phone': values.get('phone'),
            'facility_id': facility_id or False,
        }
        lead = self.env['crm.lead'].create(lead_vals)
        return {'id': lead.id}

    # ==========================================
    # User Info & Notifications
    # ==========================================

    @api.model
    def get_user_info(self):
        """Get current user's name and catchment province for top bar display."""
        user = self.env.user
        catchment_name = ''
        if hasattr(user, 'catchment_province_id') and user.catchment_province_id:
            catchment_name = user.catchment_province_id.name or ''
        return {
            'userName': user.name or '',
            'userFacility': catchment_name,  # Keep key name for backward compatibility
        }

    @api.model
    def get_booking_notifications(self):
        """
        Get booking notifications for the current user.
        Returns new bookings, upcoming bookings, cancelled bookings, and rescheduled bookings.
        """
        from datetime import datetime, timedelta
        notifications = []
        seen_booking_ids = set()  # Track which bookings we've already added

        try:
            FSO = self.env['health.fieldservice.order']
            today = fields.Datetime.now()
            tomorrow = today + timedelta(days=1)
            yesterday = today - timedelta(days=1)

            # New bookings created in the last 24 hours
            new_bookings = FSO.search([
                ('create_date', '>=', yesterday),
                ('state', '=', 'draft'),
            ], limit=5, order='create_date desc')

            for booking in new_bookings:
                if booking.id not in seen_booking_ids:
                    notifications.append({
                        'id': f"new_{booking.id}",  # Unique composite key
                        'booking_id': booking.id,
                        'type': 'new',
                        'title': _('New Booking'),
                        'subtitle': booking.patient_id.name or booking.name or _('Unknown'),
                    })
                    seen_booking_ids.add(booking.id)

            # Upcoming bookings in the next 24 hours
            upcoming_bookings = FSO.search([
                ('scheduled_datetime', '>=', today),
                ('scheduled_datetime', '<=', tomorrow),
                ('state', 'in', ['confirmed', 'assigned']),
            ], limit=5, order='scheduled_datetime asc')

            for booking in upcoming_bookings:
                if booking.id not in seen_booking_ids:
                    time_str = booking.scheduled_datetime.strftime('%H:%M') if booking.scheduled_datetime else ''
                    notifications.append({
                        'id': f"upcoming_{booking.id}",  # Unique composite key
                        'booking_id': booking.id,
                        'type': 'upcoming',
                        'title': _('Upcoming: %s', time_str),
                        'subtitle': booking.patient_id.name or booking.name or _('Unknown'),
                    })
                    seen_booking_ids.add(booking.id)

            # Cancelled bookings in the last 24 hours
            cancelled_bookings = FSO.search([
                ('write_date', '>=', yesterday),
                ('state', '=', 'cancelled'),
            ], limit=5, order='write_date desc')

            for booking in cancelled_bookings:
                if booking.id not in seen_booking_ids:
                    notifications.append({
                        'id': f"cancelled_{booking.id}",  # Unique composite key
                        'booking_id': booking.id,
                        'type': 'cancelled',
                        'title': _('Cancelled'),
                        'subtitle': booking.patient_id.name or booking.name or _('Unknown'),
                    })
                    seen_booking_ids.add(booking.id)

            # Rescheduled bookings (modified in last 24 hours with future date)
            # We'll filter in Python to check write_date != create_date
            rescheduled_bookings = FSO.search([
                ('write_date', '>=', yesterday),
                ('scheduled_datetime', '>=', today),
                ('state', 'in', ['draft', 'confirmed', 'assigned']),
            ], limit=10, order='write_date desc')

            rescheduled_count = 0
            for booking in rescheduled_bookings:
                if rescheduled_count >= 5:
                    break
                if booking.id in seen_booking_ids:
                    continue  # Skip if already in notifications
                # Only include if it was actually modified after creation (rescheduled)
                if booking.write_date and booking.create_date:
                    time_diff = abs((booking.write_date - booking.create_date).total_seconds())
                    if time_diff > 60:  # More than 1 minute difference
                        date_str = booking.scheduled_datetime.strftime('%m/%d %H:%M') if booking.scheduled_datetime else ''
                        notifications.append({
                            'id': f"rescheduled_{booking.id}",  # Unique composite key
                            'booking_id': booking.id,
                            'type': 'rescheduled',
                            'title': _('Rescheduled: %s', date_str),
                            'subtitle': booking.patient_id.name or booking.name or _('Unknown'),
                        })
                        seen_booking_ids.add(booking.id)
                        rescheduled_count += 1

        except Exception as e:
            # Return empty list if there's an error (e.g., model not installed)
            pass

        return notifications

    @api.model
    def get_home_action(self):
        """Return action to navigate to Health Flow home page."""
        try:
            action = self.env['ir.actions.actions']._for_xml_id(
                'health_flow.action_health_flow_dashboard'
            )
            action['target'] = 'current'
            return action
        except Exception:
            return {
                'type': 'ir.actions.client',
                'tag': 'health_flow_dashboard',
                'target': 'current',
            }
