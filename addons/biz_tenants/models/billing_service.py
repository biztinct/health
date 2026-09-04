# -*- coding: utf-8 -*-
"""Measuring a customer, invoicing them, and pausing them.

THE SHAPE, AND IT IS THE SAME SHAPE AS EVERY PHASE BEFORE IT: the judgements
are next door in `billing_rules.py`, pure and tested. What is left here is the
three things that can only be done on a live box — read another system, render
a document, try to send something — plus the one thing only a person may do,
which is change where a customer stands.

⚠ EVERY HELPER IN THIS FILE IS NAMED `_billing_*` (ledger F52). `biz.tenants`
is ONE model assembled from seven files, so a helper added here is a helper
added to all of them; a `_mail_shell` written twice in one facade broke a button
two phases old on the platform this was ported from.

RAIL R1, AND IT IS SHARPER HERE THAN ANYWHERE ELSE IN THE PROGRAMME. Two jobs
run in this file:

  * `_cron_meter_snapshot` READS every customer once a month and writes the
    reading down on OUR system. It has never opened a customer's registry for a
    write and never will.
  * `_cron_billing` moves OUR invoices along and raises OUR alerts. The ONE
    thing it can do to a customer is pause them — and only if the owner has
    deliberately switched `biz_tenants.auto_suspend` on, which is OFF and stays
    off until somebody moves it. Locking a working system out at 08:30 on a
    Monday because a transfer was slow is not a thing software should do on its
    own.

NOBODY IS EVER INVOICED BY A SCHEDULED JOB. `billing_raise` is a button. The
preview comes first, it lists every customer, every number, every line and the
arithmetic in words, and nothing is written until the owner has read it.
"""
import base64
import json
import logging
import re
from datetime import timedelta

import odoo
from odoo import api, fields, models
from odoo.exceptions import UserError

from . import tenants_common as common
from .billing_rules import (
    DEFAULT_DUE_DAYS, DEFAULT_REMINDER_DAYS, DEFAULT_RETENTION_DAYS,
    DEFAULT_SUSPEND_AFTER_DAYS, DEFAULT_TRIAL_DAYS,
    SERVING_STATES, T_ACCESS, T_ACCESS_TEXT, T_NEXT_INVOICE, T_PLAN_LINE,
    T_PLAN_NAME, T_RECOVERY, T_SEAT_LIMIT, T_SEAT_MODEL, T_TRIAL_ENDS, T_USAGE,
    TRIAL_WARN_DAYS, access_payload, due_date_for, invoice_number,
    invoice_totals, money, month_closed, month_end, month_start, months_back,
    next_month, next_state, period_label, prev_month, price_for,
    qty_text, retention_verdict, state_transition, trial_phase, trial_sentence,
)

_logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r'^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$')

#: The settings this phase owns, with their defaults in CODE rather than in a
#: shipped record — a `noupdate="1"` record freezes whatever value a test run
#: left behind, because the next upgrade never corrects it.
#:
#: ⚠ `auto_suspend` IS THE OWNER'S RULING AND ITS DEFAULT IS OFF. It is written
#: here, once; the screen that offers it says in red what it would do.
BILLING_DEFAULTS = {
    'biz_tenants.auto_suspend': '0',
    'biz_tenants.invoice_prefix': 'INV',
    'biz_tenants.invoice_due_days': str(DEFAULT_DUE_DAYS),
    'biz_tenants.invoice_reminder_days': ','.join(str(d) for d in
                                                  DEFAULT_REMINDER_DAYS),
    'biz_tenants.suspend_after_days': str(DEFAULT_SUSPEND_AFTER_DAYS),
    'biz_tenants.retention_days': str(DEFAULT_RETENTION_DAYS),
    # ⚠ ALL FOUR BLANK, AND THE SCREEN SAYS SO IN RED. Inventing a company
    # address or a bank account would put a plausible untruth on a document
    # that goes to a paying customer. The owner fills these in once.
    'biz_tenants.billing_company': '',
    'biz_tenants.billing_address': '',
    'biz_tenants.billing_vat': '',
    'biz_tenants.bank_details': '',
    'biz_tenants.invoice_footer': '',
    # Which model a seat limit counts on the customer's own system. The product
    # decides; the generic default is the framework's account table.
    'biz_tenants.seat_model': 'res.users',
}

#: Anything that reads as "off".
_OFF = ('', '0', 'off', 'false', 'no', 'none')

#: The report that makes the document.
INVOICE_REPORT = 'biz_tenants.report_tenant_invoice'

#: How many months back the "Backfill" button reaches. Twelve is a year of
#: history, which is as far back as any invoice this platform will ever raise.
BACKFILL_MONTHS = 12


