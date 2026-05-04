# -*- coding: utf-8 -*-

import json
import logging
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Fields to always skip when scanning models
SKIP_FIELDS = {
    'id', '__last_update', 'display_name', 'create_uid', 'create_date',
    'write_uid', 'write_date', 'message_ids', 'message_follower_ids',
    'message_partner_ids', 'message_channel_ids', 'activity_ids',
    'activity_state', 'activity_user_id', 'activity_type_id',
    'activity_date_deadline', 'activity_summary', 'activity_exception_decoration',
    'activity_exception_icon', 'message_is_follower', 'message_has_error',
    'message_has_sms_error', 'message_needaction', 'message_needaction_counter',
    'message_attachment_count', 'message_has_error_counter',
    'message_main_attachment_id', 'website_message_ids',
    'rating_ids', 'rating_last_value', 'rating_last_feedback',
    'rating_last_image', 'rating_count', 'rating_avg',
    'access_url', 'access_token', 'access_warning',
}

# Field types that should be classified as measures
MEASURE_TYPES = {'integer', 'float', 'monetary'}

# Field types that should be classified as dates
DATE_TYPES = {'date', 'datetime'}

# Field types that should be classified as dimensions
DIMENSION_TYPES = {'char', 'text', 'selection', 'many2one', 'boolean', 'html'}

# Smart field grouping heuristics
FIELD_GROUP_RULES = {
    'financial': ['amount', 'total', 'price', 'cost', 'tax', 'balance',
                  'credit', 'debit', 'revenue', 'profit', 'margin',
                  'payment', 'invoice', 'monetary', 'currency'],
    'date_time': ['date', 'datetime', 'deadline', 'scheduled', 'planned',
                  'created', 'modified', 'start', 'end', 'period'],
    'customer': ['partner', 'customer', 'client', 'contact', 'vendor',
                 'supplier', 'patient', 'employee'],
    'product': ['product', 'item', 'service', 'article', 'sku'],
    'location': ['city', 'state', 'country', 'province', 'district',
                 'address', 'zip', 'street', 'region', 'area', 'branch'],
    'status': ['state', 'status', 'stage', 'type', 'priority',
               'category', 'active'],
}


