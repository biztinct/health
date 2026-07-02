# -*- coding: utf-8 -*-
import io
import json

from odoo import http
from odoo.http import request


class BiController(http.Controller):

    @http.route('/bi/export/xlsx', type='http', auth='user')
    def export_xlsx(self, chart_id, filters='[]'):
        """Re-run a saved chart's query server-side and stream it as XLSX."""
        import xlsxwriter

        chart = request.env['bi.chart'].browse(int(chart_id))
        chart.check_access('read')
        envelope = request.env['bi.query.engine'].run(
            chart._to_query_request(json.loads(filters or '[]')))

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet(chart.name[:31] or 'Data')
        header_format = workbook.add_format(
            {'bold': True, 'bg_color': '#EEF1F5', 'border': 1})
        number_format = workbook.add_format({'num_format': '#,##0.00'})
        columns = envelope['columns']
        for col_index, column in enumerate(columns):
            sheet.write(0, col_index, column['label'], header_format)
            sheet.set_column(col_index, col_index, 18)
        for row_index, row in enumerate(envelope['rows'], start=1):
            for col_index, value in enumerate(row):
                if isinstance(value, (int, float)) and \
                        columns[col_index].get('role') == 'measure':
                    sheet.write_number(row_index, col_index, value,
                                       number_format)
                else:
                    sheet.write(row_index, col_index,
                                '' if value is None else str(value))
        workbook.close()
        request.env['bi.audit.log'].sudo().log(
            'export', dataset=chart.dataset_id, record=chart,
            payload={'format': 'xlsx'})
        filename = '%s.xlsx' % (chart.name or 'chart').replace('/', '-')
        return request.make_response(buffer.getvalue(), headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument'
                             '.spreadsheetml.sheet'),
            ('Content-Disposition',
             http.content_disposition(filename)),
        ])

    @http.route('/bi/query', type='jsonrpc', auth='user')
    def query(self, requests=None):
        """Batched query endpoint — one call per dashboard load.

        Each entry is either a raw engine request (Explore live preview) or
        {'chart_id': id, 'extra_filters': [...]} for saved charts, in which
        case the server derives the request from the chart's config —
        clients never send raw field lists for saved charts.
        """
        engine = request.env['bi.query.engine']
        expanded = []
        skipped = {}  # index -> marker for unshiftable compare requests
        for index, entry in enumerate(requests or []):
            if entry.get('chart_id'):
                chart = request.env['bi.chart'].browse(int(entry['chart_id']))
                chart.check_access('read')
                if entry.get('compare'):
                    compare_request = chart._to_compare_request(
                        entry.get('extra_filters'))
                    if compare_request is None:
                        skipped[index] = {'skipped': True}
                        expanded.append(None)
                        continue
                    expanded.append(compare_request)
                else:
                    expanded.append(chart._to_query_request(
                        entry.get('extra_filters'),
                        grain_overrides=entry.get('grain_overrides')))
            else:
                expanded.append(entry)
        results = engine.run_batch([e for e in expanded if e is not None])
        merged, cursor = [], 0
        for index in range(len(expanded)):
            if index in skipped:
                merged.append(skipped[index])
            else:
                merged.append(results[cursor])
                cursor += 1
        return merged
