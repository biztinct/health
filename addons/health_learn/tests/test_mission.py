# -*- coding: utf-8 -*-
"""Practice missions.

The structural invariants live here rather than in ORM constraints, because a
data file creates a step before its options exist — a constraint would fire on
content that is correct but not yet fully loaded. These see the finished data.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

TOKEN_RE = re.compile(r"\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}")


@tagged('post_install', '-at_install')
class TestMission(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Mission = cls.env['learn.mission']
        cls.missions = cls.Mission.search([])
        cls.full = cls.missions.filtered(lambda m: m.kind == 'full')

    def test_01_flagship_missions_exist(self):
        self.assertTrue(self.missions, "no missions shipped")
        self.assertGreaterEqual(len(self.full), 2,
                                "fewer than two full missions — the roadmap ships M1 and M2")

    def test_02_every_decision_has_exactly_one_right_answer(self):
        bad = []
        for m in self.full:
            for step in m.step_ids.filtered('is_decision'):
                right = step.option_ids.filtered('is_correct')
                if len(step.option_ids) < 2:
                    bad.append('%s/%s: %d options' % (m.key, step.key, len(step.option_ids)))
                if len(right) != 1:
                    bad.append('%s/%s: %d correct' % (m.key, step.key, len(right)))
        self.assertFalse(bad, "\n  ".join(bad))

    def test_03_every_wrong_option_recovers_in_both_languages(self):
        """A wrong choice met with silence is a rejection.

        Checked in both languages: a recovery that exists only in English
        rejects the Vietnamese reader, which is the harder failure to notice.
        """
        bad = []
        for m in self.full:
            for step in m.step_ids:
                for opt in step.option_ids.filtered(lambda o: not o.is_correct):
                    for lang in ('en_US', 'vi_VN'):
                        text = opt.with_context(lang=lang).recovery
                        if not (text or '').strip():
                            bad.append('%s/%s/%s [%s]' % (m.key, step.key, opt.key, lang))
        self.assertFalse(bad, "Wrong options with no way back:\n  " + "\n  ".join(bad))

    def test_04_full_missions_intercept_their_risky_step(self):
        """The consequence card is the mission's whole reason for existing on a
        practice surface: the learner meets the cost BEFORE the action."""
        for m in self.full:
            self.assertTrue(m.step_ids.filtered('is_consequence'),
                            "%s has no intercepted step" % m.key)
            for f in ('consequence_title', 'consequence_scope',
                      'consequence_reversible', 'consequence_verify'):
                self.assertTrue((m[f] or '').strip(),
                                "%s consequence card is missing %s" % (m.key, f))

    def test_05_full_missions_seed_exactly_one_anomaly(self):
        for m in self.full:
            self.assertTrue((m.anomaly_title or '').strip(), "%s has no anomaly title" % m.key)
            self.assertTrue((m.anomaly_body or '').strip(), "%s has no anomaly" % m.key)

    def test_06_full_missions_end_on_an_undo(self):
        """Reversibility is taught by DOING it once, not by being told."""
        for m in self.full:
            self.assertTrue(m.step_ids.filtered('is_undo'),
                            "%s never demonstrates the reversal" % m.key)

    def test_07_debrief_has_both_halves(self):
        for m in self.full:
            self.assertTrue(m.note_ids.filtered(lambda n: n.kind == 'did'),
                            "%s debrief does not say what you did" % m.key)
            self.assertTrue(m.note_ids.filtered(lambda n: n.kind == 'check'),
                            "%s debrief has no before-you-do-this-for-real list" % m.key)

    def test_08_every_target_is_a_registered_anchor(self):
        base = get_module_path('health_learn')
        with open(os.path.join(base, 'static/src/anchors.json'), encoding='utf-8') as fh:
            reg = json.load(fh)
        declared = set(reg['product']) | set(reg['practice'])
        patterns = tuple(reg['pattern'])
        unknown = []
        for step in self.env['learn.mission.step'].search([]):
            t = (step.target or '').strip()
            if t and t not in declared and not t.startswith(patterns):
                unknown.append('%s/%s -> %s' % (step.mission_id.key, step.key, t))
        self.assertFalse(unknown, "Mission steps pointing at unregistered anchors:\n  "
                                  + "\n  ".join(unknown))

    def test_09_no_unresolved_tokens(self):
        tokens = self.env['learn.tenant.override'].resolved_tokens()
        leaked = []
        for lang in ('en_US', 'vi_VN'):
            for m in self.Mission.with_context(lang=lang).search([]):
                blobs = [m.summary, m.outline_note, m.consequence_scope,
                         m.consequence_verify, m.anomaly_body]
                blobs += [s.instruction for s in m.step_ids]
                blobs += [s.detail for s in m.step_ids]
                blobs += [s.hint for s in m.step_ids]
                blobs += [n.body for n in m.note_ids]
                for o in self.env['learn.mission.option'].with_context(lang=lang).search(
                        [('step_id.mission_id', '=', m.id)]):
                    blobs += [o.label, o.recovery]
                for b in blobs:
                    for key in TOKEN_RE.findall(b or ''):
                        if key not in tokens:
                            leaked.append('%s [%s] {{%s}}' % (m.key, lang, key))
        self.assertFalse(leaked, "Undeclared slots in mission content:\n  "
                                 + "\n  ".join(sorted(set(leaked))))

    def test_10_a_recovery_scores_lower_than_a_clean_run(self):
        """Without this asymmetry, 'confidence' only measures completion —
        which the learner can already see as a tick."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        base = self.env.ref('base.group_user').id
        clean = Users.create({'name': 'Clean Run', 'login': 'mission_clean_test',
                              'group_ids': [(6, 0, [base])]})
        messy = Users.create({'name': 'Messy Run', 'login': 'mission_messy_test',
                              'group_ids': [(6, 0, [base])]})
        m = self.full[0]

        got_clean = self.env(user=clean)['learn.confidence'].award(m.key, False)
        got_messy = self.env(user=messy)['learn.confidence'].award(m.key, True)
        self.assertGreater(got_clean, got_messy,
                           "being talked out of a mistake scores the same as never making it")
        self.assertEqual(self.env(user=clean)['learn.confidence'].my_scores()[m.confidence_key],
                         got_clean)
        # And one learner's score is invisible to another.
        self.assertNotIn(m.confidence_key,
                         {k: v for k, v in
                          self.env(user=messy)['learn.confidence'].my_scores().items()
                          if v == got_clean})

    def test_11_mission_progress_is_namespaced(self):
        """Missions and stations share one progress map, so the frontend has one
        shape to read. The `mission:` prefix is what keeps them apart."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        user = Users.create({'name': 'Prog Run', 'login': 'mission_prog_test',
                             'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        env = self.env(user=user)
        m = self.full[0]
        self.assertTrue(env['learn.progress'].record('mission:' + m.key, {'state': 'done'}))
        self.assertEqual(env['learn.progress'].my_progress()['mission:' + m.key]['state'], 'done')
        # An unknown mission is refused rather than silently creating a row.
        self.assertFalse(env['learn.progress'].record('mission:not_a_mission', {'state': 'done'}))

    def test_12_missions_never_call_a_product_method(self):
        """A practice surface whose actions have real consequences is not a
        practice surface. The mission runner may only touch learner state."""
        path = os.path.join(get_module_path('health_learn'),
                            'static/src/journey/journey.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        calls = set(re.findall(r'orm\.call\(\s*"([a-z_.]+)"', src))
        allowed = {'learn.station', 'learn.progress', 'learn.event', 'learn.confidence'}
        self.assertFalse(calls - allowed,
                         "The Journey calls models outside the learning spine: %s"
                         % (calls - allowed))
