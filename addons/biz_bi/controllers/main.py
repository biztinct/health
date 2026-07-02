# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class BiController(http.Controller):

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
        for entry in (requests or []):
            if entry.get('chart_id'):
                chart = request.env['bi.chart'].browse(int(entry['chart_id']))
                chart.check_access('read')
                expanded.append(chart._to_query_request(
                    entry.get('extra_filters')))
            else:
                expanded.append(entry)
        return engine.run_batch(expanded)
