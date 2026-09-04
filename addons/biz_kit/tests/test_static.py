# -*- coding: utf-8 -*-
"""What has to be true of the kit's own source, read as text.

Every gate here catches a habit that produces a BROKEN SCREEN WITH A CLEAN
SERVER LOG — the class of failure nothing else in this repository notices. A
running test never renders a stylesheet or parses a template, so the only place
these can be caught is the file itself.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_ROOT = None


def _src(*parts):
    global _ROOT
    if _ROOT is None:
        _ROOT = get_module_path('biz_kit')
    with open(os.path.join(_ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


#: Two adjacent string literals across a newline. A Python habit, a JavaScript
#: SyntaxError, and the asset pipeline concatenates without ever parsing — so
#: one of these blanks the whole backend bundle for every user, silently.
_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")

#: The words no user-visible string in a shared module may contain. The
#: framework's own name is in the list for the white-label rule; it is allowed
#: in an import and in a comment, which is why the scans below strip both.
BANNED = ('Payobook', 'payobook', 'Viet Uc', 'Việt Úc', 'health_', 'Odoo',
          'odoo.com')

#: Technical identifiers that legitimately contain the framework's name.
ALLOWED = ('@odoo-module', '@odoo/owl', 'from odoo', 'import odoo', 'odoo.',
           'odoo-bin', '/odoo/')

JS = ('kit_icons.js', 'kit_nav.js', 'kit_registries.js')
SCSS = ('kit_tokens.scss', 'kit.scss', 'kit_modal.scss')


def _strip_js_comments(src):
    src = re.sub(r'/\*(?:.|\n)*?\*/', '', src)
    return '\n'.join(l for l in src.split('\n')
                     if not l.lstrip().startswith('//'))


@tagged('post_install', '-at_install')
class TestTheKitIsProductNeutral(TransactionCase):
    """T1 — nothing in here may name a product, or reach for one.

    A shared module that imports a product module cannot be lifted into the
    next product, which is the only reason it was made shared.
    """

    def test_no_source_file_mentions_a_product_module(self):
        """No `pb_*` module, no `pb.*` model, no old token prefix — anywhere,
        comments included. This is the rename's own proof."""
        needles = ('pbim', 'pbva', 'pb_import_kit', 'pb_hub', 'pb_settings',
                   'pb_sidebar', 'pb.sidebar', 'pb.role', 'pb.access',
                   'pb_access', 'pb_lens')
        for name in JS + SCSS:
            parts = (('static', 'src', 'js', name) if name.endswith('.js')
                     else ('static', 'src', 'scss', name))
            src = _src(*parts)
            for needle in needles:
                self.assertNotIn(
                    needle, src, '%s still mentions "%s"' % (name, needle))
        src = _src('static', 'src', 'xml', 'kit_nav.xml')
        for needle in needles:
            self.assertNotIn(needle, src)

    def test_no_user_visible_string_names_a_product(self):
        for name in JS:
            src = _strip_js_comments(_src('static', 'src', 'js', name))
            for allowed in ALLOWED:
                src = src.replace(allowed, '')
            for banned in BANNED:
                self.assertNotIn(
                    banned, src, '%s names "%s"' % (name, banned))

    def test_the_template_names_no_product(self):
        src = re.sub(r'<!--(?:.|\n)*?-->', '',
                     _src('static', 'src', 'xml', 'kit_nav.xml'))
        for banned in BANNED:
            self.assertNotIn(banned, src)

    def test_the_manifest_reads_as_a_product_agnostic_module(self):
        manifest = _src('__manifest__.py')
        for banned in ('Payobook', 'Viet Uc', 'Việt Úc', 'health_'):
            self.assertNotIn(banned, manifest)