class BiDataset(models.Model):
    """Semantic dataset — the heart of BI Studio.
    
    Like Power BI's 'Semantic Model' or Tableau's 'Data Source'.
    A dataset defines WHAT data to query: root model, selected fields
    (including from related models), grain level, filters, and aggregation.
    """
    _name = 'bi.dataset'
    _description = 'BI Dataset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Dataset Name', required=True, tracking=True)
    description = fields.Text('Description')

    # Business Domain
    domain_id = fields.Many2one('bi.business.domain', string='Business Domain',
                                tracking=True)

    # Root model
    model_id = fields.Many2one('ir.model', string='Source Model', required=True,
                               ondelete='cascade', tracking=True)
    model_name = fields.Char(related='model_id.model', string='Model', store=True)
    model_label = fields.Char(related='model_id.name', string='Model Label')

    # Report grain — critical for child table handling
    grain_level = fields.Selection([
        ('root', 'Root Model Level'),
        ('child', 'Child/Line Level'),
    ], string='Report Grain', default='root', required=True,
       help='Root: one row per main record. Child: one row per child record (e.g., invoice line).')
    grain_child_field = fields.Char(
        'Grain Child Field',
        help='If grain is child-level, the One2many field name (e.g., invoice_line_ids)')

    # Fields
    field_ids = fields.One2many('bi.dataset.field', 'dataset_id',
                                string='Dataset Fields')

    # Filters
    domain_filter = fields.Text('Domain Filter', default='[]',
                                help='Odoo domain expression for filtering records')
    
    # Options
    record_limit = fields.Integer('Record Limit', default=1000,
                                  help='Maximum records to fetch. 0 = unlimited.')
    sort_field = fields.Char('Sort By', help='Field path for default sorting')
    sort_order = fields.Selection([
        ('asc', 'Ascending'),
        ('desc', 'Descending'),
    ], string='Sort Order', default='desc')

    # Sharing
    is_shared = fields.Boolean('Shared', default=False, tracking=True,
                               help='Make this dataset available to all users')
    owner_id = fields.Many2one('res.users', string='Owner',
                               default=lambda self: self.env.user)

    # Computed
    field_count = fields.Integer('Fields', compute='_compute_field_count')
    selected_field_count = fields.Integer('Selected', compute='_compute_field_count')
    record_count = fields.Integer('Records', compute='_compute_record_count')
    active = fields.Boolean('Active', default=True)

    @api.depends('field_ids', 'field_ids.is_selected')
    def _compute_field_count(self):
        for ds in self:
            ds.field_count = len(ds.field_ids)
            ds.selected_field_count = len(ds.field_ids.filtered('is_selected'))

    def _compute_record_count(self):
        for ds in self:
            if ds.model_name:
                try:
                    domain = self._parse_domain(ds.domain_filter)
                    ds.record_count = self.env[ds.model_name].search_count(domain)
                except Exception:
                    ds.record_count = 0
            else:
                ds.record_count = 0

    @api.model_create_multi
    def create(self, vals_list):
        datasets = super().create(vals_list)
        for ds in datasets:
            if ds.model_name:
                ds._auto_scan_fields()
        return datasets

    def write(self, vals):
        result = super().write(vals)
        if 'model_id' in vals:
            for ds in self:
                ds.field_ids.unlink()
                ds._auto_scan_fields()
        return result

    # =========================================================================
    # LAYER 1 — Model Explorer
    # =========================================================================

    def _auto_scan_fields(self):
        """Scan the root model and its Many2one relations to auto-populate fields."""
        if not self.model_name:
            return

        model = self.env[self.model_name]
        field_vals = []
        seq = 0

        # --- Root model fields ---
        for fname, field_obj in model._fields.items():
            if fname in SKIP_FIELDS:
                continue
            if field_obj.type in ('one2many', 'many2many', 'binary', 'reference'):
                # One2many fields are handled as potential grain-child sources
                if field_obj.type == 'one2many':
                    # Store as a child relation marker (not a data field)
                    pass
                continue

            role = self._classify_field_role(field_obj)
            if not role:
                continue

            seq += 1
            field_vals.append({
                'dataset_id': self.id,
                'field_name': fname,
                'field_path': fname,
                'field_label': field_obj.string or fname.replace('_', ' ').title(),
                'odoo_field_type': field_obj.type,
                'field_role': role,
                'field_group': self._guess_field_group(fname, field_obj),
                'default_aggregation': self._default_aggregation(field_obj.type, role),
                'source_model': self.model_name,
                'source_model_label': self.model_label or self.model_name,
                'is_from_relation': False,
                'sequence': seq,
                'is_selected': role == 'measure' or fname in ('name', 'state',
                    'partner_id', 'date', 'invoice_date', 'date_order',
                    'create_date', 'amount_total', 'stage_id'),
            })

        # --- Many2one related fields (1-level deep) ---
        for fname, field_obj in model._fields.items():
            if fname in SKIP_FIELDS or field_obj.type != 'many2one':
                continue
            if not field_obj.comodel_name:
                continue

            try:
                related_model = self.env[field_obj.comodel_name]
            except KeyError:
                continue

            # Get key fields from the related model
            for rfname, rfield_obj in related_model._fields.items():
                if rfname in SKIP_FIELDS:
                    continue
                if rfield_obj.type in ('one2many', 'many2many', 'binary',
                                       'many2one', 'reference', 'html'):
                    continue

                role = self._classify_field_role(rfield_obj)
                if not role:
                    continue

                # Only include commonly useful related fields
                if role == 'dimension' and rfname not in (
                    'name', 'display_name', 'code', 'city', 'country_id',
                    'state_id', 'email', 'phone', 'mobile', 'street',
                    'zip', 'vat', 'ref', 'type', 'category_id',
                    'company_id', 'currency_id', 'default_code',
                    'categ_id', 'uom_id', 'barcode',
                ):
                    # Skip obscure text fields from relations to avoid noise
                    if rfield_obj.type in ('char', 'text') and rfname != 'name':
                        continue

                seq += 1
                rel_label = field_obj.string or fname.replace('_', ' ').title()
                field_label = rfield_obj.string or rfname.replace('_', ' ').title()
                
                field_vals.append({
                    'dataset_id': self.id,
                    'field_name': rfname,
                    'field_path': f'{fname}.{rfname}',
                    'field_label': f'{rel_label} → {field_label}',
                    'odoo_field_type': rfield_obj.type,
                    'field_role': role,
                    'field_group': self._guess_field_group(rfname, rfield_obj),
                    'default_aggregation': self._default_aggregation(
                        rfield_obj.type, role),
                    'source_model': field_obj.comodel_name,
                    'source_model_label': rel_label,
                    'is_from_relation': True,
                    'parent_relation_field': fname,
                    'sequence': seq,
                    'is_selected': False,
                })

        if field_vals:
            self.env['bi.dataset.field'].create(field_vals)

    def _classify_field_role(self, field_obj):
        """Classify a field as measure, dimension, or date."""
        if field_obj.type in MEASURE_TYPES:
            return 'measure'
        elif field_obj.type in DATE_TYPES:
            return 'date'
        elif field_obj.type in DIMENSION_TYPES:
            return 'dimension'
        return None

    def _guess_field_group(self, fname, field_obj):
        """Auto-guess a field group based on name heuristics."""
        fname_lower = fname.lower()
        ftype = field_obj.type

        if ftype in ('date', 'datetime'):
            return 'date_time'
        if ftype == 'monetary' or any(kw in fname_lower for kw in FIELD_GROUP_RULES['financial']):
            return 'financial'
        
        for group, keywords in FIELD_GROUP_RULES.items():
            if any(kw in fname_lower for kw in keywords):
                return group
        
        return 'general'

    def _default_aggregation(self, odoo_type, role):
        """Get default aggregation method."""
        if role == 'measure':
            if odoo_type == 'monetary':
                return 'sum'
            elif odoo_type == 'float':
                return 'sum'
            elif odoo_type == 'integer':
                return 'sum'
        return 'count'

    # =========================================================================
    # LAYER 1 — Model Explorer API (for frontend)
    # =========================================================================

    @api.model
    def get_model_explorer_data(self, model_id):
        """Get all fields for a model organized by source, for the field explorer.
        
        Returns a tree structure:
        {
            'model': { id, name, model },
            'groups': {
                'Root Model Name': {
                    'dimensions': [...],
                    'measures': [...],
                    'dates': [...]
                },
                'Related Model Name': { ... }
            }
        }
        """
        ir_model = self.env['ir.model'].browse(model_id)
        if not ir_model.exists():
            return {'error': 'Model not found'}

        try:
            self.env[ir_model.model].check_access_rights('read')
        except Exception:
            return {'error': 'Access denied to this model'}

        model = self.env[ir_model.model]
        groups = defaultdict(lambda: {'dimensions': [], 'measures': [], 'dates': []})

        # Root model fields
        root_label = ir_model.name
        for fname, field_obj in model._fields.items():
            if fname in SKIP_FIELDS:
                continue
            if field_obj.type in ('one2many', 'many2many', 'binary', 'reference'):
                continue

            role = self._classify_field_role(field_obj)
            if not role:
                continue

            category = 'measures' if role == 'measure' else (
                'dates' if role == 'date' else 'dimensions')
            
            groups[root_label][category].append({
                'field_name': fname,
                'field_path': fname,
                'label': field_obj.string or fname.replace('_', ' ').title(),
                'type': field_obj.type,
                'role': role,
                'group': self._guess_field_group(fname, field_obj),
            })

        # Many2one related fields
        for fname, field_obj in model._fields.items():
            if fname in SKIP_FIELDS or field_obj.type != 'many2one':
                continue
            if not field_obj.comodel_name:
                continue

            try:
                related_model = self.env[field_obj.comodel_name]
                related_model.check_access_rights('read')
            except Exception:
                continue

            rel_label = field_obj.string or fname.replace('_', ' ').title()

            for rfname, rfield_obj in related_model._fields.items():
                if rfname in SKIP_FIELDS:
                    continue
                if rfield_obj.type in ('one2many', 'many2many', 'binary',
                                       'many2one', 'reference', 'html'):
                    continue

                role = self._classify_field_role(rfield_obj)
                if not role:
                    continue

                category = 'measures' if role == 'measure' else (
                    'dates' if role == 'date' else 'dimensions')
                
                groups[rel_label][category].append({
                    'field_name': rfname,
                    'field_path': f'{fname}.{rfname}',
                    'label': rfield_obj.string or rfname.replace('_', ' ').title(),
                    'type': rfield_obj.type,
                    'role': role,
                    'group': self._guess_field_group(rfname, rfield_obj),
                })

        return {
            'model': {
                'id': ir_model.id,
                'name': ir_model.name,
                'model': ir_model.model,
            },
            'groups': dict(groups),
        }

    # =========================================================================
    # LAYER 2 — Data Retrieval
    # =========================================================================

    def action_preview_data(self, limit=50):
        """Get a preview of the dataset's data as a flat table."""
        self.ensure_one()
        return self._get_flat_data(limit=limit)

    def _get_flat_data(self, extra_filters=None, limit=None):
        """Core data retrieval: executes the dataset query via ORM.
        
        Returns: {
            'columns': [{ name, label, type, role }],
            'rows': [[value, value, ...], ...],
            'total_count': int
        }
        """
        if not self.model_name:
            return {'columns': [], 'rows': [], 'total_count': 0}

        selected_fields = self.field_ids.filtered('is_selected')
        if not selected_fields:
            return {'columns': [], 'rows': [], 'total_count': 0}

        # Build domain
        domain = self._parse_domain(self.domain_filter)
        if extra_filters:
            domain += extra_filters

        # Determine limit
        fetch_limit = limit or self.record_limit or 1000

        # Build field list (only direct fields for search_read)
        # For dotted paths, we read the parent many2one
        read_fields = set()
        for f in selected_fields:
            if '.' in f.field_path:
                # For "partner_id.name", we need to read "partner_id"
                read_fields.add(f.field_path.split('.')[0])
            else:
                read_fields.add(f.field_path)

        # Build sort
        order = None
        if self.sort_field:
            order = f'{self.sort_field} {self.sort_order or "desc"}'

        try:
            model = self.env[self.model_name]
            records = model.search(domain, limit=fetch_limit, order=order)
            total_count = model.search_count(domain)
        except Exception as e:
            _logger.error('BI Studio dataset query error: %s', e)
            return {'columns': [], 'rows': [], 'total_count': 0,
                    'error': str(e)}

        # Build columns
        columns = []
        for f in selected_fields.sorted('sequence'):
            columns.append({
                'name': f.field_path,
                'label': f.display_label or f.field_label,
                'type': f.odoo_field_type,
                'role': f.field_role,
                'aggregation': f.default_aggregation,
            })

        # Build rows
        rows = []
        for record in records:
            row = []
            for f in selected_fields.sorted('sequence'):
                value = self._resolve_field_value(record, f.field_path)
                row.append(value)
            rows.append(row)

        return {
            'columns': columns,
            'rows': rows,
            'total_count': total_count,
        }

    def _resolve_field_value(self, record, field_path):
        """Resolve a dotted field path to its display value."""
        try:
            parts = field_path.split('.')
            obj = record
            for part in parts[:-1]:
                obj = obj[part]
                if not obj:
                    return None
            
            value = obj[parts[-1]]
            
            # Convert recordsets to display values
            if hasattr(value, 'display_name'):
                return value.display_name
            elif hasattr(value, 'mapped'):
                return ', '.join(value.mapped('display_name'))
            
            return value
        except Exception:
            return None

    def _parse_domain(self, domain_str):
        """Safely parse a domain string."""
        if not domain_str or domain_str.strip() == '[]':
            return []
        try:
            from odoo.tools.safe_eval import safe_eval
            return safe_eval(domain_str)
        except Exception:
            return []

    # =========================================================================
    # Actions
    # =========================================================================

    def action_open_dataset_builder(self):
        """Open the interactive dataset builder (frontend component)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'bi_studio.dataset_builder',
            'params': {
                'dataset_id': self.id,
            },
            'name': _('Dataset Builder: %s') % self.name,
        }

    def action_refresh_fields(self):
        """Re-scan fields from the model."""
        self.field_ids.unlink()
        self._auto_scan_fields()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fields Refreshed'),
                'message': _('%d fields scanned.') % len(self.field_ids),
                'type': 'success',
            }
        }


class BiDatasetField(models.Model):
    """Individual field in a dataset — like a column in Power BI's field list.
    
    Each field has a path (e.g., 'partner_id.country_id.name'), a role
    (dimension/measure/date), and aggregation config.
    """
    _name = 'bi.dataset.field'
    _description = 'BI Dataset Field'
    _order = 'sequence, field_label'

    dataset_id = fields.Many2one('bi.dataset', string='Dataset',
                                 required=True, ondelete='cascade')

    # Field identity
    field_name = fields.Char('Field Name', required=True,
                             help='Technical field name (last segment)')
    field_path = fields.Char('Field Path', required=True,
                             help='Full dotted path, e.g., partner_id.country_id.name')
    field_label = fields.Char('Field Label', required=True)
    display_label = fields.Char('Display Label',
                                help='Custom label shown to user. Defaults to field_label.')
    odoo_field_type = fields.Char('Odoo Type', required=True)

    # Classification (Power BI: Dimension vs Measure vs Date)
    field_role = fields.Selection([
        ('dimension', 'Dimension'),
        ('measure', 'Measure'),
        ('date', 'Date/Time'),
    ], string='Role', required=True)

    # Smart grouping
    field_group = fields.Selection([
        ('general', 'General'),
        ('financial', 'Financial'),
        ('customer', 'Customer/Partner'),
        ('product', 'Product'),
        ('date_time', 'Date & Time'),
        ('status', 'Status'),
        ('location', 'Location'),
    ], string='Group', default='general')

    # Aggregation
    default_aggregation = fields.Selection([
        ('sum', 'Sum'),
        ('avg', 'Average'),
        ('min', 'Minimum'),
        ('max', 'Maximum'),
        ('count', 'Count'),
        ('count_distinct', 'Count Distinct'),
    ], string='Aggregation', default='count')

    # Source info
    source_model = fields.Char('Source Model')
    source_model_label = fields.Char('Source Model Label')
    is_from_relation = fields.Boolean('From Relation', default=False)
    parent_relation_field = fields.Char('Parent Relation')

    # Selection
    is_selected = fields.Boolean('Selected', default=False,
                                 help='Whether this field is included in the dataset output')

    # Display
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    format_string = fields.Char('Format',
                                help='Display format, e.g., $#,##0.00')
    color = fields.Char('Color', help='Chart color (hex)')
