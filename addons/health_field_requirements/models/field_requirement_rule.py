# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class FieldRequirementRule(models.Model):
    """Configuration model for mandatory field rules.

    Each record defines a rule that makes a specific field mandatory
    on a specific model, optionally scoped to:
    - Specific roles (or global for all roles)
    - Specific states (or always required)
    """
    _name = 'field.requirement.rule'
    _description = 'Field Requirement Rule'
    _order = 'model_id, field_id'
    _rec_name = 'display_name'

    # --- Core fields ---
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain="[('transient', '=', False)]",
        help='The model (form) this rule applies to',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Model Name',
        store=True,
        index=True,
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', model_id), ('store', '=', True), "
               "('ttype', 'not in', ['one2many', 'binary'])]",
        help='The field that should be mandatory',
    )
    field_name = fields.Char(
        related='field_id.name',
        string='Field Name',
        store=True,
        index=True,
    )
    field_label = fields.Char(
        related='field_id.field_description',
        string='Field Label',
        store=True,
    )

    # --- Scope: Global vs Role-specific ---
    is_global = fields.Boolean(
        string='Global (All Roles)',
        default=True,
        help='If checked, this rule applies to ALL users. '
             'If unchecked, only applies to users with the selected roles.',
    )
    role_ids = fields.Many2many(
        'access.role',
        string='Roles',
        help='Roles this rule applies to (only when Global is unchecked)',
    )

    # --- Scope: Always vs Per-State ---
    state_values = fields.Char(
        string='Required in States',
        help='Comma-separated list of state values where this field is required. '
             'Leave empty for "always required". '
             'Example: confirmed,assigned,in_progress',
    )
    state_values_display = fields.Char(
        string='States',
        compute='_compute_state_values_display',
    )

    # --- Meta ---
    active = fields.Boolean(default=True)
    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )

    # No SQL constraints — a model/field can have multiple rules
    # (global + role-specific, or different state configurations)

    @api.depends('model_id', 'field_id', 'state_values', 'is_global')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.model_id:
                parts.append(record.model_id.name or record.model_name)
            if record.field_id:
                parts.append(record.field_label or record.field_name)
            if record.state_values:
                parts.append(f'[{record.state_values}]')
            if not record.is_global:
                parts.append('(role-specific)')
            record.display_name = ' → '.join(parts) if parts else _('New Rule')

    @api.depends('state_values')
    def _compute_state_values_display(self):
        for record in self:
            if record.state_values:
                record.state_values_display = record.state_values.replace(',', ', ')
            else:
                record.state_values_display = _('Always')

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Clear field when model changes."""
        self.field_id = False

    @api.onchange('is_global')
    def _onchange_is_global(self):
        """Clear roles when switching to global."""
        if self.is_global:
            self.role_ids = False

    # =========================================================================
    # PUBLIC API — used by both server-side and client-side enforcement
    # =========================================================================

    @api.model
    def get_required_fields(self, model_name, state=None, user=None):
        """Return list of field names that are required for the given context.

        Args:
            model_name: Technical model name (e.g., 'health.fieldservice.order')
            state: Current state value (optional). If None, returns only
                   "always required" fields.
            user: res.users record (optional). Defaults to current user.

        Returns:
            List of field name strings.
        """
        domain = [
            ('model_name', '=', model_name),
            ('active', '=', True),
        ]
        rules = self.sudo().search(domain)
        if not rules:
            return []

        # Filter by role
        user = user or self.env.user
        role = getattr(user, 'access_role_id', None)
        applicable = rules.filtered(
            lambda r: r.is_global or (role and role in r.role_ids)
        )

        # Filter by state
        if state:
            applicable = applicable.filtered(
                lambda r: not r.state_values
                or state in [s.strip() for s in r.state_values.split(',')]
            )
        else:
            # No state context — return only "always required" rules
            applicable = applicable.filtered(lambda r: not r.state_values)

        return list(set(applicable.mapped('field_name')))

    @api.model
    def get_required_fields_with_states(self, model_name, user=None):
        """Return a dict of {field_name: [state1, state2, ...]} for dynamic
        required expressions in views.

        Fields with empty state_values (always required) get an empty list.
        """
        domain = [
            ('model_name', '=', model_name),
            ('active', '=', True),
        ]
        rules = self.sudo().search(domain)

        user = user or self.env.user
        role = getattr(user, 'access_role_id', None)
        applicable = rules.filtered(
            lambda r: r.is_global or (role and role in r.role_ids)
        )

        result = {}
        for rule in applicable:
            states = [s.strip() for s in rule.state_values.split(',')] if rule.state_values else []
            if rule.field_name in result:
                # Merge states — if any rule has empty states (always), that wins
                existing = result[rule.field_name]
                if not existing or not states:
                    result[rule.field_name] = []
                else:
                    result[rule.field_name] = list(set(existing + states))
            else:
                result[rule.field_name] = states

        return result

    # =========================================================================
    # DASHBOARD API — used by the visual client action
    # =========================================================================

    @api.model
    def get_hierarchy(self):
        """Return the 4-layer hierarchy for the Field Requirements dashboard.

        Layer 1: Primary nodes (CRM, Bookings, Finance, Admin)
        Layer 2: Tiles within each node
        Layer 3: Models used by those tiles (deduplicated)

        Returns list of node dicts, each containing tiles with models.
        """
        # Tile → model mapping (matches health_flow dashboard structure)
        tile_model_map = {
            # CRM
            'crm-contacts': ['crm.lead'],
            'crm-followup': ['crm.lead'],
            'crm-all-contacts': ['crm.lead'],
            'crm-all-clients': ['res.partner'],
            # Bookings
            'booking-all': ['health.fieldservice.order'],
            'booking-calendar': ['health.fieldservice.order'],
            'booking-staff': ['health.fieldservice.order'],
            'booking-staff-assignment': ['health.fieldservice.order'],
            'booking-draft': ['health.fieldservice.order'],
            'booking-assigned': ['health.fieldservice.order'],
            'booking-scheduled': ['health.fieldservice.order'],
            'booking-in-progress': ['health.fieldservice.order'],
            'booking-completed': ['health.fieldservice.order'],
            # Finance
            'invoicing-invoices': ['account.move'],
            'invoicing-ar': ['account.move'],
            'invoicing-add-invoice': ['account.move'],
            'invoicing-vat-log': ['account.move'],
            'invoicing-ar-log': ['account.move'],
            'invoicing-payments': ['health.payment.transaction'],
            'invoicing-ar-management': ['health.payment.transaction', 'account.move'],
            # Admin
            'admin-user-management': ['res.users'],
            'admin-pricelist': ['product.product'],
            'admin-package-products': ['product.product'],
            'admin-pricing-rules': ['advanced.pricing.rule'],
            'admin-portable-equipment': ['health.portable.equipment'],
            'admin-healthcare-staff': ['health.fieldservice.staff'],
            'admin-patient-categories': ['health.patient.category'],
            'admin-master-data': [
                'health.facility', 'health.service.type',
                'health.symptom', 'health.referral.source',
                'health.insurance.provider', 'health.urgency.level',
            ],
        }

        nodes = [
            {
                'key': 'crm',
                'name': 'Sales & CRM',
                'icon': 'fa-handshake-o',
                'color': '#4299e1',
                'tiles': [
                    {'key': 'crm-contacts', 'name': 'Contacts', 'icon': 'fa-phone'},
                    {'key': 'crm-followup', 'name': 'Follow-up Activities', 'icon': 'fa-calendar-check-o'},
                    {'key': 'crm-all-contacts', 'name': 'All Contacts', 'icon': 'fa-address-book'},
                    {'key': 'crm-all-clients', 'name': 'All Clients', 'icon': 'fa-user'},
                ],
            },
            {
                'key': 'booking',
                'name': 'Bookings & Assignments',
                'icon': 'fa-calendar',
                'color': '#ed8936',
                'tiles': [
                    {'key': 'booking-all', 'name': 'All Bookings', 'icon': 'fa-list'},
                    {'key': 'booking-staff', 'name': 'Staff Workload', 'icon': 'fa-user-md'},
                    {'key': 'booking-staff-assignment', 'name': 'Staff Assignment', 'icon': 'fa-users'},
                ],
            },
            {
                'key': 'invoicing',
                'name': 'Finance',
                'icon': 'fa-money',
                'color': '#48bb78',
                'tiles': [
                    {'key': 'invoicing-invoices', 'name': 'Invoices', 'icon': 'fa-file-text-o'},
                    {'key': 'invoicing-ar', 'name': 'Accounts Receivable', 'icon': 'fa-dashboard'},
                    {'key': 'invoicing-ar-management', 'name': 'AR Management', 'icon': 'fa-tasks'},
                    {'key': 'invoicing-payments', 'name': 'Payment Transactions', 'icon': 'fa-credit-card'},
                ],
            },
            {
                'key': 'admin',
                'name': 'Admin',
                'icon': 'fa-cog',
                'color': '#9f7aea',
                'tiles': [
                    {'key': 'admin-user-management', 'name': 'User Management', 'icon': 'fa-users'},
                    {'key': 'admin-master-data', 'name': 'Master Data', 'icon': 'fa-database'},
                    {'key': 'admin-pricelist', 'name': 'Pricelist', 'icon': 'fa-list-alt'},
                    {'key': 'admin-package-products', 'name': 'Package Products', 'icon': 'fa-cube'},
                    {'key': 'admin-pricing-rules', 'name': 'Pricing Rules', 'icon': 'fa-list-ul'},
                    {'key': 'admin-portable-equipment', 'name': 'Portable Equipment', 'icon': 'fa-briefcase'},
                    {'key': 'admin-healthcare-staff', 'name': 'Healthcare Staff', 'icon': 'fa-user-md'},
                    {'key': 'admin-patient-categories', 'name': 'Patient Categories', 'icon': 'fa-bookmark'},
                ],
            },
        ]

        # Enrich tiles with model info and rule counts
        for node in nodes:
            node_rule_count = 0
            for tile in node['tiles']:
                model_names = tile_model_map.get(tile['key'], [])
                tile_models = []
                seen = set()
                for mn in model_names:
                    if mn in seen:
                        continue
                    seen.add(mn)
                    info = self._get_model_info(mn)
                    if info:
                        tile_models.append(info)
                tile['models'] = tile_models
                tile['rule_count'] = sum(m['rule_count'] for m in tile_models)
                node_rule_count += tile['rule_count']
            node['rule_count'] = node_rule_count

        return nodes

    def _get_model_info(self, model_name):
        """Get model metadata for the hierarchy display."""
        model = self.env['ir.model'].sudo().search([
            ('model', '=', model_name),
        ], limit=1)
        if not model:
            return None

        rule_count = self.sudo().search_count([
            ('model_name', '=', model_name),
            ('active', '=', True),
        ])

        return {
            'id': model.id,
            'model': model_name,
            'name': model.name,
            'rule_count': rule_count,
        }

    @api.model
    def get_model_fields_config(self, model_name):
        """Return fields and their requirement configs for a model.

        Only returns fields that appear in the model's form views,
        making the configuration UI manageable and relevant.

        Returns dict:
            {fields: [{field_name, field_label, ...}],
             roles: [...], model_name, model_label}
        """
        import lxml.etree as ET

        model = self.env['ir.model'].sudo().search([
            ('model', '=', model_name),
        ], limit=1)
        if not model:
            return {'fields': [], 'roles': [], 'model_name': model_name, 'model_label': ''}

        # ── Step 1: Extract field names from form views ──
        form_views = self.env['ir.ui.view'].sudo().search([
            ('model', '=', model_name),
            ('type', '=', 'form'),
            ('active', '=', True),
        ])

        form_field_names = set()
        for view in form_views:
            try:
                arch = view.arch
                if not arch:
                    continue
                tree = ET.fromstring(arch.encode('utf-8') if isinstance(arch, str) else arch)
                for field_el in tree.iter('field'):
                    fname = field_el.get('name')
                    if fname:
                        form_field_names.add(fname)
            except Exception:
                continue

        if not form_field_names:
            # Fallback: if no form views found, show all storable fields
            form_field_names = None

        # ── Step 2: Get matching ir.model.fields records ──
        domain = [
            ('model_id', '=', model.id),
            ('store', '=', True),
            ('ttype', 'not in', ['one2many', 'binary']),
            ('name', 'not in', [
                'id', 'create_uid', 'create_date',
                'write_uid', 'write_date', '__last_update',
                'display_name',
            ]),
        ]
        if form_field_names is not None:
            domain.append(('name', 'in', list(form_field_names)))

        ir_fields = self.env['ir.model.fields'].sudo().search(
            domain, order='field_description'
        )

        # ── Step 3: Map existing rules ──
        rules = self.sudo().search([('model_name', '=', model_name)])
        rule_map = {r.field_name: r for r in rules}

        # ── Step 4: Available roles ──
        roles = self.env['access.role'].sudo().search([])
        available_roles = [{'id': r.id, 'name': r.name} for r in roles]

        # ── Step 5: Build result ──
        result = []
        for field in ir_fields:
            rule = rule_map.get(field.name)
            result.append({
                'field_name': field.name,
                'field_label': field.field_description or field.name,
                'field_type': field.ttype,
                'field_id': field.id,
                'model_id': model.id,
                'has_rule': bool(rule),
                'rule_id': rule.id if rule else False,
                'is_global': rule.is_global if rule else True,
                'role_ids': rule.role_ids.ids if rule else [],
                'role_names': ', '.join(rule.role_ids.mapped('name')) if rule else '',
                'state_values': rule.state_values or '' if rule else '',
                'active': rule.active if rule else False,
            })

        return {
            'fields': result,
            'roles': available_roles,
            'model_name': model_name,
            'model_label': model.name,
        }

    @api.model
    def save_field_rule(self, data):
        """Create or update a field requirement rule from the dashboard.

        Args:
            data: dict with keys: model_id, field_id, is_global,
                  role_ids, state_values, active
        Returns:
            dict with rule_id
        """
        rule_id = data.get('rule_id')
        vals = {
            'is_global': data.get('is_global', True),
            'role_ids': [(6, 0, data.get('role_ids', []))],
            'state_values': data.get('state_values', ''),
            'active': data.get('active', True),
        }

        if rule_id:
            rule = self.sudo().browse(rule_id)
            if rule.exists():
                rule.write(vals)
                return {'rule_id': rule.id}

        # Create new rule
        vals.update({
            'model_id': data.get('model_id'),
            'field_id': data.get('field_id'),
        })
        rule = self.sudo().create(vals)
        return {'rule_id': rule.id}

    @api.model
    def delete_field_rule(self, rule_id):
        """Delete a field requirement rule."""
        rule = self.sudo().browse(rule_id)
        if rule.exists():
            rule.unlink()
        return True

