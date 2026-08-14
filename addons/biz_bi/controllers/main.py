# -*- coding: utf-8 -*-
import io
import json

from odoo import _, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from ..bi_tz import (cell_value, column_is_instant, parse_engine_datetime,
                     to_user_tz, user_timezone)

XLSX_CONTENT_TYPE = ('application/vnd.openxmlformats-officedocument'
                     '.spreadsheetml.sheet')

OTHERS_KEY = '__bi_others__'


class BiController(http.Controller):

    # ==================================================================
    # Excel export
    # ==================================================================

    @http.route('/bi/export/xlsx', type='http', auth='user',
                methods=['GET'], readonly=False)
    def export_xlsx(self, chart_id, filters='[]'):
        """Re-run a SAVED chart's query server-side and stream it as XLSX."""
        chart = request.env['bi.chart'].browse(int(chart_id))
        chart.check_access('read')
        engine = request.env['bi.query.engine']
        cap = engine.export_row_cap()
        query_request = chart._to_query_request(json.loads(filters or '[]'))
        query_request['limit'] = cap
        # the envelope is the POST-label one (engine.run attaches
        # value_labels), which is what makes the cells say "Ho Chi Minh City"
        # instead of "4".
        envelope = engine.run(query_request, hard_cap=cap)
        return self._xlsx_response(
            envelope, chart.name or 'Data',
            mode=(chart.config_json or {}).get('mode') or 'aggregate',
            cap=cap, dataset=chart.dataset_id, chart=chart)

    @http.route('/bi/export/xlsx', type='http', auth='user',
                methods=['POST'], csrf=True, readonly=False)
    def export_xlsx_post(self, request_json=None, title=None, **kwargs):
        """Export exactly what the Explore preview shows — saved or not.

        The body carries a raw engine request (same shape /bi/query accepts).
        The row ceiling is decided HERE, server-side; `hard_cap` is stripped
        from the payload by the engine so a crafted body cannot raise it.
        """
        try:
            payload = json.loads(request_json or 'null')
        except ValueError:
            payload = None
        if not isinstance(payload, dict) or not payload.get('dataset_id'):
            return request.make_response(
                _("Nothing to export."),
                headers=[('Content-Type', 'text/plain; charset=utf-8')],
                status=400)

        engine = request.env['bi.query.engine']
        cap = engine.export_row_cap()
        payload.pop('hard_cap', None)
        payload['limit'] = cap
        try:
            envelope = engine.run(payload, hard_cap=cap)
        # ONLY the business exceptions — a blanket `except Exception` here
        # would swallow Odoo's readonly-cursor retry signal (ledger §5.38).
        except (UserError, ValidationError, AccessError) as exc:
            return request.make_response(
                str(exc),
                headers=[('Content-Type', 'text/plain; charset=utf-8')],
                status=400)
        return self._xlsx_response(
            envelope, title or _("Records"),
            mode=payload.get('mode') or 'aggregate', cap=cap,
            dataset=request.env['bi.dataset'].browse(
                int(payload['dataset_id'])))

    # ------------------------------------------------------------------
    # Workbook building (shared by both routes)
    # ------------------------------------------------------------------

    def _xlsx_response(self, envelope, title, mode='aggregate', cap=None,
                       dataset=None, chart=None):
        columns = envelope.get('columns') or []
        rows = envelope.get('rows') or []
        meta = envelope.get('meta') or {}
        total = meta.get('total_count')
        notice = None
        if total is not None and total > len(rows):
            notice = _(
                "Showing first %(shown)s of %(total)s rows — refine filters "
                "for the full set.", shown=len(rows), total=total)
        elif cap and len(rows) >= cap:
            # aggregate mode has no honest total to quote, but a result that
            # exactly fills the cap is still a truncated one — say so.
            notice = _(
                "Showing the first %s rows — refine filters for the full "
                "set.", len(rows))
        capped = bool(notice)
        payload = self._build_xlsx(columns, rows, title, notice,
                                   tz=self._export_tz())

        request.env['bi.audit.log'].sudo().log(
            'export', dataset=dataset if dataset else None, record=chart,
            payload={'format': 'xlsx', 'mode': mode, 'rows': len(rows),
                     'columns': len(columns), 'capped': capped})

        filename = '%s.xlsx' % (title or 'export').replace('/', '-')[:64]
        return request.make_response(payload, headers=[
            ('Content-Type', XLSX_CONTENT_TYPE),
            ('Content-Disposition', http.content_disposition(filename)),
        ])

    @staticmethod
    def _export_tz(env=None):
        """The timezone an exported datetime should READ in.

        Every datetime column comes out of the engine as a naive UTC value —
        which is right for storage and wrong on a spreadsheet: a Vietnamese
        user opening the file saw every appointment seven hours early, with
        nothing on the cell to say it was UTC. Excel has no timezone concept
        at all, so the only honest cell is the user's own wall clock.

        The rule itself lives in `biz_bi/bi_tz.py`, shared with the scheduled
        snapshot workbook and mirrored in the client formatter.
        """
        return user_timezone(env if env is not None else request.env)

    @staticmethod
    def _to_user_tz(value, tz):
        """Naive-UTC datetime -> naive datetime in `tz`. Dates are untouched:
        a pure date has no time to shift, and moving it would change the day.
        """
        return to_user_tz(value, tz)

    @staticmethod
    def _sheet_name(title):
        """Excel forbids []:*?/\\ in a sheet name and caps it at 31 chars, and
        xlsxwriter RAISES on a bad one — a chart called "Q1: Revenue" would
        otherwise 500 the export. Also rejects a leading/trailing apostrophe.
        """
        name = ''.join(
            '-' if character in '[]:*?/\\' else character
            for character in (title or ''))
        name = name.strip().strip("'")[:31].strip()
        return name or 'Data'

    def _build_xlsx(self, columns, rows, title, notice=None, tz=None):
        import xlsxwriter

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet(self._sheet_name(title))
        header_format = workbook.add_format(
            {'bold': True, 'bg_color': '#EEF1F5', 'border': 1})
        notice_format = workbook.add_format({'bold': True})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        datetime_format = workbook.add_format(
            {'num_format': 'yyyy-mm-dd hh:mm:ss'})
        number_formats = {}

        def number_format_for(column):
            fmt = column.get('format') or {}
            decimals = fmt.get('decimals')
            if decimals is None:
                decimals = 0 if fmt.get('currency') == 'VND' else 2
            try:
                decimals = max(0, min(int(decimals), 6))
            except (TypeError, ValueError):
                decimals = 2
            code = '#,##0' if not decimals else '#,##0.' + '0' * decimals
            if code not in number_formats:
                number_formats[code] = workbook.add_format(
                    {'num_format': code})
            return number_formats[code]

        for col_index, column in enumerate(columns):
            sheet.write(0, col_index, column.get('label') or '',
                        header_format)
            sheet.set_column(col_index, col_index, 18)

        for row_index, row in enumerate(rows, start=1):
            for col_index, value in enumerate(row):
                if col_index >= len(columns):
                    break
                self._write_cell(sheet, row_index, col_index,
                                 columns[col_index], value,
                                 number_format_for, date_format,
                                 datetime_format, tz)

        if columns:
            sheet.freeze_panes(1, 0)
            sheet.autofilter(0, 0, max(len(rows), 1), len(columns) - 1)
        if notice:
            sheet.write(len(rows) + 1, 0, notice, notice_format)
        workbook.close()
        return buffer.getvalue()

    def _write_cell(self, sheet, row_index, col_index, column, value,
                    number_format_for, date_format, datetime_format,
                    tz=None):
        if value is None or (value is False
                             and column.get('type') != 'boolean'):
            sheet.write(row_index, col_index, '')
            return
        if value == OTHERS_KEY:
            sheet.write(row_index, col_index, _("Others"))
            return

        # ids/selection keys render as the SAME label the table shows —
        # value_labels comes from the post-label envelope, selection_labels
        # is baked at scan time. Keys are strings on both maps.
        labels = column.get('value_labels') or column.get(
            'selection_labels') or {}
        label = labels.get(str(value))
        if label is not None:
            sheet.write(row_index, col_index, label)
            return

        if column.get('role') == 'measure' and isinstance(value, (int, float)) \
                and not isinstance(value, bool):
            sheet.write_number(row_index, col_index, value,
                               number_format_for(column))
            return
        if isinstance(value, bool):
            sheet.write_boolean(row_index, col_index, value)
            return
        if column.get('type') in ('date', 'datetime'):
            # `cell_value` converts an INSTANT into the reader's zone and
            # leaves a calendar value (a date column, a grain bucket) alone —
            # shifting `2026-04-01 00:00` UTC for a UTC-5 reader would label
            # the April bucket "March".
            parsed = cell_value(value, column, tz)
            if parsed is not None:
                sheet.write_datetime(
                    row_index, col_index, parsed,
                    datetime_format if column_is_instant(column)
                    else date_format)
                return
        if isinstance(value, (int, float)):
            sheet.write_number(row_index, col_index, value)
            return
        sheet.write(row_index, col_index, str(value))

    @staticmethod
    def _parse_date(value):
        return parse_engine_datetime(value)

    # ==================================================================
    # Query
    # ==================================================================

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
                    # `limit_override` may only SHRINK a detail request's
                    # limit (a dashboard tile draws 200 rows, not 5000) —
                    # the engine refuses anything that would grow it.
                    expanded.append(engine.apply_limit_override(
                        chart._to_query_request(
                            entry.get('extra_filters'),
                            grain_overrides=entry.get('grain_overrides')),
                        entry.get('limit_override')))
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
