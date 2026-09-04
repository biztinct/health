# -*- coding: utf-8 -*-
"""The arithmetic that decides what a customer is charged. PURE, so testable.

Numbered test case 1 of SAAS H4d, plus the pieces of 4, 6 and 7 that are
judgements rather than writes. Every function here can be run in a shell with no
registry, which is the whole reason the money rules were lifted out of the
service in the first place (rail R6).
"""
from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models import billing_rules as br


@tagged('post_install', '-at_install')
class TestMoney(TransactionCase):

    def test_a_currency_with_no_decimals_is_never_given_any(self):
        """⚠ `round(x, 2)` ON A DONG FIGURE IS A NUMBER NO STATEMENT SHOWS."""
        self.assertEqual(br.round_money(2000000.4, 1.0), 2000000.0)
        self.assertEqual(br.round_money(2000000.6, 1.0), 2000001.0)
        self.assertEqual(br.decimals_for(1.0), 0)
        self.assertEqual(br.decimals_for(0.01), 2)
        self.assertEqual(br.money(2000000, '₫', 1.0, 'after'), '2,000,000 ₫')
        self.assertEqual(br.money(12.5, '$', 0.01, 'before'), '$12.50')

    def test_the_classic_binary_near_miss_does_not_bite(self):
        self.assertEqual(br.round_money(2.675, 0.01), 2.68)

    def test_a_quantity_has_no_pointless_decimal_tail(self):
        self.assertEqual(br.qty_text(236), '236')
        self.assertEqual(br.qty_text(1236.0), '1,236')
        self.assertEqual(br.qty_text(2.5), '2.50')


@tagged('post_install', '-at_install')
class TestPeriods(TransactionCase):

    def test_month_arithmetic_across_a_year_boundary(self):
        self.assertEqual(br.month_end(date(2026, 2, 1)), date(2026, 2, 28))
        self.assertEqual(br.month_end(date(2024, 2, 1)), date(2024, 2, 29))
        self.assertEqual(br.month_end(date(2026, 12, 1)), date(2026, 12, 31))
        self.assertEqual(br.next_month(date(2026, 12, 1)), date(2027, 1, 1))
        self.assertEqual(br.prev_month(date(2026, 1, 1)), date(2025, 12, 1))
        self.assertEqual(br.period_label(date(2026, 9, 1)), 'September 2026')

    def test_a_month_is_over_only_after_its_last_day(self):
        sep = date(2026, 9, 1)
        self.assertFalse(br.month_closed(sep, date(2026, 9, 30)))
        self.assertTrue(br.month_closed(sep, date(2026, 10, 1)))

    def test_the_month_strip_walks_backwards(self):
        rows = br.months_back(date(2026, 2, 1), 3)
        self.assertEqual(rows, [date(2026, 2, 1), date(2026, 1, 1),
                                date(2025, 12, 1)])


