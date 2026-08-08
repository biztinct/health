# -*- coding: utf-8 -*-
"""Guards on the shipped frontend assets.

These check the SOURCE for hazards that only appear after Odoo's asset
pipeline has run — the class of bug you cannot see in development and cannot
see in a code review either.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

# `${...}` followed by a literal space. The minifier eats that space, inside
# template literals included.
BRACE_SPACE_RE = re.compile(r"\$\{[^{}]*\}[ ]+(?=\S)")

JS_DIRS = ('static/src/engine', 'static/src/journey')


@tagged('post_install', '-at_install')
class TestAssets(TransactionCase):

    def _js_files(self):
        base = get_module_path('health_learn')
        for rel in JS_DIRS:
            folder = os.path.join(base, rel)
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder)):
                if name.endswith('.js'):
                    yield os.path.join(rel, name), os.path.join(folder, name)

    def test_01_no_space_after_a_closing_interpolation(self):
        """Odoo's JS minifier deletes whitespace directly after `}`.

        Measured on UAT: `${esc(T("fullLesson"))} · ${mins} ${esc(T("min"))}`
        arrives in the browser as "Full lesson· 7min". The non-minified bundle
        is correct, so this is invisible in development — which is exactly why
        it needs a test rather than a code-review habit.

        The fix is to put the space in its own interpolation: `${" "}`.
        """
        offenders = []
        for rel, path in self._js_files():
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            for m in BRACE_SPACE_RE.finditer(src):
                line = src[:m.start()].count('\n') + 1
                offenders.append('%s:%d  %s' % (rel, line, m.group(0).strip()[-40:]))
        self.assertFalse(offenders,
                         "%d place(s) where the minifier will silently delete a space. "
                         "Write `}${\" \"}` instead:\n  %s"
                         % (len(offenders), "\n  ".join(offenders[:25])))

    def test_02_every_icon_referenced_exists_in_the_sprite(self):
        """A missing symbol renders as nothing at all — no error, no fallback,
        just a label with a gap where its icon should be."""
        base = get_module_path('health_learn')
        with open(os.path.join(base, 'static/src/journey/icons.xml'), encoding='utf-8') as fh:
            sprite = fh.read()
        available = set(re.findall(r'symbol id="lrn-i-([a-z0-9-]+)"', sprite))
        self.assertTrue(available, "the icon sprite is empty")

        used = set()
        for _rel, path in self._js_files():
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            used |= set(re.findall(r'\bic\("([a-z0-9-]+)"', src))
            # block(icon, ...) and the other helpers that take a bare name
            used |= set(re.findall(r'\bblock\("([a-z0-9-]+)"', src))
        for tmpl in ('static/src/journey/journey.xml',):
            with open(os.path.join(base, tmpl), encoding='utf-8') as fh:
                used |= set(re.findall(r'href="#lrn-i-([a-z0-9-]+)"', fh.read()))

        missing = sorted(used - available)
        self.assertFalse(missing, "Icons referenced but not in the sprite: %s" % missing)
