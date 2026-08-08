# -*- coding: utf-8 -*-
"""The Care Coach: precision, capability, and the honesty rules.

The honesty rules are the point of this file. They are not conventions to be
remembered — each is asserted, because "the Coach never invents a clinical
fact" is only true for as long as nothing has quietly made it false.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

# Questions a nurse or a doctor might genuinely type into a box on a clinical
# system. Every one of them must come back with NOTHING — the fallback then
# names what the Coach can actually answer. In the prototype these matched
# "what does this page do" on the shared word "what".
OUT_OF_SCOPE = [
    "what dose of antibiotic should I give",
    "what is her blood pressure",
    "is the wound infected",
    "what is the patient's diagnosis",
    "liều kháng sinh là bao nhiêu",
    "huyết áp của bà ấy là bao nhiêu",
    "vết thương có bị nhiễm trùng không",
]
# NOT out of scope: a price question SHOULD reach the `price` intent, whose
# whole job is to refuse. Refusing on purpose beats matching nothing and
# falling through to a generic list.

TOKEN_RE = re.compile(r"\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}")


@tagged('post_install', '-at_install')
class TestCoach(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intent = cls.env['learn.intent']
        cls.Screen = cls.env['learn.screen']

    # ------------------------------------------------------------ precision
    def test_01_out_of_scope_questions_resolve_to_nothing(self):
        """A wrong answer costs more than no answer.

        Especially here: the Coach sits on a clinical system, and a confident
        UI answer to a clinical question is worse than silence.
        """
        leaked = []
        for q in OUT_OF_SCOPE:
            for screen in (None, 'carecommand', 'dashboard'):
                key = self.Intent.resolve(q, screen)
                # `clinical` is the RIGHT answer: an explicit refusal that then
                # routes to a clinician. Anything else is the Coach answering a
                # clinical question with product content.
                if key and key != 'clinical':
                    leaked.append('%r on %s -> %s' % (q, screen, key))
        self.assertFalse(leaked, "Out-of-scope questions the Coach answered:\n  "
                                 + "\n  ".join(leaked))

    def test_01b_clinical_questions_are_refused_and_routed(self):
        """Refusing is half of it. A dead end leaves a worried person exactly
        where they started, so the refusal must name who can and how to ask."""
        for q in OUT_OF_SCOPE:
            res = self.Intent.ask(q, 'carecommand')
            self.assertTrue(res['matched'], "no refusal offered for %r" % q)
            kinds = {b['kind'] for b in res['blocks']}
            self.assertIn('refusal', kinds, "%r was not refused" % q)
            self.assertIn('who', kinds, "%r refused with no route to a clinician" % q)
            self.assertIn('how', kinds, "%r refused with no way to escalate" % q)

    def test_02_price_question_is_refused_not_guessed(self):
        """Prices are not in the spine, so the Coach must say so.

        There IS an intent for this — refusing on purpose beats matching
        nothing and falling through to a generic list.
        """
        key = self.Intent.resolve("how much does a visit cost", 'carecommand')
        self.assertEqual(key, 'price')
        answer = self.Intent._answer('price', 'carecommand')
        text = " ".join(b['body']['en'] for b in answer['blocks']
                        if isinstance(b.get('body'), dict))
        self.assertTrue(text.strip(), "the price refusal says nothing at all")

    # --------------------------------------------------------------- recall
    def test_03_every_intent_is_reachable_by_its_own_label(self):
        """If the Coach offers a question as a suggestion, asking it must work.

        The suggestion buttons submit the label verbatim, so a label that does
        not resolve to its own intent is a dead button.
        """
        misses = []
        for intent in self.Intent.search([]):
            for lang in ('en_US', 'vi_VN'):
                label = intent.with_context(lang=lang).label
                got = self.Intent.resolve(label, None)
                if got != intent.key:
                    misses.append('%s [%s] %r -> %s' % (intent.key, lang, label[:50], got))
        self.assertFalse(misses, "Intents unreachable by their own label:\n  "
                                 + "\n  ".join(misses))

    def test_04_every_suggested_question_resolves(self):
        misses = []
        for screen in self.Screen.search([]):
            for intent in screen.suggest_ids:
                got = self.Intent.resolve(intent.label, screen.key)
                if got != intent.key:
                    misses.append('%s on %s -> %s' % (intent.key, screen.key, got))
        self.assertFalse(misses, "Suggested questions that do not resolve:\n  "
                                 + "\n  ".join(misses))

    # ----------------------------------------------------------- capability
    def test_05_capability_is_read_from_the_real_gate(self):
        """Not from a role name the tutorial keeps its own copy of."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        base = self.env.ref('base.group_user').id
        manager = self.env.ref('health_crm.group_health_crm_manager').id

        plain = Users.create({'name': 'Coach Plain', 'login': 'coach_plain_test',
                              'group_ids': [(6, 0, [base])]})
        boss = Users.create({'name': 'Coach Boss', 'login': 'coach_boss_test',
                             'group_ids': [(6, 0, [base, manager])]})

        # With no screen in play, the group is the only thing that decides.
        self.assertEqual(self.env(user=plain)['learn.intent']._capability(None), 'operator')
        self.assertEqual(self.env(user=boss)['learn.intent']._capability(None), 'manager')

        # VISIBILITY WINS, and the ordering is deliberate. Neither of these
        # users has an access.role, so the Care Command leaf is not in their
        # sidebar — and the honest answer to "can I take a conversation off a
        # colleague" is then "you cannot even see that screen", not a lecture
        # about a permission they also do not have. Holding the CRM Manager
        # group does not change that: the group governs the action, the role
        # governs the door.
        self.assertEqual(
            self.env(user=plain)['learn.intent']._capability('carecommand'), 'no_access')
        self.assertEqual(
            self.env(user=boss)['learn.intent']._capability('carecommand'), 'no_access')

    def test_06_the_capability_answer_differs(self):
        """`takeover` is the one intent whose answer depends on permission.

        Every capability must get an answer, and the answer for someone who
        cannot do it must actually refuse — not quietly show the affirmative.
        """
        blocks_by_cap = {}
        intent = self.Intent.search([('key', '=', 'takeover')], limit=1)
        self.assertTrue(intent, "the takeover intent is missing")
        for block in intent.block_ids:
            blocks_by_cap.setdefault(block.capability, []).append(block.kind)
        for cap in ('no_access', 'operator', 'manager', 'owner'):
            self.assertIn(cap, blocks_by_cap, "no answer for capability %s" % cap)
        self.assertIn('refusal', blocks_by_cap['operator'],
                      "an operator is not told they cannot take over")
        self.assertIn('refusal', blocks_by_cap['no_access'],
                      "someone without the screen is not told so")
        self.assertIn('ok', blocks_by_cap['manager'],
                      "a manager is not told they can")

    def test_07_a_refusal_always_says_who_can_and_how_to_ask(self):
        """A refusal that stops at "you can't" leaves the person stuck, which
        is the exact state the Coach exists to get them out of."""
        bad = []
        for intent in self.Intent.search([]):
            caps = {b.capability for b in intent.block_ids if b.kind == 'refusal'}
            for cap in caps:
                kinds = {b.kind for b in intent.block_ids if b.capability == cap}
                if not ({'who', 'how'} & kinds):
                    bad.append('%s [%s]' % (intent.key, cap))
        self.assertFalse(bad, "Refusals with no route forward:\n  " + "\n  ".join(bad))

    # -------------------------------------------------------------- honesty
    def test_08_the_coach_can_never_act(self):
        """No control an answer renders may reach a product method.

        Asserted against the source: every `data-act` the Coach emits must be
        in COACH_ACTIONS, which contains only its own controls.
        """
        path = os.path.join(get_module_path('health_learn'), 'static/src/coach/coach.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        declared = set(re.findall(r'"(c-[a-z-]+)"',
                                  src.split('COACH_ACTIONS = new Set([')[1].split('])')[0]))
        emitted = set(re.findall(r'data-act="(c-[a-z-]+)"', src))
        self.assertTrue(declared, "COACH_ACTIONS could not be read")
        rogue = emitted - declared
        self.assertFalse(rogue, "The Coach renders actions outside its own set: %s" % rogue)
        # And nothing in the answer path calls the action service directly.
        answer_src = src.split('_answerHTML(')[1].split('\n    }')[0]
        self.assertNotIn('doAction', answer_src,
                         "an answer block calls doAction — the Coach must never act")

    def test_09_every_factual_intent_cites_a_source(self):
        """Anything that makes a claim about the product says where it comes
        from. An answer with no provenance is indistinguishable from a guess."""
        FACTUAL = {'p', 'steps', 'calc', 'calc_kpi', 'ok', 'warn'}
        missing = []
        for intent in self.Intent.search([]):
            if intent.dynamic != 'none':
                continue   # a screen blurb cites the screen it is on
            by_cap = {}
            for b in intent.block_ids:
                by_cap.setdefault(b.capability, set()).add(b.kind)
            for cap, kinds in by_cap.items():
                if (kinds & FACTUAL) and 'source' not in kinds:
                    missing.append('%s [%s]' % (intent.key, cap))
        self.assertFalse(missing, "Factual answers with no 'grounded in' line:\n  "
                                  + "\n  ".join(missing))

    def test_10_a_miss_names_what_it_can_answer(self):
        """Never a bare "I don't know"."""
        # Genuinely unmatched, and NOT clinical — a clinical question now has
        # its own deliberate refusal, so it exercises the wrong path.
        for screen in ('carecommand', 'dashboard', 'channelcenter'):
            res = self.Intent.ask("how do I export the payroll ledger to excel", screen)
            self.assertFalse(res['matched'], "matched a question it has no content for")
            self.assertTrue(res['suggest'],
                            "no suggestions offered after a miss on %s" % screen)
            for s in res['suggest']:
                self.assertTrue(s['label']['en'] and s['label']['vi'])

    def test_11_an_uncovered_screen_is_admitted_not_guessed(self):
        """Off the CRM map the Coach must say so, not answer about CRM."""
        res = self.Intent.ask("what does this screen do", 'not_a_real_screen')
        # `whatpage` is screens='*', so it resolves — but with no screen record
        # its dynamic blurb is empty rather than a borrowed one.
        if res['matched']:
            bodies = [b['body'] for b in res['blocks']]
            for b in bodies:
                if isinstance(b, dict):
                    self.assertNotIn('Care Command', b.get('en') or '',
                                     "answered about another screen entirely")

    # -------------------------------------------------------------- content
    def test_12_no_unresolved_tokens_in_any_answer(self):
        tokens = self.env['learn.tenant.override'].resolved_tokens()
        leaked = []
        for intent in self.Intent.search([]):
            for screen in [None] + self.Screen.search([]).mapped('key'):
                answer = self.Intent._answer(intent.key, screen)
                for block in answer['blocks']:
                    for value in (block.get('body'), ):
                        if not isinstance(value, dict):
                            continue
                        for lang in ('en', 'vi'):
                            for key in TOKEN_RE.findall(value.get(lang) or ''):
                                if key not in tokens:
                                    leaked.append('%s -> {{%s}}' % (intent.key, key))
        self.assertFalse(leaked, "Undeclared tenant slots in answers:\n  "
                                 + "\n  ".join(sorted(set(leaked))))

    def test_13_show_me_anchors_are_registered(self):
        """Extends the Phase-1 anchor lint to the Coach.

        A `show_me` anchor nobody registers means the point-at button scrolls to
        nothing, which is exactly the "confidently wrong" failure this whole
        registry exists to prevent.
        """
        base = get_module_path('health_learn')
        with open(os.path.join(base, 'static/src/anchors.json'), encoding='utf-8') as fh:
            reg = json.load(fh)
        declared = set(reg['product']) | set(reg['practice'])
        patterns = tuple(reg['pattern'])

        def known(key):
            return key in declared or key.startswith(patterns)

        unknown = []
        for intent in self.Intent.search([]):
            for a in (intent.show_me or '').split(','):
                a = a.strip()
                if a and not known(a):
                    unknown.append('%s show_me=%s' % (intent.key, a))
        for step in self.env['learn.intent.step'].search([]):
            if step.anchor and not known(step.anchor):
                unknown.append('step %s anchor=%s' % (step.id, step.anchor))
        self.assertFalse(unknown, "Coach anchors nothing registers:\n  "
                                  + "\n  ".join(sorted(set(unknown))))

    def test_14_every_screen_maps_to_a_product_action(self):
        """A screen with no action tag can never be detected, so its answers
        can never be offered — a whole screen's content, silently unreachable."""
        orphans = [s.key for s in self.Screen.search([]) if not (s.action_tags or '').strip()]
        self.assertFalse(orphans, "Screens the Coach can never detect: %s" % orphans)

    def test_15_refusals_are_reachable_but_never_advertised(self):
        """Offering "ask me something clinical" invites the exact question the
        Coach exists to decline. It must resolve; it must not be suggested."""
        clinical = self.Intent.search([('key', '=', 'clinical')], limit=1)
        self.assertTrue(clinical, "the clinical refusal is missing")
        self.assertFalse(clinical.offer, "the clinical refusal is advertised")
        self.assertEqual(self.Intent.resolve("is the wound infected", 'carecommand'),
                         'clinical', "the clinical refusal is not reachable")
        for screen in self.Screen.search([]):
            self.assertNotIn(clinical, screen.suggest_ids,
                             "%s suggests the clinical refusal" % screen.key)
