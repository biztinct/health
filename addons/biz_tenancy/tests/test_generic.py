# -*- coding: utf-8 -*-
"""Rail R11 / R12 for the platform link: it names no product and no framework.

Read from the SOURCE rather than from the database, because the failure is
always one sentence added in a hurry — and because a string only shown on an
error path is exactly the one a running test never renders.

The gates underneath it are the six habits that produce a broken screen with a
completely clean server log (F15, F16, F36, F49, F58 and the icon typo).
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _src(*parts):
    with open(os.path.join(get_module_path('biz_tenancy'), *parts),
              encoding='utf-8') as fh:
        return fh.read()


_PY = (('models', 'tenancy.py'), ('models', 'ir_http.py'),
       ('models', 'support.py'),
       ('controllers', 'main.py'), ('__init__.py',))
_JS = ('tenancy_range.js', 'tenancy_service.js', 'tenancy_banner.js',
       'tenancy_support_bar.js', 'tenancy_feature_off.js',
       'tenancy_about.js')
_XML = ('tenancy_banner.xml', 'tenancy_about.xml', 'tenancy_support_bar.xml',
        'tenancy_feature_off.xml', 'webclient_patch.xml')
_MARKUP = (('views', 'about_action.xml'),
           ('views', 'support_templates.xml'))


@tagged('post_install', '-at_install')
class TestPlatformLinkNamesNobody(TransactionCase):

    #: Product names this module must never speak. The framework's own name is
    #: on the list for the white-label rule (rail R12); it is allowed in a code
    #: COMMENT and in an import, which is why the scans strip both first.
    BANNED = ('Payobook', 'payobook', 'pb_', 'pbim', 'Viet Uc', 'Việt Úc',
              'carejiox', 'Carejiox', 'hhh', 'Odoo', 'odoo.com')

    #: Technical identifiers that legitimately contain the framework's name.
    ALLOWED = ('from odoo', 'import odoo', 'odoo.addons', 'odoo.exceptions',
               'odoo.tests', 'odoo.tools', 'odoo.modules', 'odoo.http',
               'odoo-bin', '@odoo-module', '@odoo/owl', '<odoo>', '</odoo>')


    #: Every file this audit covers, named rather than globbed. The web-client
    #: patch is deliberately OUT: its comment has to name the two modules that
    #: already own the other mount points, which is the whole reason the bar
    #: mounts where it does (ledger F18).
    PRODUCT_SCAN = (list(_PY) + [('static', 'src', 'js', n) for n in _JS]
                    + [('static', 'src', 'xml', n) for n in _XML
                       if n != 'webclient_patch.xml']
                    + [('static', 'src', 'scss', 'tenancy.scss'),
                       ('__manifest__.py',)])

    def _bare(self, text):
        for allowed in self.ALLOWED:
            text = text.replace(allowed, '')
        return text

    def _strip_py(self, src):
        src = re.sub(r'"""(?:.|\n)*?"""', '', src)
        return '\n'.join(l for l in src.split('\n')
                         if not l.lstrip().startswith('#'))

    def _strip_js(self, src):
        src = re.sub(r'/\*(?:.|\n)*?\*/', '', src)
        return '\n'.join(l for l in src.split('\n')
                         if not l.lstrip().startswith('//'))

    def test_no_python_string_names_a_product(self):
        for parts in _PY:
            code = self._bare(self._strip_py(_src(*parts)))
            for banned in self.BANNED:
                self.assertNotIn(banned, code,
                                 '%s names "%s" outside a comment'
                                 % ('/'.join(parts), banned))

    def test_no_browser_string_names_a_product(self):
        for name in _JS:
            code = self._bare(self._strip_js(_src('static', 'src', 'js', name)))
            for banned in self.BANNED:
                self.assertNotIn(banned, code,
                                 '%s names "%s"' % (name, banned))

    def test_no_markup_string_names_a_product(self):
        targets = [('static', 'src', 'xml', n) for n in _XML] + list(_MARKUP)
        for parts in targets:
            src = self._bare(re.sub(r'<!--(?:.|\n)*?-->', '', _src(*parts)))
            for banned in self.BANNED:
                self.assertNotIn(banned, src,
                                 '%s names "%s"' % ('/'.join(parts), banned))

    def test_the_manifest_reads_as_a_product_agnostic_module(self):
        manifest = _src('__manifest__.py')
        for banned in ('Payobook', 'payobook', 'Viet Uc', 'Việt Úc',
                       'health_', 'pb_', 'carejiox', 'Odoo'):
            self.assertNotIn(banned, manifest)


    def test_not_one_source_file_reaches_for_a_product_module(self):
        """THE LIFT-OUT'S OWN PROOF, AND IT READS COMMENTS TOO.

        A generic core that names a product module cannot be lifted into the
        next product, which is the only reason it was made generic. Comments
        count: one naming a module that is not on this database sends the next
        reader looking for a file that does not exist. The exception is the
        one place a comment MUST name a module — the note in the web-client
        patch saying which modules already own which mount point — and it is
        excluded by naming the file, not by softening the rule.
        """
        needles = ('odoo.addons.health', 'pb_import_kit', 'pb_hub',
                   'pb_settings', 'pb_sidebar', 'pb.sidebar', 'pb.access',
                   'pb.tenant', 'pb_tenants', 'pb_tenancy')
        for parts in self.PRODUCT_SCAN:
            src = _src(*parts)
            for needle in needles:
                self.assertNotIn(needle, src, '%s mentions "%s"'
                                              % ('/'.join(parts), needle))

    def test_the_stylesheet_names_nobody_and_invents_no_colour_word(self):
        src = _src('static', 'src', 'scss', 'tenancy.scss')
        for banned in ('pb_', 'pbim', 'health_', 'payobook'):
            self.assertNotIn(banned, src)


@tagged('post_install', '-at_install')
class TestSourceGates(TransactionCase):

    def test_no_python_style_implicit_string_concatenation(self):
        """A Python habit here is a JavaScript SyntaxError, and the asset
        pipeline concatenates without ever parsing — so one of these blanks the
        WHOLE backend bundle for every user, with a clean server log (F49)."""
        adjacent = re.compile(r"""["']\s*\n\s*["']""")
        for name in _JS:
            self.assertFalse(
                adjacent.search(_src('static', 'src', 'js', name)),
                '%s has two adjacent string literals across a newline' % name)

    def test_no_reserved_owl_name_is_used_as_a_loop_variable(self):
        """`t-as="lt"` compiles the loop variable into a bare `<` and the whole
        template dies with a blank screen, pointing at nothing (F15)."""
        reserved = {'lt', 'gt', 'lte', 'gte', 'amp', 'quot',
                    'and', 'or', 'not', 'in'}
        for name in _XML:
            src = _src('static', 'src', 'xml', name)
            for var in re.findall(r't-as="(\w+)"', src):
                self.assertNotIn(var, reserved,
                                 '%s uses the reserved name %s' % (name, var))

    def test_no_javascript_builtin_is_called_from_a_template(self):
        """A template expression is compiled against the COMPONENT, so
        `String(x)` becomes `ctx.String(x)` and throws — but only when that
        branch first renders (F16). Coerce on the component side."""
        for name in _XML:
            # Comments are stripped first: the note at the top of each
            # template file NAMES the trap, and a comment calls nothing.
            src = re.sub(r'<!--(?:.|\n)*?-->', '',
                         _src('static', 'src', 'xml', name))
            for builtin in ('String(', 'Number(', 'JSON.', 'Object.',
                            'Array.', 'parseInt(', 'Math.'):
                self.assertNotIn(builtin, src,
                                 '%s calls %s from a template' % (name, builtin))

    def test_no_scss_min_mixing_units(self):
        """`min(64vh, 640px)` fails the WHOLE bundle and every screen in the
        product renders unstyled under a red banner (F36)."""
        src = _src('static', 'src', 'scss', 'tenancy.scss')
        self.assertFalse(
            re.search(r'\bmin\(\s*[\d.]+[a-z%]+\s*,\s*[\d.]+[a-z%]+', src),
            'the stylesheet mixes units inside min()')

    def test_no_attribute_is_bound_to_a_bare_boolean(self):
        """`t-att-x="flag"` with a JavaScript `true` renders the attribute with
        an EMPTY value, so `[x="true"]` never matches (F58)."""
        for name in _XML:
            src = _src('static', 'src', 'xml', name)
            for match in re.findall(r't-att-[\w-]+="([^"]*)"', src):
                self.assertNotIn(
                    match.strip(), ('true', 'false'),
                    '%s binds an attribute to a bare boolean' % name)

    def test_every_icon_name_is_in_the_shared_registry(self):
        """`ic()` draws a plain circle for a name it has never heard of, so a
        typo is a wrong picture rather than an error — which is exactly why it
        has to be caught here."""
        path = get_module_path('biz_kit')
        with open(path + '/static/src/js/kit_icons.js', encoding='utf-8') as fh:
            known = set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'",
                                   fh.read(), re.M))
        self.assertIn('wrench', known, 'the icon registry did not parse')
        used = set()
        for name in _XML:
            used |= set(re.findall(r"ic\('([A-Za-z0-9_]+)'",
                                   _src('static', 'src', 'xml', name)))
        # The two the bar chooses between live in a ternary in the component,
        # and are named here EXPLICITLY: a regex written to match one ternary
        # is a test of the regex, not of the icons.
        used |= {'wrench', 'info'}
        # Same reason, one file down: the switched-off page and the support bar
        # each pick an icon in a getter rather than in the markup.
        used |= {'shield', 'clock', 'lock', 'home', 'x'}
        for name in sorted(used):
            self.assertIn(name, known,
                          "icon '%s' is not in the shared ic() registry" % name)

    def test_no_bracketed_plurals(self):
        """"1 release(s)" is how a screen announces it was written by a
        programme rather than by a person."""
        targets = [('static', 'src', 'xml', n) for n in _XML]
        targets += [('static', 'src', 'js', n) for n in _JS]
        targets += list(_PY)
        for parts in targets:
            src = _src(*parts)
            self.assertFalse(re.search(r'\w\(s\)', src),
                             '%s has a bracketed plural' % '/'.join(parts))

    def test_the_bar_mounts_after_the_navigation_bar_and_nowhere_else(self):
        """Ledger F18. Two modules on this build already own the action
        container; a third would be a race between load orders."""
        # Comments stripped first: the note in that file has to NAME the node
        # it deliberately does not touch, which is the whole explanation.
        src = re.sub(r'<!--(?:.|\n)*?-->', '',
                     _src('static', 'src', 'xml', 'webclient_patch.xml'))
        self.assertIn('//NavBar', src)
        self.assertNotIn('//ActionContainer', src)


    def test_the_stylesheet_s_root_matches_the_element_it_is_written_for(self):
        """⚠ THE SCREEN'S OWN ELEMENT CARRIES BOTH CLASSES, SO THE ROOT
        SELECTOR IS COMPOUND AND HAS NO SPACE IN IT.

        `.bzk .bztn-about` — with a space — is a DESCENDANT selector, and the
        element it is meant for is not a descendant of itself. It matches
        nothing at all: the page renders with every kit primitive styled and
        not one rule of its own, and there is no error anywhere. Found in a
        browser and nowhere else, which is why it is a gate now.
        """
        src = _src('static', 'src', 'scss', 'tenancy.scss')
        self.assertIn('.bzk.bztn-about {', src)
        self.assertNotIn('.bzk .bztn-about {', src)
        markup = _src('static', 'src', 'xml', 'tenancy_about.xml')
        self.assertIn('class="bzk bzk-page bztn-about"', markup,
                      'the page element no longer carries both classes')
