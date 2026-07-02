# -*- coding: utf-8 -*-
"""Programmatic seed content: datasets, bilingual field curation, charts and
starter dashboards. Python instead of XML because everything hangs off
scanned bi.field record ids that only exist after the scan runs."""
import logging

_logger = logging.getLogger(__name__)

# (technical_name, name_en, name_vi, overrides)
BOOKING_CURATION = [
    ('scheduled_date', 'Scheduled Date', 'Ngày hẹn', {'role': 'date'}),
    ('booking_date', 'Booking Created', 'Ngày đặt lịch', {}),
    ('state', 'Status', 'Trạng thái', {}),
    ('service_type', 'Service Type', 'Loại dịch vụ', {}),
    ('service_category', 'Service Category', 'Nhóm dịch vụ', {}),
    ('service_fee_vnd', 'Service Fee', 'Phí dịch vụ',
     {'role': 'measure', 'default_agg': 'sum',
      'format_json': {'currency': 'VND', 'decimals': 0}}),
    ('travel_fee', 'Travel Fee', 'Phí di chuyển',
     {'role': 'measure', 'default_agg': 'sum',
      'format_json': {'currency': 'VND', 'decimals': 0}}),
    ('priority', 'Priority', 'Độ ưu tiên', {}),
    ('service_location', 'Service Location', 'Nơi thực hiện', {}),
]

INVOICE_CURATION = [
    ('invoice_date', 'Invoice Date', 'Ngày hóa đơn', {'role': 'date'}),
    ('state', 'Status', 'Trạng thái', {}),
    ('payment_state', 'Payment Status', 'Tình trạng thanh toán', {}),
    ('amount_total', 'Invoiced Amount', 'Tổng tiền hóa đơn',
     {'role': 'measure', 'default_agg': 'sum',
      'format_json': {'currency': 'VND', 'decimals': 0}}),
    ('amount_residual', 'Outstanding Amount', 'Còn phải thu',
     {'role': 'measure', 'default_agg': 'sum',
      'format_json': {'currency': 'VND', 'decimals': 0}}),
    ('move_type', 'Document Type', 'Loại chứng từ', {}),
]

LEAD_CURATION = [
    ('create_date', 'Created On', 'Ngày tạo', {'role': 'date',
                                               'visibility': 'visible'}),
    ('expected_revenue', 'Expected Revenue', 'Doanh thu dự kiến',
     {'role': 'measure', 'default_agg': 'sum',
      'format_json': {'currency': 'VND', 'decimals': 0}}),
    ('probability', 'Probability %', 'Xác suất %',
     {'role': 'measure', 'default_agg': 'avg'}),
]

DATASET_NAMES_VI = {
    'Bookings & Service Orders': 'Lịch hẹn & Đơn dịch vụ',
    'Invoices & Revenue': 'Hóa đơn & Doanh thu',
    'CRM Leads': 'Khách hàng tiềm năng',
    'Staff Assignments': 'Phân công nhân viên',
}


def post_init_hook(env):
    seeder = HealthSeeder(env)
    seeder.run()


