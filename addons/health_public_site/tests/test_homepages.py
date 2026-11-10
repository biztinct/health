from lxml import html
from odoo.tests import HttpCase, tagged
from ..controllers.home import homepage_brand
from ..controllers.demo import INBOX, TAG_NAME, validate_demo_request


@tagged('post_install', '-at_install')
class TestPublicHomepages(HttpCase):
    """Exercise the actual public render on each named deployment database."""

    def test_tenant_identity_is_explicit(self):
        self.assertEqual(homepage_brand('carejiox'), 'platform')
        self.assertEqual(homepage_brand('hhh'), 'client')
        self.assertIsNone(homepage_brand('carejiox_template'))
        self.assertIsNone(homepage_brand('another_customer'))

    def test_public_homepage_and_assets(self):
        brand = homepage_brand(self.env.cr.dbname)
        response = self.url_open('/')
        self.assertEqual(response.status_code, 200)
        doc = html.fromstring(response.content)
        if not brand:
            self.assertFalse(doc.xpath('//body[contains(@class,"cj-platform") or contains(@class,"vu-client")]'))
            return
        self.assertTrue(response.content.lstrip().startswith(b'<!DOCTYPE html>'))
        expected = 'cj-platform' if brand == 'platform' else 'vu-client'
        self.assertEqual(doc.xpath('//body/@class'), [expected])
        self.assertEqual(len(doc.xpath('//h1')), 1)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        for path in doc.xpath('//link[@rel="stylesheet"]/@href | //script/@src | //img/@src | //meta[@property="og:image"]/@content'):
            if path.startswith('https://'):
                path = '/' + path.split('/', 3)[3]
            self.assertEqual(self.url_open(path).status_code, 200, path)
        ids = set(doc.xpath('//@id'))
        for anchor in doc.xpath('//a[starts-with(@href,"#")]/@href'):
            self.assertIn(anchor[1:], ids)

    def test_language_and_brand_isolation(self):
        brand = homepage_brand(self.env.cr.dbname)
        if not brand:
            return
        english = self.url_open('/?site_lang=en&brand=client')
        doc = html.fromstring(english.content)
        self.assertEqual(doc.get('lang'), 'en')
        if brand == 'platform':
            other = html.fromstring(self.url_open('/?site_lang=vi&brand=client').content)
            self.assertEqual(other.get('lang'), 'en')
            self.assertNotIn('1800 6896', doc.text_content())
            self.assertIn('hello@carejiyo.com', doc.text_content())
        else:
            self.assertIn('One team.', doc.text_content())
            self.assertNotIn('THE OPERATING SYSTEM FOR CONNECTED CARE', doc.text_content())
            self.assertNotIn('ash@biztinct.com', doc.text_content())
            vietnamese = self.url_open('/?site_lang=vi&brand=platform')
            vi = html.fromstring(vietnamese.content)
            self.assertEqual(vi.get('lang'), 'vi')
            self.assertIn('Một đội ngũ.', vi.text_content())
            self.assertEqual(vi.xpath('//link[@rel="canonical"]/@href'), ['https://hhh.carejiox.com/?site_lang=vi'])
            self.assertIn('cjx_site_lang=vi', vietnamese.headers.get('Set-Cookie', ''))
            self.assertEqual(html.fromstring(self.url_open('/').content).get('lang'), 'vi')

    def test_invalid_language_is_not_reflected(self):
        if not homepage_brand(self.env.cr.dbname):
            return
        response = self.url_open('/?site_lang=%3Cscript%3Ealert(123)%3C/script%3E')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<script>alert(123)</script>', response.text)
        self.assertIn(html.fromstring(response.content).get('lang'), ('en', 'vi'))

    def test_application_entry_and_motion_controls(self):
        brand = homepage_brand(self.env.cr.dbname)
        if not brand:
            return
        doc = html.fromstring(self.url_open('/?site_lang=en').content)
        # The client keeps its decorative canvas; the platform home uses drawn scenes instead.
        self.assertEqual(len(doc.xpath('//canvas[@aria-hidden="true"]')), 1 if brand == 'client' else 0)
        self.assertEqual(len(doc.xpath('//button[contains(@class,"motion-toggle")]')), 1)
        for tab in doc.xpath('//*[@role="tab"]'):
            self.assertEqual(len(doc.xpath('//*[@id="%s"]' % tab.get('aria-controls'))), 1)
        if brand == 'client':
            links = doc.xpath('//a/@href')
            self.assertIn('https://pkgdvietuc.com/', links)
            self.assertIn('/web/login?redirect=%2Fbizapp', links)
            self.assertIn('/web/login?redirect=%2Fhealth_pwa', links)
            self.assertFalse(any(link.startswith('tel:') for link in links))
            self.assertIn('Use the personal care link shared by your care team', doc.text_content())
        else:
            text = doc.text_content()
            self.assertIn('filing to government agencies where required and configured', text)
            # White-label rule and the CareJiyo rename: neither old nor platform names leak.
            self.assertIn('CareJiyo', text)
            self.assertNotIn('CareJiox', text)
            self.assertNotIn('Odoo', text)
            self.assertEqual(len(doc.xpath('//*[@role="tab"]')), 4)
            for img in doc.xpath('//img[@src]'):
                self.assertIsNotNone(img.get('alt'), img.get('src'))
            links = doc.xpath('//a/@href')
            self.assertIn('/web/login', links)
            self.assertGreaterEqual(links.count('#book-demo'), 3)
            form = doc.xpath('//dialog[@id="book-demo"]//form[@action="/carejiyo/demo-request"]')
            self.assertEqual(len(form), 1)
            self.assertTrue(form[0].xpath('.//input[@name="csrf_token"]/@value'))
            self.assertEqual(len(doc.xpath('//svg[contains(@class,"route-map")]//animatemotion')), 1)
            self.assertEqual(len(doc.xpath('//section[@id="office"]//article')), 4)

    def test_sign_in_shell(self):
        """CareJiyo frames sign-in on the platform only; the stock form is kept intact."""
        brand = homepage_brand(self.env.cr.dbname)
        for path in ('/web/login', '/web/reset_password'):
            response = self.url_open(path)
            self.assertEqual(response.status_code, 200, path)
            doc = html.fromstring(response.content)
            visible = html.fromstring(response.content)
            for node in visible.xpath('//script | //style'):
                node.drop_tree()
            text = visible.text_content()
            self.assertTrue(doc.xpath('//form//input[@name="csrf_token"]'), path)
            self.assertTrue(doc.xpath('//input[@name="login"]'), path)
            shell = doc.xpath('//div[contains(@class,"cj-auth")]')
            if brand == 'platform':
                self.assertTrue(shell, path)
                self.assertIn('CareJiyo', doc.findtext('.//title'))
                self.assertNotIn('Odoo', text)
                self.assertNotIn('555-555-5556', text)
                self.assertFalse(doc.xpath('//header[@id="top"]'), path)
                for src in doc.xpath('//div[contains(@class,"cj-auth")]//img/@src | //link[contains(@href,"login.css")]/@href'):
                    self.assertEqual(self.url_open(src).status_code, 200, src)
            else:
                self.assertFalse(shell, path)
        if brand == 'platform':
            doc = html.fromstring(self.url_open('/web/login').content)
            self.assertTrue(doc.xpath('//form[contains(@class,"oe_login_form")]//input[@name="password"]'))
            self.assertIn('Welcome back', doc.text_content())

    def _demo_post(self, **fields):
        page = html.fromstring(self.url_open('/').content)
        token = page.xpath('//form[@action="/carejiyo/demo-request"]//input[@name="csrf_token"]/@value')[0]
        data = {'csrf_token': token, 'started': '', 'name': 'Test Person', 'email': 'demo.test@example.com',
                'organisation': 'Test Care Co', 'phone': '+61 400 000 000', 'care_type': 'both',
                'message': 'We run 30 nurses.'}
        data.update(fields)
        return self.url_open('/carejiyo/demo-request', data=data)

    def test_demo_request_validation(self):
        data, errors = validate_demo_request({'name': ' A ', 'email': 'nope', 'organisation': '', 'phone': 'abc'})
        self.assertEqual(set(errors), {'name', 'email', 'organisation', 'phone'})
        data, errors = validate_demo_request({'name': 'Mai Tran', 'email': 'Mai@Example.com ',
                                              'organisation': 'Clinic', 'care_type': 'evil'})
        self.assertFalse(errors)
        self.assertEqual(data['email'], 'mai@example.com')
        self.assertEqual(data['care_type'], '')

    def test_demo_request_creates_lead_and_queues_email(self):
        brand = homepage_brand(self.env.cr.dbname)
        if brand != 'platform':
            response = self.url_open('/carejiyo/demo-request', data={'name': 'x'})
            self.assertIn(response.status_code, (400, 404))
            self.assertFalse(self.env['crm.lead'].search([('tag_ids.name', '=', TAG_NAME)]).filtered(
                lambda l: l.email_from == 'demo.test@example.com'))
            return
        Lead = self.env['crm.lead'].sudo()
        before = Lead.search_count([('email_from', '=', 'demo.test@example.com')])
        response = self._demo_post()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['ok'])
        lead = Lead.search([('email_from', '=', 'demo.test@example.com')], order='id desc', limit=1)
        self.assertEqual(Lead.search_count([('email_from', '=', 'demo.test@example.com')]), before + 1)
        self.assertEqual(lead.type, 'lead')
        self.assertIn(TAG_NAME, lead.tag_ids.mapped('name'))
        self.assertEqual(lead.partner_name, 'Test Care Co')
        self.assertEqual(lead.source_id.name, 'carejiyo.com')
        self.assertIn('+61 400 000 000', lead.description)  # overseas phone kept in the notes
        mail = self.env['mail.mail'].sudo().search([('model', '=', 'crm.lead'), ('res_id', '=', lead.id)])
        self.assertEqual(mail.email_to, INBOX)
        self.assertIn('Test Care Co', mail.subject)
        # A replay within 10 minutes is answered "ok" without a second lead.
        self.assertTrue(self._demo_post().json()['ok'])
        self.assertEqual(Lead.search_count([('email_from', '=', 'demo.test@example.com')]), before + 1)
        # Honeypot: a filled hidden field is accepted silently and never stored.
        self.assertTrue(self._demo_post(email='bot@example.com', company_website='spam.example').json()['ok'])
        self.assertFalse(Lead.search_count([('email_from', '=', 'bot@example.com')]))
        # Missing details come back as plain field messages, nothing stored.
        bad = self._demo_post(email='not-an-email', name='')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(set(bad.json()['errors']), {'name', 'email'})
        # No CSRF token: refused.
        refused = self.url_open('/carejiyo/demo-request', data={'name': 'x', 'email': 'csrf@example.com',
                                                               'organisation': 'Org'})
        self.assertNotEqual(refused.status_code, 200)
        self.assertFalse(Lead.search_count([('email_from', '=', 'csrf@example.com')]))