@tagged('post_install', '-at_install')
class TestPricing(TransactionCase):
    """Numbered test 1: one test per price structure, and the boundaries."""

    VND = {'rounding': 1.0, 'symbol': '₫', 'position': 'after'}

    def _plan(self, **kw):
        base = dict(self.VND, name='Test', price_kind='flat', price=0.0,
                    meter_key='', meter_label='', included=0, minimum=0.0,
                    tiers=[], vat_rate=0.0)
        base.update(kw)
        return base

    # ------------------------------------------------------------- 1a flat
    def test_flat_charges_the_same_whatever_was_measured(self):
        plan = self._plan(price_kind='flat', price=2000000.0)
        for readings in ({}, {'patients': 0}, {'patients': 5000}):
            out = br.price_for(plan, readings)
            self.assertEqual(out['problem'], '')
            self.assertEqual(len(out['lines']), 1)
            self.assertEqual(out['lines'][0]['amount'], 2000000.0)
            self.assertFalse(out['nothing_to_bill'])
        self.assertIn('2,000,000 ₫', out['explain'])

    # -------------------------------------------- 1b per unit + allowance
    def test_a_price_for_each_one_with_an_allowance(self):
        plan = self._plan(price_kind='per_unit', meter_key='patients',
                          meter_label='people in care', price=30000.0,
                          included=50)
        out = br.price_for(plan, {'patients': 236})
        self.assertEqual(out['lines'][0]['qty'], 186.0)
        self.assertEqual(out['lines'][0]['amount'], 5580000.0)
        # THE ARITHMETIC IN WORDS is the hero's whole content.
        self.assertIn('236 people in care', out['explain'])
        self.assertIn('30,000 ₫', out['explain'])
        self.assertIn('50 included', out['explain'])
        self.assertIn('5,580,000 ₫', out['explain'])

    def test_the_allowance_alone_makes_a_month_free_and_says_so(self):
        plan = self._plan(price_kind='per_unit', meter_key='patients',
                          meter_label='people in care', price=30000.0,
                          included=50)
        out = br.price_for(plan, {'patients': 40})
        self.assertTrue(out['nothing_to_bill'])
        self.assertEqual(out['lines'][0]['amount'], 0.0)

    def test_a_minimum_lifts_a_quiet_month_and_the_words_say_it_did(self):
        plan = self._plan(price_kind='per_unit', meter_key='visits',
                          meter_label='visits completed', price=10000.0,
                          minimum=1000000.0)
        out = br.price_for(plan, {'visits': 12})
        self.assertEqual(out['lines'][0]['amount'], 1000000.0)
        self.assertFalse(out['nothing_to_bill'])
        self.assertIn('brought up to', out['explain'])

    def test_every_one_of_the_four_numbers_can_price_a_plan(self):
        """The owner's decision 1: all four meters, not one favoured."""
        for key, value, expected in (('patients', 10, 100000.0),
                                     ('visits', 7, 70000.0),
                                     ('staff', 3, 30000.0),
                                     ('invoices', 21, 210000.0)):
            plan = self._plan(price_kind='per_unit', meter_key=key,
                              meter_label=key, price=10000.0)
            out = br.price_for(plan, {key: value})
            self.assertEqual(out['lines'][0]['amount'], expected,
                             'the %s meter did not price' % key)

    # -------------------------------------------------------- 1c the bands
    def test_a_band_includes_its_own_number(self):
        """⚠ `<=`, NOT `<`. "Up to 100" includes 100 — getting that wrong
        moves exactly one customer a band and nobody notices for a year."""
        tiers = [{'up_to': 100, 'price': 5000000.0},
                 {'up_to': 300, 'price': 9000000.0},
                 {'up_to': 1000, 'price': 15000000.0}]
        self.assertEqual(br.pick_tier(tiers, 100)['price'], 5000000.0)
        self.assertEqual(br.pick_tier(tiers, 101)['price'], 9000000.0)
        self.assertEqual(br.pick_tier(tiers, 300)['price'], 9000000.0)
        self.assertEqual(br.pick_tier(tiers, 301)['price'], 15000000.0)

    def test_the_top_band_covers_anything_above_it(self):
        """Silently charging nothing would be worse than charging the top."""
        tiers = [{'up_to': 100, 'price': 5000000.0}]
        self.assertEqual(br.pick_tier(tiers, 9999)['price'], 5000000.0)

    def test_a_banded_plan_with_no_bands_says_so_rather_than_raising(self):
        plan = self._plan(price_kind='flat_tier', meter_key='patients',
                          meter_label='people in care', tiers=[])
        out = br.price_for(plan, {'patients': 120})
        self.assertIn('no bands yet', out['problem'])
        self.assertEqual(out['lines'], [])

    def test_a_banded_plan_prices_one_line_and_names_the_band(self):
        plan = self._plan(price_kind='flat_tier', meter_key='patients',
                          meter_label='people in care',
                          tiers=[{'up_to': 100, 'price': 5000000.0},
                                 {'up_to': 300, 'price': 9000000.0}])
        out = br.price_for(plan, {'patients': 236})
        self.assertEqual(out['lines'][0]['amount'], 9000000.0)
        self.assertIn('up to 300', out['explain'])

    # ---------------------------------------------------- 1d nought vs blank
    def test_a_month_with_no_reading_prices_as_nought_and_says_why(self):
        """⚠ NOUGHT AND "NOBODY LOOKED" ARE DIFFERENT ANSWERS.

        A missing key is read as nought by the arithmetic — that is correct
        and unavoidable — so the SENTENCE has to carry the difference. A meter
        that was measurable and read nought is priced; a meter that could not
        be read at all refuses to price and names itself.
        """
        plan = self._plan(price_kind='per_unit', meter_key='patients',
                          meter_label='people in care', price=30000.0)
        measured_nought = br.price_for(plan, {'patients': 0})
        self.assertEqual(measured_nought['problem'], '')
        self.assertTrue(measured_nought['nothing_to_bill'])

        could_not_read = br.price_for(plan, {'patients': 0},
                                      unavailable={'patients'})
        self.assertIn('could not be measured', could_not_read['problem'])
        self.assertIn('people in care', could_not_read['problem'])
        self.assertEqual(could_not_read['lines'], [])

    def test_a_plan_that_does_not_say_how_it_charges_says_so(self):
        out = br.price_for(self._plan(price_kind='mystery'), {})
        self.assertIn('does not say how it charges', out['problem'])
        out = br.price_for(self._plan(price_kind='per_unit', meter_key=''), {})
        self.assertIn('does not say which number', out['problem'])


