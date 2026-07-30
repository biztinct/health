# -*- coding: utf-8 -*-
"""The static guard on CSS containment in backend assets.

Odoo's AutoComplete dropdown (every many2one / many2many_tags popup) renders
INLINE inside the field as ``position: fixed; z-index: 1056`` — it is not
portalled into ``.o-overlay-container`` the way Dropdown/Popover are. So a
single ``contain:`` declaration on any wrapper that can hold a field makes that
wrapper a stacking context AND the dropdown's containing block, and every bit
of markup that follows it in DOM order paints over the open dropdown. The
symptom is a dropdown that looks cut off halfway down; the cause is invisible
in review and invisible in every test that does not render pixels.

That is exactly what ``.o_inner_group.vu-sec { contain: layout style }`` did to
every group card in the VU form engine (found 2026-07-30 on the ir.ui.menu
form). This test keeps it from coming back anywhere in the backend bundles.

Deliberately NOT checked here: ``container-type`` / ``container``. Container
queries imply the same layout containment, but the three-column workspace
ladder genuinely needs them, so dropdown_trap_guard.scss neutralises those
hosts with a z-index lift instead of forbidding the property.
"""
import ast
import os
import re

from odoo.tests import TransactionCase, tagged

OUR_PREFIXES = ('health_', 'biz_')

#: ``contain: layout``/``paint``/``content``/``strict`` — i.e. any containment
#: that creates a stacking context. ``contain: none`` and ``contain: size`` do
#: not, and the guard file itself is built out of ``contain: none``.
CONTAINMENT_RE = re.compile(
    r'(^|[;{\s])contain\s*:\s*[^;}]*\b(layout|paint|content|strict)\b',
    re.MULTILINE,
)

GUARD_ASSET = 'health_theme/static/src/scss/dropdown_trap_guard.scss'


def _addons_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _manifest(module_dir):
    for name in ('__manifest__.py', '__openerp__.py'):
        path = os.path.join(module_dir, name)
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as fh:
                return ast.literal_eval(fh.read())
    return None


def _backend_stylesheets():
    """[(module, asset_path, abs_path)] for every stylesheet our own modules
    put in a backend bundle.

    Bundle-scoped on purpose: the PWA and the public landing pages are separate
    documents with no Odoo AutoComplete in them, and they legitimately use
    containment for scroll performance.
    """
    root = _addons_dir()
    out = []
    for module in sorted(os.listdir(root)):
        if not module.startswith(OUR_PREFIXES):
            continue
        module_dir = os.path.join(root, module)
        if not os.path.isdir(module_dir):
            continue
        try:
            manifest = _manifest(module_dir)
        except (ValueError, SyntaxError):
            continue
        if not manifest:
            continue
        for bundle, entries in (manifest.get('assets') or {}).items():
            if not bundle.startswith('web.assets_backend'):
                continue
            for entry in entries:
                # ('prepend', path) / ('after', ref, path) / 'path'
                path = entry[-1] if isinstance(entry, (tuple, list)) else entry
                if not isinstance(path, str):
                    continue
                if not path.endswith(('.scss', '.css')):
                    continue
                if '*' in path:
                    continue
                abs_path = os.path.join(root, *path.split('/'))
                if os.path.isfile(abs_path):
                    out.append((module, path, abs_path))
    return out


@tagged('post_install', '-at_install')
class TestDropdownTrapGuard(TransactionCase):

    def test_no_containment_in_backend_stylesheets(self):
        """G1 — no stacking-context containment in any backend stylesheet."""
        sheets = _backend_stylesheets()
        self.assertTrue(sheets, "found no backend stylesheets to scan — the "
                                "manifest walk is broken, not the CSS")
        offenders = []
        for module, asset_path, abs_path in sheets:
            with open(abs_path, encoding='utf-8') as fh:
                for lineno, line in enumerate(fh, start=1):
                    code = line.split('//', 1)[0]
                    if CONTAINMENT_RE.search(code):
                        offenders.append(f'{asset_path}:{lineno}: {line.strip()}')
        self.assertFalse(offenders, (
            "CSS containment in a backend stylesheet traps the inline "
            "AutoComplete dropdown (it paints under everything that follows "
            "it in DOM order). Drop the declaration, or lift the host in "
            "dropdown_trap_guard.scss if the containment is load-bearing:\n  "
            + "\n  ".join(offenders)))

    def test_guard_stylesheet_is_bundled(self):
        """G2 — the guard itself is still registered, and still a guard."""
        paths = [p for _m, p, _a in _backend_stylesheets()]
        self.assertIn(GUARD_ASSET, paths,
                      "dropdown_trap_guard.scss dropped out of "
                      "web.assets_backend — the net is gone")
        abs_path = os.path.join(_addons_dir(), *GUARD_ASSET.split('/'))
        with open(abs_path, encoding='utf-8') as fh:
            body = fh.read()
        self.assertIn('.o-autocomplete--dropdown-menu', body)
        self.assertIn('contain: none !important', body)
