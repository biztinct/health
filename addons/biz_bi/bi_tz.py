# -*- coding: utf-8 -*-
"""ONE timezone rule for the whole BI module.

    Datetimes are STORED in UTC and PRESENTED in the viewing user's
    timezone; relative-date windows are computed in that timezone and
    converted to UTC instants before they touch a UTC column.

Everything that reads a datetime out of the engine — the xlsx export
controller, the scheduled snapshot workbook, the client formatter (mirrored
in ``static/src/core/formats.js``) — goes through the helpers here, so the
screen, the spreadsheet and the emailed workbook cannot disagree.

The one distinction that matters: **an instant is not a calendar value.**
A ``date`` column and a grain truncation (``DATE_TRUNC('month', …)``) are
bucket labels, not moments — shifting one by an offset changes the day, and
for a month grain the month. Only an un-grained ``datetime`` column carries
an instant, and only that one is re-read in the viewer's zone.
"""
import datetime

import pytz


def user_tz_name(env):
    """The IANA zone name a datetime should READ in for `env`.

    Context first, then the user's own preference — the same resolution
    `fields.Date.context_today` uses, so a window computed here and a
    `today` computed by the framework can never disagree (a test env that
    pins `tz='UTC'` must move both, not one).
    """
    try:
        name = env.context.get('tz') or (env.user.tz if env.user else None)
    except AttributeError:
        name = None
    return name or 'UTC'


def user_timezone(env):
    """`user_tz_name` as a pytz zone. An unknown zone is UTC, never a crash."""
    try:
        return pytz.timezone(user_tz_name(env))
    except (pytz.UnknownTimeZoneError, AttributeError):
        return pytz.UTC


def to_user_tz(value, tz):
    """Naive-UTC datetime -> naive datetime in `tz`.

    Anything that is not a datetime (a pure `date`, a string, None) comes
    back untouched: a calendar date has no time to shift and moving it
    would change the day.
    """
    if not isinstance(value, datetime.datetime) or tz is None:
        return value
    aware = pytz.UTC.localize(value) if value.tzinfo is None else value
    return aware.astimezone(tz).replace(tzinfo=None)


def day_start_utc(day, tz):
    """The naive-UTC instant at which the calendar day `day` BEGINS in `tz`.

    This is what turns a user-tz window boundary into something comparable
    with a UTC column: "today" for a Vietnamese reader starts at 17:00 UTC
    the previous day.
    """
    if isinstance(day, datetime.datetime):
        day = day.date()
    naive = datetime.datetime(day.year, day.month, day.day)
    if tz is None:
        return naive
    return tz.localize(naive).astimezone(pytz.UTC).replace(tzinfo=None)


def as_calendar_date(value):
    """A pure calendar date, or None when the caller already gave an instant.

    `None` is the signal "leave this bound alone": a drill-down range carries
    real UTC bucket boundaries (`2026-04-01 00:00:00`) which are already the
    instants the column stores.
    """
    if isinstance(value, datetime.datetime):
        return None
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 10:
            try:
                return datetime.date.fromisoformat(text)
            except ValueError:
                return None
    return None


def column_is_instant(column):
    """True when a result column's values are UTC INSTANTS to be re-read in
    the viewer's zone; False for calendar values that must never shift.

    Mirrored in `static/src/core/formats.js` (`columnIsInstant`) — change one
    side, change both, or the screen and the export part company again.
    """
    column = column or {}
    return column.get('type') == 'datetime' and not column.get('grain')


def parse_engine_datetime(value):
    """The engine's wire format (`_json_safe_row` emits `isoformat()`) back
    into a date/datetime, or None when it is neither."""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip().replace('Z', '').replace(' ', 'T')
    # `datetime.fromisoformat('2026-03-04')` SUCCEEDS and hands back midnight,
    # so a date-only string has to be offered to the date parser first or a
    # calendar value silently becomes an instant.
    parsers = ((datetime.date.fromisoformat, datetime.datetime.fromisoformat)
               if len(text) == 10
               else (datetime.datetime.fromisoformat,
                     datetime.date.fromisoformat))
    for parser in parsers:
        try:
            return parser(text)
        except ValueError:
            continue
    return None


def cell_value(value, column, tz):
    """The value an xlsx cell should carry for `column`: a parsed
    date/datetime already in the reader's zone, or None when the value is
    not a date at all (the caller then writes it as it is)."""
    if column.get('type') not in ('date', 'datetime'):
        return None
    parsed = parse_engine_datetime(value)
    if parsed is None:
        return None
    if column_is_instant(column):
        parsed = to_user_tz(parsed, tz)
    return parsed
