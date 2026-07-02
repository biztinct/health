# -*- coding: utf-8 -*-
import base64
import io
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class BiDashboard(models.Model):
    _name = 'bi.dashboard'
    _description = 'BI Dashboard'
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True, tracking=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    workspace_id = fields.Many2one(
        'bi.workspace', required=True, index=True, ondelete='restrict',
        default=lambda self: self.env['bi.workspace'].search(
            [('is_default', '=', True)], limit=1))
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user,
                               index=True)
    active = fields.Boolean(default=True)

    widget_ids = fields.One2many('bi.dashboard.widget', 'dashboard_id',
                                 string='Widgets')
    filter_ids = fields.One2many('bi.dashboard.filter', 'dashboard_id',
                                 string='Global Filters')
    share_mode = fields.Selection([
        ('private', 'Private'),
        ('workspace', 'Workspace'),
    ], default='workspace', required=True)
    is_tv_mode_enabled = fields.Boolean(default=True)
    refresh_seconds = fields.Integer(
        default=300, help="Auto-reload interval in TV mode.")

    # scheduled email snapshots
    schedule_enabled = fields.Boolean(string='Email Snapshot')
    schedule_interval = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly (Monday)'),
        ('monthly', 'Monthly (1st)'),
    ], default='weekly')
    schedule_hour = fields.Integer(
        default=7, help="Hour of day (0-23, server timezone UTC).")
    recipient_ids = fields.Many2many(
        'res.partner', 'bi_dashboard_recipients_rel',
        string='Snapshot Recipients',
        domain=[('email', '!=', False)])
    next_send = fields.Datetime(readonly=True, copy=False)
    last_sent = fields.Datetime(readonly=True, copy=False)

    @api.onchange('schedule_enabled', 'schedule_interval', 'schedule_hour')
    def _onchange_schedule(self):
        for dashboard in self:
            dashboard.next_send = (
                dashboard._compute_next_send()
                if dashboard.schedule_enabled else False)

    def _compute_next_send(self, reference=None):
        self.ensure_one()
        now = reference or fields.Datetime.now()
        candidate = now.replace(hour=max(0, min(23, self.schedule_hour)),
                                minute=0, second=0, microsecond=0)
        while candidate <= now or not self._schedule_day_matches(candidate):
            candidate += timedelta(days=1)
        return candidate

    def _schedule_day_matches(self, when):
        self.ensure_one()
        if self.schedule_interval == 'weekly':
            return when.weekday() == 0
        if self.schedule_interval == 'monthly':
            return when.day == 1
        return True

    def write(self, vals):
        result = super().write(vals)
        if {'schedule_enabled', 'schedule_interval',
                'schedule_hour'} & set(vals):
            for dashboard in self:
                dashboard.next_send = (
                    dashboard._compute_next_send()
                    if dashboard.schedule_enabled else False)
        return result

    # ------------------------------------------------------------------
    # Snapshot cron
    # ------------------------------------------------------------------

    @api.model
    def _process_snapshot_queue(self):
        due = self.search([
            ('schedule_enabled', '=', True),
            ('next_send', '!=', False),
            ('next_send', '<=', fields.Datetime.now()),
        ])
        for dashboard in due:
            try:
                dashboard._send_snapshot()
            except Exception:  # noqa: BLE001 — one failure must not block rest
                _logger.exception(
                    "biz_bi: snapshot failed for dashboard %s", dashboard.name)
            dashboard.next_send = dashboard._compute_next_send()

    def _default_extra_filters(self, dataset_id):
        """Dashboard filter defaults compiled per dataset (mirrors what the
        frontend applies on load)."""
        self.ensure_one()
        extra = []
        for flt in self.filter_ids:
            default = flt.default_json or {}
            if not default.get('op') or default.get('value') in (None, ''):
                continue
            mapping = flt.mapping_ids.filtered(
                lambda m: m.dataset_id.id == dataset_id)[:1]
            if mapping:
                extra.append({'field_id': mapping.field_id.id,
                              'op': default['op'],
                              'value': default['value']})
        return extra

    def _build_snapshot_xlsx(self):
        """One workbook, one sheet per widget, dashboard defaults applied."""
        import xlsxwriter

        self.ensure_one()
        engine = self.env['bi.query.engine']
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        header_format = workbook.add_format(
            {'bold': True, 'bg_color': '#EEF1F5', 'border': 1})
        number_format = workbook.add_format({'num_format': '#,##0.00'})
        used_names = set()
        for widget in self.widget_ids:
            chart = widget.chart_id
            envelope = engine.run(chart._to_query_request(
                self._default_extra_filters(chart.dataset_id.id)))
            if envelope.get('error'):
                continue
            title = (widget.title_override or chart.name or 'Sheet')[:28]
            name, counter = title, 2
            while name.lower() in used_names:
                name = '%s %d' % (title[:25], counter)
                counter += 1
            used_names.add(name.lower())
            sheet = workbook.add_worksheet(name)
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
        return buffer.getvalue()

    def _send_snapshot(self):
        self.ensure_one()
        recipients = self.recipient_ids.filtered('email')
        if not recipients:
            _logger.warning("biz_bi: dashboard %s has no snapshot recipients",
                            self.name)
            return
        content = self._build_snapshot_xlsx()
        date_label = fields.Date.context_today(self).strftime('%d/%m/%Y')
        attachment = self.env['ir.attachment'].create({
            'name': '%s - %s.xlsx' % (self.name, date_label),
            'datas': base64.b64encode(content),
            'res_model': 'bi.dashboard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument'
                        '.spreadsheetml.sheet',
        })
        self.env['mail.mail'].sudo().create({
            'subject': _("Dashboard snapshot: %(name)s (%(date)s)",
                         name=self.name, date=date_label),
            'email_to': ', '.join(recipients.mapped('email')),
            'body_html': _(
                "<p>Attached is the scheduled snapshot of "
                "<b>%(name)s</b> — one sheet per chart.</p>",
                name=self.name),
            'attachment_ids': [(4, attachment.id)],
            'auto_delete': True,
        }).send()
        self.last_sent = fields.Datetime.now()
        self.env['bi.audit.log'].sudo().log(
            'export', record=self,
            payload={'kind': 'snapshot_email',
                     'recipients': len(recipients)})

    def get_dashboard_data(self):
        """Full payload for the dashboard client action."""
        self.ensure_one()
        self.env['bi.audit.log'].sudo().log(
            'dashboard_view', record=self)
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'workspace_id': self.workspace_id.id,
            'workspace': self.workspace_id.name,
            'can_edit': (
                self.owner_id == self.env.user
                and self.env.user.has_group('biz_bi.group_bi_creator')
            ) or self.env.user.has_group('biz_bi.group_bi_modeler'),
            'tv_enabled': self.is_tv_mode_enabled,
            'refresh_seconds': self.refresh_seconds,
            'widgets': [{
                'id': widget.id,
                'chart_id': widget.chart_id.id,
                'title': widget.title_override or widget.chart_id.name,
                'show_title': widget.show_title,
                'chart_type': widget.chart_id.chart_type,
                'config': widget.chart_id.config_json or {},
                'dataset_id': widget.chart_id.dataset_id.id,
                'grid': {'x': widget.grid_x, 'y': widget.grid_y,
                         'w': widget.grid_w, 'h': widget.grid_h},
            } for widget in self.widget_ids],
            'filters': [{
                'id': flt.id,
                'name': flt.name,
                'filter_type': flt.filter_type,
                'default': flt.default_json or {},
                'mappings': [{
                    'dataset_id': mapping.dataset_id.id,
                    'field_id': mapping.field_id.id,
                    'data_type': mapping.field_id.data_type,
                    'selection_labels':
                        mapping.field_id.selection_labels_json or {},
                } for mapping in flt.mapping_ids],
            } for flt in self.filter_ids],
        }

    def save_layout(self, layout):
        """Persist GridStack positions: [{widget_id, x, y, w, h}]."""
        self.ensure_one()
        widgets_by_id = {w.id: w for w in self.widget_ids}
        for item in layout:
            widget = widgets_by_id.get(item.get('widget_id'))
            if widget:
                widget.write({
                    'grid_x': item.get('x', 0),
                    'grid_y': item.get('y', 0),
                    'grid_w': item.get('w', 4),
                    'grid_h': item.get('h', 4),
                })
        return True

    def add_chart(self, chart_id):
        """Place a chart on the dashboard below existing widgets."""
        self.ensure_one()
        chart = self.env['bi.chart'].browse(int(chart_id))
        chart.check_access('read')
        bottom = max(
            (w.grid_y + w.grid_h for w in self.widget_ids), default=0)
        defaults = {'kpi': (3, 3), 'table': (6, 5)}
        width, height = defaults.get(chart.chart_type, (6, 5))
        widget = self.env['bi.dashboard.widget'].create({
            'dashboard_id': self.id,
            'chart_id': chart.id,
            'grid_x': 0, 'grid_y': bottom,
            'grid_w': width, 'grid_h': height,
        })
        return widget.id


