# -*- coding: utf-8 -*-
"""The anchor lint.

Run as an Odoo test rather than a bespoke CI script, deliberately: it then
executes in the harness this repo already runs, so it cannot quietly stop
running the way a separate script does after the first person forgets it.

Three directions, because a one-way check rots from the other side:

 1. every registered anchor exists where the registry says it does
 2. every anchor the CONTENT names is registered
 3. every ``data-a`` found in a scanned file is registered

(3) is the one that catches a typo: an unregistered anchor is nearly always a
misspelling of a real one, and without this direction it just silently points
at nothing.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

DATA_A_RE = re.compile(r'data-a="([^"{}#]+)"')
ATTF_RE = re.compile(r't-attf-data-a="([^"]*)"')
# Comments describe anchors as often as code declares them — this file's own
# header says data-a="…". Strip commentary before scanning, or the lint fails
# on prose about itself.
JS_COMMENT_RE = re.compile(r'/\*.*?\*/|(?<!:)//[^\n]*', re.S)
XML_COMMENT_RE = re.compile(r'<!--.*?-->', re.S)


def _read(module_and_path):
    module, _, rel = module_and_path.partition('/')
    base = get_module_path(module)
    if not base:
        return None
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestAnchorRegistry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        raw = _read('health_learn/static/src/anchors.json')
        cls.registry_json = json.loads(raw)
        cls.product = cls.registry_json['product']
        cls.patterns = cls.registry_json['pattern']
        cls.practice = cls.registry_json['practice']
        cls.scan = cls.registry_json['scan']

    # -- helpers ---------------------------------------------------------
    def _all_declared(self):
        return set(self.product) | set(self.practice)

    def _matches_pattern(self, key):
        return any(key.startswith(p) for p in self.patterns)

    # -- 1. every registered anchor exists where it says it does ----------
    def test_01_product_anchors_exist_in_templates(self):
        missing = []
        for key, spec in self.product.items():
            text = _read(spec['file'])
            if text is None:
                missing.append('%s -> file not found: %s' % (key, spec['file']))
            elif 'data-a="%s"' % key not in text:
                missing.append('%s -> not in %s' % (key, spec['file']))
        self.assertFalse(missing, "Registered anchors the product template no longer has.\n"
                                  "A control was renamed or removed and the content still "
                                  "points at it:\n  " + "\n  ".join(missing))

    def test_02_pattern_anchors_are_emitted(self):
        missing = []
        for prefix, spec in self.patterns.items():
            text = _read(spec['file'])
            if text is None:
                missing.append('%s -> file not found: %s' % (prefix, spec['file']))
                continue
            emitted = ATTF_RE.findall(text)
            if not any(e.startswith(prefix) for e in emitted):
                missing.append('%s -> no t-attf-data-a emits it in %s' % (prefix, spec['file']))
        self.assertFalse(missing, "Pattern anchors nothing emits:\n  " + "\n  ".join(missing))

    def test_03_practice_anchors_exist_in_replica(self):
        blob = "".join(_read(f) or "" for f in self.scan['replica'])
        missing = [k for k in self.practice if '"%s"' % k not in blob and k not in blob]
        self.assertFalse(missing, "Practice-only anchors the replica no longer draws:\n  "
                                  + "\n  ".join(missing))

    # -- 2. every anchor the content names is registered ------------------
    def test_04_content_anchors_are_registered(self):
        declared = self._all_declared()
        unknown = []
        for step in self.env['learn.step'].sudo().search([]):
            for key in (step.anchor, step.moment_from, step.moment_to):
                if key and key not in declared and not self._matches_pattern(key):
                    unknown.append('%s (lesson %s step %s)'
                                   % (key, step.lesson_id.key, step.sequence))
        self.assertFalse(unknown, "Content points at anchors nothing registers:\n  "
                                  + "\n  ".join(sorted(set(unknown))))

    # -- 3. every anchor in a scanned file is registered -------------------
    def test_05_no_stray_anchors(self):
        declared = self._all_declared()
        stray = []
        for rel in self.scan['templates'] + self.scan['replica']:
            text = _read(rel)
            if text is None:
                continue
            text = XML_COMMENT_RE.sub('', JS_COMMENT_RE.sub('', text))
            for key in DATA_A_RE.findall(text):
                # Skip the replica's template-literal interpolations — those
                # are fixture-driven and land as pattern keys at runtime.
                if '$' in key:
                    continue
                if key not in declared and not self._matches_pattern(key):
                    stray.append('%s in %s' % (key, rel))
        self.assertFalse(stray, "Anchors in a template that the registry does not declare. "
                                "Usually a typo of a real one:\n  " + "\n  ".join(sorted(set(stray))))