@tagged('post_install', '-at_install')
class TestTheBrandOverrideReachesEveryBrandToken(TransactionCase):
    """T2 — a product must be able to re-tint the kit without forking it.

    The whole indirection is one line per brand colour in `bzk-root-vars`. Miss
    one and the product's palette applies to eight things and not the ninth,
    which is a screen that is ALMOST re-tinted — the hardest kind of wrong to
    see and the easiest to ship.
    """

    #: Every token a product is allowed to override, by the name it overrides
    #: it with. `--bzk-sky` deliberately reads the same override as `soft2`:
    #: they are one colour with two names in the primitives.
    BRAND = {
        '--bzk-primary': '--bzk-brand-primary',
        '--bzk-primary-hover': '--bzk-brand-primary-hover',
        '--bzk-primary-strong': '--bzk-brand-primary-strong',
        '--bzk-primary-light': '--bzk-brand-primary-light',
        '--bzk-primary-dark': '--bzk-brand-primary-dark',
        '--bzk-ink': '--bzk-brand-ink',
        '--bzk-soft': '--bzk-brand-soft',
        '--bzk-soft2': '--bzk-brand-soft2',
        '--bzk-sky': '--bzk-brand-soft2',
        '--bzk-ring': '--bzk-brand-ring',
    }

    def test_every_brand_token_reads_an_override_first(self):
        src = _src('static', 'src', 'scss', 'kit_tokens.scss')
        block = src.split('@mixin bzk-root-vars', 1)[1]
        for token, override in self.BRAND.items():
            line = next(
                (l for l in block.split('\n')
                 if l.strip().startswith('%s:' % token)), None)
            self.assertTrue(
                line, '%s is not declared in bzk-root-vars at all' % token)
            self.assertIn(
                'var(%s,' % override, line,
                '%s does not read the %s override, so a product that sets it '
                'would see no change' % (token, override))

    def test_no_rule_paints_a_brand_colour_from_the_sass_variable(self):
        """A property written against `$bzk-primary` is compiled with the
        default baked in, and the product's override never reaches it. The
        Sass variables exist only to seed the custom properties."""
        brand = ('primary', 'primary-hover', 'primary-strong', 'primary-light',
                 'primary-dark', 'ink', 'soft', 'soft2', 'sky', 'ring')
        pattern = re.compile(r':[^;{}\n]*\$bzk-(%s)\b' % '|'.join(brand))
        for name in ('kit.scss', 'kit_modal.scss'):
            src = _src('static', 'src', 'scss', name)
            hits = [l.strip() for l in src.split('\n') if pattern.search(l)]
            self.assertFalse(
                hits, '%s paints a brand colour from a Sass variable: %s'
                      % (name, hits[:3]))


@tagged('post_install', '-at_install')
class TestTheSourceGates(TransactionCase):
    """T3 — the habits that break a bundle without an error."""

    def test_no_python_style_implicit_string_concatenation(self):
        for name in JS:
            src = _src('static', 'src', 'js', name)
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(src),
                '%s has two adjacent string literals across a newline — a '
                'JavaScript SyntaxError that blanks the whole bundle' % name)

    def test_no_reserved_owl_name_is_used_as_a_loop_variable(self):
        """`t-as="lt"` compiles the loop variable into the generated function
        as a bare `<`, and the template dies pointing at itself."""
        reserved = {'lt', 'gt', 'lte', 'gte', 'and', 'or', 'not', 'in'}
        src = _src('static', 'src', 'xml', 'kit_nav.xml')
        for name in re.findall(r't-as="(\w+)"', src):
            self.assertNotIn(name, reserved)

    def _registry_keys(self):
        src = _src('static', 'src', 'js', 'kit_icons.js')
        body = src.split('export const IC = {', 1)[1].split('\n};', 1)[0]
        return set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'", body, re.M))

    def test_every_icon_the_kit_itself_draws_is_in_the_registry(self):
        """`ic()` falls back to a circle for an unknown name, so a typo is a
        wrong picture rather than an error."""
        known = self._registry_keys()
        self.assertIn('back', known, 'the icon registry did not parse')
        self.assertIn('circle', known,
                      'the fallback glyph itself has to be in the set')
        used = set(re.findall(r"ic\('([A-Za-z0-9_]+)'",
                              _src('static', 'src', 'xml', 'kit_nav.xml')))
        for name in used:
            self.assertIn(name, known)

    def test_the_registry_parses_and_every_glyph_is_a_path(self):
        """A key whose value is not SVG markup renders an empty square, which
        looks like a missing icon and is not one."""
        src = _src('static', 'src', 'js', 'kit_icons.js')
        body = src.split('export const IC = {', 1)[1].split('\n};', 1)[0]
        rows = re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'(.*)',\s*$",
                          body, re.M)
        self.assertGreater(len(rows), 90, 'the icon set did not parse')
        for key, markup in rows:
            self.assertTrue(
                markup.startswith('<') and markup.endswith('>'),
                'the "%s" glyph is not SVG markup' % key)

    def test_an_unknown_icon_name_falls_back_rather_than_failing(self):
        """The fallback is the contract the mini rail relies on: a name this
        registry has never heard of draws a plain circle, not an exception."""
        src = _src('static', 'src', 'js', 'kit_icons.js')
        fn = src.split('export function ic(', 1)[1]
        self.assertIn('IC[n] ||', fn,
                      'ic() no longer falls back for an unknown name')

    def test_the_back_chip_can_never_be_a_dead_control(self):
        """`hubBack()` never returns null: the caller's door, else the
        product's home, else the browser's own back."""
        src = _src('static', 'src', 'js', 'kit_nav.js')
        block = src.split('export function hubBack(', 1)[1].split(
            '\nexport class', 1)[0]
        self.assertIn('homeAction()', block)
        self.assertIn('history: true', block)
        self.assertNotIn('return null', block)
