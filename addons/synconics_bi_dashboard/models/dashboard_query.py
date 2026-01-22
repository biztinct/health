# -*- coding: utf-8 -*-

import re
import json
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import sql

_logger = logging.getLogger(__name__)


class DashboardQuery(models.Model):
    _name = 'dashboard.query'
    _description = 'Custom Query Builder'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Query Name', required=True)
    query_type = fields.Selection([
        ('visual', 'Visual Builder'),
        ('sql', 'SQL Editor')
    ], string='Query Type', default='visual', required=True)

    # Visual Builder Configuration
    model_ids = fields.Many2many('ir.model', 'query_model_rel', 'query_id', 'model_id',
                                 string='Allowed Models')
    visual_config = fields.Json('Visual Configuration', help='Stores visual builder state')

    # SQL Editor
    sql_query = fields.Text('SQL Query')

    # Results & Caching
    result_fields = fields.Json('Result Fields', help='Column definitions')
    result_cache = fields.Json('Cached Results')
    cache_duration = fields.Integer('Cache Duration (seconds)', default=300)
    last_execution = fields.Datetime('Last Executed')
    execution_time = fields.Float('Last Execution Time (ms)', readonly=True)

    # Security
    is_read_only = fields.Boolean('Read-Only', default=True,
                                  help='Prevent write operations')
    allowed_user_ids = fields.Many2many('res.users', 'query_user_rel', 'query_id', 'user_id',
                                       string='Allowed Users')
    allowed_group_ids = fields.Many2many('res.groups', 'query_group_rel', 'query_id', 'group_id',
                                        string='Allowed Groups')

    # Metadata
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', 'Created By',
                             default=lambda self: self.env.user, readonly=True)

    @api.constrains('sql_query')
    def _check_sql_query(self):
        """Validate SQL query for security"""
        for record in self:
            if record.query_type == 'sql' and record.sql_query:
                self._validate_sql_security(record.sql_query)

    def _validate_sql_security(self, sql_query):
        """
        Validate SQL query for security concerns
        Only SELECT statements are allowed
        """
        if not sql_query or not sql_query.strip():
            raise ValidationError(_('SQL query cannot be empty'))

        # Remove comments and normalize whitespace
        query_normalized = re.sub(r'--[^\n]*', '', sql_query)
        query_normalized = re.sub(r'/\*.*?\*/', '', query_normalized, flags=re.DOTALL)
        query_normalized = ' '.join(query_normalized.split())

        # Check for dangerous keywords
        forbidden_patterns = [
            r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b',
            r'\b(EXEC|EXECUTE|PROCEDURE)\b',
            r'\b(INTO\s+OUTFILE|INTO\s+DUMPFILE)\b',
            r';.*(?:INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)',  # Multiple statements
        ]

        for pattern in forbidden_patterns:
            if re.search(pattern, query_normalized, re.IGNORECASE):
                raise ValidationError(_(
                    'Security Error: Only SELECT queries are allowed. '
                    'INSERT, UPDATE, DELETE, and DDL statements are forbidden.'
                ))

        # Ensure query starts with SELECT
        if not re.match(r'^\s*SELECT\b', query_normalized, re.IGNORECASE):
            raise ValidationError(_('Query must start with SELECT statement'))

        return True

    def _check_user_access(self):
        """Check if current user has access to this query"""
        self.ensure_one()

        # Superuser always has access
        if self.env.user._is_superuser():
            return True

        # Check if user is explicitly allowed
        if self.allowed_user_ids and self.env.user not in self.allowed_user_ids:
            raise UserError(_('You do not have permission to execute this query'))

        # Check if user's groups are allowed
        if self.allowed_group_ids:
            user_groups = self.env.user.group_ids
            if not any(group in self.allowed_group_ids for group in user_groups):
                raise UserError(_('Your user group does not have permission to execute this query'))

        return True

    def _check_model_access(self, model_name):
        """Check if user has read access to model"""
        try:
            model = self.env[model_name]
            model.check_access_rights('read')
            return True
        except Exception as e:
            raise UserError(_(
                'Access Denied: You do not have read permission for model: %s'
            ) % model_name)

    def execute_query(self, limit=1000):
        """
        Execute query with security checks and caching
        Returns: dict with 'data' and 'fields' keys
        """
        self.ensure_one()
        self._check_user_access()

        # Check cache
        if self._is_cache_valid():
            _logger.info(f'Query {self.id} ({self.name}): Using cached results')
            return {
                'data': self.result_cache,
                'fields': self.result_fields,
                'cached': True,
                'execution_time': self.execution_time
            }

        # Execute based on query type
        start_time = datetime.now()

        try:
            if self.query_type == 'visual':
                result = self._execute_visual_query(limit)
            else:  # sql
                result = self._execute_sql_query(limit)

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Cache results
            self.sudo().write({
                'result_cache': result['data'],
                'result_fields': result['fields'],
                'last_execution': fields.Datetime.now(),
                'execution_time': execution_time
            })

            result['cached'] = False
            result['execution_time'] = execution_time

            _logger.info(f'Query {self.id} ({self.name}): Executed in {execution_time:.2f}ms')

            return result

        except Exception as e:
            _logger.error(f'Query execution failed for {self.id} ({self.name}): {str(e)}')
            raise UserError(_('Query execution failed: %s') % str(e))

    def _is_cache_valid(self):
        """Check if cached results are still valid"""
        if not self.result_cache or not self.last_execution:
            return False

        cache_age = (fields.Datetime.now() - self.last_execution).total_seconds()
        return cache_age < self.cache_duration

    def _execute_visual_query(self, limit):
        """Execute visual builder query"""
        if not self.visual_config:
            raise UserError(_('Visual query configuration is empty'))

        config = self.visual_config

        # Extract configuration
        model_name = config.get('model')
        fields_list = config.get('fields', [])
        domain = config.get('domain', [])
        group_by = config.get('group_by', [])
        order = config.get('order', '')

        if not model_name:
            raise UserError(_('Model not specified in visual configuration'))

        # Check model access
        self._check_model_access(model_name)

        model = self.env[model_name]

        # Build query
        if group_by:
            # Use read_group for aggregation
            result_data = model.read_group(
                domain=domain,
                fields=fields_list,
                groupby=group_by,
                limit=limit,
                orderby=order
            )
        else:
            # Regular search_read
            result_data = model.search_read(
                domain=domain,
                fields=fields_list,
                limit=limit,
                order=order
            )

        # Get field definitions
        field_defs = model.fields_get(fields_list)
        result_fields = [
            {
                'name': fname,
                'string': field_defs[fname].get('string', fname),
                'type': field_defs[fname].get('type', 'char')
            }
            for fname in fields_list if fname in field_defs
        ]

        return {
            'data': result_data,
            'fields': result_fields
        }

    def _execute_sql_query(self, limit):
        """Execute SQL query with security validation"""
        if not self.sql_query:
            raise UserError(_('SQL query is empty'))

        # Validate security
        self._validate_sql_security(self.sql_query)

        # Add limit if not present
        sql_with_limit = self.sql_query.strip()
        if not re.search(r'\bLIMIT\b', sql_with_limit, re.IGNORECASE):
            sql_with_limit += f' LIMIT {limit}'

        # Execute query
        try:
            self.env.cr.execute(sql_with_limit)
            result_data = self.env.cr.dictfetchall()

            # Get column information
            if result_data:
                result_fields = [
                    {
                        'name': key,
                        'string': key.replace('_', ' ').title(),
                        'type': 'char'  # Default type
                    }
                    for key in result_data[0].keys()
                ]
            else:
                result_fields = []

            return {
                'data': result_data,
                'fields': result_fields
            }

        except Exception as e:
            raise UserError(_('SQL Execution Error: %s') % str(e))

    def clear_cache(self):
        """Clear cached results"""
        self.write({
            'result_cache': False,
            'last_execution': False
        })
        return True

    def action_test_query(self):
        """Test query execution (limit to 10 rows) and display results"""
        result = self.execute_query(limit=10)

        # Store the test results in the record
        self.sudo().write({
            'result_cache': result['data'],
            'result_fields': result['fields'],
            'last_execution': fields.Datetime.now(),
            'execution_time': result['execution_time']
        })

        # Create a display record with formatted results
        QueryResultDisplay = self.env['query.result.display']
        display_record = QueryResultDisplay.create_from_query(
            query_id=self,
            result_data=result['data'],
            result_fields=result['fields'],
            execution_time=result['execution_time']
        )

        # Open the results in a modal window
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'query.result.display',
            'res_id': display_record.id,
            'view_mode': 'form',
            'view_type': 'form',
            'views': [(False, 'form')],
            'target': 'new',  # Open as modal dialog
        }
