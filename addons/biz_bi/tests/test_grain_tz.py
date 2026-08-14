# -*- coding: utf-8 -*-
"""Phase BG-3 — a grain bucket is cut in the VIEWER's calendar.

BG-2 fixed how a bucket is LABELLED (a calendar value never shifts); this
suite pins where the CUT lands. `DATE_TRUNC('month', col)` splits a UTC
column at UTC midnight, so a Vietnamese "April" used to begin at 07:00 local
on 1 April and seven hours of rows sat in March. The engine now truncates
`(col AT TIME ZONE 'UTC') AT TIME ZONE <viewer zone>`, with the zone as a
BOUND VALUE validated through pytz.

Every window here is measured from a FROZEN instant (`_relative_now`), so a
month-boundary case is testable at 09:00 on a Tuesday rather than by waiting
for the last day of a month (ledger §5.107's flake class).
"""
import datetime
import json
import pathlib
from unittest.mock import patch

from odoo.tests import HttpCase, new_test_user, tagged

from .test_detail_mode import DetailCase

SAIGON = 'Asia/Ho_Chi_Minh'          # UTC+7 all year, no DST
# 18:00 UTC on 31 March is already 01:00 on 1 April in Vietnam: the two
# calendars name different MONTHS, which is the whole point of the fixture.
MONTH_EDGE = datetime.datetime(2026, 3, 31, 18, 0, 0)


class GrainCase(DetailCase):

    def setUp(self):
        super().setUp()
        self.engine_vn = self.env['bi.query.engine'].with_context(tz=SAIGON)
        self.engine_utc = self.env['bi.query.engine'].with_context(tz='UTC')

    def _freeze(self, when):
        return patch.object(
            type(self.env['bi.query.engine']), '_relative_now',
            lambda engine_self: when)

    def _set_create_dates(self, mapping):
        """Raw-SQL backdate: `create_date` is ORM-managed (§5.9)."""
        self.env.flush_all()
        for partner, when in mapping.items():
            self.env.cr.execute(
                "UPDATE res_partner SET create_date = %s WHERE id = %s",
                (when, partner.id))
        self.env.invalidate_all()

    def _month_request(self, field=None, **overrides):
        """One row per month bucket, summing the fixture's latitudes."""
        request = {
            'dataset_id': self.dataset.id,
            'dimensions': [{'field_id': (field or self.f_create_date).id,
                            'grain': 'month'}],
            'measures': [{'field_id': self.f_latitude.id, 'agg': 'sum'}],
            'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                         'value': 'BI Test'}],
            'sort': [{'ref': 'd0', 'dir': 'asc'}],
            'limit': 100,
        }
        request.update(overrides)
        return request

    @staticmethod
    def _buckets(envelope):
        return {row[0]: row[1] for row in envelope['rows']}

    def _straddling_fixture(self):
        """Three partners around the VN/UTC month boundary.

        alpha  2026-03-31 10:00 UTC = 17:00 local — MARCH on both calendars
        beta   2026-03-31 18:30 UTC = 01:30 on 1 April local — the tell
        gamma  2026-04-10 06:00 UTC                — APRIL on both calendars
        """
        alpha, beta, gamma = self.partners
        self._set_create_dates({
            alpha: '2026-03-31 10:00:00',
            beta: '2026-03-31 18:30:00',
            gamma: '2026-04-10 06:00:00',
        })
        return alpha, beta, gamma


