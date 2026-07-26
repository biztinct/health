# -*- coding: utf-8 -*-
"""Phase GB — the shared guard on this repo's Vietnamese catalogues.

Three separate things have each, on their own, shipped a catalogue that
installed cleanly and translated nothing:

  §5.58  no ``#. odoo-python`` / ``#. odoo-javascript`` marker
  §5.67  no ``#:`` occurrence line — ``PoFileReader`` yields one row per
         occurrence and has no fallback, so the entry produces zero rows
  GB     a filename that is not a language code, so ``get_po_paths()`` never
         yields the file at all (health_pwa/i18n/viVNpo.po, 146 translations,
         dead from the day it landed)

Each is invisible in review and invisible at install. Only a test that reads
the file the way Odoo reads it, or loads it the way Odoo loads it, catches
any of them — which is why this lives here, in the module every clinical
addon sits on top of, and walks the whole repo rather than one module.
"""
import os
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import code_translations, get_base_langs

HEADER = 'Content-Type'
OUR_PREFIXES = ('health_', 'biz_')


def _addons_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _our_catalogues():
    """[(module, filename, path)] for every .po our own modules ship."""
    root = _addons_dir()
    out = []
    for mod in sorted(os.listdir(root)):
        if not mod.startswith(OUR_PREFIXES):
            continue
        i18n = os.path.join(root, mod, 'i18n')
        if not os.path.isdir(i18n):
            continue
        for fn in sorted(os.listdir(i18n)):
            if fn.endswith('.po'):
                out.append((mod, fn, os.path.join(i18n, fn)))
    return out


def _blocks(path):
    """Entry blocks, skipping the header and obsolete (#~) entries."""
    text = open(path, encoding='utf-8').read()
    for block in text.split('\n\n'):
        if not re.search(r'^msgid ', block, re.M) or HEADER in block:
            continue
        if re.search(r'^#~', block, re.M):
            continue
        yield block


_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\'}


def _field(block, keyword):
    """The unescaped value of msgid/msgstr, continuation lines included.

    Both details matter and both bit on the first run of this test: a msgid
    written across several quoted lines reads as empty to a naive
    `^msgid "(.+)"$`, and one containing \\" reads with the backslashes still
    in it — neither form then matches what the loader keyed on, so a perfectly
    good entry looks like it failed to load.
    """
    m = re.search(r'^%s ((?:"(?:[^"\\]|\\.)*"\s*?\n?)+)' % keyword, block, re.M)
    if not m:
        return None
    joined = ''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))
    return re.sub(r'\\(.)', lambda x: _ESCAPES.get(x.group(1), x.group(1)),
                  joined)


@tagged('post_install', '-at_install')
class TestI18nCatalogueShape(TransactionCase):
    """G1 — the file shape Odoo's reader actually requires."""

    def test_g1_every_entry_carries_module_and_occurrence(self):
        """No entry may be missing `#. module:` or `#: ` (§5.67)."""
        bad = []
        for mod, fn, path in _our_catalogues():
            for block in _blocks(path):
                first = block.strip().split('\n')[0][:70]
                if not re.search(r'^#\. module: ', block, re.M):
                    bad.append(f'{mod}/{fn}: no `#. module:` — {first}')
                if not re.search(r'^#: ', block, re.M):
                    bad.append(f'{mod}/{fn}: no `#:` occurrence — {first}')
        self.assertFalse(bad, 'inert catalogue entries:\n' + '\n'.join(bad[:40]))

    def test_g1b_code_marker_implies_code_occurrence(self):
        """A code marker without a `code:` occurrence translates nothing.

        The pair is what makes a `_()` string reachable: the marker decides
        which of python/web translations it lands in (§5.58), the occurrence
        decides whether it is read at all (§5.67). One without the other is
        the failure both entries describe.
        """
        bad = []
        for mod, fn, path in _our_catalogues():
            for block in _blocks(path):
                if not re.search(r'^#\. odoo-(python|javascript)', block, re.M):
                    continue
                if not re.search(r'^#: code:addons/%s/' % re.escape(mod),
                                 block, re.M):
                    first = block.strip().split('\n')[0][:70]
                    bad.append(f'{mod}/{fn}: marker without code occurrence '
                               f'— {first}')
        self.assertFalse(bad, 'markers that reach nothing:\n' + '\n'.join(bad[:40]))

    def test_g1c_filename_is_a_language_odoo_reads(self):
        """A catalogue Odoo never opens is the same bug with no symptom.

        `get_po_paths(mod, lang)` builds `i18n/<base_lang>.po` and
        `i18n/<lang>.po` — nothing else is ever opened. health_pwa shipped
        `viVNpo.po` for nine months under that rule.
        """
        readable = set()
        for lang in ('vi_VN', 'en_US'):
            readable.update('%s.po' % base for base in get_base_langs(lang))
        bad = [f'{mod}/i18n/{fn}'
               for mod, fn, _p in _our_catalogues()
               if fn not in readable]
        self.assertFalse(
            bad,
            'catalogue filenames Odoo will never read (rename to <lang>.po '
            'or merge them): %s' % bad)


