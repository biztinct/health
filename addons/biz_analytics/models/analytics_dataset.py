# -*- coding: utf-8 -*-
import json
from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AnalyticsDataset(models.Model):
    """Dataset configuration for analytics"""
    _name = 'analytics.dataset'
    _description = 'Analytics Dataset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char('Dataset Name', required=True, tracking=True)
    description = fields.Text('Description')
    
    # Dataset Configuration
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True, tracking=True)
    color = fields.Integer('Color Index', default=0)
    
    # Data Source
    model_id = fields.Many2one('ir.model', string='Source Model', required=True,
                              ondelete='cascade', tracking=True)
    model_name = fields.Char(related='model_id.model', string='Model', store=True)
    
    # Field Configuration
    available_field_ids = fields.One2many('analytics.dataset.field', 'dataset_id', 
                                         string='Available Fields')
    dimension_field_ids = fields.One2many('analytics.dataset.field', 'dataset_id',
                                         string='Dimension Fields',
                                         domain=[('field_type', '=', 'dimension')])
    measure_field_ids = fields.One2many('analytics.dataset.field', 'dataset_id',
                                       string='Measure Fields', 
                                       domain=[('field_type', '=', 'measure')])
    date_field_ids = fields.One2many('analytics.dataset.field', 'dataset_id',
                                    string='Date Fields',
                                    domain=[('field_type', '=', 'date')])
    
    # Default Filters and Domain
    domain = fields.Text('Domain Filter', default='[]',
                        help='Python domain for filtering records')
    default_filters = fields.Text('Default Filters', default='{}')
    
    # Data Refresh
    auto_refresh = fields.Boolean('Auto Refresh', default=False)
    refresh_interval = fields.Integer('Refresh Interval (minutes)', default=30)
    last_refresh = fields.Datetime('Last Refresh')
    
    # Access Control
    user_ids = fields.Many2many('res.users', string='Allowed Users')
    group_ids = fields.Many2many('res.groups', string='Allowed Groups')
    
    # Computed Fields
    field_count = fields.Integer('Field Count', compute='_compute_field_count')
    record_count = fields.Integer('Record Count', compute='_compute_record_count')
    
    # Dataset Metadata (JSON)
    dataset_metadata = fields.Text('Dataset Metadata', compute='_compute_dataset_metadata')

    @api.depends('available_field_ids')
    def _compute_field_count(self):
        for dataset in self:
            dataset.field_count = len(dataset.available_field_ids)

    def _compute_record_count(self):
        for dataset in self:
            if dataset.model_name:
                try:
                    domain = eval(dataset.domain) if dataset.domain else []
                    dataset.record_count = self.env[dataset.model_name].search_count(domain)
                except Exception:
                    dataset.record_count = 0
            else:
                dataset.record_count = 0

    def _compute_dataset_metadata(self):
        for dataset in self:
            metadata = {
                'id': dataset.id,
                'name': dataset.name,
                'model': dataset.model_name,
                'record_count': dataset.record_count,
                'last_refresh': dataset.last_refresh.isoformat() if dataset.last_refresh else None,
                'fields': {
                    'dimensions': [],
                    'measures': [],
                    'dates': []
                }
            }
            
            # Add field information
            for field in dataset.dimension_field_ids.filtered('active'):
                metadata['fields']['dimensions'].append({
                    'id': field.id,
                    'name': field.field_name,
                    'label': field.field_label,
                    'type': field.odoo_field_type,
                    'aggregation': field.aggregation_method
                })
                
            for field in dataset.measure_field_ids.filtered('active'):
                metadata['fields']['measures'].append({
                    'id': field.id,
                    'name': field.field_name,
                    'label': field.field_label,
                    'type': field.odoo_field_type,
                    'aggregation': field.aggregation_method
                })
                
            for field in dataset.date_field_ids.filtered('active'):
                metadata['fields']['dates'].append({
                    'id': field.id,
                    'name': field.field_name,
                    'label': field.field_label,
                    'type': field.odoo_field_type,
                    'aggregation': field.aggregation_method
                })
            
            dataset.dataset_metadata = json.dumps(metadata)

    @api.model_create_multi
    def create(self, vals_list):
        datasets = super().create(vals_list)
        for dataset in datasets:
            dataset._auto_populate_fields()
        return datasets

    def write(self, vals):
        result = super().write(vals)
        if 'model_id' in vals:
            for record in self:
                record._auto_populate_fields()
        return result

    def _auto_populate_fields(self):
        """Auto-populate fields from the selected model"""
        if not self.model_name:
            return
            
        model = self.env[self.model_name]
        field_obj = self.env['analytics.dataset.field']
        
        # Clear existing fields
        self.available_field_ids.unlink()
        
        # Get model fields
        field_data = []
        for field_name, field in model._fields.items():
            if field_name in ('id', '__last_update', 'display_name'):
                continue
                
            field_type = self._determine_field_type(field)
            if field_type:
                field_data.append({
                    'dataset_id': self.id,
                    'field_name': field_name,
                    'field_label': field.string or field_name.replace('_', ' ').title(),
                    'odoo_field_type': field.type,
                    'field_type': field_type,
                    'aggregation_method': self._get_default_aggregation(field.type, field_type),
                    'active': field_type in ('measure', 'date') or field_name in ('name', 'state', 'stage_id'),
                    'sequence': 10 if field_type == 'dimension' else (20 if field_type == 'measure' else 30)
                })
        
        field_obj.create(field_data)

    def _determine_field_type(self, field):
        """Determine analytics field type based on Odoo field type"""
        if field.type in ('integer', 'float', 'monetary'):
            return 'measure'
        elif field.type in ('date', 'datetime'):
            return 'date'
        elif field.type in ('char', 'text', 'selection', 'many2one', 'many2many', 'boolean'):
            return 'dimension'
        return None

    def _get_default_aggregation(self, odoo_type, field_type):
        """Get default aggregation method for field"""
        if field_type == 'measure':
            if odoo_type in ('integer', 'float', 'monetary'):
                return 'sum'
        elif field_type == 'dimension':
            return 'count'
        elif field_type == 'date':
            return 'count'
        return 'count'

    def action_refresh_data(self):
        """Manually refresh dataset"""
        self.last_refresh = fields.Datetime.now()
        self._compute_record_count()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Dataset Refreshed'),
                'message': _('Dataset "%s" has been refreshed successfully.') % self.name,
                'type': 'success'
            }
        }

    def action_view_records(self):
        """View records from this dataset"""
        if not self.model_name:
            raise UserError(_('No model configured for this dataset'))
            
        domain = eval(self.domain) if self.domain else []
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dataset Records: %s') % self.name,
            'res_model': self.model_name,
            'view_mode': 'list,form',
            'domain': domain,
            'context': {}
        }

    def action_configure_fields(self):
        """Configure dataset fields"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Configure Fields: %s') % self.name,
            'res_model': 'analytics.dataset.field',
            'view_mode': 'list,form',
            'domain': [('dataset_id', '=', self.id)],
            'context': {
                'default_dataset_id': self.id,
                'create': True
            }
        }

    @api.model
    def get_dataset_data(self, dataset_id, filters=None, limit=None):
        """Get data for analytics processing"""
        dataset = self.browse(dataset_id)
        if not dataset.exists():
            return {'error': 'Dataset not found'}
        
        try:
            domain = eval(dataset.domain) if dataset.domain else []
            if filters:
                # Apply additional filters
                domain.extend(filters)
            
            records = self.env[dataset.model_name].search(domain, limit=limit)
            
            # Get field data
            field_data = {}
            for field in dataset.available_field_ids.filtered('active'):
                field_values = []
                for record in records:
                    try:
                        value = record[field.field_name]
                        if field.odoo_field_type == 'many2one' and value:
                            value = value.name
                        elif field.odoo_field_type == 'many2many' and value:
                            value = ', '.join(value.mapped('name'))
                        field_values.append(value)
                    except Exception:
                        field_values.append(None)
                
                field_data[field.field_name] = {
                    'label': field.field_label,
                    'type': field.field_type,
                    'values': field_values
                }
            
            return {
                'success': True,
                'dataset': dataset.name,
                'record_count': len(records),
                'fields': field_data
            }
            
        except Exception as e:
            return {'error': str(e)}


class AnalyticsDatasetField(models.Model):
    """Individual field configuration for analytics dataset"""
    _name = 'analytics.dataset.field'
    _description = 'Analytics Dataset Field'
    _order = 'sequence, field_label'

    dataset_id = fields.Many2one('analytics.dataset', string='Dataset', 
                                required=True, ondelete='cascade')
    
    # Field Information
    field_name = fields.Char('Field Name', required=True)
    field_label = fields.Char('Field Label', required=True)
    odoo_field_type = fields.Char('Odoo Field Type', required=True)
    
    # Analytics Configuration
    field_type = fields.Selection([
        ('dimension', 'Dimension'),
        ('measure', 'Measure'),
        ('date', 'Date/Time')
    ], string='Analytics Type', required=True)
    
    aggregation_method = fields.Selection([
        ('sum', 'Sum'),
        ('avg', 'Average'),
        ('min', 'Minimum'),
        ('max', 'Maximum'),
        ('count', 'Count'),
        ('count_distinct', 'Count Distinct')
    ], string='Aggregation Method', default='count')
    
    # Display Configuration
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    color = fields.Char('Color', help='Color for charts (hex format)')
    
    # Formatting
    number_format = fields.Selection([
        ('default', 'Default'),
        ('integer', 'Integer'),
        ('decimal_2', '2 Decimals'),
        ('percentage', 'Percentage'),
        ('currency', 'Currency')
    ], string='Number Format', default='default')

    @api.constrains('field_name', 'dataset_id')
    def _check_field_name_unique(self):
        for field in self:
            if self.search_count([
                ('dataset_id', '=', field.dataset_id.id),
                ('field_name', '=', field.field_name),
                ('id', '!=', field.id)
            ]) > 0:
                raise ValidationError(_('Field name must be unique within the dataset.'))