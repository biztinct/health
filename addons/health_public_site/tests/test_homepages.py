from lxml import html
from odoo.tests import HttpCase, tagged
from ..controllers.home import homepage_brand


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
            self.assertIn('ash@biztinct.com', doc.text_content())
        else:
            self.assertIn('Expert care.', doc.text_content())
            self.assertNotIn('THE CONNECTED CARE PLATFORM', doc.text_content())
            self.assertNotIn('ash@biztinct.com', doc.text_content())
            vietnamese = self.url_open('/?site_lang=vi&brand=platform')
            vi = html.fromstring(vietnamese.content)
            self.assertEqual(vi.get('lang'), 'vi')
            self.assertIn('Chăm sóc tận tâm.', vi.text_content())
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
