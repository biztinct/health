# -*- coding: utf-8 -*-
"""Programmatic seed: the margin SQL view, its BI dataset (gold, daily) and the
"Visit Margin" dashboard in the Finance workspace. Python (not XML) because
everything hangs off scanned bi.field ids that only exist after the scan runs —
the biz_bi_health seeder is the canonical precedent this mirrors."""
import logging
import os

_logger = logging.getLogger(__name__)

_SQL_PATH = os.path.join(os.path.dirname(__file__),
                         'data', 'bi_margin_visit_view.sql')

# Monetary measure preset (VND, 0 decimals).
_MONEY = {'role': 'measure', 'default_agg': 'sum', 'data_type': 'monetary',
          'format_json': {'currency': 'VND', 'decimals': 0}}

# (technical_name, name_en, name_vi, overrides)
MARGIN_CURATION = [
    ('completed_date', 'Completed Date', 'Ngày hoàn thành', {'role': 'date'}),
    ('name', 'Visit', 'Lượt thăm', {}),
    ('service_type', 'Service Type', 'Loại dịch vụ', {}),
    ('state', 'Status', 'Trạng thái', {}),
    ('revenue_source', 'Revenue Source', 'Nguồn doanh thu', {}),
    ('labor_source', 'Labor Source', 'Nguồn thời gian lao động', {}),
    ('is_invoiced', 'Invoiced', 'Đã xuất hóa đơn', {}),
    ('revenue_total_vnd', 'Revenue', 'Doanh thu', _MONEY),
    ('revenue_service_vnd', 'Service Revenue', 'Doanh thu dịch vụ', _MONEY),
    ('revenue_travel_vnd', 'Travel Revenue', 'Doanh thu di chuyển', _MONEY),
    ('labor_cost_vnd', 'Labor Cost', 'Chi phí nhân công', _MONEY),
    ('travel_cost_vnd', 'Travel Cost', 'Chi phí di chuyển', _MONEY),
    ('commission_vnd', 'Commission', 'Hoa hồng', _MONEY),
    ('cost_total_vnd', 'Total Cost', 'Tổng chi phí', _MONEY),
    ('margin_vnd', 'Margin', 'Lợi nhuận', _MONEY),
    ('margin_pct', 'Margin %', 'Biên lợi nhuận %',
     {'role': 'measure', 'default_agg': 'avg',
      'format_json': {'decimals': 1, 'suffix': '%'}}),
    ('labor_minutes', 'Labor Minutes', 'Số phút lao động',
     {'role': 'measure', 'default_agg': 'sum',
      'format_json': {'decimals': 0}}),
    ('travel_km', 'Travel km', 'Số km di chuyển',
     {'role': 'measure', 'default_agg': 'sum',
      'format_json': {'decimals': 1}}),
    ('evv_verified_hours', 'EVV Verified Hours', 'Giờ xác minh EVV',
     {'role': 'measure', 'default_agg': 'sum',
      'format_json': {'decimals': 2}}),
]


def post_init_hook(env):
    MarginSeeder(env).run()


