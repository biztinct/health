# -*- coding: utf-8 -*-
"""Phase BG-2 — one timezone rule, pinned on every surface.

    Datetimes are STORED in UTC and PRESENTED in the viewing user's
    timezone; relative-date windows are computed in that timezone and
    converted to UTC instants before they touch a UTC column; calendar
    values (a `date` column, a grain bucket) never move at all.

Every window here is measured from a FROZEN instant (`_relative_now` is the
engine's seam for exactly this) so a near-midnight or month-end case is
testable at 09:00 on a Tuesday instead of by waiting for 23:59 — the class
of flake ledger §5.107 records.
"""
import datetime
import pathlib
from unittest.mock import patch

import pytz

from odoo.tests import tagged

from ..bi_tz import (as_calendar_date, cell_value, column_is_instant,
                     day_start_utc, to_user_tz, user_tz_name)
from .common import excel_serial, xlsx_numbers
from .test_detail_mode import DetailCase

SAIGON = 'Asia/Ho_Chi_Minh'          # UTC+7 all year, no DST
# 19:00 UTC on 4 March is already 02:00 on 5 March in Vietnam: the two
# calendars disagree, which is the whole point of the fixture.
NEAR_MIDNIGHT = datetime.datetime(2026, 3, 4, 19, 0, 0)
# 18:00 UTC on 31 March is 01:00 on 1 April in Vietnam — the month boundary
MONTH_EDGE = datetime.datetime(2026, 3, 31, 18, 0, 0)


