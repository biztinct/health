# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class QueryResultDisplay(models.TransientModel):
    """Transient model to display query test results in a user-friendly format"""
    _name = 'query.result.display'
    _description = 'Query Results Display'

    query_id = fields.Many2one('dashboard.query', 'Query', readonly=True)
    result_count = fields.Integer('Total Rows', readonly=True)
    execution_time = fields.Float('Execution Time (ms)', readonly=True)
    is_cached = fields.Boolean('From Cache', readonly=True)

    # Display result data as JSON
    result_fields_json = fields.Text('Column Information', readonly=True)
    result_data_json = fields.Text('Results Data', readonly=True)

    # Display result in table format (HTML)
    result_html = fields.Html('Results Table', readonly=True)

    # For better UX - store formatted data
    result_lines = fields.Json('Result Lines', readonly=True)

    @api.model
    def create_from_query(self, query_id, result_data, result_fields, execution_time):
        """Create a display record from query results"""
        html_table = self._build_html_table(result_fields, result_data)

        return self.create({
            'query_id': query_id.id,
            'result_count': len(result_data) if result_data else 0,
            'execution_time': execution_time,
            'result_fields_json': json.dumps(result_fields, indent=2),
            'result_data_json': json.dumps(result_data, indent=2, default=str),
            'result_html': html_table,
            'result_lines': result_data or []
        })

    def _build_html_table(self, fields, data):
        """Build an HTML table from results"""
        if not data:
            return '<div class="alert alert-info"><strong>No results found</strong></div>'

        html = '''
        <div class="table-responsive">
            <table class="table table-striped table-bordered table-sm">
                <thead class="table-dark">
                    <tr>
        '''

        # Add headers
        for field in fields:
            field_name = field.get('string', field.get('name', 'Unknown'))
            html += f'<th>{field_name}</th>'

        html += '''
                    </tr>
                </thead>
                <tbody>
        '''

        # Add data rows
        for row in data:
            html += '<tr>'
            for field in fields:
                field_key = field.get('name')
                value = row.get(field_key, '')

                # Format value based on type
                if value is None or value == '':
                    display_value = '<span class="text-muted">—</span>'
                elif isinstance(value, bool):
                    display_value = '<span class="badge bg-success">✓ True</span>' if value else '<span class="badge bg-danger">✗ False</span>'
                elif isinstance(value, (list, tuple)):
                    display_value = f'<code>{json.dumps(value)}</code>'
                elif isinstance(value, dict):
                    display_value = f'<code>{json.dumps(value)}</code>'
                else:
                    display_value = str(value)[:100]  # Truncate long values

                html += f'<td>{display_value}</td>'
            html += '</tr>'

        html += '''
                </tbody>
            </table>
        </div>
        '''

        return html

    def action_close(self):
        """Close the display wizard"""
        return {'type': 'ir.actions.act_window_close'}

    def action_copy_json(self):
        """Copy JSON results to clipboard (for users to export)"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Results Ready'),
                'message': _('You can copy the JSON data from the Results Data field below'),
                'type': 'info',
                'sticky': True,
            }
        }