@tagged('biz_bi', 'post_install', '-at_install')
class TestGrainTimezone(GrainCase):

    # ------------------------------------------------------------------
    # T1 — the cut itself
    # ------------------------------------------------------------------
    def test_01_month_bucket_is_cut_in_the_readers_calendar(self):
        self._straddling_fixture()

        vn = self._buckets(self.engine_vn.run(self._month_request()))
        utc = self._buckets(self.engine_utc.run(self._month_request()))

        # 18:30 UTC on 31 March is 01:30 on 1 April in Vietnam: beta (20.0)
        # belongs to the Vietnamese April and to the UTC March, and the two
        # readers must each hold a row the other does not.
        self.assertEqual(vn, {'2026-03-01T00:00:00': 10.0,
                              '2026-04-01T00:00:00': 50.0},
                         "a Vietnamese April starts at 17:00 UTC on 31 March")
        self.assertEqual(utc, {'2026-03-01T00:00:00': 30.0,
                               '2026-04-01T00:00:00': 30.0},
                         "a UTC reader's months are unchanged")

        # the LABEL is the naive local truncation and is emitted un-shifted —
        # BG-2's rule (a grained column is not an instant) still holds, so the
        # client renders exactly the bucket the server cut.
        for value in vn:
            self.assertTrue(value.endswith('-01T00:00:00'),
                            "a month bucket is midnight on the 1st, locally")
        column = self.engine_vn.run(self._month_request())['columns'][0]
        self.assertEqual(column['grain'], 'month')
        self.assertEqual(column['type'], 'datetime')

    def test_02_a_date_column_grain_is_untouched(self):
        """A `date` column is already a calendar: no zone may touch it."""
        alpha, beta, gamma = self.partners
        alpha.date_localization = datetime.date(2026, 3, 31)
        beta.date_localization = datetime.date(2026, 4, 1)
        gamma.date_localization = datetime.date(2026, 4, 10)

        request = self._month_request(field=self.f_date_localization)
        vn = self._buckets(self.engine_vn.run(request))
        utc = self._buckets(self.engine_utc.run(request))
        self.assertEqual(vn, utc,
                         "a calendar date must bucket identically in every "
                         "timezone on earth")
        # (DATE_TRUNC casts a date to a timestamp, so the bucket reads
        # `2026-03-01T00:00:00` — pre-existing and deliberately unchanged)
        self.assertEqual({key[:10]: value for key, value in vn.items()},
                         {'2026-03-01': 10.0, '2026-04-01': 50.0})

        # and the SQL carries no zone at all for a date column
        spec = self.engine_vn._resolve_request(self.dataset, request)
        query = self.engine_vn._build_sql(self.dataset, spec)
        self.assertNotIn('AT TIME ZONE', query.code)
        self.assertNotIn(SAIGON, list(query.params))

    def test_03_the_expression_is_identical_in_select_and_group_by(self):
        """One expression, bound values, used at every grain site.

        If SELECT and GROUP BY ever compiled the truncation separately, a
        change to one of them would either break grouping outright or — far
        worse — group by the UTC cut while LABELLING the local one. And the
        zone is the one thing in this expression that comes from user
        preference, so it must arrive as a PARAMETER: never an identifier,
        never a format-string interpolation (engine file header).
        """
        spec = self.engine_vn._resolve_request(
            self.dataset, self._month_request())
        query = self.engine_vn._build_sql(self.dataset, spec)
        code, params = query.code, list(query.params)

        # (the column's own expression is composed INTO the code, so the
        # fingerprint is the wrapper around it)
        self.assertEqual(code.count('DATE_TRUNC(%s,'), 2,
                         "the same truncation must appear in SELECT and in "
                         "GROUP BY:\n%s" % code)
        self.assertEqual(
            code.count("AT TIME ZONE 'UTC') AT TIME ZONE %s"), 2,
            "…and both must convert to the viewer's calendar:\n%s" % code)
        self.assertIn('GROUP BY', code)
        head, tail = code.split('GROUP BY', 1)
        for half in (head, tail):
            self.assertIn("AT TIME ZONE 'UTC') AT TIME ZONE %s", half)

        # the trust boundary: the zone (and the grain) are VALUES
        self.assertNotIn(SAIGON, code)
        self.assertNotIn('Ho_Chi_Minh', code)
        self.assertEqual(params.count(SAIGON), 2)
        self.assertEqual(params.count('month'), 2)

        # a UTC reader gets the identical shape, with 'UTC' as the value
        utc_query = self.engine_utc._build_sql(
            self.dataset,
            self.engine_utc._resolve_request(
                self.dataset, self._month_request()))
        self.assertEqual(list(utc_query.params).count('UTC'), 2)

    def test_04_an_unknown_zone_falls_back_to_utc(self):
        """The zone is round-tripped through pytz before it is bound."""
        rogue = self.env['bi.query.engine'].with_context(
            tz="Mars/Olympus'); DROP TABLE bi_field; --")
        self._straddling_fixture()
        buckets = self._buckets(rogue.run(self._month_request()))
        self.assertEqual(buckets, {'2026-03-01T00:00:00': 30.0,
                                   '2026-04-01T00:00:00': 30.0},
                         "an unresolvable zone reads as UTC, never a crash")
        self.assertTrue(self.env['bi.field'].search_count([]),
                        "and nothing was injected")

    # ------------------------------------------------------------------
    # T2 — congruence with BG-2's relative windows
    # ------------------------------------------------------------------
    def test_05_this_month_filter_and_month_grain_agree(self):
        """The filter selects the reader's April; the grain buckets it as
        April. Two independently-implemented calendars, one answer."""
        alpha, beta, gamma = self._straddling_fixture()
        request = self._month_request(filters=[
            {'field_id': self.f_name.id, 'op': 'like_i', 'value': 'BI Test'},
            {'field_id': self.f_create_date.id, 'op': 'relative',
             'value': 'this_month'}])

        with self._freeze(MONTH_EDGE):
            vn = self._buckets(self.engine_vn.run(request))
            utc = self._buckets(self.engine_utc.run(request))

        self.assertEqual(
            vn, {'2026-04-01T00:00:00': 50.0},
            "a Vietnamese 'this month' is April, and every row it selects "
            "must fall in the April bucket — a single bucket, or the filter "
            "and the grain are cutting the month in different places")
        self.assertEqual(
            utc, {'2026-03-01T00:00:00': 30.0},
            "for a UTC reader it is still March, filter and bucket alike")

    def test_06_drilling_into_a_bucket_returns_that_bucket(self):
        """The filter-on-truncated-value path.

        The dashboard hands a bucket's own edges back as a `date_range`.
        Those edges are now wall-clock moments in the reader's zone, so the
        engine has to read them that way — otherwise clicking the Vietnamese
        April returns the UTC April, and the drill-down disagrees with the
        chart it was launched from.
        """
        alpha, beta, gamma = self._straddling_fixture()
        vn_april = self.engine_vn.run(self._month_request())['rows']
        bucket = [row[0] for row in vn_april if row[0].startswith('2026-04')][0]

        rows = self.engine_vn.run(self._detail_request(
            [self.f_name.id],
            filters=[{'field_id': self.f_name.id, 'op': 'like_i',
                      'value': 'BI Test'},
                     {'field_id': self.f_create_date.id, 'op': 'date_range',
                      'value': [bucket.replace('T', ' '),
                                '2026-05-01 00:00:00']}]))['rows']
        self.assertEqual({row[0] for row in rows},
                         {'BI Test Beta', 'BI Test Gamma'},
                         "the drill-down must return exactly the rows the "
                         "bucket it came from was built out of")

        # and the same edges read by a UTC viewer mean the UTC April
        utc_rows = self.engine_utc.run(self._detail_request(
            [self.f_name.id],
            filters=[{'field_id': self.f_name.id, 'op': 'like_i',
                      'value': 'BI Test'},
                     {'field_id': self.f_create_date.id, 'op': 'date_range',
                      'value': ['2026-04-01 00:00:00',
                                '2026-05-01 00:00:00']}]))['rows']
        self.assertEqual({row[0] for row in utc_rows}, {'BI Test Gamma'})

    # ------------------------------------------------------------------
    # T3 — the drill-down grain override uses the same cut
    # ------------------------------------------------------------------
    def test_07_grain_override_uses_the_same_tz_cut(self):
        self._straddling_fixture()
        chart = self.env['bi.chart'].create({
            'name': 'BG3 Yearly',
            'dataset_id': self.dataset.id,
            'chart_type': 'bar',
            'config_json': {
                'version': 1, 'chart_type': 'bar',
                'slots': {
                    'x': [{'field_id': self.f_create_date.id,
                           'grain': 'year'}],
                    'values': [{'field_id': self.f_latitude.id,
                                'agg': 'sum'}]},
                'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                             'value': 'BI Test'}],
                'limit': 100,
            },
        })
        request = chart._to_query_request(
            grain_overrides={str(self.f_create_date.id): 'month'})
        self.assertEqual(request['dimensions'][0]['grain'], 'month')

        self.assertEqual(
            self._buckets(self.engine_vn.run(request)),
            {'2026-03-01T00:00:00': 10.0, '2026-04-01T00:00:00': 50.0},
            "a drilled bucket is cut in the same calendar as the chart it "
            "was drilled from")
        self.assertEqual(
            self._buckets(self.engine_utc.run(request)),
            {'2026-03-01T00:00:00': 30.0, '2026-04-01T00:00:00': 30.0})

    # ------------------------------------------------------------------
    # T4 — the cache never serves one reader another reader's cut
    # ------------------------------------------------------------------
    def test_08_two_timezones_never_share_a_cached_grain(self):
        self._straddling_fixture()
        request = self._month_request()

        first = self.engine_vn.run(dict(request))
        self.assertEqual(first['meta']['cache'], 'miss')
        again = self.engine_vn.run(dict(request))
        self.assertEqual(again['meta']['cache'], 'hit')
        other = self.engine_utc.run(dict(request))
        self.assertEqual(other['meta']['cache'], 'miss',
                         "a different calendar is a different question")
        self.assertNotEqual(self._buckets(again), self._buckets(other))
        # the hit really is the same answer, not a coincidence
        self.assertEqual(self._buckets(first), self._buckets(again))


