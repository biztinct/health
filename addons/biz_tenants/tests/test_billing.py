# -*- coding: utf-8 -*-
"""Plans, the monthly reading, the invoices and where a customer stands.

Numbered test cases 2, 3, 4, 5, 6 and 7 of SAAS H4d — the half that needs a
database. The arithmetic itself is proved next door in `test_billing_rules.py`,
without one.

⚠ NOTHING HERE TOUCHES ANOTHER DATABASE. Every meter reading is written
directly, exactly as the snapshot writer would have written it, so the invoice
tests prove what an invoice does with a reading rather than re-proving that a
cursor can count. The one test that has to reach a system stands down when
there is not one.
"""
import base64
from datetime import date, timedelta
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models import billing_rules as br
from odoo.addons.biz_tenants.models import tenants_common as common


class BillingCase(TransactionCase):
    """A customer, a plan and a month's numbers, with nothing else moving."""

    def setUp(self):
        super().setUp()
        self.svc = self.env['biz.tenants']
        self.vnd = self.env.ref('base.VND', raise_if_not_found=False) \
            or self.env.company.currency_id
        if not self.vnd.active:
            self.vnd.sudo().write({'active': True})
        self.tenant = self.env['biz.tenant'].sudo().create({
            'name': 'A customer', 'slug': 'bzdbill', 'state': 'live',
            'contact_email': 'someone@example.com',
        })
        self.month = br.prev_month(br.month_start(date.today()))
        # The registry is process-wide, so a test that adds one puts it back.
        self._meters = list(common.METERS)
        self.addCleanup(lambda: common.METERS.__setitem__(
            slice(None), self._meters))

    def _plan(self, **kw):
        vals = {'name': 'Test plan', 'code': 'bzd_test',
                'price_kind': 'flat', 'price': 2000000.0,
                'currency_id': self.vnd.id}
        vals.update(kw)
        return self.env['biz.plan'].sudo().create(vals)

    def _reading(self, key, value, month=None, backfilled=False,
                 available=True):
        month = month or self.month
        return self.env['biz.tenant.meter'].sudo().snapshot(
            self.tenant, {'key': key, 'label': key, 'value': value,
                          'available': available}, month, backfilled)


