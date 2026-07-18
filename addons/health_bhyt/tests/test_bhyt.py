# -*- coding: utf-8 -*-
"""health_bhyt Phase 1 tests — coverage kernel + claim spine.

Kernel tests are pure/fast (the §2.2 worked vectors + the money invariant).
Model/flow tests build a completed+invoiced BHYT visit and exercise
generation, idempotency, eligibility, evidence-lock, append-only audit, the
cron and catchment security.
"""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_bhyt.models import bhyt_coverage


def _base_fixture(env):
    """Two provinces (for catchment security), a facility in province1, a
    product, and a valid-BHYT patient in province1."""
    Province = env['health.catchment.province']
    Facility = env['health.facility']
    Partner = env['res.partner']

    province = Province.search([], limit=1) or Province.create({
        'name': 'BHYT Test Province', 'code': 'BTP'})
    province2 = Province.create({'name': 'BHYT Other Province', 'code': 'BTP2'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'BHYT Test Facility', 'code': 'BTF',
            'catchment_province_id': province.id})

    product = env['product.product'].search([], limit=1) or \
        env['product.product'].create({'name': 'BHYT Test Service'})

    patient = Partner.create({
        'name': 'BHYT Test Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
        'insurance_number': 'DN4790012345678',
        'insurance_expiry': fields.Date.today() + timedelta(days=365),
        'bhyt_coverage_rate': 80.0,
    })
    return province, province2, facility, product, patient


@tagged('post_install', '-at_install')
class TestBhytKernel(TransactionCase):
    """Pure coverage-split kernel — the §2.2 worked vectors + invariant."""

    def test_01_split_vectors(self):
        cs = bhyt_coverage.coverage_split
        self.assertEqual(cs(100000, 80), (80000, 20000))
        self.assertEqual(cs(100000, 95), (95000, 5000))
        self.assertEqual(cs(100000, 100), (100000, 0))
        self.assertEqual(cs(100000, 80, service_covered=False), (0, 100000))
        # 12345 @ 80%: covered round(9876.0)=9876, copay remainder 2469
        self.assertEqual(cs(12345, 80), (9876, 2469))
        self.assertEqual(cs(0, 80), (0, 0))
        # Negative eligible (a credit-note / adjustment line): `covered` is
        # clamped into [0, total] so a non-positive line nets (0, 0) — the
        # kernel never emits a negative "covered" that would understate the
        # BHYT bill and overcharge the patient (ledger §5.46, hardened).
        self.assertEqual(cs(-500, 80), (0, 0))
        self.assertEqual(sum(cs(-500, 80)), 0)

    def test_02_rounding_invariant(self):
        """covered + copay == _round(eligible) for a spread — no đồng lost."""
        cs = bhyt_coverage.coverage_split
        for amount in (0, 1, 999, 12345, 100000, 333333, 7777777, 12345.67):
            for rate in (0, 33, 50, 80, 95, 100):
                covered, copay = cs(amount, rate)
                self.assertEqual(
                    covered + copay,
                    bhyt_coverage._round(max(0.0, amount), 1),
                    'invariant broke at amount=%s rate=%s' % (amount, rate))
                self.assertGreaterEqual(covered, 0)
                self.assertGreaterEqual(copay, 0)

    def test_03_claim_totals_mixed(self):
        totals = bhyt_coverage.claim_totals([
            {'eligible': 100000, 'rate': 80, 'covered_service': True},
            {'eligible': 50000, 'rate': 80, 'covered_service': False},
        ])
        self.assertEqual(totals, {'total': 150000, 'bhyt': 80000,
                                  'patient': 70000})
        self.assertEqual(totals['bhyt'] + totals['patient'], totals['total'])