@tagged('biz_bi', 'post_install', '-at_install')
class TestTimezoneWindows(DetailCase):
    """The engine half: a window means the READER's day."""

    def setUp(self):
        super().setUp()
        self.engine_vn = self.env['bi.query.engine'].with_context(tz=SAIGON)
        self.engine_utc = self.env['bi.query.engine'].with_context(tz='UTC')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _freeze(self, when):
        """Pin the instant every relative window is measured from."""
        return patch.object(
            type(self.env['bi.query.engine']), '_relative_now',
            lambda engine_self: when)

    def _set_create_dates(self, mapping):
        """Raw-SQL backdate: `create_date` is ORM-managed (§5.9 — flush
        before, invalidate after, or a pending write races the UPDATE)."""
        self.env.flush_all()
        for partner, when in mapping.items():
            self.env.cr.execute(
                "UPDATE res_partner SET create_date = %s WHERE id = %s",
                (when, partner.id))
        self.env.invalidate_all()

    def _names_for(self, engine, field, value, op='relative'):
        envelope = engine.run(self._detail_request(
            [self.f_name.id],
            filters=[{'field_id': self.f_name.id, 'op': 'like_i',
                      'value': 'BI Test'},
                     {'field_id': field.id, 'op': op, 'value': value}]))
        return {row[0] for row in envelope['rows']}

    # ------------------------------------------------------------------
    # the conversion itself
    # ------------------------------------------------------------------

    def test_01_window_bounds_convert_only_for_a_datetime_column(self):
        start, end = datetime.date(2026, 3, 5), datetime.date(2026, 3, 6)

        # a datetime column stores UTC instants: the reader's local midnights
        # become the instants at which that local day begins and ends
        self.assertEqual(
            self.engine_vn.window_bounds_for_field(
                start, end, self.f_create_date),
            (datetime.datetime(2026, 3, 4, 17, 0),
             datetime.datetime(2026, 3, 5, 17, 0)))

        # a date column is a CALENDAR: the boundaries go in untouched, and a
        # 7-hour nudge would silently move every row across midnight
        self.assertEqual(
            self.engine_vn.window_bounds_for_field(
                start, end, self.f_date_localization),
            (start, end))

        # a bound that already carries a clock is somebody's real instant —
        # the dashboard drill-down passes bucket edges — and is left alone
        self.assertEqual(
            self.engine_vn.window_bounds_for_field(
                '2026-04-01 00:00:00', '2026-05-01 00:00:00',
                self.f_create_date),
            ('2026-04-01 00:00:00', '2026-05-01 00:00:00'))

        # and for a UTC reader the conversion is the identity in VALUE, even
        # though the type becomes a datetime
        self.assertEqual(
            self.engine_utc.window_bounds_for_field(
                start, end, self.f_create_date),
            (datetime.datetime(2026, 3, 5), datetime.datetime(2026, 3, 6)))

    def test_02_today_is_the_readers_day_not_the_utc_one(self):
        alpha, beta, gamma = self.partners
        self._set_create_dates({
            # 09:00 on 4 March in Vietnam — YESTERDAY for a Vietnamese reader
            alpha: '2026-03-04 02:00:00',
            # 01:30 on 5 March in Vietnam — today for them, still the 4th UTC
            beta: '2026-03-04 18:30:00',
            # 17:00 on 5 March in Vietnam — today for them, the 5th UTC
            gamma: '2026-03-05 10:00:00',
        })
        with self._freeze(NEAR_MIDNIGHT):
            self.assertEqual(
                self.engine_vn.relative_today(), datetime.date(2026, 3, 5))
            self.assertEqual(
                self.engine_utc.relative_today(), datetime.date(2026, 3, 4))

            vn = self._names_for(self.engine_vn, self.f_create_date, 'today')
            utc = self._names_for(self.engine_utc, self.f_create_date, 'today')

        self.assertEqual(vn, {'BI Test Beta', 'BI Test Gamma'},
                         "a Vietnamese 'today' is the Vietnamese day")
        self.assertEqual(utc, {'BI Test Alpha', 'BI Test Beta'},
                         "a UTC reader still gets the UTC day")
        # the discriminating rows: each reader has one the other does not,
        # so this cannot pass by the window merely being wide
        self.assertNotIn('BI Test Alpha', vn)
        self.assertNotIn('BI Test Gamma', utc)

    def test_03_last_7_days_moves_with_the_reader(self):
        alpha, beta, gamma = self.partners
        self._set_create_dates({
            # 17:00 on 25 Feb in Vietnam: inside the UTC window (which opens
            # at 25 Feb 00:00 UTC) and outside the VN one (opens 25 Feb 17:00)
            alpha: '2026-02-25 10:00:00',
            beta: '2026-03-01 06:00:00',       # comfortably inside both
            gamma: '2026-03-05 10:00:00',      # inside VN, past the UTC end
        })
        with self._freeze(NEAR_MIDNIGHT):
            self.assertEqual(
                self.engine_vn.relative_bounds('last_7_days'),
                (datetime.date(2026, 2, 26), datetime.date(2026, 3, 6)))
            vn = self._names_for(
                self.engine_vn, self.f_create_date, 'last_7_days')
            utc = self._names_for(
                self.engine_utc, self.f_create_date, 'last_7_days')

        self.assertEqual(vn, {'BI Test Beta', 'BI Test Gamma'})
        self.assertEqual(utc, {'BI Test Alpha', 'BI Test Beta'})

    def test_04_this_month_at_a_month_boundary(self):
        alpha, beta, gamma = self.partners
        self._set_create_dates({
            # 17:00 on 31 March in Vietnam — still MARCH for them
            alpha: '2026-03-31 10:00:00',
            # 01:30 on 1 April in Vietnam — April for them, March in UTC
            beta: '2026-03-31 18:30:00',
            gamma: '2026-04-10 06:00:00',      # April on both calendars
        })
        with self._freeze(MONTH_EDGE):
            self.assertEqual(
                self.engine_vn.relative_bounds('this_month'),
                (datetime.date(2026, 4, 1), datetime.date(2026, 5, 1)))
            self.assertEqual(
                self.engine_utc.relative_bounds('this_month'),
                (datetime.date(2026, 3, 1), datetime.date(2026, 4, 1)))
            vn = self._names_for(
                self.engine_vn, self.f_create_date, 'this_month')
            utc = self._names_for(
                self.engine_utc, self.f_create_date, 'this_month')

        self.assertEqual(vn, {'BI Test Beta', 'BI Test Gamma'},
                         "for a Vietnamese reader it is already April")
        self.assertEqual(utc, {'BI Test Alpha', 'BI Test Beta'})

    def test_05_a_date_column_never_shifts(self):
        """The off-by-one trap in the other direction: a `2026-03-05` is a
        calendar date, not midnight UTC, and no offset may touch it."""
        alpha, beta, gamma = self.partners
        alpha.date_localization = datetime.date(2026, 3, 4)
        beta.date_localization = datetime.date(2026, 3, 5)
        gamma.date_localization = False

        with self._freeze(NEAR_MIDNIGHT):
            vn = self._names_for(
                self.engine_vn, self.f_date_localization, 'today')
            utc = self._names_for(
                self.engine_utc, self.f_date_localization, 'today')

        # the WINDOW still follows the reader's calendar (VN is already the
        # 5th) but the BOUNDARIES stay plain dates — nothing is nudged by 7h
        self.assertEqual(vn, {'BI Test Beta'})
        self.assertEqual(utc, {'BI Test Alpha'})

    def test_06_two_timezones_never_share_a_cached_answer(self):
        """A relative window is resolved per reader, so the cache key has to
        carry the zone — otherwise the second reader is served the first
        one's day, silently, for the whole TTL."""
        Cache = self.env['bi.query.cache']
        self.assertNotEqual(
            Cache.make_key({'x': 1}, 'fp', 'en_US', SAIGON),
            Cache.make_key({'x': 1}, 'fp', 'en_US', 'UTC'))

        alpha, beta, gamma = self.partners
        self._set_create_dates({
            alpha: '2026-03-04 02:00:00',
            beta: '2026-03-04 18:30:00',
            gamma: '2026-03-05 10:00:00',
        })
        request = self._detail_request(
            [self.f_name.id],
            filters=[{'field_id': self.f_name.id, 'op': 'like_i',
                      'value': 'BI Test'},
                     {'field_id': self.f_create_date.id,
                      'op': 'relative', 'value': 'today'}])
        with self._freeze(NEAR_MIDNIGHT):
            first = self.engine_vn.run(dict(request))
            self.assertEqual(first['meta']['cache'], 'miss')
            again = self.engine_vn.run(dict(request))
            self.assertEqual(again['meta']['cache'], 'hit')
            other = self.engine_utc.run(dict(request))

        self.assertEqual(other['meta']['cache'], 'miss',
                         "a different timezone is a different question")
        self.assertNotEqual({row[0] for row in first['rows']},
                            {row[0] for row in other['rows']})

    def test_07_tz_helpers(self):
        saigon = pytz.timezone(SAIGON)
        self.assertEqual(
            to_user_tz(datetime.datetime(2026, 3, 4, 18, 30), saigon),
            datetime.datetime(2026, 3, 5, 1, 30))
        self.assertEqual(
            day_start_utc(datetime.date(2026, 3, 5), saigon),
            datetime.datetime(2026, 3, 4, 17, 0))
        self.assertEqual(
            day_start_utc(datetime.date(2026, 3, 5), pytz.UTC),
            datetime.datetime(2026, 3, 5, 0, 0))
        # calendar date in, calendar date out; an instant reads as None so
        # the caller knows to leave it alone
        self.assertEqual(as_calendar_date('2026-03-05'),
                         datetime.date(2026, 3, 5))
        self.assertIsNone(as_calendar_date('2026-03-05 00:00:00'))
        self.assertIsNone(as_calendar_date(
            datetime.datetime(2026, 3, 5)))
        # context first, then the user's own preference — the same order
        # `fields.Date.context_today` uses
        self.assertEqual(
            user_tz_name(self.env(context=dict(self.env.context, tz=SAIGON))),
            SAIGON)
        self.assertEqual(
            user_tz_name(self.env(context=dict(self.env.context, tz=False))),
            self.env.user.tz or 'UTC')

    def test_08_only_an_ungrained_datetime_is_an_instant(self):
        """The rule the export, the snapshot and formats.js all share."""
        self.assertTrue(column_is_instant({'type': 'datetime'}))
        self.assertTrue(column_is_instant({'type': 'datetime',
                                           'grain': None}))
        # a grain truncation is a bucket LABEL: shifting 2026-04-01 00:00 for
        # a negative-offset reader would rename the April bucket "March"
        self.assertFalse(column_is_instant({'type': 'datetime',
                                            'grain': 'month'}))
        self.assertFalse(column_is_instant({'type': 'date'}))
        self.assertFalse(column_is_instant({'type': 'text'}))
        self.assertFalse(column_is_instant(None))

        saigon = pytz.timezone(SAIGON)
        self.assertEqual(
            cell_value('2026-03-04T18:30:00', {'type': 'datetime'}, saigon),
            datetime.datetime(2026, 3, 5, 1, 30))
        self.assertEqual(
            cell_value('2026-04-01T00:00:00',
                       {'type': 'datetime', 'grain': 'month'}, saigon),
            datetime.datetime(2026, 4, 1, 0, 0))
        self.assertEqual(
            cell_value('2026-03-04', {'type': 'date'}, saigon),
            datetime.date(2026, 3, 4))
        self.assertIsNone(cell_value('Hanoi', {'type': 'text'}, saigon))