@tagged('biz_bi', 'post_install', '-at_install')
class TestLimitOverride(GrainCase):
    """A client may shrink a derived detail request, and nothing else."""

    def _detail_chart(self, limit=5000):
        return self.env['bi.chart'].create({
            'name': 'BG3 Records',
            'dataset_id': self.dataset.id,
            'chart_type': 'table',
            'config_json': {
                'version': 1, 'chart_type': 'table', 'mode': 'detail',
                'slots': {'columns': [{'field_id': self.f_name.id}]},
                'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                             'value': 'BI Test'}],
                'limit': limit,
            },
        })

    def test_09_shrink_is_honoured_grow_is_ignored(self):
        engine = self.env['bi.query.engine']
        request = self._detail_chart()._to_query_request()
        self.assertEqual(request['limit'], 5000)

        self.assertEqual(
            engine.apply_limit_override(request, 201)['limit'], 201,
            "a tile that draws 200 rows may ask for 201")
        # ...and the original request is not mutated in place
        self.assertEqual(request['limit'], 5000)

        for grow in (5001, 20000, 999999):
            self.assertEqual(
                engine.apply_limit_override(request, grow)['limit'], 5000,
                "a client must never raise its own row ceiling")
        for junk in (None, 0, -5, 'lots', {'limit': 1}, True):
            result = engine.apply_limit_override(request, junk)
            self.assertEqual(result['limit'], 5000,
                             "junk is ignored, never obeyed: %r" % (junk,))

    def test_10_an_aggregate_request_is_never_shrunk(self):
        """Fewer rows of an aggregate is a different ANSWER (fewer groups),
        not a shorter page — so the override does not apply there."""
        engine = self.env['bi.query.engine']
        aggregate = self.env['bi.chart'].create({
            'name': 'BG3 Aggregate',
            'dataset_id': self.dataset.id,
            'chart_type': 'bar',
            'config_json': {
                'slots': {
                    'x': [{'field_id': self.f_country_name.id}],
                    'values': [{'field_id': self.f_latitude.id,
                                'agg': 'sum'}]},
                'limit': 500},
        })._to_query_request()
        self.assertNotIn('mode', aggregate)
        self.assertEqual(
            engine.apply_limit_override(aggregate, 1)['limit'], 500)

    def test_11_the_shrunk_limit_reaches_the_query(self):
        """End to end on the engine: fewer rows, an honest total, and the
        truncation flag the tile's overflow line is built from."""
        chart = self._detail_chart(limit=100)
        request = self.env['bi.query.engine'].apply_limit_override(
            chart._to_query_request(), 2)
        envelope = self.engine.run(request)
        self.assertEqual(len(envelope['rows']), 2)
        self.assertEqual(envelope['meta']['total_count'], 3,
                         "the honest total is unaffected by the page size")
        self.assertTrue(envelope['meta']['truncated'])