@tagged('post_install', '-at_install')
class TestTotals(TransactionCase):

    def test_the_tax_is_the_tax_on_the_number_printed_above_it(self):
        lines = [{'amount': 5580000.0}, {'amount': 419999.6}]
        out = br.invoice_totals(lines, 10.0, 1.0)
        self.assertEqual(out['subtotal'], 6000000.0)
        self.assertEqual(out['vat_amount'], 600000.0)
        self.assertEqual(out['total'], 6600000.0)
        self.assertEqual(out['subtotal'] + out['vat_amount'], out['total'])

    def test_no_tax_adds_nothing(self):
        out = br.invoice_totals([{'amount': 2000000.0}], 0.0, 1.0)
        self.assertEqual(out['vat_amount'], 0.0)
        self.assertEqual(out['total'], 2000000.0)


@tagged('post_install', '-at_install')
class TestOverdue(TransactionCase):
    """Numbered test 6: reminders are counted, not timed."""

    def _inv(self, **kw):
        base = {'state': 'issued', 'due_on': date(2026, 9, 1),
                'reminder_count': 0}
        base.update(kw)
        return base

    def test_a_draft_or_a_paid_invoice_is_never_overdue(self):
        for state in ('draft', 'paid', 'cancelled'):
            self.assertEqual(
                br.overdue_days(self._inv(state=state), date(2026, 12, 1)), 0)

    def test_the_reminder_is_raised_once_per_step_not_once_per_run(self):
        """⚠ THE COUNT ON THE RECORD IS WHAT DECIDES, so a job that runs twice
        on the same morning — or a box that was off for a week — raises each
        reminder exactly once rather than one per run or none at all."""
        today = date(2026, 9, 5)          # four days overdue, step 3 is due
        first = br.next_state(self._inv(reminder_count=0), today, (3, 10), 21)
        self.assertTrue(first['remind'])
        self.assertEqual(first['reminder_no'], 1)
        # Same day, second run: already sent.
        again = br.next_state(self._inv(reminder_count=1), today, (3, 10), 21)
        self.assertFalse(again['remind'])
        # A box switched off for a fortnight raises the SECOND, not two.
        late = br.next_state(self._inv(reminder_count=1), date(2026, 9, 20),
                             (3, 10), 21)
        self.assertTrue(late['remind'])
        self.assertEqual(late['reminder_no'], 2)
        after = br.next_state(self._inv(reminder_count=2), date(2026, 9, 20),
                              (3, 10), 21)
        self.assertFalse(after['remind'])

    def test_a_candidate_for_pausing_is_only_ever_a_flag(self):
        early = br.next_state(self._inv(), date(2026, 9, 10), (3, 10), 21)
        self.assertFalse(early['suspend_candidate'])
        late = br.next_state(self._inv(), date(2026, 9, 23), (3, 10), 21)
        self.assertTrue(late['suspend_candidate'])
        self.assertEqual(late['days_overdue'], 22)

    def test_the_number_is_sequential_inside_a_year(self):
        self.assertEqual(br.invoice_number('CX', 2026, 1), 'CX-2026-0001')
        self.assertEqual(br.invoice_number('CX', 2026, 42), 'CX-2026-0042')
        self.assertEqual(br.due_date_for(date(2026, 9, 1), 14),
                         date(2026, 9, 15))


