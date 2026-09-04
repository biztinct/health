# -*- coding: utf-8 -*-
"""Rail R11 / R12 for the cockpit: it names no product and no framework.

The whole reason this module was written here rather than inside the product is
that the next product should be able to have it. A cockpit that says "clinic",
"visit" or "Viet Uc Care" anywhere a person can read is a cockpit that has been
lifted out of one product and only half cleaned — and the reader of the next
product meets a word from a system they do not have.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _src(*parts):
    with open(os.path.join(get_module_path('biz_tenants'), *parts),
              encoding='utf-8') as fh:
        return fh.read()


_PY = (('models', 'tenants_common.py'), ('models', 'sync_rules.py'),
       ('models', 'provision_rules.py'), ('models', 'tenant.py'),
       ('models', 'release.py'), ('models', 'service.py'),
       # H4b. Listed rather than globbed, for the reason in the comment
       # below: a file added and not named here is a file this audit
       # quietly stops covering.
       ('models', 'rollout_rules.py'), ('models', 'rollout.py'),
       ('models', 'rollout_service.py'), ('models', 'alert_rules.py'),
       ('models', 'alert.py'), ('models', 'alert_service.py'),
       # H4c.
       ('models', 'module_set.py'), ('models', 'feature.py'),
       ('models', 'feature_service.py'), ('models', 'support_service.py'),
       # H4d.
       ('models', 'billing_rules.py'), ('models', 'plan.py'),
       ('models', 'billing.py'), ('models', 'billing_service.py'),
       ('models', '__init__.py'), ('__init__.py',))
_JS = ('tenants.js',)
_XML = ('tenants.xml',)
_MARKUP = (('views', 'biz_tenants_action.xml'), ('data', 'ir_cron.xml'),
           ('data', 'biz_feature.xml'), ('data', 'biz_plan.xml'),
           # ⚠ THE ONE THAT GOES TO A PAYING CUSTOMER. A document with the
           # framework's name anywhere on it is the white-label rule's worst
           # case, so the invoice is scanned like every other surface — and
           # `test_no_user_visible_string_names_the_framework` in
           # `test_billing.py` scans what is actually RENDERED as well.
           ('report', 'tenant_invoice.xml'))


@tagged('post_install', '-at_install')
class TestCockpitNamesNobody(TransactionCase):

    #: Product names and industry words this layer must never speak. The
    #: framework's own name is on the list for the white-label rule (R12); it
    #: is allowed in a comment and in an import, which is why the scans strip
    #: both first.
    BANNED = ('Payobook', 'payobook', 'pb_', 'pbim', 'Viet Uc', 'Việt Úc',
              'carejiox', 'Carejiox', 'Odoo', 'odoo.com')

    #: ONE INDUSTRY'S VOCABULARY IS AS WRONG AS ONE PRODUCT'S NAME (ledger
    #: H12). These are the words this cockpit would have picked up from the
    #: product it lives beside.
    DOMAIN_WORDS = ('clinic', 'Clinic', 'patient', 'Patient', 'nurse',
                    'Nurse', 'payroll', 'Payroll', 'payslip')

    ALLOWED = ('from odoo', 'import odoo', 'odoo.addons', 'odoo.exceptions',
               'odoo.tests', 'odoo.tools', 'odoo.modules', 'odoo.service',
               'odoo.sql_db', 'odoo.http', 'odoo-bin', '@odoo-module',
               '@odoo/owl', '<odoo>', '</odoo>', 'import odoo\n')


    #: Every file this audit covers. Named rather than globbed: a file added
    #: and not listed is a file this audit quietly stops covering.
    PRODUCT_SCAN = (list(_PY) + [('static', 'src', 'js', n) for n in _JS]
                    + [('static', 'src', 'xml', n) for n in _XML]
                    + list(_MARKUP)
                    + [('static', 'src', 'scss', 'tenants.scss'),
                       ('security', 'ir.model.access.csv'),
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

    def _strip_xml(self, src):
        return re.sub(r'<!--(?:.|\n)*?-->', '', src)

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
                self.assertNotIn(banned, code, '%s names "%s"' % (name, banned))

    def test_no_markup_string_names_a_product(self):
        targets = [('static', 'src', 'xml', n) for n in _XML] + list(_MARKUP)
        for parts in targets:
            src = self._bare(self._strip_xml(_src(*parts)))
            for banned in self.BANNED:
                self.assertNotIn(banned, src,
                                 '%s names "%s"' % ('/'.join(parts), banned))

    def test_no_user_visible_string_speaks_one_industry_s_vocabulary(self):
        targets = list(_PY) + [('static', 'src', 'xml', n) for n in _XML]
        targets += [('static', 'src', 'js', n) for n in _JS]
        targets += list(_MARKUP)
        for parts in targets:
            src = _src(*parts)
            if parts[-1].endswith('.py'):
                src = self._strip_py(src)
            elif parts[-1].endswith('.js'):
                src = self._strip_js(src)
            else:
                src = self._strip_xml(src)
            for word in self.DOMAIN_WORDS:
                self.assertNotIn(
                    word, src,
                    '%s puts "%s" on a screen — this cockpit has to read '
                    'correctly under every product' % ('/'.join(parts), word))

    def test_the_manifest_reads_as_a_product_agnostic_module(self):
        manifest = _src('__manifest__.py')
        for banned in ('Payobook', 'payobook', 'Viet Uc', 'Việt Úc',
                       'health_', 'pb_', 'carejiox', 'Odoo', 'clinic',
                       'patient'):
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

    def test_the_stylesheet_names_nobody(self):
        src = _src('static', 'src', 'scss', 'tenants.scss')
        for banned in ('pb_', 'pbim', 'health_', 'payobook', 'carejiox'):
            self.assertNotIn(banned, src)

    def test_it_seeds_no_never_list_and_no_meter_of_its_own(self):
        """A generic core that shipped somebody else's exceptions would put the
        wrong names on the next product's screen. The ONE entry it owns is
        itself, which is a fact about this module."""
        from odoo.addons.biz_tenants.models import tenants_common as common
        self.assertNotIn('biz_tenants', common.NEVER,
                         'the cockpit owns its own entry outside the registry')
        self.assertTrue(common.is_never('biz_tenants'))


@tagged('post_install', '-at_install')
class TestSourceGates(TransactionCase):

    def test_no_python_style_implicit_string_concatenation(self):
        """A Python habit here is a JavaScript SyntaxError, and the asset
        pipeline concatenates without ever parsing — one of these blanks the
        WHOLE backend bundle for every user, with a clean server log (F49)."""
        adjacent = re.compile(r"""["']\s*\n\s*["']""")
        for name in _JS:
            self.assertFalse(
                adjacent.search(_src('static', 'src', 'js', name)),
                '%s has two adjacent string literals across a newline' % name)

    def test_no_reserved_owl_name_is_used_as_a_loop_variable(self):
        """`t-as="lt"` compiles the name into a bare `<` and the whole
        component dies with a blank screen (F15)."""
        reserved = {'lt', 'gt', 'lte', 'gte', 'amp', 'quot',
                    'and', 'or', 'not', 'in'}
        for name in _XML:
            src = _src('static', 'src', 'xml', name)
            for var in re.findall(r't-as="(\w+)"', src):
                self.assertNotIn(var, reserved,
                                 '%s uses the reserved name %s' % (name, var))

    def test_no_javascript_builtin_is_called_from_a_template(self):
        """A template expression is compiled against the COMPONENT, so
        `String(x)` becomes `ctx.String(x)` and throws the first time that
        branch renders (F16). The framework's own reserved list covers `Math`,
        `Array`, `Object` and `Date`; these four are not on it."""
        for name in _XML:
            # Comments are stripped first: the note at the top of each
            # template file NAMES the trap, and a comment calls nothing.
            src = re.sub(r'<!--(?:.|\n)*?-->', '',
                         _src('static', 'src', 'xml', name))
            for builtin in ('String(', 'Number(', 'JSON.', 'parseInt('):
                self.assertNotIn(builtin, src,
                                 '%s calls %s from a template' % (name, builtin))

    def test_no_attribute_is_bound_to_a_bare_boolean(self):
        """`t-att-x="flag"` with a JavaScript `true` renders the attribute with
        an EMPTY value, so `[x="true"]` never matches (F58)."""
        for name in _XML:
            src = _src('static', 'src', 'xml', name)
            for value in re.findall(r't-att-[\w-]+="([^"]*)"', src):
                self.assertNotIn(
                    value.strip(), ('true', 'false'),
                    '%s binds an attribute to a bare boolean' % name)

    def test_the_dialog_scrim_is_spelled_the_kit_s_way(self):
        """⚠ `bzk-modal-scrim`, ONE hyphen — the only part of that primitive
        that is not written the other way. Spelled BEM it matches no rule at
        all and the dialog renders INLINE, in the flow of the page, with no
        overlay, no centring and no error anywhere (F57)."""
        for name in _XML:
            src = _src('static', 'src', 'xml', name)
            self.assertNotIn('bzk-modal__scrim', src)
            if 'bzk-modal' in src:
                self.assertIn('bzk-modal-scrim', src)

    def test_no_scss_min_mixing_units(self):
        """`min(64vh, 640px)` fails the WHOLE bundle and every screen in the
        product renders unstyled under a red banner (F36)."""
        src = _src('static', 'src', 'scss', 'tenants.scss')
        self.assertFalse(
            re.search(r'\bmin\(\s*[\d.]+[a-z%]+\s*,\s*[\d.]+[a-z%]+', src),
            'the stylesheet mixes units inside min()')

    def test_the_stylesheet_says_how_many_root_blocks_it_has(self):
        """Ledger F35. A rule appended after the wrong closing brace compiles
        to nothing and fails silently, so the file has to name its roots."""
        src = _src('static', 'src', 'scss', 'tenants.scss')
        self.assertIn('ROOT BLOCK', src.upper())

    def test_every_icon_name_is_in_the_shared_registry(self):
        """`ic()` draws a plain circle for a name it has never heard of, so a
        typo is a wrong picture rather than an error."""
        path = get_module_path('biz_kit')
        with open(path + '/static/src/js/kit_icons.js', encoding='utf-8') as fh:
            known = set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'",
                                   fh.read(), re.M))
        self.assertIn('gauge', known, 'the icon registry did not parse')
        used = set()
        for name in _XML:
            used |= set(re.findall(r"ic\('([A-Za-z0-9_]+)'",
                                   _src('static', 'src', 'xml', name)))
        for name in _JS:
            used |= set(re.findall(r'icon:\s*"([A-Za-z0-9_]+)"',
                                   _src('static', 'src', 'js', name)))
        self.assertTrue(used, 'no icons were found to check')
        for name in sorted(used):
            self.assertIn(name, known,
                          "icon '%s' is not in the shared ic() registry" % name)

    def test_no_bracketed_plurals(self):
        """"1 part(s)" is how a screen announces it was written by a programme
        rather than by a person."""
        targets = list(_PY) + [('static', 'src', 'xml', n) for n in _XML]
        targets += [('static', 'src', 'js', n) for n in _JS]
        for parts in targets:
            self.assertFalse(
                re.search(r'\w\(s\)', _src(*parts)),
                '%s has a bracketed plural' % '/'.join(parts))

    def test_no_keyboard_shortcut_is_bound_to_the_window(self):
        """A shortcut bound to `window` never fires in this web client —
        something in the shared client stops keydown at the body, silently
        (F10). `document` with `{capture: true}` is the working form."""
        src = _src('static', 'src', 'js', 'tenants.js')
        self.assertNotIn('window.addEventListener("keydown"', src)
        self.assertIn('document.addEventListener("keydown"', src)
        self.assertIn('capture: true', src)

    def test_the_scheduled_jobs_only_read(self):
        """Rail R1, asserted on the source: the two nightly jobs must not be
        able to install anything on anybody's system."""
        src = _src('models', 'service.py')
        for name in ('_cron_drift', '_cron_health'):
            body = src.split('def %s' % name, 1)[1].split('\n    @api.model')[0]
            for forbidden in ('button_immediate_install',
                              'button_immediate_upgrade', 'sync_bring_in_step'):
                self.assertNotIn(forbidden, body,
                                 '%s can install something' % name)

    def test_the_alert_sweep_installs_nothing_and_speaks_to_no_customer(self):
        """Rail R1 for H4b's own jobs. The sweep READS: cached fields, one
        request per customer, read-only queries, the machine's log. It must not
        be able to install anything anywhere, and it must not write onto a
        customer's system either."""
        src = _src('models', 'alert_service.py')
        for name in ('_cron_alerts', '_gather_readings'):
            body = src.split('def %s' % name, 1)[1].split('\n    @api.model')[0]
            for forbidden in ('button_immediate_install',
                              'button_immediate_upgrade', 'sync_bring_in_step',
                              '_tenant_env', 'push_settings'):
                self.assertNotIn(forbidden, body,
                                 '%s reaches into a customer system' % name)

    def test_the_status_page_writer_stands_down_under_a_test_run(self):
        """⚠ A FILE WRITTEN BY A MODEL IS NOT ROLLED BACK BY A TEST (F44), and
        the guard belongs AT THE WRITER rather than in each test, because the
        next caller will be written by somebody who has not read the comment.
        Asserted on the source as well as by behaviour: the behavioural test
        can only prove the guard that is there, not that it stayed there."""
        src = _src('models', 'alert_service.py')
        body = src.split('def _write_status_page', 1)[1]
        head = body.split('\n    def ', 1)[0]
        self.assertIn("config['test_enable']", head,
                      'the public page writer no longer stands down in a test')
        # And it must return BEFORE anything is rendered or written.
        before = head.split("config['test_enable']")[1].split('return')[0]
        self.assertNotIn('open(', before)

    def test_the_send_path_stands_down_under_a_test_run(self):
        """Ledger F67. The suite's own attempts to send wrote error lines into
        the very log the rollout's health gate reads, so a test run could fail
        the next rollout."""
        src = _src('models', 'alert_service.py')
        body = src.split('def _send_alert_mail', 1)[1].split('\n    @', 1)[0]
        self.assertIn("config['test_enable']", body)

    def test_the_rollout_start_takes_the_lock_before_it_does_anything(self):
        """Ledger F50. Two presses inside ninety seconds are two rollouts that
        destroy each other's practice copy, and the whole practice run happens
        before the first one commits — so the guard has to be a lock held to the
        end of the transaction, taken on the FIRST line."""
        src = _src('models', 'rollout_service.py')
        body = src.split('def rollout_start', 1)[1].split('\n    def ', 1)[0]
        self.assertIn('pg_advisory_xact_lock', body)
        lock_at = body.index('pg_advisory_xact_lock')
        for later in ('_plan_for', 'create(', '_rollout_tick'):
            self.assertGreater(body.index(later), lock_at,
                               '%s happens before the lock is taken' % later)


    def test_the_stylesheet_s_root_matches_the_element_it_is_written_for(self):
        """⚠ THE SCREEN'S OWN ELEMENT CARRIES BOTH CLASSES, SO THE ROOT
        SELECTOR IS COMPOUND AND HAS NO SPACE IN IT.

        `.bzk .bzt` — with a space — is a DESCENDANT selector, and the
        element it is meant for is not a descendant of itself. It matches
        nothing at all: the page renders with every kit primitive styled and
        not one rule of its own, and there is no error anywhere. Found in a
        browser and nowhere else, which is why it is a gate now.
        """
        src = _src('static', 'src', 'scss', 'tenants.scss')
        self.assertIn('.bzk.bzt {', src)
        self.assertNotIn('.bzk .bzt {', src)
        markup = _src('static', 'src', 'xml', 'tenants.xml')
        self.assertIn('class="bzk bzk-page bzt"', markup,
                      'the page element no longer carries both classes')
