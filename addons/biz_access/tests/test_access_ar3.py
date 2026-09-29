# -*- coding: utf-8 -*-
"""ACCESS AR-3, the generic half — the Access home can be read in Vietnamese.

  * T4  no user-visible sentence on the Access home is English glued around a
        value. `'Give a role to ' + name` is untranslatable twice over: the
        pieces are not strings any extractor reads, and Vietnamese does not put
        the name where English does. Asserted at the SOURCE, in the style of
        the other source gates, because a browser test cannot run on this
        server (ledger §5.222).
  *     the area words are the APPLICATION's, so their translation comes from
        the application's catalogue: `area_label` asks the module that
        registered the label, never this one (which has no product words).
  *     this module's own catalogue loads: the headline of the board and a
        template string, in Vietnamese.
"""
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_open
from odoo.tools.translate import LazyTranslate, code_translations

from odoo.addons.biz_access.models import access_common

TEMPLATES = ('biz_access/static/src/xml/access_board.xml',
             'biz_access/static/src/xml/mini_rail.xml')
SCRIPTS = ('biz_access/static/src/js/access_board.js',
           'biz_access/static/src/js/mini_rail.js',
           'biz_access/static/src/js/access_palette.js')

#: A template expression. Class and style attributes are layout, not words.
EXPR_RE = re.compile(
    r'\bt-(?:esc|out|att-(?!class|style)[\w-]+)="([^"]*)"')
#: A quoted piece that reads as English prose: a word and a space, or a
#: capitalised word. `'true'`, `'img'`, `'is-on'` are values, not words.
WORDY = (r"'(?:[^'\\]|\\.)*[A-Za-z]{2,}(?:[^'\\]|\\.)*\s(?:[^'\\]|\\.)*'"
         r"|'\s*[A-Z][a-z]+(?:[^'\\]|\\.)*'")
GLUED_RE = re.compile(r'(?:%s)\s*\+|\+\s*(?:%s)' % (WORDY, WORDY))
#: A ternary choosing between two English sentences inside the template.
TERNARY_RE = re.compile(r"\?\s*(?:%s)\s*:\s*(?:%s)" % (WORDY, WORDY))
COMMENT_RE = re.compile(r'<!--.*?-->', re.S)
JS_COMMENT_RE = re.compile(r'/\*.*?\*/|(?<![:"\'])//[^\n]*', re.S)


def _read(path):
    with file_open(path) as fh:
        return fh.read()


def _calls(src, name='_t'):
    """(start, end) of every `_t(...)` call, balanced on parentheses and
    aware of quoted strings."""
    out = []
    for m in re.finditer(r'(?<![\w.])%s\(' % re.escape(name), src):
        depth, i, quote = 0, m.end() - 1, None
        while i < len(src):
            ch = src[i]
            if quote:
                if ch == '\\':
                    i += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in '"\'`':
                quote = ch
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    out.append((m.start(), i + 1))
                    break
            i += 1
    return out


@tagged('post_install', '-at_install')
class TestAr3Generic(TransactionCase):

    # ------------------------------------------------------------------ T4
    def test_01_no_template_sentence_is_glued_around_a_value(self):
        bad = []
        for path in TEMPLATES:
            text = COMMENT_RE.sub('', _read(path))
            for expr in EXPR_RE.findall(text):
                expr = expr.replace('&apos;', "'").replace('&quot;', '"')
                if GLUED_RE.search(expr) or TERNARY_RE.search(expr):
                    bad.append('%s: %s' % (path.rsplit('/', 1)[-1], expr[:90]))
        self.assertFalse(bad, 'English glued around a value in a template '
                              '(make it one _t() sentence with a %s):\n  '
                              + '\n  '.join(bad))

    def test_02_no_script_glues_a_translation_to_a_value(self):
        """`_t("…") + name` or `name + _t("…")`. A `_t("a " + "b")` whose
        pieces are all literals is ONE string to the extractor and is fine."""
        bad = []
        for path in SCRIPTS:
            src = JS_COMMENT_RE.sub('', _read(path))
            for start, end in _calls(src):
                after = src[end:end + 40].lstrip()
                before = src[max(0, start - 40):start].rstrip()
                if after.startswith('+') or before.endswith('+'):
                    line = src.count('\n', 0, start) + 1
                    bad.append('%s:%s %s' % (path.rsplit('/', 1)[-1], line,
                                             src[start:end][:70]))
        self.assertFalse(bad, 'a translation glued to a value:\n  '
                              + '\n  '.join(bad))

    # ------------------------------------------------ the application's words
    def test_03_area_words_come_from_the_registering_module(self):
        """A label registered as a lazy translation is translated from the
        module that made it — here this module's own, standing in for an
        application's — and stays English for an English reader."""
        saved = (list(access_common._AREAS), dict(access_common._AREA_MODULES))
        try:
            probe = LazyTranslate('biz_access')('Access')
            access_common.register_areas([('zz_ar3_probe', probe)])
            self.assertIn(('zz_ar3_probe', 'Access'),
                          access_common.profile_areas(),
                          'the registry keeps the English source')
            vi = self.env(context={'lang': 'vi_VN'})
            en = self.env(context={'lang': 'en_US'})
            self.assertEqual(access_common.area_label('zz_ar3_probe', en),
                             'Access')
            source = 'No roles have been written down yet.'
            probe = LazyTranslate('biz_access')(source)
            access_common._AREAS[:] = [a for a in access_common._AREAS
                                       if a[0] != 'zz_ar3_probe']
            access_common.register_areas([('zz_ar3_probe', probe)])
            expected = code_translations.get_python_translations(
                'biz_access', 'vi_VN').get(source)
            if not expected:
                self.skipTest('no Vietnamese catalogue loaded for biz_access')
            self.assertEqual(access_common.area_label('zz_ar3_probe', vi),
                             expected)
            labels = dict(access_common.area_selection(vi))
            self.assertEqual(labels['zz_ar3_probe'], expected)
        finally:
            access_common._AREAS[:] = saved[0]
            access_common._AREA_MODULES.clear()
            access_common._AREA_MODULES.update(saved[1])

    # ------------------------------------------------------- the catalogue
    def test_04_the_board_speaks_vietnamese(self):
        if not self.env['res.lang'].search_count(
                [('code', '=', 'vi_VN'), ('active', '=', True)]):
            self.skipTest('Vietnamese is not active on this database')
        py = code_translations.get_python_translations('biz_access', 'vi_VN')
        web = code_translations.get_web_translations('biz_access', 'vi_VN')
        self.assertIn('No roles have been written down yet.', py)
        self.assertNotEqual(py['No roles have been written down yet.'],
                            'No roles have been written down yet.')
        sources = {m['id'] for m in web['messages']}
        for source in ('See it as', 'Hand my access over',
                       'Give a role to %s', 'The whole %s block'):
            self.assertIn(source, sources,
                          '%r is not in the Vietnamese web catalogue' % source)