@tagged('biz_bi', 'post_install', '-at_install')
class TestLimitOverrideEndpoint(GrainCase, HttpCase):
    """The wiring: /bi/query really applies it to a chart-derived request."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bi_user = new_test_user(
            cls.env, login='bg3_query_user', password='bg3_query_user',
            groups='base.group_user,biz_bi.group_bi_creator')

    def setUp(self):
        super().setUp()
        self._allow_all_partners()

    def _query(self, entries):
        response = self.url_open(
            '/bi/query',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
                             'params': {'requests': entries}}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn('error', body, body)
        return body['result']

    def test_12_dashboard_tile_fetches_what_it_draws(self):
        chart = self.env['bi.chart'].create({
            'name': 'BG3 Tile Records',
            'dataset_id': self.dataset.id,
            'chart_type': 'table',
            'config_json': {
                'version': 1, 'chart_type': 'table', 'mode': 'detail',
                'slots': {'columns': [{'field_id': self.f_name.id}]},
                'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                             'value': 'BI Test'}],
                'limit': 5000,
            },
            'owner_id': self.bi_user.id,
        })
        self.authenticate('bg3_query_user', 'bg3_query_user')

        [full] = self._query([{'chart_id': chart.id}])
        self.assertEqual(len(full['rows']), 3)

        [capped] = self._query([{'chart_id': chart.id, 'limit_override': 2}])
        self.assertEqual(len(capped['rows']), 2,
                         "the tile asked for fewer rows and got fewer")
        self.assertEqual(capped['meta']['total_count'], 3,
                         "…while the overflow row still has an honest total")

        [grown] = self._query([{'chart_id': chart.id,
                                'limit_override': 999999}])
        self.assertEqual(len(grown['rows']), 3,
                         "a client-supplied override must never grow a limit")


@tagged('biz_bi', 'post_install', '-at_install')
class TestRecordsEscapeContract(GrainCase):
    """The wizard→Explore hand-off is OWL on both ends (no JS tier here), so
    the contract is asserted on the source and DRIVEN in the evidence pack.
    Fingerprints carry operators/punctuation so a comment cannot satisfy
    them (ledger §5.72)."""

    def test_13_explore_seeds_records_state_from_action_params(self):
        source = pathlib.Path(__file__).parent.parent.joinpath(
            'static/src/components/explore/explore_action.js').read_text()
        # the boot path reads it AFTER the dataset (metadata must exist, or
        # every field id is unknown and every column is dropped)
        boot = source.split('await this.selectDataset(params.dataset_id);')[1]
        self.assertIn('this.applyRecordsConfig(params.records_config);',
                      boot.split('} else if')[0])
        # ...and the seeding really enters Records mode with the columns
        self.assertIn('applyRecordsConfig(config) {', source)
        self.assertIn('this.state.tableMode = "records";', source)
        self.assertIn('.map((fieldId) => byId[fieldId])', source)
        self.assertIn('.filter(Boolean)', source)

    def test_14_the_dashboard_tile_sends_a_shrinking_override(self):
        source = pathlib.Path(__file__).parent.parent.joinpath(
            'static/src/components/dashboard/dashboard_action.js').read_text()
        self.assertIn('const RECORDS_TILE_FETCH = 201;', source)
        self.assertIn('limit_override: this._widgetLimitOverride(widget)',
                      source)
        self.assertIn('return mode === "detail" ? RECORDS_TILE_FETCH '
                      ': undefined;', source)
        # the bucket-edge arithmetic happens on the wall clock, not the
        # browser's zone (§5.159d) — the drill-down boundary is a bucket the
        # server cut in the VIEWER's calendar
        self.assertIn('text + "T00:00:00Z"', source)
        self.assertIn('text.endsWith("Z") ? text : text + "Z"', source)
        self.assertNotIn('const date = new Date(startIso);', source)