@tagged('post_install', '-at_install')
class TestBhytClaim(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.province2, cls.facility, cls.product,
         cls.patient) = _base_fixture(cls.env)
        cls.Claim = cls.env['bhyt.claim']

    # ---- fixture helpers -------------------------------------------------
    def _make_invoice(self, partner, lines=((100000.0, 1.0),)):
        """A POSTED customer invoice with `lines` = ((price_unit, qty), ...)."""
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'BHYT Service %s' % i,
                'quantity': qty,
                'price_unit': price,
                'tax_ids': [(5, 0, 0)],
            }) for i, (price, qty) in enumerate(lines)],
        })
        inv.action_post()
        return inv

    def _make_completed_fso(self, patient, invoice, state='completed'):
        """Create an FSO then drive it to completed+invoiced via raw SQL
        (§5.9 — bypass the workflow/gates for a deterministic fixture)."""
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() - timedelta(days=1),
            'scheduled_duration': 60,
        })
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_fieldservice_order "
            "SET state=%s, is_invoiced=%s, invoice_id=%s WHERE id=%s",
            (state, True, invoice.id, fso.id))
        self.env.invalidate_all()
        return fso

    def _eligible_fso(self, patient=None):
        patient = patient or self.patient
        inv = self._make_invoice(patient)
        return self._make_completed_fso(patient, inv), inv

    # ---- generation ------------------------------------------------------
    def test_04_generate_mirrors_invoice(self):
        fso, inv = self._eligible_fso()
        claim = self.Claim._build_claim_for(fso)
        self.assertTrue(claim)
        self.assertEqual(claim.state, 'draft')
        self.assertEqual(claim.fso_id, fso)
        self.assertEqual(claim.invoice_id, inv)
        self.assertEqual(len(claim.line_ids), 1)
        # totals match the kernel on live data (report item b)
        self.assertEqual(claim.total_amount, 100000)
        self.assertEqual(claim.bhyt_amount, 80000)
        self.assertEqual(claim.patient_amount, 20000)
        self.assertEqual(claim.bhyt_amount + claim.patient_amount,
                         claim.total_amount)
        # snapshot frozen from the patient at generation time
        self.assertEqual(claim.bhyt_card_no, self.patient.insurance_number)
        self.assertEqual(claim.bhyt_coverage_rate, 80.0)
        # a 'generated' audit event was written
        self.assertEqual(claim.event_ids.mapped('event'), ['generated'])

    def test_05_idempotent(self):
        fso, _inv = self._eligible_fso()
        c1 = self.Claim._build_claim_for(fso)
        c2 = self.Claim._build_claim_for(fso)
        self.assertEqual(c1, c2)
        self.assertEqual(
            self.Claim.search_count([('fso_id', '=', fso.id)]), 1)

    def test_06_not_eligible(self):
        # (a) completed but NOT invoiced
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() - timedelta(days=1),
            'scheduled_duration': 60,
        })
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_fieldservice_order SET state='completed' "
            "WHERE id=%s", (fso.id,))
        self.env.invalidate_all()
        self.assertFalse(self.Claim._build_claim_for(fso))

        # (b) expired card
        expired = self.env['res.partner'].create({
            'name': 'Expired BHYT', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'insurance_number': 'DN4790099999999',
            'insurance_expiry': fields.Date.today() - timedelta(days=1),
            'bhyt_coverage_rate': 80.0,
        })
        fso_b, _b = self._eligible_fso(expired)
        self.assertFalse(self.Claim._build_claim_for(fso_b))

        # (c) non-BHYT patient (no card)
        plain = self.env['res.partner'].create({
            'name': 'No BHYT', 'is_patient': True,
            'catchment_province_id': self.province.id,
        })
        fso_c, _c = self._eligible_fso(plain)
        self.assertFalse(self.Claim._build_claim_for(fso_c))

    def test_07_uncovered_line_all_patient(self):
        inv = self._make_invoice(self.patient,
                                 lines=((100000.0, 1.0), (50000.0, 1.0)))
        fso = self._make_completed_fso(self.patient, inv)
        claim = self.Claim._build_claim_for(fso)
        self.assertEqual(len(claim.line_ids), 2)
        # flip the second line out-of-list → its full amount is patient copay
        line2 = claim.line_ids.sorted('id')[1]
        line2.covered_service = False
        self.assertEqual(line2.bhyt_amount, 0)
        self.assertEqual(line2.patient_amount, 50000)
        # totals recompute: 100000@80 covered 80000 + 0; patient 20000 + 50000
        self.assertEqual(claim.total_amount, 150000)
        self.assertEqual(claim.bhyt_amount, 80000)
        self.assertEqual(claim.patient_amount, 70000)

    # ---- evidence-lock ---------------------------------------------------
    def test_08_evidence_lock(self):
        """Runs as uid 1 (su) — the lock must still fire (§5.4 unconditional)."""
        fso, _inv = self._eligible_fso()
        claim = self.Claim._build_claim_for(fso)
        claim.action_mark_ready()
        self.assertEqual(claim.state, 'ready')

        # a locked snapshot/amount write raises even as su
        with self.assertRaises(UserError):
            claim.write({'bhyt_coverage_rate': 95.0})
        with self.assertRaises(UserError):
            claim.write({'bhyt_amount': 1})
        # a locked LINE write raises too
        with self.assertRaises(UserError):
            claim.line_ids[0].covered_service = False

        # state + reset stay allowed; reset writes a 'reset' event + unlocks
        claim.action_reset_draft()
        self.assertEqual(claim.state, 'draft')
        self.assertIn('reset', claim.event_ids.mapped('event'))
        # unlocked again: a snapshot write now succeeds
        claim.write({'bhyt_coverage_rate': 90.0})
        self.assertEqual(claim.bhyt_coverage_rate, 90.0)

    def test_09_event_append_only(self):
        fso, _inv = self._eligible_fso()
        claim = self.Claim._build_claim_for(fso)
        event = claim.event_ids[0]
        with self.assertRaises(UserError):
            event.write({'note': 'tamper'})
        with self.assertRaises(UserError):
            event.unlink()

    def test_10_unlink_state_guard(self):
        fso, _inv = self._eligible_fso()
        claim = self.Claim._build_claim_for(fso)
        claim.action_mark_ready()
        with self.assertRaises(UserError):
            claim.unlink()          # ready = evidence, not deletable
        claim.action_cancel()
        claim.unlink()              # cancelled is deletable
        self.assertFalse(claim.exists())

    # ---- cron ------------------------------------------------------------
    def test_11_cron_gate_and_savepoint(self):
        Param = self.env['ir.config_parameter'].sudo()
        good_fso, _g = self._eligible_fso()
        bad_fso, _b = self._eligible_fso(self.env['res.partner'].create({
            'name': 'Bad BHYT', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'insurance_number': 'DN4790088888888',
            'insurance_expiry': fields.Date.today() + timedelta(days=365),
            'bhyt_coverage_rate': 80.0,
        }))

        # gate OFF → no-op
        Param.set_param('bhyt.generate_enabled', 'False')
        self.Claim.cron_bhyt_generate()
        self.assertFalse(self.Claim.search([('fso_id', '=', good_fso.id)]))

        # gate ON → generates; a bad order in the batch is skipped, not fatal
        Param.set_param('bhyt.generate_enabled', 'True')
        orig = self.Claim._build_claim_for

        def _side(order):
            if order.id == bad_fso.id:
                raise ValueError('boom')
            return orig(order)

        with patch.object(type(self.Claim), '_build_claim_for',
                          side_effect=_side, autospec=False):
            self.Claim.cron_bhyt_generate()
        # good order produced a claim despite the bad one raising
        self.assertTrue(self.Claim.search([('fso_id', '=', good_fso.id)]))

    def test_12_cron_batch_cap(self):
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('bhyt.generate_enabled', 'True')
        Param.set_param('bhyt.generate_batch_cap', '1')
        f1, _1 = self._eligible_fso()
        f2, _2 = self._eligible_fso(self.env['res.partner'].create({
            'name': 'Cap BHYT', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'insurance_number': 'DN4790077777777',
            'insurance_expiry': fields.Date.today() + timedelta(days=365),
            'bhyt_coverage_rate': 80.0,
        }))
        self.Claim.cron_bhyt_generate()
        made = self.Claim.search_count(
            [('fso_id', 'in', (f1.id, f2.id))])
        self.assertEqual(made, 1)  # cap honoured

    # ---- security --------------------------------------------------------
    def test_13_catchment_and_create_acl(self):
        fso, _inv = self._eligible_fso()
        claim = self.Claim._build_claim_for(fso)  # patient in province1

        finance_here = self._make_user(
            'bhyt_fin_here', 'health_base.group_healthcare_finance',
            self.province)
        finance_other = self._make_user(
            'bhyt_fin_other', 'health_base.group_healthcare_finance',
            self.province2)
        owner = self._make_user(
            'bhyt_owner', 'health_base.group_healthcare_owner', self.province2)
        nurse = self._make_user(
            'bhyt_nurse', 'health_base.group_healthcare_nurse', self.province)

        # same-catchment finance sees it; other-catchment finance does not
        self.assertTrue(
            self.Claim.with_user(finance_here).search([('id', '=', claim.id)]))
        self.assertFalse(
            self.Claim.with_user(finance_other).search(
                [('id', '=', claim.id)]))
        # owner sees all catchments
        self.assertTrue(
            self.Claim.with_user(owner).search([('id', '=', claim.id)]))
        # a non-finance user cannot create a claim
        with self.assertRaises(AccessError):
            self.Claim.with_user(nurse).create({
                'fso_id': fso.id, 'patient_id': self.patient.id})

    def _make_user(self, login, group_xmlid, province):
        group = self.env.ref(group_xmlid)
        base_user = self.env.ref('base.group_user')
        return self.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(6, 0, [base_user.id, group.id])],
            'catchment_province_id': province.id,
        })

    # ---- bhyt_valid compute ---------------------------------------------
    def test_14_bhyt_valid_compute(self):
        self.assertTrue(self.patient.bhyt_valid)
        expired = self.env['res.partner'].create({
            'name': 'Expired', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'insurance_number': 'DN1',
            'insurance_expiry': fields.Date.today() - timedelta(days=1),
        })
        self.assertFalse(expired.bhyt_valid)
        no_card = self.env['res.partner'].create({
            'name': 'NoCard', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'insurance_expiry': fields.Date.today() + timedelta(days=1),
        })
        self.assertFalse(no_card.bhyt_valid)
