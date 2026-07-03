# Part of the Viet Uc Care white-label layer. License LGPL-3.
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBizDebrandingData(TransactionCase):
    def _brand(self):
        return self.env["ir.config_parameter"].sudo().get_param("biz_debranding.brand_name")

    def test_brand_params_seeded(self):
        icp = self.env["ir.config_parameter"].sudo()
        brand = self._brand()
        self.assertTrue(brand, "biz_debranding.brand_name not seeded")
        self.assertEqual(icp.get_param("web_debranding.new_name"), brand)
        self.assertEqual(icp.get_param("web_debranding.new_title"), brand)

    def test_website_url_not_malformed(self):
        website = self.env["ir.config_parameter"].sudo().get_param("web_debranding.new_website")
        self.assertTrue(website, "new_website empty")
        # regression guard for the live single-slash bug: https:/care...
        self.assertNotRegex(website, r"^https:/[^/]", "single-slash URL bug: %s" % website)
        self.assertTrue(website.startswith("https://"))

    def test_odoobot_debranded(self):
        bot = self.env.ref("base.partner_root")
        self.assertEqual(bot.name, self._brand())
        self.assertNotIn("odoo", (bot.name or "").lower())
        self.assertTrue(bot.image_1920, "bot avatar not set")

    def test_company_favicon_set(self):
        for company in self.env["res.company"].search([]):
            self.assertTrue(company.favicon, "favicon not set for %s" % company.name)

    def test_pwa_theme_color_not_aubergine(self):
        color = self.env["ir.config_parameter"].sudo().get_param("health_pwa.theme_color")
        self.assertNotEqual((color or "").upper(), "#875A7B", "aubergine leak remains")


@tagged("post_install", "-at_install")
class TestBizDebrandingHttp(HttpCase):
    def test_login_has_no_powered_by_odoo(self):
        html = self.url_open("/web/login").text
        # the "Powered by Odoo" login link carries utm_medium=auth
        self.assertNotIn("utm_medium=auth", html)

    def test_pwa_manifest_is_debranded(self):
        text = self.url_open("/health_pwa/manifest.json").text
        self.assertNotIn("875A7B", text)  # no aubergine leak
        brand = self.env["ir.config_parameter"].sudo().get_param("biz_debranding.brand_name")
        self.assertIn(brand, text)