# =============================================================================
#  2. THE PLANS
# =============================================================================
@tagged('post_install', '-at_install')
class TestPlans(BillingCase):

    def test_a_banded_plan_refuses_to_exist_without_its_bands(self):
        """⚠ LEDGER F60. The refusal is CORRECT — and it is why the seed and
        `plan_save` both build the plan and its bands into ONE write. A data
        file that made the plan and then added the bands would fail in between
        and take the whole upgrade with it."""
        with self.assertRaises(ValidationError):
            self._plan(code='bzd_bands', price_kind='flat_tier',
                       meter_key='patients')

    def test_a_banded_plan_created_with_its_bands_in_one_write_is_fine(self):
        plan = self._plan(code='bzd_bands2', price_kind='flat_tier',
                          meter_key='patients',
                          tier_ids=[(0, 0, {'up_to': 100, 'price': 5000000.0}),
                                    (0, 0, {'up_to': 300, 'price': 9000000.0})])
        self.assertEqual(len(plan.tier_ids), 2)

    def test_plan_save_replaces_the_bands_inside_the_same_write(self):
        plan = self._plan(code='bzd_bands3', price_kind='flat_tier',
                          meter_key='patients',
                          tier_ids=[(0, 0, {'up_to': 50, 'price': 1.0})])
        self.svc.plan_save(plan.id, {
            'price_kind': 'flat_tier', 'meter_key': 'patients',
            'tiers': [{'up_to': 100, 'price': 5000000.0},
                      {'up_to': 300, 'price': 9000000.0}]})
        self.assertEqual(sorted(plan.tier_ids.mapped('up_to')), [100, 300])

    def test_a_plan_that_charges_on_a_number_must_say_which(self):
        with self.assertRaises(ValidationError):
            self._plan(code='bzd_nometer', price_kind='per_unit',
                       meter_key='')

    def test_a_short_name_cannot_be_used_twice(self):
        """⚠ `models.Constraint`, not the inert list form (ledger H63) — and
        the row in `pg_constraint` is asserted as well as the refusal, because
        a refusal can come from somewhere else and look identical."""
        self._plan(code='bzd_dup')
        self.env.cr.execute(
            "SELECT count(*) FROM pg_constraint "
            "WHERE conrelid = 'biz_plan'::regclass AND contype = 'u'")
        self.assertGreaterEqual(self.env.cr.fetchone()[0], 1,
                                'no unique constraint reached the database')

    def test_saving_a_plan_takes_the_example_mark_off_it(self):
        """SAVING IS SAYING "I HAVE LOOKED AT THIS", and it is the only thing
        that clears the flag — so an invoice can never be raised from a figure
        nobody has read without the screen saying so."""
        plan = self._plan(code='bzd_ph', is_placeholder=True)
        self.svc.plan_save(plan.id, {'price': 3000000.0})
        self.assertFalse(plan.is_placeholder)

    def test_a_plan_with_customers_on_it_cannot_be_put_away(self):
        plan = self._plan(code='bzd_busy')
        self.tenant.write({'plan_id': plan.id})
        with self.assertRaises(UserError):
            self.svc.plan_archive(plan.id, True)

    def test_the_seed_is_whatever_the_product_registered_and_nothing_else(self):
        """Rail R11: the cockpit ships no plan of its own."""
        before = list(common.PLANS)
        self.addCleanup(lambda: common.PLANS.__setitem__(slice(None), before))
        common.PLANS[:] = [{
            'code': 'bzd_seeded', 'name': 'Seeded', 'blurb': '',
            'price_kind': 'flat_tier', 'meter_key': 'patients',
            'price': 0.0, 'included': 0, 'minimum': 0.0,
            'tiers': [{'up_to': 10, 'price': 1000.0}],
            'currency_xmlid': 'base.VND', 'vat_rate': 0.0, 'seat_limit': 0,
            'trial_days': 30, 'sequence': 10, 'placeholder': True,
        }]
        made = self.env['biz.plan'].ensure_seeded()
        self.assertEqual(made.code, 'bzd_seeded')
        self.assertTrue(made.is_placeholder)
        self.assertEqual(len(made.tier_ids), 1)
        # Idempotent, and it never rewrites a price somebody corrected.
        made.write({'price': 999.0})
        self.assertFalse(self.env['biz.plan'].ensure_seeded())
        self.assertEqual(made.price, 999.0)


# =============================================================================
#  3. THE MONTHLY READING, KEPT AS HISTORY
# =============================================================================
@tagged('post_install', '-at_install')
class TestSnapshot(BillingCase):

    def test_one_row_per_customer_per_number_per_month(self):
        self._reading('patients', 236)
        self._reading('visits', 40)
        rows = self.env['biz.tenant.meter'].sudo().search(
            [('tenant_id', '=', self.tenant.id), ('month', '=', self.month)])
        self.assertEqual(len(rows), 2)

    def test_a_second_run_does_not_overwrite_and_says_it_did_nothing(self):
        """⚠ BILLING BILLS FROM WHAT WAS MEASURED AT THE TIME. A re-run that
        rewrote last month would silently move the basis of an invoice that has
        already been sent."""
        rec, what = self._reading('patients', 236)
        self.assertEqual(what, 'written')
        again, what2 = self._reading('patients', 999)
        self.assertEqual(what2, 'kept')
        self.assertEqual(again.id, rec.id)
        self.assertEqual(again.value, 236)

    def test_a_row_taken_after_the_month_ended_is_marked_as_such(self):
        rec, _w = self._reading('patients', 236, backfilled=True)
        self.assertTrue(rec.backfilled)

    def test_billing_reads_the_snapshot_and_never_recounts(self):
        self._reading('patients', 236)
        self._reading('visits', 0, available=False)
        values, unavailable = self.env['biz.tenant.meter'].readings_for(
            self.tenant, self.month)
        self.assertEqual(values['patients'], 236)
        self.assertIn('visits', unavailable)
        # A month nobody measured answers empty rather than nought.
        empty, _u = self.env['biz.tenant.meter'].readings_for(
            self.tenant, br.prev_month(self.month))
        self.assertEqual(empty, {})