class BiDashboardWidget(models.Model):
    _name = 'bi.dashboard.widget'
    _description = 'BI Dashboard Widget'
    _order = 'grid_y, grid_x'

    dashboard_id = fields.Many2one('bi.dashboard', required=True,
                                   ondelete='cascade', index=True)
    chart_id = fields.Many2one('bi.chart', required=True, ondelete='cascade')
    title_override = fields.Char(translate=True)
    show_title = fields.Boolean(default=True)
    grid_x = fields.Integer(default=0)
    grid_y = fields.Integer(default=0)
    grid_w = fields.Integer(default=6)
    grid_h = fields.Integer(default=5)
    local_filters_json = fields.Json()


class BiDashboardFilter(models.Model):
    """A dashboard-level filter mapped onto one field per dataset, so a
    single date picker can drive widgets built on different datasets."""
    _name = 'bi.dashboard.filter'
    _description = 'BI Dashboard Filter'
    _order = 'sequence'

    dashboard_id = fields.Many2one('bi.dashboard', required=True,
                                   ondelete='cascade', index=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    filter_type = fields.Selection([
        ('list', 'Value List'),
        ('daterange', 'Date Range'),
        ('relative_date', 'Relative Date'),
        ('search', 'Text Search'),
    ], required=True, default='list')
    default_json = fields.Json(help='{"op": "relative", "value": "this_month"}')
    mapping_ids = fields.One2many('bi.dashboard.filter.mapping', 'filter_id',
                                  string='Field Mappings')


class BiDashboardFilterMapping(models.Model):
    _name = 'bi.dashboard.filter.mapping'
    _description = 'BI Dashboard Filter Mapping'

    filter_id = fields.Many2one('bi.dashboard.filter', required=True,
                                ondelete='cascade')
    dataset_id = fields.Many2one('bi.dataset', required=True,
                                 ondelete='cascade')
    field_id = fields.Many2one(
        'bi.field', required=True, ondelete='cascade',
        domain="[('dataset_id', '=', dataset_id)]")

    _sql_constraints = [
        ('dataset_uniq', 'unique(filter_id, dataset_id)',
         'One field mapping per dataset per filter.'),
    ]
