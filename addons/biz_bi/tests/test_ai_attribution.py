# -*- coding: utf-8 -*-
"""Who asked the model, and what the model is told to prefer."""
import json
from unittest.mock import patch

from odoo import SUPERUSER_ID
from odoo.tests import tagged

from ..models.bi_ai import NLQ_SYSTEM_PROMPT
from .common import BiCase


@tagged('biz_bi', 'post_install', '-at_install')
class TestAiAttribution(BiCase):
    """An AI request is something a PERSON did.

    Every write on the path is sudo'd (provider records, both logs), and it
    only takes one of them resolving the user from the sudo'd recordset for
    the whole audit trail to read `uid 1`. These tests pin the answer at the
    two places it is stored.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.creator = cls.env['res.users'].create({
            'name': 'BI Asking Creator', 'login': 'bi_asking_creator',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('biz_bi.group_bi_creator').id,
            ])],
        })
        # Ollama on loopback: a LOCAL provider by ai_egress's definition, so
        # the gate is exercised on its allow path rather than mocked away.
        cls.provider = cls.env['bi.ai.provider'].create({
            'name': 'BG1 Test Model',
            'provider': 'ollama',
            'endpoint': 'http://127.0.0.1:11434/api/chat',
            'model_name': 'llama3',
        })

    def _canned_config(self):
        return json.dumps({
            'name': 'Partners by country',
            'chart_type': 'bar',
            'slots': {
                'x': [{'field_id': self.f_country_name.id}],
                'series': [],
                'values': [{'field_id': self.f_name.id, 'agg': 'count'}],
            },
            'filters': [],
        })

    def _run_nlq_as_creator(self):
        provider = self.provider
        canned = self._canned_config()

        # plain functions, never autospec — a second autospec patch on an
        # already-patched method stops binding `self` (ledger §5.76)
        def fake_get_default(model, *args, **kwargs):
            return provider.with_env(model.env)

        def fake_complete(prov, system, user_message, force_json=True):
            return canned

        provider_cls = type(self.env['bi.ai.provider'])
        with patch.object(provider_cls, 'get_default', fake_get_default), \
                patch.object(provider_cls, '_complete', fake_complete):
            return self.env['bi.ai'].with_user(self.creator).nlq_chart(
                self.dataset.id, "how many partners by country")

    def test_audit_row_names_the_person_who_asked(self):
        before = self.env['bi.audit.log'].sudo().search(
            [('event', '=', 'ai_request')], limit=1).id or 0

        result = self._run_nlq_as_creator()
        self.assertIn('config', result, result.get('error'))

        audit = self.env['bi.audit.log'].sudo().search(
            [('event', '=', 'ai_request'), ('id', '>', before)])
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit.user_id.id, self.creator.id)
        self.assertNotEqual(audit.user_id.id, SUPERUSER_ID)

        ai_log = self.env['bi.ai.log'].sudo().search([], limit=1)
        self.assertEqual(ai_log.kind, 'nlq')
        self.assertTrue(ai_log.accepted)
        self.assertEqual(ai_log.user_id.id, self.creator.id)

    def test_egress_decision_is_recorded_for_the_same_person(self):
        """The gate's own log is the third place the user is written."""
        before = self.env['ai.egress.log'].sudo().search([], limit=1).id or 0
        self._run_nlq_as_creator()
        decision = self.env['ai.egress.log'].sudo().search(
            [('id', '>', before), ('surface', '=', 'biz_bi.nlq')])
        self.assertEqual(len(decision), 1)
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.local, "loopback ollama must read as local")
        self.assertEqual(decision.user_id.id, self.creator.id)

    def test_nlq_prompt_prefers_counting_over_money(self):
        """"leads by source" is a question about how many, and the model has
        to be told so — the validator cannot tell a wrong measure from a
        right one."""
        self.assertIn('COUNTING BEATS MONEY BY DEFAULT', NLQ_SYSTEM_PROMPT)
        self.assertIn('"agg": "count"', NLQ_SYSTEM_PROMPT)
        # the rule is CONDITIONAL — it must not override an explicit amount
        for amount_word in ('revenue', 'total', 'average', 'doanh thu'):
            self.assertIn(amount_word, NLQ_SYSTEM_PROMPT)