class MarginSeeder:

    def __init__(self, env):
        self.env = env
        self.vi_active = 'vi_VN' in {
            code for code, _n in env['res.lang'].get_installed()}

    def run(self):
        # The view is idempotent (CREATE OR REPLACE) — always (re)create it so
        # an -i refreshes the SQL. The dataset/dashboard seed is guarded.
        self._create_view()
        marker = self.env['ir.config_parameter'].sudo().get_param(
            'biz_bi_margin.seeded')
        if marker or self.env['bi.dataset'].search_count(
                [('name', '=', 'Visit Margin')]):
            _logger.info("biz_bi_margin: seed content already present")
            return
        try:
            dataset = self._build_margin_dataset()
            self._build_dashboard(dataset)
            self.env['ir.config_parameter'].sudo().set_param(
                'biz_bi_margin.seeded', '1')
        except Exception:
            _logger.exception("biz_bi_margin: seed failed")

    # ------------------------------------------------------------------
    # View + source
    # ------------------------------------------------------------------
    def _create_view(self):
        with open(_SQL_PATH, 'r', encoding='utf-8') as fh:
            self.env.cr.execute(fh.read())
        _logger.info("biz_bi_margin: (re)created view bi_margin_visit")

    def _sql_view_source(self):
        Source = self.env['bi.source']
        source = Source.search([('type', '=', 'sql_view'),
                                ('view_name', '=', 'bi_margin_visit')], limit=1)
        if not source:
            source = Source.create({
                'name': 'Visit Margin (view)', 'type': 'sql_view',
                'view_name': 'bi_margin_visit', 'state': 'ready'})
        return source

    def _odoo_source(self, model_name):
        Source = self.env['bi.source']
        ir_model = self.env['ir.model']._get(model_name)
        source = Source.search([('model_id', '=', ir_model.id)], limit=1)
        if not source:
            source = Source.create({
                'name': ir_model.name, 'type': 'odoo_model',
                'model_id': ir_model.id, 'state': 'ready'})
        return source

    # ------------------------------------------------------------------
    # Dataset (mirrors biz_bi_health._new_dataset/_join/_curate)
    # ------------------------------------------------------------------
    def _build_margin_dataset(self):
        dataset = self.env['bi.dataset'].create({
            'name': 'Visit Margin',
            'description': 'One row per completed visit: revenue minus direct '
                           'cost (labor + travel + commission). Costs are v1 '
                           'rate × time assumptions — see Settings.',
            'workspace_id': self.env.ref('biz_bi_health.workspace_finance').id,
            'is_certified': True,
            'storage_mode': 'gold',
        })
        root = self.env['bi.dataset.node'].create({
            'dataset_id': dataset.id,
            'source_id': self._sql_view_source().id,
            'is_root': True,
        })
        root.action_scan_fields()
        if self.vi_active:
            dataset.with_context(lang='vi_VN').name = 'Lợi nhuận theo lượt thăm'
        self._join(dataset, root, 'facility_id', 'health.facility',
                   'Facility', 'Cơ sở')
        self._join(dataset, root, 'patient_id', 'res.partner',
                   'Client', 'Khách hàng')
        self._join(dataset, root, 'lead_staff_id', 'hr.employee',
                   'Lead Staff', 'Nhân viên phụ trách')
        self._curate(dataset, root, MARGIN_CURATION)
        company_field = self._field(dataset, 'company_id', root)
        if company_field:
            dataset.company_field_id = company_field.id
        dataset.action_publish()
        # Margin is a morning-report number, not realtime — refresh daily.
        if dataset.refresh_job_id:
            dataset.refresh_job_id.interval_minutes = '1440'
        return dataset

    def _join(self, dataset, parent_node, parent_field, child_model,
              label_en, label_vi):
        if child_model not in self.env:
            return None
        child = self.env['bi.dataset.node'].create({
            'dataset_id': dataset.id,
            'source_id': self._odoo_source(child_model).id,
        })
        self.env['bi.relationship'].create({
            'dataset_id': dataset.id,
            'parent_node_id': parent_node.id,
            'child_node_id': child.id,
            'parent_field': parent_field,
            'child_field': 'id',
            'cardinality': 'many2one',
            'origin': 'auto',
        })
        child.action_scan_fields()
        for field in child.field_ids:
            if field.technical_name == 'name':
                field.write({'name': label_en, 'folder': label_en,
                             'visibility': 'visible', 'sequence': 1})
                if self.vi_active:
                    field.with_context(lang='vi_VN').name = label_vi
            else:
                field.visibility = 'hidden'
        return child

    def _curate(self, dataset, root, curation):
        by_name = {f.technical_name: f
                   for f in dataset.field_ids if f.node_id == root}
        for technical, name_en, name_vi, overrides in curation:
            field = by_name.get(technical)
            if not field:
                continue
            field.write(dict(overrides, name=name_en, visibility='visible',
                             sequence=10))
            if self.vi_active:
                field.with_context(lang='vi_VN').name = name_vi
        curated = {c[0] for c in curation}
        for field in dataset.field_ids:
            if (field.node_id == root and field.technical_name not in curated
                    and field.role == 'dimension'
                    and field.data_type == 'text'
                    and field.technical_name != 'name'):
                field.visibility = 'hidden'

    def _field(self, dataset, technical_name, node=None):
        for field in dataset.field_ids:
            if field.technical_name == technical_name and (
                    node is None or field.node_id == node):
                return field
        return None

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def _make_chart(self, name, name_vi, dataset, chart_type, config):
        chart = self.env['bi.chart'].create({
            'name': name,
            'dataset_id': dataset.id,
            'chart_type': chart_type,
            'config_json': dict(config, version=1, chart_type=chart_type),
        })
        if self.vi_active:
            chart.with_context(lang='vi_VN').name = name_vi
        return chart

    def _place(self, dashboard, chart, x, y, w, h):
        self.env['bi.dashboard.widget'].create({
            'dashboard_id': dashboard.id, 'chart_id': chart.id,
            'grid_x': x, 'grid_y': y, 'grid_w': w, 'grid_h': h,
        })

    def _build_dashboard(self, dataset):
        f_state = self._field(dataset, 'state')
        f_rev = self._field(dataset, 'revenue_total_vnd')
        f_cost = self._field(dataset, 'cost_total_vnd')
        f_margin = self._field(dataset, 'margin_vnd')
        f_pct = self._field(dataset, 'margin_pct')
        f_date = self._field(dataset, 'completed_date')
        f_type = self._field(dataset, 'service_type')
        f_name = self._field(dataset, 'name')
        facility_name = dataset.field_ids.filtered(
            lambda f: f.name in ('Facility', 'Cơ sở')
            and f.technical_name == 'name')
        patient_name = dataset.field_ids.filtered(
            lambda f: f.name in ('Client', 'Khách hàng')
            and f.technical_name == 'name')
        staff_name = dataset.field_ids.filtered(
            lambda f: f.name in ('Lead Staff', 'Nhân viên phụ trách')
            and f.technical_name == 'name')

        def slots(x=None, values=None, series=None, sort=None, limit=500):
            return {'slots': {'x': x or [], 'values': values or [],
                              'series': series or []},
                    'filters': [], 'sort': sort or [], 'limit': limit}

        kpi_visits = self._make_chart(
            'Completed Visits', 'Số lượt hoàn thành', dataset, 'kpi',
            slots(values=[{'field_id': f_state.id, 'agg': 'count'}]))
        kpi_rev = self._make_chart(
            'Revenue', 'Doanh thu', dataset, 'kpi',
            slots(values=[{'field_id': f_rev.id, 'agg': 'sum'}]))
        kpi_cost = self._make_chart(
            'Total Cost', 'Tổng chi phí', dataset, 'kpi',
            slots(values=[{'field_id': f_cost.id, 'agg': 'sum'}]))
        kpi_margin = self._make_chart(
            'Margin', 'Lợi nhuận', dataset, 'kpi',
            slots(values=[{'field_id': f_margin.id, 'agg': 'sum'}]))
        kpi_pct = self._make_chart(
            'Margin %', 'Biên lợi nhuận %', dataset, 'kpi',
            slots(values=[{'field_id': f_pct.id, 'agg': 'avg'}]))
        line_month = self._make_chart(
            'Margin by Month', 'Lợi nhuận theo tháng', dataset, 'line',
            slots(x=[{'field_id': f_date.id, 'grain': 'month'}],
                  values=[{'field_id': f_margin.id, 'agg': 'sum'}]))
        bar_type = self._make_chart(
            'Margin by Service Type', 'Lợi nhuận theo loại dịch vụ',
            dataset, 'bar',
            slots(x=[{'field_id': f_type.id}],
                  values=[{'field_id': f_margin.id, 'agg': 'sum'}]))

        dashboard = self.env['bi.dashboard'].create({
            'name': 'Visit Margin',
            'workspace_id': self.env.ref(
                'biz_bi_health.workspace_finance').id,
        })
        if self.vi_active:
            dashboard.with_context(lang='vi_VN').name = \
                'Lợi nhuận theo lượt thăm'
        self._place(dashboard, kpi_visits, 0, 0, 3, 2)
        self._place(dashboard, kpi_rev, 3, 0, 3, 2)
        self._place(dashboard, kpi_cost, 6, 0, 3, 2)
        self._place(dashboard, kpi_margin, 9, 0, 3, 2)
        self._place(dashboard, kpi_pct, 0, 2, 3, 2)
        self._place(dashboard, line_month, 3, 2, 9, 5)
        self._place(dashboard, bar_type, 0, 7, 6, 5)
        if facility_name:
            bar_facility = self._make_chart(
                'Margin by Facility', 'Lợi nhuận theo cơ sở', dataset, 'bar_h',
                slots(x=[{'field_id': facility_name[0].id}],
                      values=[{'field_id': f_margin.id, 'agg': 'sum'}]))
            self._place(dashboard, bar_facility, 6, 7, 6, 5)

        # The loss list — bottom 20 visits by margin (m0 ascending).
        loss_x = [{'field_id': f_name.id}]
        if patient_name:
            loss_x.append({'field_id': patient_name[0].id})
        if staff_name:
            loss_x.append({'field_id': staff_name[0].id})
        loss_x.append({'field_id': f_date.id})
        loss_list = self._make_chart(
            'Loss-Making Visits (bottom 20)',
            'Lượt thăm lỗ (20 thấp nhất)', dataset, 'table',
            slots(x=loss_x,
                  values=[{'field_id': f_margin.id, 'agg': 'sum'},
                          {'field_id': f_rev.id, 'agg': 'sum'},
                          {'field_id': f_cost.id, 'agg': 'sum'}],
                  sort=[{'ref': 'm0', 'dir': 'asc'}], limit=20))
        self._place(dashboard, loss_list, 0, 12, 12, 6)

        period = self.env['bi.dashboard.filter'].create({
            'dashboard_id': dashboard.id, 'name': 'Period',
            'filter_type': 'relative_date',
            'default_json': {'op': 'relative', 'value': 'last_6_months'},
        })
        self.env['bi.dashboard.filter.mapping'].create({
            'filter_id': period.id, 'dataset_id': dataset.id,
            'field_id': f_date.id})
        if self.vi_active:
            period.with_context(lang='vi_VN').name = 'Kỳ'
        return dashboard
