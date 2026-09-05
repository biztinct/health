# -*- coding: utf-8 -*-
"""The globe in the top bar, and the four ways it could silently not be there.

Every check here is for a failure that produces NO error anywhere: an asset
left out of the manifest, a template name that does not match the component's,
a dropdown panel styled only inside `.o_main_navbar` when the panel is
portalled out of it, and a database where the control offers a language nobody
installed. None of those raise; they just quietly mean nobody can change
language.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

JS = "health_theme/static/src/webclient/language_switcher.js"
SCSS = "health_theme/static/src/webclient/language_switcher.scss"
XML = "health_theme/static/src/webclient/language_switcher.xml"
TEMPLATE_NAME = "health_theme.LanguageSwitcher"


def _module_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(asset_path):
    relative = asset_path.split("/", 1)[1]
    with open(os.path.join(_module_dir(), relative), encoding="utf-8") as handle:
        return handle.read()


@tagged("post_install", "-at_install")
class TestLanguageSwitcherIsWiredUp(TransactionCase):
    def test_all_three_assets_are_in_the_manifest(self):
        """A file on disk that no bundle names is a file that never loads."""
        with open(
            os.path.join(_module_dir(), "__manifest__.py"), encoding="utf-8"
        ) as handle:
            manifest = handle.read()
        for asset in (JS, SCSS, XML):
            self.assertIn(asset, manifest, "%s is not in web.assets_backend" % asset)

    def test_the_component_and_the_template_agree_on_a_name(self):
        """A mismatch renders an empty systray slot and logs nothing."""
        self.assertIn('static template = "%s"' % TEMPLATE_NAME, _read(JS))
        self.assertIn('t-name="%s"' % TEMPLATE_NAME, _read(XML))

    def test_it_is_registered_in_the_systray(self):
        js = _read(JS)
        self.assertIn('registry.category("systray")', js)
        self.assertIn("health_theme.language_switcher", js)

    def test_it_draws_nothing_when_there_is_nothing_to_choose(self):
        """One language is not a choice; the control must hide, not offer it."""
        self.assertIn("hasChoice", _read(JS))
        self.assertRegex(
            _read(XML),
            r't-if="hasChoice"',
            "the template must be behind the has-a-choice guard",
        )

    def test_the_panel_is_styled_outside_the_navbar_block_too(self):
        """The dropdown is portalled OUT of the navbar onto a light surface.

        Styled only under `.o_main_navbar` those rules match nothing and the
        panel renders unstyled — invisible until somebody opens it.
        """
        scss = _read(SCSS)
        panel_rules = re.search(
            r"^\.vu-language-switcher\s*\{", scss, re.MULTILINE
        )
        self.assertTrue(
            panel_rules,
            "the panel needs a rule block that is NOT nested under .o_main_navbar",
        )
        for part in ("__heading", "__item--current"):
            self.assertIn(part, scss)

    def test_no_framework_name_and_no_gradient(self):
        """Standing rules: never the framework's name, never a gradient.

        The gradient check looks for the CSS FUNCTIONS, not the word: the first
        version searched for the substring and was failed by this module's own
        comment promising not to use one.
        """
        for asset in (JS, SCSS, XML):
            body = _read(asset).lower()
            for fn in ("linear-gradient", "radial-gradient", "conic-gradient"):
                self.assertNotIn(fn, body, "%s uses %s" % (asset, fn))
        # The framework's name may appear in an import path (`@odoo/owl`) and
        # nowhere else, so only the two files with no imports are swept.
        for line in _read(XML).splitlines() + _read(SCSS).splitlines():
            self.assertNotIn("Odoo", line)


@tagged("post_install", "-at_install")
class TestLanguageSwitcherHasSomethingToOffer(TransactionCase):
    def test_this_database_speaks_more_than_one_language(self):
        """The control is only useful where a second language is installed.

        Not a failure of the switcher if it is not — this platform's clinics are
        seeded with English and Vietnamese, and this is the check that says so
        out loud if that ever stops being true.
        """
        codes = self.env["res.lang"].get_installed()
        self.assertGreaterEqual(
            len(codes),
            2,
            "only %s language installed, so the switcher will hide itself" % len(codes),
        )
        self.assertIn(
            "vi_VN",
            [code for code, _name in codes],
            "Vietnamese is not installed on this database",
        )

    def test_a_person_can_be_moved_between_the_two(self):
        """The write the control makes, made here — including the way back."""
        someone = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Language test",
                    "login": "language.test@example.com",
                    "lang": "en_US",
                }
            )
        )
        someone.write({"lang": "vi_VN"})
        self.assertEqual(someone.lang, "vi_VN")
        someone.write({"lang": "en_US"})
        self.assertEqual(someone.lang, "en_US")
