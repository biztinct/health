# -*- coding: utf-8 -*-
import datetime
import json
import re

from odoo.exceptions import UserError
from odoo.tests import HttpCase, new_test_user, tagged

from .common import BiCase, excel_serial, xlsx_numbers, xlsx_strings


class DetailCase(BiCase):
    """BiCase plus the many2one column, which is what makes the
    'names, not ids' contract testable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.f_country_id = cls.dataset.field_ids.filtered(
            lambda f: f.technical_name == 'country_id'
            and f.node_id == cls.node_root)
        cls.f_country_id.visibility = 'visible'

    # `_allow_all_partners` now lives on BiCase (tests/common.py): the RLS
    # suite needs the identical widening, and one copy is one behaviour.

    def _detail_request(self, field_ids=(), **overrides):
        """A records request scoped to this fixture's three partners — the
        dataset sits on res.partner and vietuat holds thousands of them."""
        request = {
            'dataset_id': self.dataset.id,
            'mode': 'detail',
            'dimensions': [{'field_id': field_id} for field_id in field_ids],
            'measures': [],
            'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                         'value': 'BI Test'}],
            'sort': [],
            'limit': 100,
        }
        request.update(overrides)
        return request


@tagged('biz_bi', 'post_install', '-at_install')
class TestDetailMode(DetailCase):

    def test_detail_returns_record_rows(self):
        """One row per record, measures raw, refs d0..d2."""
        result = self.engine.run(self._detail_request(
            [self.f_name.id, self.f_country_id.id, self.f_latitude.id]))
        self.assertNotIn('error', result)
        self.assertEqual([col['ref'] for col in result['columns']],
                         ['d0', 'd1', 'd2'])
        self.assertEqual(result['columns'][0]['role'], 'dimension')
        self.assertEqual(result['columns'][2]['role'], 'measure')
        # a records column carries no aggregation, by construction
        for column in result['columns']:
            self.assertNotIn('agg', column)
        self.assertEqual(result['meta']['mode'], 'detail')

        self.assertEqual(len(result['rows']), 3)
        self.assertEqual(sorted(row[0] for row in result['rows']),
                         ['BI Test Alpha', 'BI Test Beta', 'BI Test Gamma'])
        # raw latitudes, not a 60.0 sum
        self.assertEqual(sorted(row[2] for row in result['rows']),
                         [10.0, 20.0, 30.0])

    def test_detail_total_count_and_truncation(self):
        capped = self.engine.run(
            self._detail_request([self.f_name.id], limit=2))
        self.assertEqual(len(capped['rows']), 2)
        self.assertEqual(capped['meta']['total_count'], 3)
        self.assertTrue(capped['meta']['truncated'])
        # unconfigured must mean the 20k default, NOT int(False) == 0
        self.assertEqual(capped['meta']['export_cap'], 20000)
        self.assertEqual(self.engine.export_row_cap(), 20000)

        full = self.engine.run(self._detail_request([self.f_name.id]))
        self.assertEqual(len(full['rows']), 3)
        self.assertEqual(full['meta']['total_count'], 3)
        self.assertFalse(full['meta']['truncated'])

    def test_detail_respects_where_chain(self):
        """Request filters, and an RLS row rule, both reduce the rows — and
        the honest total is computed through the same WHERE chain."""
        self._allow_all_partners()
        restricted = self.env['res.users'].create({
            'name': 'BI Detail Restricted', 'login': 'bi_detail_restricted',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('biz_bi.group_bi_viewer').id,
            ])],
        })
        narrowed = self.engine.run(self._detail_request(
            [self.f_name.id],
            filters=[
                {'field_id': self.f_name.id, 'op': 'like_i',
                 'value': 'BI Test'},
                {'field_id': self.f_latitude.id, 'op': 'gte', 'value': 15},
            ]))
        self.assertEqual(len(narrowed['rows']), 2)
        self.assertEqual(narrowed['meta']['total_count'], 2)

        self.env['bi.access.rule'].create({
            'name': 'Alpha only',
            'dataset_id': self.dataset.id,
            'rule_type': 'row',
            'user_ids': [(6, 0, restricted.ids)],
            'domain_json': [[self.f_name.id, 'like_i', 'BI Test Alpha']],
        })
        scoped = self.engine.with_user(restricted).run(
            self._detail_request([self.f_name.id]))
        self.assertEqual([row[0] for row in scoped['rows']],
                         ['BI Test Alpha'])
        self.assertEqual(scoped['meta']['total_count'], 1)

    def test_detail_nulls_masked_dimension(self):
        """A mask_mode='null' field is emptied as a DIMENSION too — in
        records mode AND (the §3.9 regression) in aggregate mode."""
        self._allow_all_partners()
        restricted = self.env['res.users'].create({
            'name': 'BI Mask Reader', 'login': 'bi_mask_reader',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('biz_bi.group_bi_viewer').id,
            ])],
        })
        self.env['bi.access.rule'].create({
            'name': 'Null the partner name',
            'dataset_id': self.dataset.id,
            'rule_type': 'column',
            'mask_mode': 'null',
            'user_ids': [(6, 0, restricted.ids)],
            'field_ids': [(6, 0, self.f_name.ids)],
        })
        engine = self.engine.with_user(restricted)

        detail = engine.run(self._detail_request(
            [self.f_name.id, self.f_latitude.id]))
        self.assertEqual(len(detail['rows']), 3)
        self.assertTrue(all(row[0] is None for row in detail['rows']),
                        "a nulled column must not leak a single value")
        self.assertTrue(detail['columns'][0].get('nulled'))
        self.assertFalse(detail['columns'][1].get('nulled'))
        # only the masked column is emptied
        self.assertEqual(sorted(row[1] for row in detail['rows']),
                         [10.0, 20.0, 30.0])

        # §3.9: the same field as an AGGREGATE dimension used to come back in
        # full — it now collapses to a single NULL-keyed group.
        aggregate = engine.run(self._base_request(
            dimensions=[{'field_id': self.f_name.id}]))
        self.assertEqual(len(aggregate['rows']), 1)
        self.assertIsNone(aggregate['rows'][0][0])
        self.assertEqual(aggregate['rows'][0][1], 60.0)
        self.assertTrue(aggregate['columns'][0].get('nulled'))

    def test_detail_relation_labels(self):
        """A many2one records column is labelled per reader, on a cache miss
        AND on a cache hit (labels are never stored in the shared cache)."""
        request = self._detail_request(
            [self.f_country_id.id, self.f_name.id])
        fresh = self.engine.run(request)
        self.assertEqual(fresh['meta']['cache'], 'miss')
        labels = fresh['columns'][0].get('value_labels') or {}
        self.assertEqual(labels.get(str(self.country_a.id)),
                         self.country_a.display_name)

        cached = self.engine.run(request)
        self.assertEqual(cached['meta']['cache'], 'hit')
        self.assertTrue(cached['columns'][0].get('value_labels'),
                        "a cache hit must still carry resolved labels")

    def test_detail_rejects_measures_and_grain(self):
        with self.assertRaises(UserError):
            self.engine.run(self._detail_request(
                [self.f_name.id],
                measures=[{'field_id': self.f_latitude.id, 'agg': 'sum'}]))
        with self.assertRaises(UserError):
            self.engine.run(self._detail_request([self.f_name.id],
                                                 mode='sql'))

        # grain is stripped, never compiled: a year bucket would have
        # collapsed the three fixtures into one row
        result = self.engine.run(self._detail_request(dimensions=[
            {'field_id': self.f_create_date.id, 'grain': 'year'}]))
        self.assertIsNone(result['columns'][0]['grain'])
        self.assertEqual(len(result['rows']), 3)
        for row in result['rows']:
            self.assertFalse(str(row[0]).endswith('-01-01T00:00:00'),
                             "records must show the real datetime")

    def test_chart_roundtrip_detail(self):
        chart = self.env['bi.chart'].create({
            'name': 'Records Chart',
            'dataset_id': self.dataset.id,
            'chart_type': 'table',
            'config_json': {
                'version': 1,
                'chart_type': 'table',
                'mode': 'detail',
                'slots': {'columns': [
                    {'field_id': self.f_name.id},
                    {'field_id': self.f_latitude.id},
                    {'field_id': self.f_name.id},  # duplicate: keep the first
                ]},
                'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                             'value': 'BI Test'}],
                'sort': [{'ref': 'd1', 'dir': 'desc'}],
                'limit': 100,
            },
        })
        request = chart._to_query_request()
        self.assertEqual(request['mode'], 'detail')
        self.assertEqual(request['measures'], [])
        self.assertEqual([dim['field_id'] for dim in request['dimensions']],
                         [self.f_name.id, self.f_latitude.id])
        result = self.engine.run(request)
        self.assertEqual([row[1] for row in result['rows']],
                         [30.0, 20.0, 10.0])

        # dashboard global filters still append on a saved Records widget
        filtered = chart._to_query_request(extra_filters=[
            {'field_id': self.f_latitude.id, 'op': 'gte', 'value': 25}])
        self.assertEqual(
            len(self.engine.run(filtered)['rows']), 1)

        # the aggregate path is untouched — no 'mode' key at all
        aggregate = self.env['bi.chart'].create({
            'name': 'Aggregate Chart',
            'dataset_id': self.dataset.id,
            'chart_type': 'bar',
            'config_json': {'slots': {
                'x': [{'field_id': self.f_country_name.id}],
                'values': [{'field_id': self.f_latitude.id, 'agg': 'sum'}]}},
        })
        self.assertNotIn('mode', aggregate._to_query_request())


@tagged('biz_bi', 'post_install', '-at_install')
class TestExportXlsx(DetailCase, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bi_user = new_test_user(
            cls.env, login='bi_export_user', password='bi_export_user',
            groups='base.group_user,biz_bi.group_bi_creator')

    def setUp(self):
        super().setUp()
        self._allow_all_partners()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _csrf_token(self):
        """The POST route is csrf=True; the backend layout embeds the token."""
        page = self.url_open('/odoo')
        match = re.search(
            r'csrf_token[\'"]?\s*[:=]\s*[\'"]([0-9a-zA-Z]+)[\'"]', page.text)
        self.assertTrue(match, "no csrf token in the backend page")
        return match.group(1)

    # the xlsx readers themselves now live in tests/common.py — the BG-2
    # snapshot suite needs the identical pair, and one copy is one behaviour
    _excel_serial = staticmethod(excel_serial)
    _xlsx_numbers = staticmethod(xlsx_numbers)
    _xlsx_strings = staticmethod(xlsx_strings)

    def _post_export(self, payload, title='QA Records'):
        response = self.url_open('/bi/export/xlsx', data={
            'request_json': json.dumps(payload),
            'title': title,
            'csrf_token': self._csrf_token(),
        })
        return response

    def _last_export_log(self):
        self.env.invalidate_all()
        return self.env['bi.audit.log'].sudo().search(
            [('event', '=', 'export'), ('user_id', '=', self.bi_user.id)],
            limit=1)

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_export_xlsx_post(self):
        self.authenticate('bi_export_user', 'bi_export_user')
        payload = self._detail_request(
            [self.f_name.id, self.f_country_id.id, self.f_latitude.id])
        expected_label = self.env['bi.query.engine'].with_user(
            self.bi_user).run(dict(payload))['columns'][1][
                'value_labels'][str(self.country_a.id)]

        response = self._post_export(payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'PK'),
                        "an xlsx is a zip — magic bytes PK")

        strings = self._xlsx_strings(response.content)
        self.assertIn('BI Test Alpha', strings)
        self.assertIn(expected_label, strings,
                      "relation columns must export the record NAME")
        self.assertNotIn(str(self.country_a.id), strings,
                         "a raw many2one id must never reach a cell")

        log = self._last_export_log()
        self.assertTrue(log)
        self.assertEqual(log.payload_json['format'], 'xlsx')
        self.assertEqual(log.payload_json['mode'], 'detail')
        self.assertEqual(log.payload_json['rows'], 3)
        self.assertEqual(log.payload_json['columns'], 3)
        self.assertFalse(log.payload_json['capped'])

    def test_export_row_cap_is_server_side_only(self):
        """The cap comes from ir.config_parameter. A `hard_cap` in the body
        is ignored, and the capped sheet says so in plain language."""
        self.env['ir.config_parameter'].sudo().set_param(
            'biz_bi.export_row_cap', '2')
        self.addCleanup(
            self.env['ir.config_parameter'].sudo().set_param,
            'biz_bi.export_row_cap', '')
        self.authenticate('bi_export_user', 'bi_export_user')

        payload = self._detail_request([self.f_name.id, self.f_latitude.id])
        payload['hard_cap'] = 999999
        payload['limit'] = 999999
        response = self._post_export(payload)
        self.assertEqual(response.status_code, 200)

        strings = self._xlsx_strings(response.content)
        notice = [text for text in strings if text.startswith('Showing first')]
        self.assertTrue(notice, "a capped export must say it was capped")
        self.assertIn('of 3 rows', notice[0])

        log = self._last_export_log()
        self.assertEqual(log.payload_json['rows'], 2,
                         "a client-supplied hard_cap must not raise the cap")
        self.assertTrue(log.payload_json['capped'])

    def test_sheet_name_is_sanitised(self):
        """xlsxwriter RAISES on []:*?/\\ — a chart name is user input."""
        from odoo.addons.biz_bi.controllers.main import BiController
        self.assertEqual(BiController._sheet_name('Q1: Revenue [VN]/HCM'),
                         'Q1- Revenue -VN--HCM')
        self.assertEqual(BiController._sheet_name(''), 'Data')
        self.assertEqual(BiController._sheet_name("'quoted'"), 'quoted')
        self.assertEqual(len(BiController._sheet_name('x' * 60)), 31)

    def test_export_datetime_reads_in_the_users_timezone(self):
        """A datetime cell is the READER's wall clock, not UTC.

        The engine returns naive UTC. Excel has no timezone concept, so a UTC
        serial in a Vietnamese user's spreadsheet is simply seven hours wrong
        — and for anything after 17:00 UTC it is wrong by a whole DAY, which
        is the case pinned here.
        """
        self.bi_user.tz = 'Asia/Ho_Chi_Minh'
        # a UTC instant that is already tomorrow in Vietnam
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE res_partner SET create_date = %s WHERE id = %s",
            ('2026-03-04 18:30:00', self.partners[0].id))
        self.env.invalidate_all()

        self.authenticate('bi_export_user', 'bi_export_user')
        response = self._post_export(self._detail_request(
            [self.f_name.id, self.f_create_date.id]))
        self.assertEqual(response.status_code, 200)

        utc_serial = self._excel_serial(
            datetime.datetime(2026, 3, 4, 18, 30))
        vn_serial = self._excel_serial(
            datetime.datetime(2026, 3, 5, 1, 30))  # UTC+7, next day
        cells = self._xlsx_numbers(response.content, 'B')
        self.assertTrue(cells, "the datetime column wrote no numeric cell")
        matched = [value for value in cells if abs(value - vn_serial) < 1e-6]
        self.assertTrue(matched,
                        "expected the Ho Chi Minh City wall clock in the cell")
        self.assertFalse(
            [value for value in cells if abs(value - utc_serial) < 1e-6],
            "a raw UTC datetime must not reach a spreadsheet cell")

        # ...and the same export for a UTC reader is unshifted
        self.bi_user.tz = 'UTC'
        self.env.flush_all()
        response = self._post_export(self._detail_request(
            [self.f_name.id, self.f_create_date.id]), title='QA Records UTC')
        cells = self._xlsx_numbers(response.content, 'B')
        self.assertTrue(
            [value for value in cells if abs(value - utc_serial) < 1e-6])

    def test_export_tz_helpers(self):
        """The conversion itself, without the HTTP round trip."""
        import pytz

        from odoo.addons.biz_bi.controllers.main import BiController
        saigon = pytz.timezone('Asia/Ho_Chi_Minh')
        self.assertEqual(
            BiController._to_user_tz(
                datetime.datetime(2026, 3, 4, 18, 30), saigon),
            datetime.datetime(2026, 3, 5, 1, 30))
        # a pure date has no time to move — shifting it would change the day
        self.assertEqual(
            BiController._to_user_tz(datetime.date(2026, 3, 4), saigon),
            datetime.date(2026, 3, 4))
        # no timezone configured is UTC, never a crash
        self.assertEqual(
            BiController._to_user_tz(
                datetime.datetime(2026, 3, 4, 18, 30), None),
            datetime.datetime(2026, 3, 4, 18, 30))
        self.bi_user.tz = False
        self.assertEqual(
            BiController._export_tz(self.env(user=self.bi_user)), pytz.UTC)
        self.bi_user.tz = 'Asia/Ho_Chi_Minh'
        self.assertEqual(
            str(BiController._export_tz(self.env(user=self.bi_user))),
            'Asia/Ho_Chi_Minh')

    def test_datatable_can_suppress_a_duplicate_overflow_row(self):
        """The opt-in exists, defaults OFF, and gates the overflow row only.

        A host that states the truncation itself (the CMS wizard's banner)
        must be able to stop the table repeating it; every other host keeps
        the row, because the alternative is a silent cap.
        """
        import pathlib

        source = pathlib.Path(__file__).parent.parent.joinpath(
            'static/src/components/explore/data_table.js').read_text()
        # the prop is declared optional (so nothing else has to pass it)
        self.assertIn('suppressOverflowRow: { type: Boolean, optional: true }',
                      source)
        # and it is read into the overflow decision, not into the row slice
        self.assertIn('shown.length < all.length && !quiet', source)
        self.assertIn('const quiet = !!this.props.suppressOverflowRow;',
                      source)

    def test_export_xlsx_get_saved_chart_uses_labels(self):
        """The pre-existing saved-chart GET route now writes names too."""
        chart = self.env['bi.chart'].create({
            'name': 'QA Saved: Records [RT1]',
            'dataset_id': self.dataset.id,
            'chart_type': 'table',
            'config_json': {
                'version': 1, 'chart_type': 'table', 'mode': 'detail',
                'slots': {'columns': [{'field_id': self.f_country_id.id},
                                      {'field_id': self.f_name.id}]},
                'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                             'value': 'BI Test'}],
                'limit': 100,
            },
            'owner_id': self.bi_user.id,
        })
        self.authenticate('bi_export_user', 'bi_export_user')
        response = self.url_open('/bi/export/xlsx?chart_id=%d' % chart.id)
        self.assertEqual(response.status_code, 200)
        strings = self._xlsx_strings(response.content)
        self.assertNotIn(str(self.country_a.id), strings)
        self.assertIn('BI Test Alpha', strings)