class HealthSeeder:

    def __init__(self, env):
        self.env = env
        self.vi_active = 'vi_VN' in {
            code for code, _n in env['res.lang'].get_installed()}

    def run(self):
        if self.env['bi.dataset'].search_count(
                [('name', '=', 'Bookings & Service Orders')]):
            _logger.info("biz_bi_health: seed content already present")
            return
        datasets = {}
        for builder in (self._build_bookings, self._build_invoices,
                        self._build_leads, self._build_assignments):
            try:
                dataset = builder()
                if dataset:
                    datasets[dataset.name] = dataset
            except Exception:
                _logger.exception(
                    "biz_bi_health: seed builder %s failed — skipping",
                    builder.__name__)
        try:
            self._build_dashboards(datasets)
        except Exception:
            _logger.exception("biz_bi_health: dashboard seed failed")

    # ------------------------------------------------------------------
    # Shared plumbing
    # ------------------------------------------------------------------

    def _get_source(self, model_name):
        Source = self.env['bi.source']
        ir_model = self.env['ir.model']._get(model_name)
        source = Source.search([('model_id', '=', ir_model.id)], limit=1)
        if not source:
            source = Source.create({
                'name': ir_model.name, 'type': 'odoo_model',
                'model_id': ir_model.id, 'state': 'ready'})
        return source

    def _new_dataset(self, name, workspace_xmlid, root_model, description=''):
        dataset = self.env['bi.dataset'].create({
            'name': name,
            'description': description,
            'workspace_id': self.env.ref(workspace_xmlid).id,
            'is_certified': True,
        })
        root = self.env['bi.dataset.node'].create({
            'dataset_id': dataset.id,
            'source_id': self._get_source(root_model).id,
            'is_root': True,
        })
        root.action_scan_fields()
        if self.vi_active and name in DATASET_NAMES_VI:
            dataset.with_context(lang='vi_VN').name = DATASET_NAMES_VI[name]
        return dataset, root

    def _join(self, dataset, parent_node, parent_field, child_model,
              label_en, label_vi):
        child = self.env['bi.dataset.node'].create({
            'dataset_id': dataset.id,
            'source_id': self._get_source(child_model).id,
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
        # keep only the display name from lookup nodes; hide the rest
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
        # tidy noise: hide uncurated text fields with no obvious value
        curated = {c[0] for c in curation}
        for field in dataset.field_ids:
            if (field.node_id == root and field.technical_name not in curated
                    and field.role == 'dimension'
                    and field.data_type == 'text'
                    and field.technical_name not in ('name',)):
                field.visibility = 'hidden'

    def _field(self, dataset, technical_name, node=None):
        for field in dataset.field_ids:
            if field.technical_name == technical_name and (
                    node is None or field.node_id == node):
                return field
        return None

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    def _build_bookings(self):
        dataset, root = self._new_dataset(
            'Bookings & Service Orders', 'biz_bi_health.workspace_operations',
            'health.fieldservice.order',
            'One row per home-care booking (field service order).')
        self._join(dataset, root, 'patient_id', 'res.partner',
                   'Client', 'Khách hàng')
        if 'health.facility' in self.env:
            self._join(dataset, root, 'facility_id', 'health.facility',
                       'Facility', 'Cơ sở')
        self._join(dataset, root, 'primary_nurse_id', 'hr.employee',
                   'Primary Nurse', 'Điều dưỡng chính')
        self._curate(dataset, root, BOOKING_CURATION)
        dataset.action_publish()
        self.dataset_bookings = dataset
        return dataset

    def _build_invoices(self):
        dataset, root = self._new_dataset(
            'Invoices & Revenue', 'biz_bi_health.workspace_finance',
            'account.move', 'Customer invoices and credit notes.')
        self._join(dataset, root, 'partner_id', 'res.partner',
                   'Customer', 'Khách hàng')
        self._curate(dataset, root, INVOICE_CURATION)
        move_type = self._field(dataset, 'move_type', root)
        if move_type:
            dataset.static_filters_json = [{
                'field_id': move_type.id, 'op': 'in',
                'value': ['out_invoice', 'out_refund'],
            }]
        dataset.action_publish()
        return dataset

    def _build_leads(self):
        dataset, root = self._new_dataset(
            'CRM Leads', 'biz_bi_health.workspace_growth',
            'crm.lead', 'Leads and opportunities with pipeline stages.')
        self._join(dataset, root, 'stage_id', 'crm.stage',
                   'Stage', 'Giai đoạn')
        self._curate(dataset, root, LEAD_CURATION)
        dataset.action_publish()
        return dataset

    def _build_assignments(self):
        dataset, root = self._new_dataset(
            'Staff Assignments', 'biz_bi_health.workspace_operations',
            'health.staff.assignment',
            'One row per staff-to-booking assignment.')
        self._join(dataset, root, 'staff_id', 'hr.employee',
                   'Staff Member', 'Nhân viên')
        curation = [
            ('assignment_status', 'Assignment Status', 'Trạng thái phân công', {}),
            ('assignment_role', 'Role', 'Vai trò', {}),
            ('planned_start_time', 'Planned Start', 'Bắt đầu dự kiến',
             {'role': 'date'}),
        ]
        self._curate(dataset, root, curation)
        dataset.action_publish()
        return dataset

    # ------------------------------------------------------------------
    # Charts & dashboards
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

    def _build_dashboards(self, datasets):
        bookings = datasets.get('Bookings & Service Orders')
        invoices = datasets.get('Invoices & Revenue')

        if bookings:
            f_date = self._field(bookings, 'scheduled_date')
            f_state = self._field(bookings, 'state')
            f_fee = self._field(bookings, 'service_fee_vnd')
            f_type = self._field(bookings, 'service_type')
            facility_name = bookings.field_ids.filtered(
                lambda f: f.name in ('Facility', 'Cơ sở')
                and f.technical_name == 'name')

            def slots(x=None, values=None, series=None):
                return {'slots': {
                    'x': x or [], 'values': values or [], 'series': series or [],
                }, 'filters': [], 'limit': 500}

            kpi_count = self._make_chart(
                'Total Bookings', 'Tổng lịch hẹn', bookings, 'kpi',
                slots(values=[{'field_id': f_state.id, 'agg': 'count'}]))
            kpi_fee = self._make_chart(
                'Service Revenue', 'Doanh thu dịch vụ', bookings, 'kpi',
                slots(values=[{'field_id': f_fee.id, 'agg': 'sum'}]))
            line_month = self._make_chart(
                'Bookings by Month', 'Lịch hẹn theo tháng', bookings, 'line',
                slots(x=[{'field_id': f_date.id, 'grain': 'month'}],
                      values=[{'field_id': f_state.id, 'agg': 'count'}]))
            donut_state = self._make_chart(
                'Bookings by Status', 'Lịch hẹn theo trạng thái',
                bookings, 'donut',
                slots(x=[{'field_id': f_state.id}],
                      values=[{'field_id': f_state.id, 'agg': 'count'}]))
            bar_type = self._make_chart(
                'Revenue by Service Type', 'Doanh thu theo loại dịch vụ',
                bookings, 'bar',
                slots(x=[{'field_id': f_type.id}],
                      values=[{'field_id': f_fee.id, 'agg': 'sum'}]))

            dashboard = self.env['bi.dashboard'].create({
                'name': 'Operations Overview',
                'workspace_id': self.env.ref(
                    'biz_bi_health.workspace_operations').id,
            })
            if self.vi_active:
                dashboard.with_context(lang='vi_VN').name = \
                    'Tổng quan hoạt động'
            self._place(dashboard, kpi_count, 0, 0, 3, 2)
            self._place(dashboard, kpi_fee, 3, 0, 3, 2)
            self._place(dashboard, donut_state, 6, 0, 6, 5)
            self._place(dashboard, line_month, 0, 2, 6, 5)
            self._place(dashboard, bar_type, 0, 7, 12, 5)
            if facility_name:
                bar_facility = self._make_chart(
                    'Bookings by Facility', 'Lịch hẹn theo cơ sở',
                    bookings, 'bar_h',
                    slots(x=[{'field_id': facility_name[0].id}],
                          values=[{'field_id': f_state.id, 'agg': 'count'}]))
                self._place(dashboard, bar_facility, 6, 5, 6, 5)

            period = self.env['bi.dashboard.filter'].create({
                'dashboard_id': dashboard.id,
                'name': 'Period',
                'filter_type': 'relative_date',
                'default_json': {'op': 'relative', 'value': 'last_6_months'},
            })
            self.env['bi.dashboard.filter.mapping'].create({
                'filter_id': period.id, 'dataset_id': bookings.id,
                'field_id': f_date.id})
            if self.vi_active:
                period.with_context(lang='vi_VN').name = 'Kỳ'

        if invoices:
            f_idate = self._field(invoices, 'invoice_date')
            f_total = self._field(invoices, 'amount_total')
            f_residual = self._field(invoices, 'amount_residual')
            f_paystate = self._field(invoices, 'payment_state')

            def slots(x=None, values=None, series=None, filters=None):
                return {'slots': {
                    'x': x or [], 'values': values or [], 'series': series or [],
                }, 'filters': filters or [], 'limit': 500}

            posted = []
            f_status = self._field(invoices, 'state')
            if f_status:
                posted = [{'field_id': f_status.id, 'op': 'eq',
                           'value': 'posted'}]

            kpi_inv = self._make_chart(
                'Total Invoiced', 'Tổng đã xuất hóa đơn', invoices, 'kpi',
                slots(values=[{'field_id': f_total.id, 'agg': 'sum'}],
                      filters=posted))
            kpi_out = self._make_chart(
                'Outstanding', 'Còn phải thu', invoices, 'kpi',
                slots(values=[{'field_id': f_residual.id, 'agg': 'sum'}],
                      filters=posted))
            line_inv = self._make_chart(
                'Invoiced by Month', 'Hóa đơn theo tháng', invoices, 'area',
                slots(x=[{'field_id': f_idate.id, 'grain': 'month'}],
                      values=[{'field_id': f_total.id, 'agg': 'sum'}],
                      filters=posted))
            donut_pay = self._make_chart(
                'By Payment Status', 'Theo tình trạng thanh toán',
                invoices, 'donut',
                slots(x=[{'field_id': f_paystate.id}],
                      values=[{'field_id': f_total.id, 'agg': 'sum'}],
                      filters=posted))

            dashboard = self.env['bi.dashboard'].create({
                'name': 'Revenue & Receivables',
                'workspace_id': self.env.ref(
                    'biz_bi_health.workspace_finance').id,
            })
            if self.vi_active:
                dashboard.with_context(lang='vi_VN').name = \
                    'Doanh thu & Công nợ'
            self._place(dashboard, kpi_inv, 0, 0, 3, 2)
            self._place(dashboard, kpi_out, 3, 0, 3, 2)
            self._place(dashboard, donut_pay, 6, 0, 6, 5)
            self._place(dashboard, line_inv, 0, 2, 6, 5)

            period = self.env['bi.dashboard.filter'].create({
                'dashboard_id': dashboard.id,
                'name': 'Period',
                'filter_type': 'relative_date',
                'default_json': {'op': 'relative', 'value': 'this_year'},
            })
            self.env['bi.dashboard.filter.mapping'].create({
                'filter_id': period.id, 'dataset_id': invoices.id,
                'field_id': f_idate.id})
            if self.vi_active:
                period.with_context(lang='vi_VN').name = 'Kỳ'