@tagged('post_install', '-at_install')
class TestI18nCatalogueLoads(TransactionCase):
    """G2 — loading, not shape. A green file that loads nothing is the bug."""

    def _python_entries(self, path):
        """msgid -> msgstr for entries Odoo should serve as python translations."""
        out = {}
        for block in _blocks(path):
            if not re.search(r'^#\. odoo-python', block, re.M):
                continue
            src, val = _field(block, 'msgid'), _field(block, 'msgstr')
            if src and val:
                out[src] = val
        return out

    def test_g2_python_catalogues_actually_load(self):
        """Every module claiming python translations must serve some.

        This is the assertion that exposed §5.67 in the first place: the
        catalogue was well-formed, installed silently, and
        `get_python_translations` returned an empty dict.
        """
        empty = []
        for mod, fn, path in _our_catalogues():
            expected = self._python_entries(path)
            if not expected:
                continue
            loaded = code_translations.get_python_translations(mod, 'vi_VN')
            if not loaded:
                empty.append(f'{mod}: {len(expected)} python entries, 0 loaded')
                continue
            missing = [s for s in expected if s not in loaded]
            if missing:
                empty.append(f'{mod}: {len(missing)} of {len(expected)} python '
                             f'entries did not load, e.g. {missing[0][:50]!r}')
        self.assertFalse(empty, 'catalogues that load nothing:\n' + '\n'.join(empty))

    def test_g2b_field_labels_reach_the_database_in_vietnamese(self):
        """The half a clinic actually sees: a translated field label.

        Code translations are mostly error text. What clinic staff read all
        day are field labels, and those travel a different road entirely —
        `model:ir.model.fields,field_description:` occurrences imported into
        the jsonb column at upgrade. Proving the code half loads says nothing
        about this half, so assert it separately, through the ORM, in the
        language the user has.
        """
        checked, wrong = 0, []
        for mod, fn, path in _our_catalogues():
            if not self.env['ir.module.module'].search_count(
                    [('name', '=', mod), ('state', '=', 'installed')]):
                continue
            for block in _blocks(path):
                m = re.search(
                    r'^#: model:ir\.model\.fields,field_description:'
                    r'([\w.]+)\.(field_[\w.]+)$', block, re.M)
                src, val = _field(block, 'msgid'), _field(block, 'msgstr')
                if not (m and src and val) or src == val:
                    continue
                field = self.env.ref('%s.%s' % m.groups(),
                                     raise_if_not_found=False)
                if not field:
                    continue
                label = field.with_context(lang='vi_VN').field_description
                checked += 1
                # Assert the label is TRANSLATED, not that it equals the
                # catalogue. `_load_module_terms` runs with overwrite=False on
                # upgrade, so a value already refined in the database
                # legitimately wins over the .po — res_partner.is_patient
                # holds 'Là bệnh nhân' where the file says 'Là Bệnh nhân'.
                # Demanding equality would fail on correct data and push the
                # next person to "fix" the database to match a file.
                if label == src:
                    wrong.append(f'{mod}.{m.group(2)}: still English '
                                 f'({src!r}) under lang=vi_VN')
                break  # one proof per module is enough; this runs for all
        self.assertTrue(checked, 'no translated field label found to check')
        self.assertFalse(
            wrong,
            'field labels that did not reach the database in Vietnamese '
            '(the module needs an upgrade, or the occurrence is wrong):\n'
            + '\n'.join(wrong[:20]))