@tagged('post_install', '-at_install')
class TestTrialsSeatsAndStandings(TransactionCase):
    """Numbered test 7 and 9's judgements."""

    def test_a_trial_that_has_not_started_reads_as_none(self):
        # ⚠ An unset date is `False` on this framework, not `None` (F23), so
        # the test is falsiness and never identity.
        self.assertEqual(br.trial_phase(False, date(2026, 9, 5))['phase'],
                         'none')

    def test_the_countdown_and_its_words(self):
        today = date(2026, 9, 5)
        self.assertEqual(br.trial_phase(date(2026, 10, 30), today)['phase'],
                         'ok')
        self.assertEqual(br.trial_phase(date(2026, 9, 12), today)['phase'],
                         'ending')
        self.assertEqual(br.trial_phase(date(2026, 9, 1), today)['phase'],
                         'ended')
        self.assertIn('tomorrow', br.trial_sentence(1, 'Brand'))
        self.assertIn('today', br.trial_sentence(0, 'Brand'))
        self.assertIn('has ended', br.trial_sentence(-2, 'Brand'))
        # No brand set: the neutral word, never a product name (rail R12).
        self.assertIn('this system', br.trial_sentence(3, ''))

    def test_an_absent_limit_and_a_limit_of_nought_both_mean_no_limit(self):
        for limit in (0, None, ''):
            out = br.seat_verdict(limit, 900)
            self.assertEqual(out['verdict'], 'ok')
            self.assertEqual(out['left'], -1)

    def test_the_limit_warns_before_it_refuses(self):
        self.assertEqual(br.seat_verdict(10, 5)['verdict'], 'ok')
        self.assertEqual(br.seat_verdict(10, 9)['verdict'], 'near')
        self.assertEqual(br.seat_verdict(10, 10)['verdict'], 'full')
        self.assertEqual(br.seat_verdict(10, 12)['verdict'], 'full')

    def test_the_refusal_names_the_number_the_plan_and_who_to_ask(self):
        text = br.seat_refusal(10, 10, 'Growth', 'help@example.com')
        self.assertIn('10', text)
        self.assertIn('Growth', text)
        self.assertIn('help@example.com', text)
        self.assertIn('larger plan', text)

    def test_nothing_ever_comes_back_from_being_closed_down(self):
        ok, why = br.state_transition('decommissioned', 'live')
        self.assertFalse(ok)
        self.assertIn('closed down', why)

    def test_the_moves_that_are_allowed_and_the_ones_that_are_not(self):
        for frm, to in (('trial', 'live'), ('live', 'paused'),
                        ('paused', 'live'), ('pending_deletion', 'live')):
            ok, _why = br.state_transition(frm, to)
            self.assertTrue(ok, '%s -> %s should be allowed' % (frm, to))
        for frm, to in (('live', 'draft'), ('paused', 'decommissioned')):
            ok, _why = br.state_transition(frm, to)
            self.assertFalse(ok, '%s -> %s should not be' % (frm, to))

    def test_the_retention_clock_only_ever_offers_a_button(self):
        """⚠ `due` MEANS "THE SCREEN MAY NOW OFFER IT". It has never meant
        that anything happens on its own, and nothing in this programme does."""
        self.assertEqual(br.retention_verdict(False, date(2026, 9, 5))['phase'],
                         'none')
        self.assertEqual(
            br.retention_verdict(date(2026, 10, 5), date(2026, 9, 5))['phase'],
            'waiting')
        self.assertEqual(
            br.retention_verdict(date(2026, 9, 1), date(2026, 9, 5))['phase'],
            'due')

    def test_only_paused_shuts_a_door(self):
        for state in ('live', 'trial', 'pending_deletion'):
            self.assertEqual(br.access_payload(state)['access'], 'open')
        out = br.access_payload('paused', brand='Brand')
        self.assertEqual(out['access'], 'paused')
        # A pause with no words still says something a person can act on.
        self.assertIn('Brand', out['access_text'])
