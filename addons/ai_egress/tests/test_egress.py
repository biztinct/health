# -*- coding: utf-8 -*-
"""The gate, and the honesty of its own claims.

Several of these assert what the guard CANNOT do. That is deliberate: the
failure mode for a privacy control is not that it breaks, it is that people
believe it covers more than it does.
"""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..egress import (AGGREGATE, RECORDS, SCHEMA, EgressRefused, check,
                      is_local_provider, redact, scan)


@tagged('post_install', '-at_install')
class TestEgressKernel(TransactionCase):

    # -- locality ---------------------------------------------------------
    def test_01_a_cloud_vendor_is_never_local(self):
        for endpoint in (None, 'http://localhost:11434', 'http://127.0.0.1'):
            self.assertFalse(is_local_provider('openai', endpoint),
                             "openai counted as local for %s" % endpoint)

    def test_02_self_hosted_is_local_only_on_a_private_host(self):
        self.assertTrue(is_local_provider('ollama', 'http://localhost:11434'))
        self.assertTrue(is_local_provider('mistral', 'http://127.0.0.1:8000'))
        self.assertTrue(is_local_provider('llama', 'http://10.0.3.7:11434'))
        self.assertTrue(is_local_provider('vllm', 'http://192.168.1.20:8000'))

    def test_03_the_same_model_on_someone_elses_box_is_remote(self):
        """Self-hosted software on a public endpoint is not self-hosting.

        This is the distinction that matters commercially: 'we run Mistral'
        says nothing about where the packet goes.
        """
        self.assertFalse(is_local_provider('mistral', 'https://api.mistral.ai'))
        self.assertFalse(is_local_provider('ollama', 'http://45.32.11.9:11434'))

    def test_04_an_unknown_provider_fails_closed(self):
        """A vendor nobody taught this function about must not inherit trust."""
        self.assertFalse(is_local_provider('some_new_llm', 'http://127.0.0.1'))
        self.assertFalse(is_local_provider('', 'http://127.0.0.1'))
        self.assertFalse(is_local_provider(None, None))

    # -- the gate ---------------------------------------------------------
    def test_05_records_may_not_reach_a_remote_provider(self):
        with self.assertRaises(EgressRefused) as caught:
            check('Visit notes for the patient.', RECORDS, 'openai')
        self.assertEqual(caught.exception.reason, 'records_to_remote_provider')

    def test_06_records_may_reach_a_local_one(self):
        decision = check('Visit notes for the patient.', RECORDS,
                         'ollama', 'http://localhost:11434')
        self.assertTrue(decision['local'])

    def test_07_schema_and_aggregates_may_go_anywhere(self):
        for kind in (SCHEMA, AGGREGATE):
            decision = check('Field: district. Type: char. 63 invoices.',
                             kind, 'openai')
            self.assertFalse(decision['local'])

    def test_08_an_undeclared_classification_is_refused(self):
        for bad in (None, '', 'safe', 'public'):
            with self.assertRaises(EgressRefused) as caught:
                check('anything', bad, 'ollama', 'http://localhost:11434')
            self.assertEqual(caught.exception.reason, 'undeclared_classification')

    # -- the backstop -----------------------------------------------------
    def test_09_an_identifier_overrides_the_declaration(self):
        """A wrong declaration is the failure mode that matters.

        Someone will one day build a prompt from rows and label it schema.
        When the content and the label disagree, believe the content.
        """
        cases = [
            'Why has 0912345678 not paid?',
            'Contact is hoa.nguyen@example.com',
            'Card 0123456789012 is expired',
            'Token enc$1$YWJjZGVmZ2hpamtsbW5vcHFy is stored',
        ]
        for prompt in cases:
            with self.assertRaises(EgressRefused) as caught:
                check(prompt, SCHEMA, 'openai')
            self.assertEqual(caught.exception.reason,
                             'identifier_in_exportable_prompt', prompt)

    def test_10_the_backstop_does_not_fire_on_ordinary_help_text(self):
        """A gate that refuses normal work gets switched off."""
        benign = [
            'What is the due date field used for?',
            'Show revenue by district for August 2026',
            'There are 63 invoices totalling 25,850,000 VND',
            'Call the client back within 24 hours',
        ]
        for prompt in benign:
            self.assertFalse(scan(prompt), 'false positive on: %s' % prompt)
            check(prompt, SCHEMA, 'openai')

    def test_11_a_local_provider_is_not_blocked_by_the_backstop(self):
        """Identifiers are fine when nothing leaves. Otherwise the local path
        would be no more capable than the remote one, and there would be no
        reason to run it."""
        decision = check('Why has 0912345678 not paid?', RECORDS,
                         'ollama', 'http://localhost:11434')
        # Recorded, not blocked. A number can match more than one pattern —
        # findings is evidence for the log, not a single verdict.
        self.assertIn('phone_vn', decision['findings'])

    def test_12_redaction_removes_what_the_scanner_can_see(self):
        out = redact('Ring 0912345678 or hoa@example.com about #4172')
        self.assertNotIn('0912345678', out)
        self.assertNotIn('hoa@example.com', out)

    def test_13_THE_GUARD_CANNOT_SEE_A_NAME(self):
        """Documented limit, asserted so nobody discovers it by accident.

        'Why has Nguyễn Thị Hoa not paid' contains personal data and passes
        every check here. The structural gate — the caller declaring RECORDS —
        is what protects that case. If this test ever starts failing because
        someone added a name detector, read the module docstring before
        celebrating: a rule tight enough to catch this refuses ordinary
        Vietnamese prose.
        """
        prompt = 'Why has Nguyễn Thị Hoa not paid her August invoice?'
        self.assertFalse(scan(prompt))
        check(prompt, SCHEMA, 'openai')          # allowed — and that is the point
        with self.assertRaises(EgressRefused):   # unless declared honestly
            check(prompt, RECORDS, 'openai')

    # -- the log ----------------------------------------------------------
    def test_14_every_decision_is_logged_both_ways(self):
        """An allowed send and a refusal are equally worth knowing about.

        NOTE the manual try/except instead of ``with self.assertRaises(...)``.
        That is not style. unittest's assertRaises context manager calls
        traceback.clear_frames() on exit to break reference cycles, and doing
        so discarded the INSERT this test had just made — the row was present
        inside the except block and gone immediately after. Verified: the same
        sequence in an odoo shell writes both rows every time.

        If you reach for assertRaises here again, this test will start failing
        for a reason that has nothing to do with the guard.
        """
        Log = self.env['ai.egress.log']
        Log.guard('Field: district', SCHEMA, 'openai', surface='test.allow')

        raised = None
        try:
            Log.guard('notes', RECORDS, 'openai', surface='test.refuse')
        except EgressRefused as caught:
            raised = caught
        self.assertIsNotNone(raised, "records to a remote provider was allowed")
        self.assertEqual(raised.reason, 'records_to_remote_provider')

        allowed = Log.search([('surface', '=', 'test.allow')])
        refused = Log.search([('surface', '=', 'test.refuse')])
        self.assertEqual(len(allowed), 1, "the allowed send was not recorded")
        self.assertEqual(len(refused), 1,
                         "a refusal that leaves no trace looks like a feature "
                         "quietly not working")
        self.assertTrue(allowed.allowed)
        self.assertFalse(refused.allowed)
        self.assertEqual(refused.reason, 'records_to_remote_provider')

    def test_15_the_log_never_stores_the_prompt(self):
        Log = self.env['ai.egress.log']
        secret = 'What is the ageing column for?'
        Log.guard(secret, SCHEMA, 'openai', surface='test.hash')
        row = Log.search([('surface', '=', 'test.hash')], limit=1)
        self.assertNotIn('ageing', str(row.read()[0]),
                         "storing prompts recreates the exposure this module "
                         "exists to prevent")
        self.assertEqual(len(row.prompt_sha256), 64)

    def test_16_the_log_is_append_only(self):
        Log = self.env['ai.egress.log']
        Log.guard('Field: district', SCHEMA, 'openai', surface='test.immutable')
        row = Log.search([('surface', '=', 'test.immutable')], limit=1)
        with self.assertRaises(UserError):
            row.write({'allowed': False})
        with self.assertRaises(UserError):
            row.unlink()

    def test_17_the_log_survives_a_rolled_back_transaction(self):
        """Refusals are written on their own cursor, not the caller's.

        A refusal is raised, and a raised exception normally ends with the
        request transaction rolled back — taking the record of the refusal
        with it. The log would then hold every allowed send and no refusals,
        which is exactly backwards.

        Asserted by inspection because the behaviour cannot be observed from
        inside a test: a test runs in a savepoint, so a truly independent
        cursor writes somewhere the assertions cannot see. What is checkable
        is that the code reaches for one.
        """
        import inspect
        from ..models import ai_egress_log
        src = inspect.getsource(ai_egress_log.AIEgressLog._record)
        self.assertIn('registry.cursor()', src,
                      "the audit write shares the caller's transaction, so a "
                      "refusal disappears with the request that caused it")
        self.assertIn("config.get('test_enable')", src,
                      "the test-mode branch is what makes the rest of this "
                      "suite able to see its own log rows")
