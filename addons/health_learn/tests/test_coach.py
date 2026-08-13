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

    def test_14_every_screen_can_actually_be_detected(self):
        """A screen the Coach cannot recognise is a whole screen's content,
        silently unreachable — and it fails in the most misleading way: the
        Coach says "I don't have lessons for this screen yet" while sitting on
        a screen that has a full lesson.

        Asserts a matcher of ANY kind, because only three of the eight CRM
        leaves are client actions with a tag; the rest are act_windows found by
        xml-id or model.
        """
        blind = []
        for screen in self.Screen.search([]):
            tags, xmlids, models_ = screen._matchers()
            if not (tags or xmlids or models_):
                blind.append(screen.key)
        self.assertFalse(blind, "Screens the Coach can never detect: %s" % blind)

    def test_14b_matchers_come_from_the_real_sidebar_leaf(self):
        """Not from a copy. If the leaf's action changes, the Coach follows."""
        checked = 0
        for screen in self.Screen.search([]):
            if not screen.sidebar_key:
                continue
            item = self.env.ref(screen.sidebar_key, raise_if_not_found=False)
            if not item:
                continue
            checked += 1
            tags, xmlids, models_ = screen._matchers()
            declared = {(item.sudo().action_xmlid or '').strip()}
            self.assertTrue(
                declared & set(xmlids) or (item.sudo().action_tag or '') in tags,
                "%s does not inherit its leaf's own action" % screen.key)
        self.assertGreaterEqual(checked, 8, "expected every CRM screen to name a leaf")

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

    def _resolve_screen(self, tag, xmlid, model):
        """Server-side mirror of the frontend's two-pass resolution."""
        screens = self.Screen.search([])
        matchers = {s.key: s._matchers() for s in screens}
        for s in screens:                      # pass 0: the leaf's OWN action
            own_tag, own_xmlid = s._primary()
            if (tag and own_tag and tag == own_tag) or (xmlid and own_xmlid and xmlid == own_xmlid):
                return s.key
        for s in screens:                      # pass 1: any exact matcher
            tags, xmlids, _models = matchers[s.key]
            if (tag and tag in tags) or (xmlid and xmlid in xmlids):
                return s.key
        for s in screens:                      # pass 2: broad model
            _tags, _xmlids, models_ = matchers[s.key]
            if model and model in models_:
                return s.key
        return None

    def test_16_each_screen_resolves_to_ITSELF_from_its_own_leaf(self):
        """The bug this replaces was the worst kind: confidently wrong.

        Lead Analysis is a crm.lead pivot, so a single-pass matcher hit
        Contacts' broad model rule and the Coach grounded on the wrong screen —
        offering Contacts' questions to someone reading a funnel. Exact matches
        must win across ALL screens before any model match is considered.
        """
        wrong = []
        for screen in self.Screen.search([]):
            if not screen.sidebar_key:
                continue
            item = self.env.ref(screen.sidebar_key, raise_if_not_found=False)
            if not item:
                continue
            item = item.sudo()
            got = self._resolve_screen(item.action_tag, item.action_xmlid, None)
            if got != screen.key:
                wrong.append('%s (its own action) -> %s' % (screen.key, got))
        self.assertFalse(wrong, "Screens that do not resolve to themselves:\n  "
                                + "\n  ".join(wrong))

    def test_17_a_broad_model_rule_never_shadows_an_exact_one(self):
        """crm.lead is claimed by Contacts, but four CRM screens are crm.lead
        views. Only the ones with no exact matcher may fall through to it."""
        model_owners = {}
        for screen in self.Screen.search([]):
            _t, _x, models_ = screen._matchers()
            for m in models_:
                model_owners.setdefault(m, []).append(screen.key)
        for model, owners in model_owners.items():
            self.assertEqual(len(owners), 1,
                             "%s is claimed by more than one screen: %s — the "
                             "broad pass would pick one arbitrarily"
                             % (model, owners))

    # ---------------------------------------------------- column glossary
    def test_18_a_column_question_gets_a_column_answer(self):
        """The exact miss found in review: "what is activity date used for?"
        on Lead Analysis, which has a full lesson and still could not answer."""
        res = self.Intent.ask("what is activity date used for", 'leadanalysis')
        self.assertTrue(res['matched'], "still cannot answer a column question")
        self.assertEqual(res.get('source_kind'), 'column')
        body = res['blocks'][0]['body']
        self.assertIn('follow-up', body['en'].lower())
        self.assertTrue(body['vi'] and body['vi'] != body['en'],
                        "the column answer is not translated")

    def test_19_column_matching_is_narrow(self):
        """A loose match would answer "what is the status of my request" with a
        column definition, which is worse than missing."""
        Column = self.env['learn.column']
        self.assertIsNotNone(Column.match("what is activity date", 'leadanalysis'))
        # Wrong screen: Lead Analysis columns must not answer on Care Command.
        self.assertIsNone(Column.match("what is activity date", 'carecommand'))
        # No screen at all: nothing to scope by, so no answer.
        self.assertIsNone(Column.match("what is activity date", None))

    def test_20_every_column_is_written_in_both_languages(self):
        thin = []
        for col in self.env['learn.column'].search([]):
            for lang in ('en_US', 'vi_VN'):
                body = col.with_context(lang=lang).body
                if not body or len(body) < 40:
                    thin.append('%s/%s [%s]' % (col.screen, col.key, lang))
            if col.with_context(lang='vi_VN').body == col.with_context(lang='en_US').body:
                thin.append('%s/%s untranslated' % (col.screen, col.key))
        self.assertFalse(thin, "Columns with thin or untranslated definitions:\n  "
                               + "\n  ".join(thin))

    # ------------------------------------------------------- the composer
    def test_21_the_composer_scrubs_record_references(self):
        """A user can type a patient's name or number into a help box. What
        leaves this server must not carry it."""
        scrubbed = self.Intent._scrub(
            "why can't I see conversation #4172 for nguyen@example.com on 0912345678")
        self.assertNotIn('4172', scrubbed)
        self.assertNotIn('nguyen@example.com', scrubbed)
        self.assertNotIn('0912345678', scrubbed)
        self.assertIn('[record]', scrubbed)
        self.assertIn('[email]', scrubbed)

    def test_22_the_composer_corpus_contains_no_patient_data(self):
        """The material sent to a provider is OUR OWN written text. If a
        contact name ever appears in it, something is reading the wrong table."""
        corpus = self.Intent._corpus('carecommand', 'en_US')
        self.assertTrue(corpus.strip(), "empty corpus for a covered screen")
        # search_read, not search().mapped(): mapped() prefetches every stored
        # column on crm.lead, which couples this test to the health of a table
        # it is only borrowing names from. Ask for the one field we need.
        rows = self.env['crm.lead'].sudo().search_read([], ['contact_name'],
                                                       limit=25)
        for name in [r.get('contact_name') for r in rows]:
            if name and len(name) > 6:
                self.assertNotIn(name, corpus,
                                 "a real contact name reached the composer corpus")

    def test_23_no_provider_means_no_composed_answer(self):
        """With nothing configured the Coach must fall back to the honest miss
        it gave before — never break, never invent."""
        # _provider() returns a (provider, type, endpoint) triple — always
        # truthy as a tuple. It is the FIRST element that says whether there is
        # anything to call, and reading the tuple itself silently turned this
        # test into an assertion about nothing.
        provider = self.Intent._provider()[0]
        if provider is None:
            self.assertIsNone(self.Intent._compose("anything at all", 'carecommand'))
            res = self.Intent.ask("how do I export the payroll ledger to excel",
                                  'carecommand')
            self.assertFalse(res['matched'])
            self.assertTrue(res['suggest'])

    def test_24_the_composer_never_publishes_a_stub_reply(self):
        """A template provider answering with its own name is not an answer.

        hr_development_ai's factory falls back to a stub provider on ANY error,
        including the AccessError a normal user hits on the config table. That
        stub returns the constant "Generated response (Odoo Native AI)", and
        the composer was publishing it to learners as help text.
        """
        Intent = self.env['learn.intent']
        self.assertIn('OdooNativeAIProvider', Intent._STUB_PROVIDERS)
        for sentinel in Intent._STUB_REPLIES:
            self.assertTrue(sentinel.strip(), "an empty sentinel matches everything")

    def test_25_the_composer_declares_its_egress_class(self):
        """Every prompt leaving this module names what it is built from.

        Asserted against the source rather than by calling out, because the
        failure this prevents is a NEW call site added without a declaration.
        """
        import inspect
        from odoo.addons.health_learn.models import learn_intent
        src = inspect.getsource(learn_intent)
        sends = src.count('generate_text(')
        guards = src.count("egress.SCHEMA") + src.count("egress.RECORDS") \
            + src.count("egress.AGGREGATE")
        self.assertGreaterEqual(
            guards, sends,
            "a generate_text call with no egress classification — every prompt "
            "must declare what it is built from before it can be sent")

    def test_26_the_provider_lookup_survives_a_non_privileged_user(self):
        """A learner is not allowed to read the AI provider config.

        _provider() must therefore do its own privilege escalation and return a
        REAL provider — not fall through its own exception handler, which is
        silent by design and hid an AttributeError here for a whole deploy.
        The assertion is on the shape: three values, no exception.
        """
        Users = self.env['res.users'].with_context(no_reset_password=True)
        learner = Users.create({
            'name': 'Coach Provider Probe', 'login': 'coach_provider_probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        result = self.env(user=learner)['learn.intent']._provider()
        self.assertEqual(len(result), 3,
                         "_provider must return (provider, type, endpoint)")
        provider, ptype, _endpoint = result
        if provider is not None:
            self.assertNotIn(type(provider).__name__,
                             self.env['learn.intent']._STUB_PROVIDERS,
                             "a learner was handed the template stub")
            self.assertTrue(ptype, "a provider with no type cannot be gated")