class BizTenantsBilling(models.AbstractModel):
    """The plans, the readings, the invoices and the standings."""
    _inherit = 'biz.tenants'

    # =====================================================================
    #  1. SETTINGS
    # =====================================================================
    def _billing_param(self, key, default=''):
        """A setting whose EMPTY value is meaningful, read off the row (F24).

        Every one of these settings has a meaningful blank: "the owner has not
        filled the bank details in" and "the owner deliberately cleared them"
        are the same to `get_param` and different to the person looking at an
        invoice that cannot be paid.
        """
        row = self.env['ir.config_parameter'].sudo().search(
            [('key', '=', key)], limit=1)
        if not row:
            return default
        return row.value if row.value is not None else default

    def _billing_commit(self):
        """Commit between customers — EXCEPT under a test run.

        ⚠ WHY THE COMMIT IS THERE AT ALL. These loops walk every customer on
        the machine, reading another database and rendering a document for
        each. Without a commit between them, a fault on the twelfth throws away
        the eleven invoices that were raised correctly — and on the meter, a
        month's readings for every customer.

        ⚠ AND WHY IT STANDS DOWN IN A TEST. The framework's test cursor refuses
        `commit()` outright ("this will lead to a broken cursor when trying to
        roll back"), so a method that commits is a method no test can call —
        which would leave the whole of this file unreachable from the suite.
        The guard is AT THE COMMIT rather than in each test, because the next
        caller will be written by somebody who has not read this comment (the
        same shape as the public page's writer, ledger F44).
        """
        if odoo.tools.config['test_enable']:
            return False
        self.env.cr.commit()
        return True

    def _billing_settings(self):
        """Every number and sentence the billing screens work from."""
        out = {}
        for key, fallback in BILLING_DEFAULTS.items():
            out[key.split('.', 1)[1]] = self._billing_param(key, fallback)
        return out

    def _billing_auto_suspend_on(self):
        raw = (self._billing_param('biz_tenants.auto_suspend', '0')
               or '').strip().lower()
        return raw not in _OFF

    def _billing_int(self, key, fallback):
        try:
            return max(0, int(self._billing_param(key, str(fallback))
                              or fallback))
        except (TypeError, ValueError):
            return int(fallback)

    def _billing_due_days(self):
        return self._billing_int('biz_tenants.invoice_due_days',
                                 DEFAULT_DUE_DAYS)

    def _billing_suspend_after(self):
        return self._billing_int('biz_tenants.suspend_after_days',
                                 DEFAULT_SUSPEND_AFTER_DAYS)

    def _billing_retention_days(self):
        return max(1, self._billing_int('biz_tenants.retention_days',
                                        DEFAULT_RETENTION_DAYS))

    def _billing_reminder_days(self):
        raw = self._billing_param('biz_tenants.invoice_reminder_days', '')
        days = []
        for part in re.split(r'[,;\s]+', raw or ''):
            try:
                days.append(int(part))
            except (TypeError, ValueError):
                continue
        return tuple(sorted(d for d in days if d > 0)) or DEFAULT_REMINDER_DAYS

    def _billing_seat_model(self):
        return (self._billing_param('biz_tenants.seat_model', 'res.users')
                or 'res.users').strip()

    def _billing_seller(self):
        """Who the invoice comes FROM. Blank where nobody has said."""
        brand = common.brand(self.env)
        return {
            'brand': brand,
            'name': (self._billing_param('biz_tenants.billing_company', '')
                     or brand or '').strip(),
            'address': (self._billing_param('biz_tenants.billing_address', '')
                        or '').strip(),
            'vat': (self._billing_param('biz_tenants.billing_vat', '')
                    or '').strip(),
            'bank': (self._billing_param('biz_tenants.bank_details', '')
                     or '').strip(),
            'footer': (self._billing_param('biz_tenants.invoice_footer', '')
                       or '').strip(),
        }

    def _billing_serving(self):
        """Every customer who still has a system. Paused ones included."""
        return self._tenants().search([('state', 'in', SERVING_STATES)])

    def _billing_ready_to_send(self):
        """`(ok, [what is missing])` — is an invoice fit to go out at all?"""
        seller = self._billing_seller()
        missing = []
        if not seller['name']:
            missing.append(self.env._("the company name it comes from"))
        if not seller['address']:
            missing.append(self.env._("a company address"))
        if not seller['vat']:
            missing.append(self.env._("a tax number"))
        if not seller['bank']:
            missing.append(self.env._("bank details to pay into"))
        return (not missing), missing

    # =====================================================================
    #  2. THE MONTHLY READING, KEPT AS HISTORY
    #
    #  READ-ONLY, ALWAYS (rail R1). The numbers come through H4a's guarded
    #  meter registry, each one guarding on its own table and column, and the
    #  rows land on OUR system and nowhere else.
    #
    #  ⚠ AND A MONTH THAT HAS A READING IS NEVER GIVEN A SECOND ONE. Billing
    #  bills from what was measured AT THE TIME; a re-run that overwrote last
    #  month would silently move the basis of an invoice already sent.
    # =====================================================================
    def _billing_month_from(self, month):
        """Whatever the browser sent, as the first of a month."""
        if not month:
            return prev_month(month_start(fields.Date.context_today(self)))
        if isinstance(month, str):
            try:
                parsed = fields.Date.to_date(month)
            except (ValueError, TypeError):
                raise UserError(self.env._('"%s" is not a month.', month))
            if not parsed:
                raise UserError(self.env._('"%s" is not a month.', month))
            return month_start(parsed)
        return month_start(month)

    def _billing_snapshot_one(self, tenant, month, today):
        """One customer, one month. Returns `{'written', 'kept', 'rows'}`."""
        Meter = self.env['biz.tenant.meter'].sudo()
        start = month.isoformat()
        end = month_end(month).isoformat()
        # ⚠ A READING TAKEN AFTER THE MONTH HAS ENDED IS TODAY'S NUMBER WEARING
        # AN OLD DATE, and the row says so. A count of people is a count NOW;
        # a count of things that happened between two dates is not.
        backfilled = month_end(month) < today
        data = self.read_meters(tenant.id, start, end)
        written, kept, rows = 0, 0, []
        if not data.get('measurable'):
            return {'written': 0, 'kept': 0, 'rows': [], 'reachable': False}
        for row in data['rows']:
            _rec, what = Meter.snapshot(tenant, row, month, backfilled)
            written += 1 if what == 'written' else 0
            kept += 1 if what == 'kept' else 0
            rows.append(dict(row, outcome=what))
        return {'written': written, 'kept': kept, 'rows': rows,
                'reachable': True, 'backfilled': backfilled}

    @api.model
    def meters_snapshot(self, month=None, tenant_id=None):
        """Take the month's reading now. Idempotent, and it SAYS it was.

        A re-run writes nothing and reports a no-op in those words, rather than
        succeeding silently in a way that looks the same as the first run.
        """
        self._require_platform_admin()
        month = self._billing_month_from(month)
        today = fields.Date.context_today(self)
        domain = ([('id', '=', int(tenant_id))] if tenant_id
                  else [('state', 'in', SERVING_STATES)])
        written, kept, missed = 0, 0, []
        for t in self._tenants().search(domain):
            res = self._billing_snapshot_one(t, month, today)
            if not res['reachable']:
                missed.append(t.name)
                continue
            written += res['written']
            kept += res['kept']
            self._billing_commit()
        return {
            'month': month.isoformat(), 'month_label': period_label(month),
            'written': written, 'kept': kept, 'missed': missed,
            'noop': written == 0 and kept > 0,
        }

    @api.model
    def meters_backfill(self, months=BACKFILL_MONTHS):
        """Fill in the months this platform has been running, and mark them.

        So the first invoice preview has something to show. Nothing already
        recorded is touched, and every row written here carries the flag that
        says it was taken after the fact.
        """
        self._require_platform_admin()
        today = fields.Date.context_today(self)
        this_month = month_start(today)
        out = []
        for month in months_back(prev_month(this_month), int(months or 1)):
            res = self.meters_snapshot(month.isoformat())
            out.append({'month': month.isoformat(),
                        'label': period_label(month),
                        'written': res['written'], 'kept': res['kept']})
        return {'months': out,
                'written': sum(r['written'] for r in out),
                'kept': sum(r['kept'] for r in out)}

    @api.model
    def _cron_meter_snapshot(self):
        """On the 1st: write down last month, and top up the one before it.

        READS a customer's system, WRITES only our own rows (rail R1). The
        month before last is only touched if it is MISSING — a platform whose
        meter started in the middle of September can still invoice August, and
        the row says it was taken late.
        """
        today = fields.Date.context_today(self)
        this_month = month_start(today)
        last = prev_month(this_month)
        done = {'last': None, 'before': None}
        for month, slot in ((last, 'last'), (prev_month(last), 'before')):
            try:
                written, kept = 0, 0
                for t in self._tenants().search(
                        [('state', 'in', SERVING_STATES)]):
                    res = self._billing_snapshot_one(t, month, today)
                    if res['reachable']:
                        written += res['written']
                        kept += res['kept']
                    self._billing_commit()
                done[slot] = {'month': month.isoformat(), 'written': written,
                              'kept': kept}
            except Exception:                                # noqa: BLE001
                _logger.exception("biz_tenants: the monthly reading for %s "
                                  "could not be taken", month)
        _logger.info("biz_tenants: monthly readings %s", done)
        return done

    # =====================================================================
    #  3. THE INVOICE PREVIEW — THE HERO, AND IT WRITES NOTHING
    # =====================================================================
    def _billing_currency(self, plan):
        return plan.currency_id or self.env.company.currency_id

    def _billing_plan_dict(self, plan, cur):
        data = plan.as_dict()
        data.update({'rounding': cur.rounding or 0.01,
                     'symbol': cur.symbol or '',
                     'position': cur.position or 'after'})
        return data

    def _billing_preview_row(self, tenant, month, today):
        """One customer's invoice, worked out and NOT written down.

        Every customer appears, including every customer who would be skipped —
        and a skipped customer says why in a sentence somebody can act on. A
        preview that silently drops a row is a preview that hides the very
        customer somebody is looking for.
        """
        Meter = self.env['biz.tenant.meter'].sudo()
        Invoice = self.env['biz.tenant.invoice'].sudo()
        row = {
            'tenant_id': tenant.id, 'tenant': tenant.name, 'slug': tenant.slug,
            'state': tenant.state,
            'plan': tenant.plan_id.name or '', 'plan_id': tenant.plan_id.id or 0,
            'plan_headline': tenant.plan_id.headline() if tenant.plan_id else '',
            'readings': [], 'lines': [], 'explain': '',
            'subtotal': 0.0, 'subtotal_h': '', 'vat_rate': 0.0,
            'vat_amount': 0.0, 'vat_h': '', 'total': 0.0, 'total_h': '',
            'currency': '', 'skip': '', 'problem': '', 'existing': '',
            'placeholder': bool(tenant.plan_id and tenant.plan_id.is_placeholder),
        }
        values, unavailable = Meter.readings_for(tenant, month)
        # THE MEASURED NUMBERS ARE SHOWN WHETHER OR NOT THEY BILL, because the
        # question the screen answers first is "what did the platform actually
        # measure", and the answer to that does not depend on a plan.
        for spec in common.meters():
            key = spec['key']
            row['readings'].append({
                'key': key, 'label': spec.get('label') or key,
                'unit': spec.get('unit') or '',
                'value': values.get(key),
                'known': key in values,
                'available': key not in unavailable,
                'charged': bool(tenant.plan_id
                                and tenant.plan_id.meter_key == key),
            })
        existing = Invoice.search([('tenant_id', '=', tenant.id),
                                   ('period_start', '=', month),
                                   ('state', '!=', 'cancelled')], limit=1)
        if existing:
            row['existing'] = existing.number
            row['skip'] = self.env._("Already invoiced as %s.", existing.number)
            return row
        if not tenant.plan_id:
            row['skip'] = self.env._(
                "No plan yet — pick one on their Plan tab and this month will "
                "price itself.")
            return row
        if tenant.state == 'trial':
            row['skip'] = self.env._(
                "On trial until %s — nothing to charge yet.",
                tenant.trial_ends_on.isoformat() if tenant.trial_ends_on
                else '—')
            return row
        if not values:
            # ⚠ NOUGHT AND "NOBODY LOOKED" ARE DIFFERENT ANSWERS, and this is
            # the sentence that keeps them apart. Pricing a month with no
            # reading as zero would quietly invoice nothing and look identical
            # to a genuinely quiet month.
            row['skip'] = self.env._(
                "No reading was taken for %s, so there is nothing to price "
                "this on. Press “Take the reading” first — it is not the same "
                "as a quiet month.", period_label(month))
            return row
        cur = self._billing_currency(tenant.plan_id)
        plan = self._billing_plan_dict(tenant.plan_id, cur)
        row['currency'] = cur.name or ''
        priced = price_for(plan, values, unavailable)
        if priced['problem']:
            row['problem'] = priced['problem']
            row['skip'] = priced['problem']
            return row
        if priced['nothing_to_bill']:
            row['skip'] = self.env._(
                "Nothing to charge for %(month)s — %(why)s.",
                month=period_label(month), why=priced['explain'] or
                self.env._("the number this plan charges on was nought"))
            return row
        totals = invoice_totals(priced['lines'], plan['vat_rate'],
                                cur.rounding or 0.01)
        fmt = lambda v: money(v, cur.symbol or '', cur.rounding or 0.01,   # noqa: E731
                              cur.position or 'after')
        row.update({
            'lines': [dict(l, amount_h=fmt(l['amount']),
                           unit_h=fmt(l['unit_price']),
                           qty_h=qty_text(l['qty']))
                      for l in priced['lines']],
            'explain': priced['explain'],
            'subtotal': totals['subtotal'], 'subtotal_h': fmt(totals['subtotal']),
            'vat_rate': totals['vat_rate'], 'vat_amount': totals['vat_amount'],
            'vat_h': fmt(totals['vat_amount']),
            'total': totals['total'], 'total_h': fmt(totals['total']),
        })
        return row

    @api.model
    def billing_preview(self, month=None):
        """Every invoice this month would raise, before any of them exists.

        ⚠ NOTHING IS WRITTEN HERE. Not a row, not a number, not a log line —
        the whole point of the screen is that the owner can look at what a
        month would cost every customer, change a plan, and look again, with
        nothing having happened.
        """
        self._require_platform_admin()
        month = self._billing_month_from(month)
        today = fields.Date.context_today(self)
        rows = [self._billing_preview_row(t, month, today)
                for t in self._billing_serving()]
        billable = [r for r in rows if not r['skip']]
        # ⚠ THE TOTAL IS FORMATTED HERE, BY THE ONE MONEY FORMATTER. A figure
        # that reaches a screen as "2000000" is a number nobody can read at a
        # glance and nobody can check against an invoice.
        by_currency, by_symbol = {}, {}
        for r in billable:
            by_currency.setdefault(r['currency'], 0.0)
            by_currency[r['currency']] += r['total']
            plan = self._tenants().browse(r['tenant_id']).plan_id
            cur = self._billing_currency(plan)
            by_symbol[r['currency']] = (cur.symbol or '', cur.rounding or 0.01,
                                        cur.position or 'after')
        ok, missing = self._billing_ready_to_send()
        return {
            'month': month.isoformat(),
            'month_label': period_label(month),
            'closed': month_closed(month, today),
            'rows': rows,
            'billable': len(billable),
            'skipped': len(rows) - len(billable),
            'totals': [{'currency': c, 'amount': a,
                        'amount_h': money(a, *by_symbol.get(c, ('', 0.01,
                                                                'after')))}
                       for c, a in sorted(by_currency.items())],
            'ready': ok, 'missing': missing,
            # ⚠ THE STRIP STARTS AT THE MONTH WE ARE IN, NOT AT THE LAST ONE
            # THAT FINISHED. Raising a month early is allowed and deliberate
            # (the button says so in those words) — and a strip that could not
            # offer the current month made it unreachable from the screen while
            # the method underneath happily accepted it. Found in a browser.
            'months': [{'month': m.isoformat(), 'label': period_label(m),
                        'closed': month_closed(m, today)}
                       for m in months_back(month_start(today),
                                            BACKFILL_MONTHS + 1)],
        }

    # =====================================================================
    #  4. RAISING THEM — A PERSON PRESSES THIS
    # =====================================================================
    def _billing_next_number(self, year):
        """The next number in this year, never reused, and with no gaps.

        Read off the invoices that exist rather than off a sequence record: a
        sequence bumped inside a transaction that is then rolled back leaves a
        gap, and a gap in an invoice book is a question from an auditor with no
        good answer.
        """
        prefix = (self._billing_param('biz_tenants.invoice_prefix', 'INV')
                  or 'INV').strip() or 'INV'
        Invoice = self.env['biz.tenant.invoice'].sudo()
        stem = invoice_number(prefix, year, 0)[:-4]
        highest = 0
        for inv in Invoice.search([('number', 'like', stem + '%')]):
            tail = (inv.number or '')[len(stem):]
            if tail.isdigit():
                highest = max(highest, int(tail))
        return invoice_number(prefix, year, highest + 1)

    @api.model
    def billing_raise(self, month=None, early=False, tenant_ids=None):
        """Create the invoices the preview just showed."""
        self._require_platform_admin()
        month = self._billing_month_from(month)
        today = fields.Date.context_today(self)
        if not month_closed(month, today) and not early:
            raise UserError(self.env._(
                "%s is not over yet, so the numbers would be incomplete. Raise "
                "it early on purpose if that is what you want — the button "
                "says so.", period_label(month)))
        wanted = set(int(i) for i in (tenant_ids or [])) or None
        made, skipped = [], []
        for tenant in self._billing_serving():
            if wanted is not None and tenant.id not in wanted:
                continue
            row = self._billing_preview_row(tenant, month, today)
            if row['skip']:
                skipped.append({'tenant': tenant.name, 'why': row['skip']})
                continue
            invoice = self._billing_create_invoice(tenant, month, row, today)
            made.append({'tenant': tenant.name, 'number': invoice.number,
                         'total_h': row['total_h'], 'pdf': bool(invoice.pdf)})
            self._billing_commit()
        return {'created': made, 'skipped': skipped,
                'month_label': period_label(month),
                'data': self.billing_data(month.isoformat())}

    def _billing_create_invoice(self, tenant, month, row, today):
        plan = tenant.plan_id
        cur = self._billing_currency(plan)
        invoice = self.env['biz.tenant.invoice'].sudo().create({
            'tenant_id': tenant.id,
            'number': self._billing_next_number(today.year),
            'period_start': month,
            'period_end': month_end(month),
            'plan_id': plan.id,
            'plan_name': plan.name,
            'plan_kind': plan.price_kind,
            'explain': row['explain'][:512],
            'currency_id': cur.id,
            'subtotal': row['subtotal'], 'vat_rate': row.get('vat_rate') or 0.0,
            'vat_amount': row['vat_amount'], 'total': row['total'],
            'state': 'issued',
            'issued_on': today,
            'due_on': due_date_for(today, self._billing_due_days()),
            'line_ids': [(0, 0, {
                'sequence': (i + 1) * 10, 'label': l['label'],
                'detail': l.get('detail') or '',
                'meter_key': plan.meter_key or '',
                'measured': int((l.get('qty') or 0) + (plan.included or 0)),
                'qty': l['qty'], 'unit_price': l['unit_price'],
                'amount': l['amount'],
            }) for i, l in enumerate(row['lines'])],
        })
        self._billing_attach_pdf(invoice)
        tenant.log('Invoice %s raised for %s — %s.'
                   % (invoice.number, period_label(month), row['total_h']))
        self._billing_push_standing(tenant)
        return invoice

    def _billing_attach_pdf(self, invoice):
        """Render the document once and keep the bytes.

        A document re-rendered on demand is a document that changes after it
        was sent — the plan gets repriced, the company details get corrected,
        and the copy the customer downloads no longer matches the one they
        already have. So it is made here, at issue, and stored.
        """
        try:
            pdf, _fmt = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                INVOICE_REPORT, res_ids=[invoice.id])
        except Exception:                                    # noqa: BLE001
            _logger.exception("biz_tenants: could not render invoice %s",
                              invoice.number)
            return False
        invoice.sudo().write({
            'pdf': base64.b64encode(pdf),
            'pdf_name': '%s.pdf' % invoice.number,
        })
        return True

    def _billing_invoice(self, invoice_id):
        invoice = self.env['biz.tenant.invoice'].sudo().browse(
            int(invoice_id or 0)).exists()
        if not invoice:
            raise UserError(self.env._("There is no such invoice."))
        return invoice

    @api.model
    def invoice_pdf(self, invoice_id):
        """The stored document, for the download button.

        Renders one if it is missing rather than leaving the owner with a dead
        button — and says what to do if the renderer itself is not there.
        """
        self._require_platform_admin()
        invoice = self._billing_invoice(invoice_id)
        if not invoice.pdf:
            self._billing_attach_pdf(invoice)
        if not invoice.pdf:
            raise UserError(self.env._(
                "The document could not be made. The printer this machine "
                "renders documents with does not seem to be installed — that "
                "is a server change, not something on this screen."))
        return {'name': invoice.pdf_name or ('%s.pdf' % invoice.number),
                'data': invoice.pdf.decode() if isinstance(invoice.pdf, bytes)
                        else invoice.pdf}

    @api.model
    def invoice_mark_paid(self, invoice_id, reference='', paid_via='',
                          paid_on=''):
        self._require_platform_admin()
        invoice = self._billing_invoice(invoice_id)
        if invoice.state == 'cancelled':
            raise UserError(self.env._("That invoice was cancelled."))
        when = fields.Date.context_today(self)
        if paid_on:
            try:
                when = fields.Date.to_date(paid_on) or when
            except (ValueError, TypeError):
                pass
        invoice.write({'state': 'paid', 'paid_on': when,
                       'payment_reference': (reference or '')[:120],
                       'paid_via': (paid_via or '')[:60]})
        self._billing_clear_alert('invoice_overdue:%s' % invoice.number,
                                  self.env._("The invoice was paid."))
        self._billing_clear_alert('suspend_candidate:%s' % invoice.number,
                                  self.env._("The invoice was paid."))
        invoice.tenant_id.log('Invoice %s marked paid%s.'
                              % (invoice.number,
                                 (' — %s' % reference) if reference else ''))
        self._billing_push_standing(invoice.tenant_id)
        return {'ok': True, 'data': self.billing_data(
            invoice.period_start.isoformat())}

    @api.model
    def invoice_cancel(self, invoice_id, reason=''):
        self._require_platform_admin()
        invoice = self._billing_invoice(invoice_id)
        if invoice.state == 'paid':
            raise UserError(self.env._(
                "That invoice is already paid. Cancelling it would leave the "
                "money with nothing against it — mark it unpaid first if that "
                "is really what happened."))
        if not (reason or '').strip():
            raise UserError(self.env._(
                "Say why it is being cancelled — it stays on the record, and "
                "it is the only thing that will explain the gap later."))
        invoice.write({'state': 'cancelled',
                       'cancel_reason': reason.strip()[:200]})
        self._billing_clear_alert('invoice_overdue:%s' % invoice.number,
                                  self.env._("The invoice was cancelled."))
        invoice.tenant_id.log('Invoice %s cancelled: %s'
                              % (invoice.number, reason.strip()))
        self._billing_push_standing(invoice.tenant_id)
        return {'ok': True, 'data': self.billing_data(
            invoice.period_start.isoformat())}

    @api.model
    def invoice_send(self, invoice_id):
        """Try to send it — and say honestly that nothing left.

        ⚠ THE BUTTON EXISTS AND IT IS DARK, WHICH IS THE POINT (ledger F40/F42).
        A platform with no mail account that HIDES the send button is a platform
        whose owner discovers the channel is missing on the day it matters. It
        is here, it is pressed, it says exactly why nothing went, and it offers
        the download instead. `spoken_at` stays empty, because nothing was said.
        """
        self._require_platform_admin()
        invoice = self._billing_invoice(invoice_id)
        to = self._billing_invoice_to(invoice.tenant_id)
        subject = self.env._("Invoice %(n)s — %(p)s", n=invoice.number,
                             p=period_label(invoice.period_start))
        body = self.env._(
            "Invoice %(n)s for %(p)s, %(t)s, due %(d)s.",
            n=invoice.number, p=period_label(invoice.period_start),
            t=invoice.money(invoice.total),
            d=invoice.due_on.isoformat() if invoice.due_on else '—')
        state, why = self._send_alert_mail(subject, body, [to] if to else [])
        if state == 'sent':
            invoice.write({'spoken_at': fields.Datetime.now()})
            invoice.tenant_id.log('Invoice %s emailed to %s.'
                                  % (invoice.number, to))
            return {'ok': True, 'sent': True, 'to': to,
                    'message': self.env._("Sent to %s.", to)}
        return {
            'ok': False, 'sent': False, 'to': to, 'reason': why,
            'message': self.env._(
                "Nothing was sent. %(why)s Download the document and send it "
                "yourself — the button is beside this one.", why=why),
        }

    def _billing_invoice_to(self, tenant):
        for candidate in (tenant.billing_email, tenant.contact_email):
            value = (candidate or '').strip()
            if value and EMAIL_RE.match(value):
                return value
        return ''

    def _billing_customer_identity(self, tenant):
        """Who this invoice is addressed to, read off THEIR system.

        READ-ONLY SQL on the customer's own system (rail R1): the details a
        customer corrects on their own company page are the details that must
        print on the invoice, and copying them onto our record would mean
        printing whatever they were on the day they were created.

        A system that cannot be read falls back to what the platform knows,
        rather than printing a blank block. An invoice with no addressee is not
        a document.
        """
        fallback = {'name': tenant.name or '', 'address': '', 'vat': '',
                    'email': self._billing_invoice_to(tenant)}
        if not tenant.slug or not self._db_exists(tenant.slug):
            return fallback
        try:
            with self._pg_cursor(tenant.slug) as cr:
                cr.execute("""
                    SELECT p.name, p.street, p.street2, p.city, p.zip,
                           p.vat, p.email
                      FROM res_company c
                      JOIN res_partner p ON p.id = c.partner_id
                  ORDER BY c.id LIMIT 1""")
                row = cr.fetchone()
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: could not read %s's own company "
                            "details for an invoice", tenant.slug)
            return fallback
        if not row:
            return fallback
        name, street, street2, city, zipcode, vat, email = row
        parts = [p for p in (street, street2,
                             ' '.join(x for x in (zipcode, city) if x)) if p]
        return {
            'name': name or fallback['name'],
            'address': '\n'.join(parts),
            'vat': vat or '',
            'email': email or fallback['email'],
        }

    # =====================================================================
    #  5. WHERE A CUSTOMER STANDS — EVERY MOVE IS A PERSON PRESSING SOMETHING
    # =====================================================================
    def _billing_tenant(self, tenant_id):
        tenant = self._tenants().browse(int(tenant_id or 0)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not on the list."))
        return tenant

    def _billing_move_state(self, tenant, to, extra=None):
        ok, why = state_transition(tenant.state, to)
        if not ok:
            raise UserError(why)
        was = tenant.state
        tenant.write(dict(extra or {}, state=to))
        tenant.log('Standing changed from "%s" to "%s".'
                   % (was.replace('_', ' '), to.replace('_', ' ')))
        return was

    def _billing_standing_values(self, tenant):
        plan = tenant.plan_id
        payload = access_payload(
            tenant.state, tenant.paused_reason or '',
            tenant.trial_ends_on if tenant.state == 'trial' else None,
            plan.name or '', plan.headline() if plan else '',
            plan.seat_limit or 0, common.brand(self.env))
        # ⚠ THE SAME ANSWER THE SUPPORT DOOR USES, NOT THE SETTING ALONE.
        # `biz_tenants.recovery_login` is UNSET on this platform — provisioning
        # creates the account and nobody ever wrote the name down — so reading
        # the setting here pushed an EMPTY recovery login onto every customer,
        # and the paused door's way back in did not exist. Found by looking at
        # what had actually been written onto a live customer's system rather
        # than at what the code intended to write. `_support_recovery_uid`
        # already resolves it properly (setting first, then the one active
        # passwordless account a blank system ships with) and says which one it
        # used; asking it is the only way the two doors cannot disagree.
        try:
            _uid, recovery = self._support_recovery_uid(tenant.slug)
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: could not work out %s's way back in; "
                            "the paused door will fall back to the platform "
                            "administrator alone.", tenant.slug, exc_info=True)
            recovery = common.param(self.env, common.P_RECOVERY_LOGIN) or ''
        return {
            T_ACCESS: payload['access'],
            T_ACCESS_TEXT: payload['access_text'],
            T_TRIAL_ENDS: payload['trial_ends'],
            T_PLAN_NAME: payload['plan_name'],
            T_PLAN_LINE: payload['plan_line'],
            T_SEAT_LIMIT: payload['seat_limit'],
            T_SEAT_MODEL: self._billing_seat_model(),
            T_RECOVERY: recovery,
            T_USAGE: self._billing_usage_payload(tenant),
            T_NEXT_INVOICE: self._billing_next_invoice_payload(tenant),
        }

    def _billing_usage_payload(self, tenant):
        """The numbers for the customer's own "Plan & usage" card, as JSON.

        Sent to THEM rather than counted by them: the platform is the thing
        that measures, and a second count on their side would answer a
        different question five minutes later.
        """
        month = month_start(fields.Date.context_today(self))
        Meter = self.env['biz.tenant.meter'].sudo()
        values, unavailable = Meter.readings_for(tenant, month)
        if not values:
            values, unavailable = Meter.readings_for(
                tenant, prev_month(month))
            month = prev_month(month)
        rows = []
        for spec in common.meters():
            key = spec['key']
            if key not in values:
                continue
            rows.append({'key': key, 'label': spec.get('label') or key,
                         'unit': spec.get('unit') or '',
                         'value': values[key],
                         'available': key not in unavailable,
                         'charged': bool(tenant.plan_id
                                         and tenant.plan_id.meter_key == key)})
        return json.dumps({'month': month.isoformat(),
                           'month_label': period_label(month), 'rows': rows})

    def _billing_next_invoice_payload(self, tenant):
        """When their next invoice is expected, in one plain sentence."""
        if tenant.state == 'trial' and tenant.trial_ends_on:
            return self.env._(
                "Nothing is charged while your trial is running.")
        if not tenant.plan_id:
            return ''
        today = fields.Date.context_today(self)
        due = next_month(month_start(today))
        return self.env._(
            "The next invoice covers %(month)s and is expected in early "
            "%(when)s.", month=period_label(month_start(today)),
            when=period_label(due))

    def _billing_push_standing(self, tenant, why=''):
        """Tell one customer's system where they stand. NEVER RAISES.

        A system that cannot be reached leaves the platform's own record
        correct and the customer's out of step, which is a row on the screen
        and a retry — not a failed button.
        """
        try:
            res = self.push_settings(tenant.id,
                                     self._billing_standing_values(tenant))
        except UserError as e:
            return {'ok': False, 'reason': str(e)}
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: could not tell %s where they stand",
                            tenant.slug, exc_info=True)
            return {'ok': False, 'reason': self.env._(
                "Their system could not be reached just now. Their own screen "
                "will catch up the next time this is pushed.")}
        if res.get('ok'):
            tenant.sudo().write({'standing_pushed_at': fields.Datetime.now()})
            if why:
                tenant.log(why)
        return res

    @api.model
    def tenant_set_plan(self, tenant_id, plan_id, start_trial=False):
        """Put a customer on a plan, and tell their system about it."""
        self._require_platform_admin()
        tenant = self._billing_tenant(tenant_id)
        plan = self.env['biz.plan'].sudo().browse(int(plan_id or 0)).exists()
        if not plan:
            raise UserError(self.env._("Pick a plan first."))
        vals = {'plan_id': plan.id}
        if start_trial:
            if tenant.state != 'trial':
                ok, why = state_transition(tenant.state, 'trial')
                if not ok:
                    raise UserError(why)
                vals['state'] = 'trial'
            vals['trial_ends_on'] = fields.Date.context_today(self) + timedelta(
                days=plan.trial_days or DEFAULT_TRIAL_DAYS)
            vals['trial_told'] = ''
        tenant.write(vals)
        tenant.log('Moved onto the "%s" plan.%s'
                   % (plan.name,
                      (' Trial runs to %s.' % vals['trial_ends_on'].isoformat())
                      if start_trial else ''))
        push = self._billing_push_standing(tenant)
        return {'ok': True, 'push': push,
                'data': self.tenant_billing(tenant.id)}

    @api.model
    def tenant_convert(self, tenant_id):
        """From a trial to a paying customer."""
        self._require_platform_admin()
        tenant = self._billing_tenant(tenant_id)
        self._billing_move_state(tenant, 'live',
                                 {'trial_ends_on': False, 'trial_told': ''})
        self._billing_clear_alert('trial_ending:%s' % tenant.slug,
                                  self.env._("They are a paying customer now."))
        self._billing_push_standing(tenant, self.env._(
            "The trial ended and they are now a paying customer."))
        return {'ok': True, 'data': self.tenant_billing(tenant.id)}

    @api.model
    def tenant_pause(self, tenant_id, reason='', confirm_slug=''):
        """Shut the door. THEIR DATA IS UNTOUCHED."""
        self._require_platform_admin()
        tenant = self._billing_tenant(tenant_id)
        if (confirm_slug or '').strip() != tenant.slug:
            raise UserError(self.env._(
                "Type %s to confirm. Pausing shuts every one of their people "
                "out until somebody lets them back in. Nothing is deleted.",
                tenant.slug))
        if not (reason or '').strip():
            raise UserError(self.env._(
                "Say why. It is the sentence their own people will read on the "
                "page they meet, so write it for them."))
        return self._billing_do_pause(tenant, reason.strip())

    def _billing_do_pause(self, tenant, reason):
        self._billing_move_state(tenant, 'paused', {
            'paused_at': fields.Datetime.now(),
            'paused_reason': (reason or '')[:200],
        })
        push = self._billing_push_standing(
            tenant, self.env._("Access paused: %s", reason))
        self._billing_raise_alert(
            'tenant_paused:%s' % tenant.slug, 'tenant_paused', 'warning',
            self.env._("%s is paused", tenant.name),
            self.env._(
                "%(name)s's people cannot sign in. The reason on their screen "
                "is: “%(why)s”. Let them back in from their Plan tab the "
                "moment it is settled — it takes effect within a minute.",
                name=tenant.name, why=reason), tenant)
        return {'ok': True, 'push': push,
                'data': self.tenant_billing(tenant.id)}

    @api.model
    def tenant_resume(self, tenant_id):
        """Let them back in. ONE PRESS, NO TYPING — undoing harm is never made
        harder than doing it."""
        self._require_platform_admin()
        tenant = self._billing_tenant(tenant_id)
        today = fields.Date.context_today(self)
        back = ('trial' if (tenant.trial_ends_on and tenant.trial_ends_on >= today)
                else 'live')
        self._billing_move_state(tenant, back, {'paused_at': False,
                                                'paused_reason': False})
        push = self._billing_push_standing(tenant,
                                           self.env._("Access restored."))
        self._billing_clear_alert('tenant_paused:%s' % tenant.slug,
                                  self.env._("They were let back in."))
        return {'ok': True, 'push': push,
                'data': self.tenant_billing(tenant.id)}

    @api.model
    def tenant_schedule_deletion(self, tenant_id, days=None, reason='',
                                 confirm_slug=''):
        """Set the day their data MAY be removed — and take a copy now.

        ⚠ NOTHING DELETES ANYTHING. The date is a promise to the customer and a
        reminder to the owner; the removal itself is still the closing-down
        button with its own typed confirmation. A clock that erases somebody's
        records on its own is not a feature.
        """
        self._require_platform_admin()
        tenant = self._billing_tenant(tenant_id)
        if (confirm_slug or '').strip() != tenant.slug:
            raise UserError(self.env._("Type %s to confirm.", tenant.slug))
        try:
            days = max(1, int(days or self._billing_retention_days()))
        except (TypeError, ValueError):
            days = self._billing_retention_days()
        copy_note = ''
        try:
            self._take_backup(tenant, 'final')
            copy_note = self.env._("A copy was taken first.")
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: the copy before scheduling %s for "
                            "removal failed", tenant.slug, exc_info=True)
            copy_note = self.env._(
                "The copy did NOT succeed — take one by hand before anything "
                "is removed.")
        self._billing_move_state(tenant, 'pending_deletion', {
            'delete_after': fields.Date.context_today(self) + timedelta(days=days),
            'deletion_reason': (reason or '')[:200],
        })
        tenant.log('Scheduled for closing down after %s. %s'
                   % (tenant.delete_after.isoformat(), copy_note))
        return {'ok': True, 'copy': copy_note,
                'data': self.tenant_billing(tenant.id)}

    @api.model
    def tenant_cancel_deletion(self, tenant_id):
        self._require_platform_admin()
        tenant = self._billing_tenant(tenant_id)
        self._billing_move_state(tenant, 'live', {'delete_after': False,
                                                  'deletion_reason': False})
        self._billing_push_standing(tenant,
                                    self.env._("Closing down called off."))
        return {'ok': True, 'data': self.tenant_billing(tenant.id)}

    # =====================================================================
    #  6. ALERTS — RAISED BY THIS FILE, CLOSED BY THIS FILE
    # =====================================================================
    def _billing_raise_alert(self, key, kind, severity, subject, text,
                             tenant=None):
        """Raise or refresh one billing alert.

        ⚠ EVERY KIND THIS FILE RAISES IS ON `SELF_MANAGED_KINDS` (ledger F67).
        The fifteen-minute sweep takes no reading that could see an unpaid
        invoice or a trial running out, so if it were allowed to reconcile
        these it would close every one of them on its very next run — minutes
        after the morning job raised them.
        """
        Alert = self.env['biz.alert'].sudo()
        now = fields.Datetime.now()
        row = Alert.search([('key', '=', key),
                            ('state', 'in', ('open', 'acknowledged'))], limit=1)
        if row:
            row.write({'last_seen': now, 'count': row.count + 1,
                       'severity': severity, 'subject': subject,
                       'body_text': text})
            return row
        return Alert.create({
            'key': key, 'kind': kind, 'severity': severity, 'subject': subject,
            'body_text': text, 'tenant_id': tenant.id if tenant else False,
            'first_seen': now, 'last_seen': now, 'count': 1, 'state': 'open',
        })

    def _billing_clear_alert(self, key, why):
        rows = self.env['biz.alert'].sudo().search(
            [('key', '=', key), ('state', 'in', ('open', 'acknowledged'))])
        if rows:
            rows.write({'state': 'resolved',
                        'resolved_at': fields.Datetime.now(),
                        'resolution': why})
        return len(rows)

    # =====================================================================
    #  7. THE DAILY JOB
    # =====================================================================
    @api.model
    def _cron_billing(self):
        """Once a morning: chase what is owed, and count the trials down.

        THE ONE THING IT CAN DO TO A CUSTOMER is pause them, and only when the
        owner has switched that on. Everything else it does is raise a flag on
        our own screen.
        """
        today = fields.Date.context_today(self)
        res = {'overdue': 0, 'reminders': 0, 'candidates': 0, 'paused': 0,
               'trials': 0, 'retention': 0}
        for step in (self._billing_chase, self._billing_trial_watch,
                     self._billing_retention_watch):
            try:
                res.update(step(today))
            except Exception:                                # noqa: BLE001
                _logger.exception("biz_tenants: %s failed", step.__name__)
        self._billing_commit()
        return res

    def _billing_chase(self, today):
        Invoice = self.env['biz.tenant.invoice'].sudo()
        reminders = self._billing_reminder_days()
        suspend_after = self._billing_suspend_after()
        auto = self._billing_auto_suspend_on()
        counts = {'overdue': 0, 'reminders': 0, 'candidates': 0, 'paused': 0}
        for inv in Invoice.search([('state', '=', 'issued')]):
            verdict = next_state(
                {'state': inv.state, 'due_on': inv.due_on,
                 'reminder_count': inv.reminder_count},
                today, reminders, suspend_after)
            if not verdict['days_overdue']:
                continue
            counts['overdue'] += 1
            self._billing_raise_alert(
                'invoice_overdue:%s' % inv.number, 'invoice_overdue', 'warning',
                self.env._("%(who)s has not paid %(n)s",
                           who=inv.tenant_id.name, n=inv.number),
                self.env._(
                    "%(n)s for %(p)s (%(t)s) was due on %(d)s — %(days)s days "
                    "ago. Mark it paid on their Plan tab when the transfer "
                    "arrives, or cancel it with a reason.",
                    n=inv.number, p=period_label(inv.period_start),
                    t=inv.money(inv.total),
                    d=inv.due_on.isoformat() if inv.due_on else '—',
                    days=verdict['days_overdue']), inv.tenant_id)
            if verdict['remind']:
                self._billing_remind(inv, verdict, today)
                counts['reminders'] += 1
            if verdict['suspend_candidate']:
                counts['candidates'] += 1
                self._billing_suspend_candidate(inv, verdict, auto)
                if auto:
                    counts['paused'] += 1
            self._billing_commit()
        return counts

    def _billing_remind(self, invoice, verdict, today):
        """One reminder, counted rather than timed.

        ⚠ THE COUNT GOES UP WHETHER OR NOT ANYTHING LEFT THE MACHINE, and
        `spoken_at` only moves if something did (ledger F40). Those two facts
        are different and both of them matter: the count stops the same
        reminder being raised on every run, and the empty stamp is the honest
        record that nobody has actually been told.
        """
        to = self._billing_invoice_to(invoice.tenant_id)
        subject = self.env._("Reminder: invoice %(n)s is overdue",
                             n=invoice.number)
        body = self.env._(
            "Invoice %(n)s for %(p)s, %(t)s, was due on %(d)s.",
            n=invoice.number, p=period_label(invoice.period_start),
            t=invoice.money(invoice.total),
            d=invoice.due_on.isoformat() if invoice.due_on else '—')
        state, why = self._send_alert_mail(subject, body, [to] if to else [])
        vals = {'reminder_count': verdict['reminder_no'],
                'last_reminder_on': today}
        if state == 'sent':
            vals['spoken_at'] = fields.Datetime.now()
        invoice.write(vals)
        invoice.tenant_id.log(
            'Reminder %d for invoice %s: %s'
            % (verdict['reminder_no'], invoice.number,
               'sent to %s' % to if state == 'sent' else 'not sent — %s' % why))
        return state

    def _billing_suspend_candidate(self, invoice, verdict, auto):
        tenant = invoice.tenant_id
        self._billing_raise_alert(
            'suspend_candidate:%s' % invoice.number, 'suspend_candidate',
            'critical',
            self.env._("%(who)s is %(days)s days overdue", who=tenant.name,
                       days=verdict['days_overdue']),
            self.env._(
                "Invoice %(n)s (%(t)s) is %(days)s days past its date. "
                "Pausing is NOT automatic on this platform — nothing has "
                "happened to %(who)s. If you want to shut their door, the "
                "button is on their Plan tab and it asks you to type their "
                "short name first.",
                n=invoice.number, t=invoice.money(invoice.total),
                days=verdict['days_overdue'], who=tenant.name), tenant)
        if not auto:
            return False
        if tenant.state not in ('live', 'trial'):
            return False
        _logger.warning("biz_tenants: pausing %s automatically — the "
                        "auto-pause switch is ON and %s is %d days overdue",
                        tenant.slug, invoice.number, verdict['days_overdue'])
        self._billing_do_pause(tenant, self.env._(
            "An invoice has not been settled."))
        return True

    def _billing_trial_watch(self, today):
        """Count the trials down. ⚠ A TRIAL RUNNING OUT PAUSES NOTHING."""
        counts = {'trials': 0}
        warn = TRIAL_WARN_DAYS
        for tenant in self._tenants().search([('state', '=', 'trial')]):
            if not tenant.trial_ends_on:
                continue
            phase = trial_phase(tenant.trial_ends_on, today, warn)
            if phase['phase'] not in ('ending', 'ended'):
                continue
            counts['trials'] += 1
            if tenant.trial_told == phase['phase']:
                # Said once, not once a night.
                continue
            tenant.write({'trial_told': phase['phase']})
            severity = 'warning' if phase['phase'] == 'ended' else 'info'
            self._billing_raise_alert(
                'trial_ending:%s' % tenant.slug, 'trial_ending', severity,
                (self.env._("%s's trial has ended", tenant.name)
                 if phase['phase'] == 'ended'
                 else self.env._("%(who)s's trial ends in %(days)s days",
                                 who=tenant.name, days=phase['days_left'])),
                self.env._(
                    "Their trial %(when)s. NOTHING HAS HAPPENED TO THEIR "
                    "SYSTEM — a trial running out does not lock anybody out on "
                    "this platform. Press “They are paying now” on their Plan "
                    "tab to move them across, or extend the date.",
                    when=(self.env._("ended on %s",
                                     tenant.trial_ends_on.isoformat())
                          if phase['phase'] == 'ended'
                          else self.env._("ends on %s",
                                          tenant.trial_ends_on.isoformat()))),
                tenant)
            self._billing_commit()
        return counts

    def _billing_retention_watch(self, today):
        """A customer whose retention clock has run out. ⚠ NOTHING IS REMOVED."""
        counts = {'retention': 0}
        for tenant in self._tenants().search(
                [('state', '=', 'pending_deletion')]):
            verdict = retention_verdict(tenant.delete_after, today)
            if verdict['phase'] != 'due':
                continue
            counts['retention'] += 1
            self._billing_raise_alert(
                'pending_deletion:%s' % tenant.slug, 'suspend_candidate',
                'warning',
                self.env._("%s's data may now be removed", tenant.name),
                self.env._(
                    "%(who)s was scheduled for closing down and the date "
                    "(%(day)s) has passed. NOTHING HAS BEEN REMOVED and "
                    "nothing on this platform ever removes a customer's system "
                    "on a schedule. The button is on their Closing down tab "
                    "and it takes a final copy first.",
                    who=tenant.name,
                    day=tenant.delete_after.isoformat()), tenant)
            self._billing_commit()
        return counts

    # =====================================================================
    #  8. WHAT THE COCKPIT READS
    # =====================================================================
    @api.model
    def billing_data(self, month=None):
        """Everything the Billing screen draws, in one call."""
        self._require_platform_admin()
        month = self._billing_month_from(month)
        today = fields.Date.context_today(self)
        Invoice = self.env['biz.tenant.invoice'].sudo()
        invoices = Invoice.search([], limit=200).as_dict()
        outstanding = [i for i in invoices if i['state'] == 'issued']
        ok, missing = self._billing_ready_to_send()
        return {
            'month': month.isoformat(),
            'month_label': period_label(month),
            'months': [{'month': m.isoformat(), 'label': period_label(m),
                        'closed': month_closed(m, today)}
                       for m in months_back(month_start(today),
                                            BACKFILL_MONTHS + 1)],
            'invoices': invoices,
            'outstanding': len(outstanding),
            'overdue': len([i for i in outstanding if i['days_overdue'] > 0]),
            'plans': self.env['biz.plan'].sudo().catalogue(),
            'meters': [{'key': m['key'], 'label': m['label'],
                        'unit': m.get('unit') or '',
                        'help': m.get('help') or ''}
                       for m in common.meters()],
            'settings': self._billing_settings(),
            'ready': ok, 'missing': missing,
            'auto_suspend': self._billing_auto_suspend_on(),
            'currency': self.env.company.currency_id.name or '',
        }

    @api.model
    def tenant_billing(self, tenant_id):
        """One customer's Plan tab: their plan, their standing, their invoices."""
        self._require_platform_admin()
        tenant = self._billing_tenant(tenant_id)
        today = fields.Date.context_today(self)
        month = month_start(today)
        Meter = self.env['biz.tenant.meter'].sudo()
        values, unavailable = Meter.readings_for(tenant, month)
        looking_at = month
        if not values:
            looking_at = prev_month(month)
            values, unavailable = Meter.readings_for(tenant, looking_at)
        phase = trial_phase(tenant.trial_ends_on, today)
        retention = retention_verdict(tenant.delete_after, today)
        return {
            'tenant_id': tenant.id, 'name': tenant.name, 'slug': tenant.slug,
            'state': tenant.state,
            'plan': tenant.plan_id.as_dict() if tenant.plan_id else None,
            'plans': self.env['biz.plan'].sudo().catalogue(),
            'trial_ends_on': (tenant.trial_ends_on.isoformat()
                              if tenant.trial_ends_on else ''),
            'trial': phase,
            'trial_text': trial_sentence(phase['days_left'],
                                         common.brand(self.env))
                          if phase['phase'] in ('ending', 'ended') else '',
            'paused_reason': tenant.paused_reason or '',
            'paused_at': (tenant.paused_at.strftime('%Y-%m-%d %H:%M')
                          if tenant.paused_at else ''),
            'delete_after': (tenant.delete_after.isoformat()
                             if tenant.delete_after else ''),
            'retention': retention,
            'deletion_reason': tenant.deletion_reason or '',
            'standing_pushed_at': (
                tenant.standing_pushed_at.strftime('%Y-%m-%d %H:%M')
                if tenant.standing_pushed_at else ''),
            'billing_email': tenant.billing_email or '',
            'contact_email': tenant.contact_email or '',
            'usage_month': looking_at.isoformat(),
            'usage_month_label': period_label(looking_at),
            'usage': [{'key': m['key'], 'label': m['label'],
                       'unit': m.get('unit') or '',
                       'value': values.get(m['key']),
                       'known': m['key'] in values,
                       'available': m['key'] not in unavailable,
                       'charged': bool(tenant.plan_id
                                       and tenant.plan_id.meter_key == m['key'])}
                      for m in common.meters()],
            'invoices': self.env['biz.tenant.invoice'].sudo().search(
                [('tenant_id', '=', tenant.id)]).as_dict(),
            'retention_days': self._billing_retention_days(),
        }

    @api.model
    def tenant_billing_save(self, tenant_id, vals):
        """The two fields on a customer that belong to billing."""
        self._require_platform_admin()
        tenant = self._billing_tenant(tenant_id)
        write = {}
        if 'billing_email' in (vals or {}):
            value = (vals['billing_email'] or '').strip()
            if value and not EMAIL_RE.match(value):
                raise UserError(self.env._(
                    "“%s” is not an email address.", value))
            write['billing_email'] = value
        if 'trial_ends_on' in (vals or {}):
            raw = (vals['trial_ends_on'] or '').strip()
            write['trial_ends_on'] = fields.Date.to_date(raw) if raw else False
            write['trial_told'] = ''
        if write:
            tenant.write(write)
            self._billing_push_standing(tenant)
        return {'ok': True, 'data': self.tenant_billing(tenant.id)}

    # =====================================================================
    #  9. THE PLAN CATALOGUE
    # =====================================================================
    @api.model
    def plan_preview(self, plan_id, tenant_id=None):
        """⚠ WHAT THIS PLAN WOULD HAVE CHARGED, ON THE SCREEN WHERE THE PRICE
        IS TYPED.

        The connection between a price and a measurement is the one thing a
        pricing screen normally leaves to somebody's imagination. Here the plan
        form asks the real readings of a real customer for last month and shows
        the arithmetic in words underneath the box.
        """
        self._require_platform_admin()
        plan = self.env['biz.plan'].sudo().browse(int(plan_id or 0)).exists()
        if not plan:
            return {'ok': False, 'reason': self.env._("There is no such plan.")}
        today = fields.Date.context_today(self)
        month = prev_month(month_start(today))
        Meter = self.env['biz.tenant.meter'].sudo()
        cur = self._billing_currency(plan)
        data = self._billing_plan_dict(plan, cur)
        fmt = lambda v: money(v, cur.symbol or '', cur.rounding or 0.01,   # noqa: E731
                              cur.position or 'after')
        rows = []
        targets = (self._tenants().browse(int(tenant_id)).exists()
                   if tenant_id else self._billing_serving())
        for tenant in targets:
            values, unavailable = Meter.readings_for(tenant, month)
            if not values:
                rows.append({'tenant': tenant.name, 'slug': tenant.slug,
                             'explain': '', 'total_h': '',
                             'why': self.env._(
                                 "No reading for %s yet.",
                                 period_label(month))})
                continue
            priced = price_for(data, values, unavailable)
            if priced['problem']:
                rows.append({'tenant': tenant.name, 'slug': tenant.slug,
                             'explain': '', 'total_h': '',
                             'why': priced['problem']})
                continue
            totals = invoice_totals(priced['lines'], data['vat_rate'],
                                    cur.rounding or 0.01)
            rows.append({'tenant': tenant.name, 'slug': tenant.slug,
                         'explain': priced['explain'],
                         'total_h': fmt(totals['total']), 'why': ''})
        return {'ok': True, 'month': month.isoformat(),
                'month_label': period_label(month), 'rows': rows}

    @api.model
    def plan_save(self, plan_id, vals):
        """Create or change a plan — BANDS AND ALL, IN ONE WRITE (F60).

        The constraint refuses a banded plan with no bands, correctly, so the
        bands cannot be a second write: they are built into the same `write`
        as `[(5, 0, 0)] + [(0, 0, …)]`.
        """
        self._require_platform_admin()
        vals = dict(vals or {})
        tiers = vals.pop('tiers', None)
        write = {}
        for key in ('name', 'code', 'blurb', 'price_kind', 'meter_key'):
            if key in vals:
                write[key] = (vals[key] or '').strip()
        for key in ('price', 'minimum', 'vat_rate'):
            if key in vals:
                try:
                    write[key] = float(vals[key] or 0.0)
                except (TypeError, ValueError):
                    raise UserError(self.env._(
                        "“%(value)s” is not a number.", value=vals[key]))
        for key in ('included', 'seat_limit', 'trial_days', 'sequence'):
            if key in vals:
                try:
                    write[key] = int(vals[key] or 0)
                except (TypeError, ValueError):
                    raise UserError(self.env._(
                        "“%(value)s” is not a whole number.", value=vals[key]))
        if 'currency_id' in vals and vals['currency_id']:
            write['currency_id'] = int(vals['currency_id'])
        if 'active' in vals:
            write['active'] = bool(vals['active'])
        # A price somebody has just typed is a price somebody has looked at.
        write['is_placeholder'] = bool(vals.get('is_placeholder', False))
        if tiers is not None:
            write['tier_ids'] = [(5, 0, 0)] + [
                (0, 0, {'up_to': int(t.get('up_to') or 0),
                        'price': float(t.get('price') or 0.0),
                        'meter_key': write.get('meter_key')
                                     or (vals.get('meter_key') or '')})
                for t in tiers if t]
        Plan = self.env['biz.plan'].sudo()
        if plan_id:
            plan = Plan.browse(int(plan_id)).exists()
            if not plan:
                raise UserError(self.env._("There is no such plan."))
            plan.write(write)
        else:
            if not write.get('name'):
                raise UserError(self.env._("Give the plan a name."))
            if not write.get('code'):
                write['code'] = re.sub(r'[^a-z0-9]+', '_',
                                       write['name'].lower()).strip('_')
            if not write.get('currency_id'):
                write['currency_id'] = self.env.company.currency_id.id
            plan = Plan.create(write)
        return {'ok': True, 'plan_id': plan.id,
                'plans': Plan.catalogue()}

    @api.model
    def plan_archive(self, plan_id, archive=True):
        self._require_platform_admin()
        plan = self.env['biz.plan'].sudo().browse(int(plan_id or 0)).exists()
        if not plan:
            raise UserError(self.env._("There is no such plan."))
        if archive and plan.tenant_count:
            raise UserError(self.env._(
                "%(n)s customers are on the %(name)s plan. Move them somewhere "
                "else first — a customer on an archived plan would still be "
                "invoiced by it and nobody would be able to find it.",
                n=plan.tenant_count, name=plan.name))
        plan.write({'active': not archive})
        return {'ok': True, 'plans': self.env['biz.plan'].sudo().catalogue()}

    # =====================================================================
    #  10. THE BILLING SETTINGS SCREEN
    # =====================================================================
    @api.model
    def billing_settings(self):
        self._require_platform_admin()
        ok, missing = self._billing_ready_to_send()
        can_mail, mail_why = self._mail_capability()
        return {
            'values': self._billing_settings(),
            'ready': ok, 'missing': missing,
            'auto_suspend': self._billing_auto_suspend_on(),
            'mail_ok': can_mail, 'mail_reason': mail_why,
            'brand': common.brand(self.env),
        }

    @api.model
    def billing_settings_save(self, vals):
        self._require_platform_admin()
        icp = self.env['ir.config_parameter'].sudo()
        allowed = set(BILLING_DEFAULTS)
        for key, value in (vals or {}).items():
            full = key if key.startswith('biz_tenants.') else \
                'biz_tenants.%s' % key
            if full not in allowed:
                continue
            if full == 'biz_tenants.auto_suspend':
                # ⚠ STORED AS "1"/"0", AND THE SCREEN BINDS ITS `aria-pressed`
                # TO A STRING (ledger F58). `t-att-` with a JavaScript `true`
                # renders an EMPTY attribute, so the switch sat grey beside a
                # paragraph in red saying it was on.
                value = '1' if value in (True, '1', 'on', 'true', 'yes') else '0'
                if value == '1':
                    _logger.warning(
                        "biz_tenants: THE AUTOMATIC PAUSE SWITCH HAS BEEN "
                        "TURNED ON by uid %s. From now on an invoice %d days "
                        "past its date will shut a customer's people out "
                        "without anybody pressing anything.", self.env.uid,
                        self._billing_suspend_after())
            icp.set_param(full, '' if value is None else str(value))
        return self.billing_settings()
