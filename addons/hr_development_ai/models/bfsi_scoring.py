# -*- coding: utf-8 -*-
"""
BFSI Scoring — the ONE canonical scoring & formatting service.

Every screen (workspace home, person 360, analytics, drawers, AI coach)
must get scores, coverage and formatted values from here so the same team
is never shown two different numbers.

Canonical rules:
  * An employee's score   = rounded overall_score of their latest KPI record.
  * A branch's score      = average of the latest score of bankers WITH data,
                            always paired with a coverage figure (with/total).
  * A period with no data = transparently falls back to the latest period
                            that has data (the UI shows a fallback banner,
                            never a wall of zeros).
"""

from datetime import timedelta, datetime, date as date_cls

from odoo import models, fields, api, _
from odoo.tools.misc import format_date as _odoo_format_date
from odoo.tools.misc import format_datetime as _odoo_format_datetime


class BfsiScoring(models.AbstractModel):
    _name = 'bfsi.scoring'
    _description = 'BFSI Canonical Scoring & Formatting Service'

    # ════════════════════════════════════════════════════════════════
    #  PERIOD RESOLUTION — never show a zero wall
    # ════════════════════════════════════════════════════════════════
    @api.model
    def resolve_period(self, banker_ids, date_from, date_to, range_type='custom'):
        """If the requested window has no KPI rows for these bankers, shift it
        to the equivalent window anchored on the latest period_date that has
        data. Returns a dict so callers can show a fallback banner."""
        KPI = self.env['bfsi.performance.kpi'].sudo()
        banker_ids = list(banker_ids or [])
        base_dom = [('employee_id', 'in', banker_ids)] if banker_ids else []

        has_data = KPI.search_count(
            base_dom + [('period_date', '>=', date_from),
                        ('period_date', '<=', date_to)])
        if has_data:
            return {'date_from': date_from, 'date_to': date_to,
                    'fallback_applied': False, 'fallback_label': ''}

        latest = KPI.search(base_dom, order='period_date desc', limit=1)
        if not latest:
            # genuinely no data anywhere — keep the window, caller shows empty state
            return {'date_from': date_from, 'date_to': date_to,
                    'fallback_applied': False, 'fallback_label': ''}

        anchor = latest.period_date
        if range_type in ('today', 'yesterday'):
            new_from = new_to = anchor
        elif range_type == 'wtd':
            new_from, new_to = anchor - timedelta(days=anchor.weekday()), anchor
        elif range_type == 'mtd':
            new_from, new_to = anchor.replace(day=1), anchor
        elif range_type == 'qtd':
            q_month = ((anchor.month - 1) // 3) * 3 + 1
            new_from, new_to = anchor.replace(month=q_month, day=1), anchor
        else:
            span = (date_to - date_from).days
            new_from, new_to = anchor - timedelta(days=span), anchor

        return {
            'date_from': new_from,
            'date_to': new_to,
            'fallback_applied': True,
            'fallback_label': _('Showing latest available data: %s') % (
                self.fmt_range(new_from, new_to)),
        }

    # ════════════════════════════════════════════════════════════════
    #  SNAPSHOTS — the only score math in the module
    # ════════════════════════════════════════════════════════════════
    @api.model
    def employee_snapshot(self, employee_id, as_of=None):
        """Canonical per-employee performance snapshot from the latest KPI."""
        KPI = self.env['bfsi.performance.kpi'].sudo()
        dom = [('employee_id', '=', int(employee_id))]
        if as_of:
            dom.append(('period_date', '<=', as_of))
        latest = KPI.search(dom, order='period_date desc', limit=1)
        hist = KPI.search(dom, order='period_date desc', limit=8)
        trend = list(reversed([round(k.overall_score or 0) for k in hist]))
        return {
            'kpi_id': latest.id or False,
            'score': round(latest.overall_score or 0) if latest else 0,
            'rank': latest.branch_rank if latest else 0,
            'movement': latest.rank_movement if latest else 0,
            'priority': (latest.coaching_priority if latest else 'low') or 'low',
            'period_date': self.date_pack(latest.period_date if latest else False),
            'trend': trend or [0],
            'has_data': bool(latest),
        }

    @api.model
    def branch_snapshot(self, branch_id, as_of=None):
        """Canonical branch rollup: average over bankers WITH data + coverage.
        Population = front-line bankers only — branch.banker_ids is a One2many
        that also contains the managers themselves, which skewed the old avg."""
        branch = self.env['bfsi.branch'].sudo().browse(int(branch_id))
        bankers = branch.banker_ids.filtered(
            lambda e: e.active and e.banker_type not in (
                'branch_manager', 'regional_manager'))
        total, with_data, revenue, needs_coaching = 0, 0, 0.0, 0
        for banker in bankers:
            snap = self.employee_snapshot(banker.id, as_of=as_of)
            if snap['has_data']:
                with_data += 1
                total += snap['score']
                if snap['priority'] in ('high', 'critical'):
                    needs_coaching += 1
                kpi = self.env['bfsi.performance.kpi'].sudo().browse(snap['kpi_id'])
                revenue += kpi.revenue or 0
        avg = round(total / with_data) if with_data else 0
        return {
            'branch_id': branch.id,
            'branch_name': branch.name,
            'avg_score': avg,
            'coverage': {'with_data': with_data, 'total': len(bankers)},
            'coverage_label': _('%(with)s/%(total)s reporting',
                                **{'with': with_data, 'total': len(bankers)}),
            'needs_coaching': needs_coaching,
            'latest_revenue': revenue,
            'latest_revenue_formatted': self.fmt_currency(revenue),
            'has_data': with_data > 0,
        }

    # ════════════════════════════════════════════════════════════════
    #  FORMATTING — one locale source for every payload
    # ════════════════════════════════════════════════════════════════
    @api.model
    def fmt_currency(self, amount, currency=None):
        """Abbreviated currency: ₫3.0B / $12.5K — for cards and strips."""
        if not currency:
            currency = self.env.company.currency_id
        symbol = currency.symbol or '$'
        amount = amount or 0
        sign = '-' if amount < 0 else ''
        a = abs(amount)
        if a >= 1_000_000_000:
            return f"{sign}{symbol}{a / 1_000_000_000:.1f}B"
        if a >= 1_000_000:
            return f"{sign}{symbol}{a / 1_000_000:.1f}M"
        if a >= 1_000:
            return f"{sign}{symbol}{a / 1_000:.1f}K"
        return f"{sign}{symbol}{a:,.0f}"

    @api.model
    def fmt_date(self, d):
        if not d:
            return ''
        # project rule: always dd/mm/yyyy
        return _odoo_format_date(self.env, d, date_format='dd/MM/yyyy')

    @api.model
    def fmt_datetime(self, dt):
        if not dt:
            return ''
        return _odoo_format_datetime(self.env, dt, dt_format='dd/MM/yyyy HH:mm')

    @api.model
    def fmt_range(self, date_from, date_to):
        if date_from == date_to:
            return self.fmt_date(date_from)
        return '%s – %s' % (self.fmt_date(date_from), self.fmt_date(date_to))

    @api.model
    def fmt_relative(self, d):
        """'Today' / 'In 5 days' / '3 days ago' — falls back to the date."""
        if not d:
            return ''
        if isinstance(d, datetime):
            d = fields.Datetime.context_timestamp(self, d).date()
        elif not isinstance(d, date_cls):
            d = fields.Date.from_string(d)
        today = fields.Date.context_today(self)
        delta = (d - today).days
        if delta == 0:
            return _('Today')
        if delta == 1:
            return _('Tomorrow')
        if delta == -1:
            return _('Yesterday')
        if 1 < delta <= 60:
            return _('In %s days') % delta
        if -60 <= delta < -1:
            return _('%s days ago') % (-delta)
        return self.fmt_date(d)

    @api.model
    def date_pack(self, d):
        """{raw, label, relative} — what every drawer/360 payload sends for a date."""
        if not d:
            return {'raw': '', 'label': '', 'relative': ''}
        raw = fields.Date.to_string(d) if not isinstance(d, datetime) \
            else fields.Datetime.to_string(d)
        label = self.fmt_datetime(d) if isinstance(d, datetime) else self.fmt_date(d)
        return {'raw': raw, 'label': label, 'relative': self.fmt_relative(d)}