@tagged('biz_bi', 'post_install', '-at_install')
class TestTimezoneWorkbooks(DetailCase):
    """The two writers: the interactive export and the emailed snapshot."""

    def assertSerials(self, values, expected, message=''):
        """An Excel serial is a float built by dividing seconds by 86400, so
        `18:30` round-trips as 46085.770833333336 on one side and
        46085.77083333334 on the other — compare within a tolerance, never
        with `==` (a millisecond is 1.2e-8 of a day, so 1e-6 is still a far
        tighter check than any timezone offset)."""
        self.assertEqual(len(values), len(expected), message or 'cell count')
        for got, want in zip(values, expected):
            self.assertAlmostEqual(got, want, places=6, msg=message)

    def test_09_export_shifts_an_instant_and_leaves_a_bucket_alone(self):
        from odoo.addons.biz_bi.controllers.main import BiController

        saigon = pytz.timezone(SAIGON)
        columns = [
            {'ref': 'd0', 'label': 'Month', 'type': 'datetime',
             'grain': 'month', 'role': 'dimension'},
            {'ref': 'd1', 'label': 'Created', 'type': 'datetime',
             'grain': None, 'role': 'dimension'},
            {'ref': 'd2', 'label': 'Geo Date', 'type': 'date',
             'role': 'dimension'},
        ]
        rows = [['2026-04-01T00:00:00', '2026-03-04T18:30:00', '2026-03-04']]
        content = BiController()._build_xlsx(columns, rows, 'TZ', tz=saigon)

        self.assertSerials(
            xlsx_numbers(content, 'A'),
            [excel_serial(datetime.datetime(2026, 4, 1))],
            "a month bucket is a label — shifting it renames the month")
        self.assertSerials(
            xlsx_numbers(content, 'B'),
            [excel_serial(datetime.datetime(2026, 3, 5, 1, 30))],
            "an instant reads in the reader's wall clock")
        self.assertSerials(
            xlsx_numbers(content, 'C'),
            [excel_serial(datetime.datetime(2026, 3, 4))],
            "a calendar date has no time to move")

    def test_10_snapshot_email_workbook_reads_in_the_users_timezone(self):
        """`_build_snapshot_xlsx` wrote `str(value)` — the raw naive UTC ISO
        string — so every scheduled email was seven hours early for a
        Vietnamese recipient, and a whole day early after 17:00 UTC. It is
        the second writer BG-1 could not reach; it now shares the first
        one's conversion."""
        alpha = self.partners[0]
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE res_partner SET create_date = %s WHERE id = %s",
            ('2026-03-04 18:30:00', alpha.id))
        self.env.invalidate_all()

        chart = self.env['bi.chart'].create({
            'name': 'BG2 Snapshot Records',
            'dataset_id': self.dataset.id,
            'chart_type': 'table',
            'config_json': {
                'version': 1, 'chart_type': 'table', 'mode': 'detail',
                'slots': {'columns': [{'field_id': self.f_name.id},
                                      {'field_id': self.f_create_date.id}]},
                'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                             'value': 'BI Test Alpha'}],
                'limit': 100,
            },
        })
        dashboard = self.env['bi.dashboard'].create({
            'name': 'BG2 Snapshot Dash', 'workspace_id': self.workspace.id})
        self.env['bi.dashboard.widget'].create({
            'dashboard_id': dashboard.id, 'chart_id': chart.id})

        content = dashboard.with_context(tz=SAIGON)._build_snapshot_xlsx()
        self.assertTrue(content.startswith(b'PK'))
        self.assertSerials(
            xlsx_numbers(content, 'B'),
            [excel_serial(datetime.datetime(2026, 3, 5, 1, 30))],
            "the snapshot must carry the recipient-side wall clock")

        utc = dashboard.with_context(tz='UTC')._build_snapshot_xlsx()
        self.assertSerials(
            xlsx_numbers(utc, 'B'),
            [excel_serial(datetime.datetime(2026, 3, 4, 18, 30))],
            "...and a UTC reader's copy is unshifted")

    def test_11_client_formatter_mirrors_the_instant_rule(self):
        """No JS test tier exists here, so the contract is asserted on the
        source and PROVEN in the browser evidence pack. The fingerprints are
        expressions, not prose, so a comment cannot satisfy them (§5.72)."""
        source = pathlib.Path(__file__).parent.parent.joinpath(
            'static/src/core/formats.js').read_text()

        # the mirrored predicate, character for character with its operators
        self.assertIn(
            'return (column || {}).type === "datetime" '
            '&& !(column || {}).grain;', source)
        # a naive datetime is read as UTC before it is formatted...
        self.assertIn('iso.endsWith("Z") ? iso : iso + "Z"', source)
        # ...a date-only value is pinned to a calendar day in every zone...
        self.assertIn('new Date(text + "T00:00:00Z")', source)
        self.assertIn('timeZone: "UTC" };', source)
        # ...and the render happens in the viewer's zone, not the browser's
        self.assertIn('user.tz || undefined', source)
        self.assertIn('{ ...options, timeZone }', source)
        # the bare constructor that caused all of it is gone
        self.assertNotIn('new Date(value)', source)