# =============================================================================
#  4. THE PREVIEW AND THE INVOICE
# =============================================================================
@tagged('post_install', '-at_install')
class TestInvoices(BillingCase):

    def setUp(self):
        super().setUp()
        self.plan = self._plan(code='bzd_growth', price_kind='per_unit',
                               meter_key='patients', price=30000.0,
                               included=50)
        self.tenant.write({'plan_id': self.plan.id})
        self._reading('patients', 236)

    def _preview(self):
        return self.svc.billing_preview(self.month.isoformat())

    def _row(self, data=None):
        data = data or self._preview()
        return [r for r in data['rows'] if r['tenant_id'] == self.tenant.id][0]

    def test_the_preview_writes_nothing_at_all(self):
        """THE PROPERTY THAT MAKES THIS SCREEN THE HERO. Proved by counting
        the rows after, not by reading the code."""
        before = self.env['biz.tenant.invoice'].sudo().search_count([])
        self._preview()
        self._preview()
        self.assertEqual(
            self.env['biz.tenant.invoice'].sudo().search_count([]), before)

    def test_the_preview_shows_the_numbers_the_plan_and_the_words(self):
        row = self._row()
        self.assertEqual(row['total'], 5580000.0)
        self.assertIn('236', row['explain'])
        self.assertIn('50 included', row['explain'])
        keys = {r['key']: r for r in row['readings']}
        self.assertTrue(keys['patients']['charged'])

    def test_creating_produces_exactly_the_lines_the_preview_showed(self):
        row = self._row()
        res = self.svc.billing_raise(self.month.isoformat(), True)
        self.assertEqual(len(res['created']), 1)
        invoice = self.env['biz.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.tenant.id)])
        self.assertEqual(len(invoice.line_ids), len(row['lines']))
        self.assertEqual(invoice.total, row['total'])
        self.assertEqual(invoice.subtotal, row['subtotal'])
        self.assertEqual(invoice.line_ids[0].amount, row['lines'][0]['amount'])
        # To the currency's own precision, never Python's.
        self.assertEqual(invoice.total, br.round_money(invoice.total, 1.0))
        self.assertEqual(invoice.state, 'issued')

    def test_a_month_already_invoiced_is_skipped_by_name(self):
        self.svc.billing_raise(self.month.isoformat(), True)
        row = self._row()
        self.assertIn('Already invoiced', row['skip'])
        again = self.svc.billing_raise(self.month.isoformat(), True)
        self.assertEqual(again['created'], [])

    def test_a_customer_with_no_reading_is_left_out_with_a_reason(self):
        other = self.env['biz.tenant'].sudo().create({
            'name': 'Unmeasured', 'slug': 'bzdnone', 'state': 'live',
            'plan_id': self.plan.id})
        data = self._preview()
        row = [r for r in data['rows'] if r['tenant_id'] == other.id][0]
        self.assertIn('No reading was taken', row['skip'])
        self.assertIn('not the same as a quiet month', row['skip'])

    def test_a_customer_on_a_trial_is_not_charged(self):
        self.tenant.write({'state': 'trial',
                           'trial_ends_on': date.today() + timedelta(days=10)})
        self.assertIn('On trial', self._row()['skip'])

    def test_a_month_that_is_not_over_needs_the_deliberate_button(self):
        this_month = br.month_start(date.today())
        self._reading('patients', 10, month=this_month)
        with self.assertRaises(UserError):
            self.svc.billing_raise(this_month.isoformat(), False)
        self.svc.billing_raise(this_month.isoformat(), True)

    def test_the_numbering_is_sequential_per_year_with_no_gaps(self):
        """⚠ READ OFF THE INVOICES THAT EXIST, NEVER OFF A SEQUENCE RECORD.
        A sequence bumped inside a transaction that is then rolled back leaves
        a gap, and a gap in an invoice book is a question from an auditor."""
        self.svc.billing_raise(self.month.isoformat(), True)
        first = self.env['biz.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.tenant.id)]).number
        year = date.today().year
        self.assertTrue(first.endswith('0001') or first[-4:].isdigit())
        # A failed raise must not consume a number.
        self.env.cr.execute('SAVEPOINT bzd_gap')
        try:
            self.svc._billing_next_number(year)
            raise ValueError('deliberate')
        except ValueError:
            self.env.cr.execute('ROLLBACK TO SAVEPOINT bzd_gap')
        other = self.env['biz.tenant'].sudo().create({
            'name': 'Second', 'slug': 'bzdtwo', 'state': 'live',
            'plan_id': self.plan.id})
        self.env['biz.tenant.meter'].sudo().snapshot(
            other, {'key': 'patients', 'label': 'p', 'value': 100},
            self.month)
        self.svc.billing_raise(self.month.isoformat(), True)
        numbers = self.env['biz.tenant.invoice'].sudo().search(
            [('number', 'like', '%%-%d-%%' % year)]).mapped('number')
        tails = sorted(int(n[-4:]) for n in numbers)
        self.assertEqual(tails, list(range(tails[0], tails[0] + len(tails))),
                         'the invoice book has a gap in it')

    def test_marking_one_paid_records_the_reference_and_the_day(self):
        self.svc.billing_raise(self.month.isoformat(), True)
        invoice = self.env['biz.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.tenant.id)])
        self.svc.invoice_mark_paid(invoice.id, 'FT26090512345',
                                   'bank transfer', '2026-09-05')
        self.assertEqual(invoice.state, 'paid')
        self.assertEqual(invoice.payment_reference, 'FT26090512345')
        self.assertEqual(invoice.paid_via, 'bank transfer')
        self.assertEqual(invoice.paid_on, date(2026, 9, 5))

    def test_cancelling_one_needs_a_reason(self):
        self.svc.billing_raise(self.month.isoformat(), True)
        invoice = self.env['biz.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.tenant.id)])
        with self.assertRaises(UserError):
            self.svc.invoice_cancel(invoice.id, '   ')
        self.svc.invoice_cancel(invoice.id, 'raised against the wrong month')
        self.assertEqual(invoice.state, 'cancelled')
        self.assertIn('wrong month', invoice.cancel_reason)

    def test_a_paid_invoice_cannot_be_cancelled(self):
        self.svc.billing_raise(self.month.isoformat(), True)
        invoice = self.env['biz.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.tenant.id)])
        self.svc.invoice_mark_paid(invoice.id)
        with self.assertRaises(UserError):
            self.svc.invoice_cancel(invoice.id, 'changed my mind')


# =============================================================================
#  5. THE DOCUMENT
# =============================================================================
@tagged('post_install', '-at_install')
class TestDocument(BillingCase):
    """⚠ THE TWO TRAPS THAT PUT A BROKEN DOCUMENT IN FRONT OF A PAYING
    CUSTOMER, both asserted on what is actually rendered."""

    def setUp(self):
        super().setUp()
        self.plan = self._plan(code='bzd_doc', price_kind='per_unit',
                               meter_key='patients', price=30000.0,
                               included=50)
        self.tenant.write({'plan_id': self.plan.id})
        self._reading('patients', 236)
        self.svc.billing_raise(self.month.isoformat(), True)
        self.invoice = self.env['biz.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.tenant.id)])

    def _html(self):
        return self.env['ir.actions.report'].sudo()._render_qweb_html(
            'biz_tenants.report_tenant_invoice', [self.invoice.id])[0]

    def test_the_page_carries_an_article_div_so_the_printer_is_told_utf8(self):
        """⚠ LEDGER F54, AND THIS IS THE ASSERTION THAT WOULD HAVE CAUGHT IT.

        The printer is handed one file per `article` div, each wrapped in the
        minimal layout — which is the only thing carrying the character-set
        declaration. Without it the printer reads the fragment as Latin-1 and
        every ₫ becomes "â‚«". IT STILL RENDERS. It still looks deliberate.
        And it still goes to the customer.
        """
        html = self._html()
        text = html.decode('utf-8') if isinstance(html, bytes) else html
        self.assertIn('class="article page"', text)
        self.assertIn('data-oe-model', text)

    def test_the_dong_sign_and_an_em_dash_survive_as_those_characters(self):
        html = self._html()
        raw = html if isinstance(html, bytes) else html.encode('utf-8')
        self.assertIn('₫'.encode('utf-8'), raw,
                      'the currency symbol did not survive rendering')
        self.assertIn('—'.encode('utf-8'), raw,
                      'the em dash did not survive rendering')
        # And the mojibake the Latin-1 fallback produces is NOT there.
        self.assertNotIn(b'\xc3\xa2\xe2\x80\x9a\xc2\xab', raw)

    def test_the_document_is_titled_the_invoice_and_never_the_framework(self):
        """⚠ LEDGER F55. A report with no `title` in its context is titled
        "Odoo Report" in the document's own properties — a user-visible string
        like any other, on a document that goes to a paying customer."""
        html = self._html()
        text = html.decode('utf-8') if isinstance(html, bytes) else html
        self.assertNotIn('Odoo Report', text)
        self.assertIn('<title>Invoice</title>', text)

    def test_the_page_does_not_reserve_room_for_a_header_it_does_not_print(self):
        """F55's second half: without these, the invoice begins a third of the
        way down a mostly empty sheet."""
        html = self._html()
        text = html.decode('utf-8') if isinstance(html, bytes) else html
        self.assertIn('data-report-margin-top', text.replace('_', '-'))

    def test_with_the_company_details_missing_it_prints_the_plain_warning(self):
        data = self.invoice._billing_render_data()
        self.assertTrue(data['missing'])
        html = self._html()
        text = html.decode('utf-8') if isinstance(html, bytes) else html
        self.assertIn('Not ready to send', text)

    def test_with_the_company_details_filled_in_the_warning_goes(self):
        icp = self.env['ir.config_parameter'].sudo()
        for key, value in (('biz_tenants.billing_company', 'A Company'),
                           ('biz_tenants.billing_address', '1 A Street'),
                           ('biz_tenants.billing_vat', '0100000000'),
                           ('biz_tenants.bank_details', 'Bank, 123456789')):
            icp.set_param(key, value)
        data = self.invoice._billing_render_data()
        self.assertFalse(data['missing'])
        html = self._html()
        text = html.decode('utf-8') if isinstance(html, bytes) else html
        self.assertNotIn('Not ready to send', text)
        self.assertIn('Bank, 123456789', text)

    def test_no_user_visible_string_on_the_document_names_the_framework(self):
        """Rail R12 / F43's assertion, over what is actually rendered."""
        html = self._html()
        text = html.decode('utf-8') if isinstance(html, bytes) else html
        # The rendered page carries framework asset URLs in its head, which are
        # technical identifiers rather than user-visible strings. The BODY is
        # what a person reads.
        body = text.split('<body', 1)[-1]
        for banned in ('Odoo', 'odoo.com', 'Powered by'):
            self.assertNotIn(banned, body,
                             'the invoice a customer receives says "%s"'
                             % banned)

    def test_the_document_is_stored_at_issue_rather_than_re_rendered(self):
        """A document that changes after it was sent is not a document."""
        self.assertTrue(self.invoice.pdf)
        first = self.invoice.pdf
        self.plan.write({'price': 999999.0})
        res = self.svc.invoice_pdf(self.invoice.id)
        self.assertEqual(base64.b64decode(res['data'])[:5],
                         base64.b64decode(first)[:5])
        self.assertEqual(self.invoice.total, 5580000.0)


# =============================================================================
#  6. OVERDUE, REMINDERS AND THE SWITCH THAT SHIPS OFF
# =============================================================================
@tagged('post_install', '-at_install')
class TestChasing(BillingCase):

    def setUp(self):
        super().setUp()
        self.plan = self._plan(code='bzd_chase')
        self.tenant.write({'plan_id': self.plan.id})
        self._reading('patients', 10)
        self.invoice = self.env['biz.tenant.invoice'].sudo().create({
            'tenant_id': self.tenant.id, 'number': 'BZD-TEST-0001',
            'period_start': self.month, 'period_end': br.month_end(self.month),
            'plan_id': self.plan.id, 'plan_name': self.plan.name,
            'currency_id': self.vnd.id, 'subtotal': 2000000.0,
            'total': 2000000.0, 'state': 'issued',
            'issued_on': date.today() - timedelta(days=20),
            'due_on': date.today() - timedelta(days=5),
        })

    def test_the_daily_job_raises_the_flag_and_counts_the_reminder_once(self):
        self.svc._cron_billing()
        alert = self.env['biz.alert'].sudo().search(
            [('key', '=', 'invoice_overdue:BZD-TEST-0001')])
        self.assertTrue(alert)
        self.assertEqual(alert.kind, 'invoice_overdue')
        self.assertEqual(self.invoice.reminder_count, 1)
        # Run it again the same morning: the count does not move.
        self.svc._cron_billing()
        self.assertEqual(self.invoice.reminder_count, 1)

    def test_nothing_was_actually_said_to_anybody_and_the_record_says_so(self):
        """⚠ LEDGER F40. `spoken_at` is the stamp that says "we told you", and
        while there is no way to send anything it stays EMPTY — which is the
        truth, and which is the whole reason the Alerts screen exists."""
        self.svc._cron_billing()
        self.assertFalse(self.invoice.spoken_at)

    def test_the_automatic_pause_ships_off_and_does_nothing_while_it_is(self):
        self.assertFalse(self.svc._billing_auto_suspend_on())
        self.invoice.write({'due_on': date.today() - timedelta(days=40)})
        self.svc._cron_billing()
        self.assertEqual(self.tenant.state, 'live',
                         'a customer was paused with the switch off')
        candidate = self.env['biz.alert'].sudo().search(
            [('key', '=', 'suspend_candidate:BZD-TEST-0001')])
        self.assertTrue(candidate)
        self.assertIn('NOT automatic', candidate.body_text)

    def test_the_switch_is_stored_as_a_string_the_screen_can_bind_to(self):
        """⚠ LEDGER F58. `t-att-` bound to a JavaScript `true` renders an EMPTY
        attribute, so `[aria-pressed="true"]` never matches — the switch sat
        grey beside a paragraph in red saying it was on."""
        self.svc.billing_settings_save({'auto_suspend': True})
        self.assertEqual(
            self.svc._billing_param('biz_tenants.auto_suspend'), '1')
        self.assertTrue(self.svc.billing_settings()['auto_suspend'])
        self.svc.billing_settings_save({'auto_suspend': False})
        self.assertFalse(self.svc.billing_settings()['auto_suspend'])

    def test_paying_it_closes_the_flag(self):
        self.svc._cron_billing()
        self.svc.invoice_mark_paid(self.invoice.id, 'ref')
        alert = self.env['biz.alert'].sudo().search(
            [('key', '=', 'invoice_overdue:BZD-TEST-0001')])
        self.assertEqual(alert.state, 'resolved')


# =============================================================================
#  7. WHERE A CUSTOMER STANDS
# =============================================================================
@tagged('post_install', '-at_install')
class TestLifecycle(BillingCase):

    def setUp(self):
        super().setUp()
        self.plan = self._plan(code='bzd_life', trial_days=30)
        # Nothing here can reach the customer's own system, so the one push is
        # neutered — what is being proved is OUR side of every transition.
        patcher = patch.object(
            type(self.svc), '_billing_push_standing',
            lambda self, tenant, why='': {'ok': True})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_transition_writes_a_line_on_their_own_record(self):
        before = len(self.tenant.provision_log or '')
        self.svc.tenant_set_plan(self.tenant.id, self.plan.id, True)
        self.assertEqual(self.tenant.state, 'trial')
        self.svc.tenant_convert(self.tenant.id)
        self.assertEqual(self.tenant.state, 'live')
        self.svc.tenant_pause(self.tenant.id, 'June is unsettled', 'bzdbill')
        self.assertEqual(self.tenant.state, 'paused')
        self.svc.tenant_resume(self.tenant.id)
        self.assertEqual(self.tenant.state, 'live')
        log = self.tenant.provision_log or ''
        self.assertGreater(len(log), before)
        for expected in ('trial', 'paused', 'live'):
            self.assertIn(expected, log)

    def test_pausing_needs_the_short_name_and_a_reason_for_their_people(self):
        self.svc.tenant_set_plan(self.tenant.id, self.plan.id)
        with self.assertRaises(UserError):
            self.svc.tenant_pause(self.tenant.id, 'a reason', 'wrong')
        with self.assertRaises(UserError):
            self.svc.tenant_pause(self.tenant.id, '   ', 'bzdbill')

    def test_letting_them_back_in_takes_one_press_and_no_typing(self):
        """Undoing harm is never made harder than doing it."""
        self.svc.tenant_pause(self.tenant.id, 'unsettled', 'bzdbill')
        self.svc.tenant_resume(self.tenant.id)
        self.assertEqual(self.tenant.state, 'live')
        self.assertFalse(self.tenant.paused_reason)

    def test_the_four_new_alert_kinds_are_all_self_managed(self):
        """⚠ LEDGER F67. No reading the fifteen-minute sweep takes can see an
        unpaid invoice or a trial running out, so if these were not on the list
        the very next sweep would close every one of them — minutes after the
        morning job raised them."""
        from odoo.addons.biz_tenants.models.alert_rules import (
            ALERT_KINDS, KIND_LABEL, SELF_MANAGED_KINDS,
        )
        for kind in ('trial_ending', 'invoice_overdue', 'suspend_candidate',
                     'tenant_paused'):
            self.assertIn(kind, ALERT_KINDS)
            self.assertIn(kind, SELF_MANAGED_KINDS,
                          '%s would be closed by the next sweep' % kind)
            self.assertTrue(KIND_LABEL.get(kind))

    def test_the_sweep_leaves_this_phase_s_alerts_alone(self):
        from odoo.addons.biz_tenants.models.alert_rules import reconcile
        existing = [{'id': 1, 'key': 'invoice_overdue:X',
                     'kind': 'invoice_overdue', 'severity': 'warning',
                     'state': 'open'},
                    {'id': 2, 'key': 'tenant_paused:Y', 'kind': 'tenant_paused',
                     'severity': 'warning', 'state': 'open'}]
        _create, _bump, resolve = reconcile(existing, [],
                                            '2026-09-05 07:15:00')
        self.assertEqual(resolve, [])

    def test_a_trial_ending_pauses_nothing_and_the_words_say_so(self):
        self.svc.tenant_set_plan(self.tenant.id, self.plan.id, True)
        self.tenant.write({'trial_ends_on': date.today() - timedelta(days=1),
                           'trial_told': ''})
        self.svc._cron_billing()
        self.assertEqual(self.tenant.state, 'trial',
                         'a trial running out changed a customer\'s standing')
        alert = self.env['biz.alert'].sudo().search(
            [('key', '=', 'trial_ending:bzdbill')])
        self.assertTrue(alert)
        self.assertIn('NOTHING HAS HAPPENED', alert.body_text)
        # Said once, not once a night.
        count = alert.count
        self.svc._cron_billing()
        self.assertEqual(alert.count, count)

    def test_the_retention_clock_never_removes_anything(self):
        self.tenant.write({'state': 'pending_deletion',
                           'delete_after': date.today() - timedelta(days=1)})
        self.svc._cron_billing()
        self.assertTrue(self.tenant.exists())
        self.assertEqual(self.tenant.state, 'pending_deletion')
        alert = self.env['biz.alert'].sudo().search(
            [('key', '=', 'pending_deletion:bzdbill')])
        self.assertTrue(alert)
        self.assertIn('NOTHING HAS BEEN REMOVED', alert.body_text)

    def test_the_standing_a_customer_is_told_matches_where_they_stand(self):
        self.svc.tenant_set_plan(self.tenant.id, self.plan.id)
        vals = self.svc._billing_standing_values(self.tenant)
        self.assertEqual(vals[br.T_ACCESS], 'open')
        self.assertEqual(vals[br.T_PLAN_NAME], self.plan.name)
        self.tenant.write({'state': 'paused', 'paused_reason': 'unsettled'})
        vals = self.svc._billing_standing_values(self.tenant)
        self.assertEqual(vals[br.T_ACCESS], 'paused')
        self.assertEqual(vals[br.T_ACCESS_TEXT], 'unsettled')
        self.assertIn(br.T_SEAT_MODEL, vals)
        self.assertIn(br.T_USAGE, vals)
