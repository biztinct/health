# Part of the Viet Uc Care white-label layer. License LGPL-3.
"""AR-3 G4 — the browser tab never reads the framework's name (ledger §5.236).

Two places wrote it: the server-rendered `<title>` of a page that passes no title
of its own (the web client's start page), and the web client's title service,
which falls back to the framework's name until a screen sets a title. Both are
asserted here: the first by rendering the page, the second at the source — the
service's fallback cannot be reached once the brand part is set in the same
setup that starts the title service, and a browser test cannot run on this
server (ledger §5.222).
"""
import re

from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged
from odoo.modules.module import get_manifest
from odoo.tools.misc import file_open

from odoo.addons.biz_debranding.models.ir_http import brand_name

FRAMEWORK = "Od" + "oo"   # spelled apart so a grep for leaks does not hit this file


def _title(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return (m.group(1) if m else "").strip()


@tagged("post_install", "-at_install")
class TestBrandTitleSource(TransactionCase):

    def test_01_the_brand_is_never_empty(self):
        """`session_info` itself needs a request (the served page proves it,
        test_04); the value it hands out is this, and it is never empty."""
        self.assertTrue(brand_name(self.env))
        self.assertNotIn(FRAMEWORK, brand_name(self.env))

    def test_02_layout_title_falls_back_to_the_brand(self):
        arch = self.env.ref("web.layout").get_combined_arch()
        title = re.search(r"<title[^>]*/?>", arch).group(0)
        self.assertIn("biz_debranding.brand_name", title)
        self.assertNotIn("'%s'" % FRAMEWORK, title)

    def test_03_web_client_sets_the_brand_before_anything_else(self):
        """The JS patch sets the title part from the session, synchronously."""
        with file_open("biz_debranding/static/src/js/brand_title.js") as fh:
            src = fh.read()
        self.assertIn("session.biz_brand_name", src)
        self.assertRegex(src, r"super\.setup\(\);\s*\n(\s*//.*\n)*\s*this\.title\.setParts\(")
        self.assertNotIn('"%s"' % FRAMEWORK, src)
        manifest = get_manifest("biz_debranding")
        self.assertIn("biz_debranding/static/src/js/brand_title.js",
                      manifest["assets"]["web.assets_backend"])


@tagged("post_install", "-at_install")
class TestBrandTitleServed(HttpCase):

    def test_04_start_page_is_titled_with_the_brand(self):
        new_test_user(self.env, login="ar3_brand_title", password="ar3_brand_title!1",
                      groups="base.group_user")
        self.authenticate("ar3_brand_title", "ar3_brand_title!1")
        res = self.url_open("/web")
        self.assertEqual(res.status_code, 200)
        title = _title(res.text)
        self.assertEqual(title, brand_name(self.env))
        self.assertNotIn(FRAMEWORK, title)
        self.assertRegex(res.text, r'"biz_brand_name":\s*"%s"'
                         % re.escape(brand_name(self.env)))
