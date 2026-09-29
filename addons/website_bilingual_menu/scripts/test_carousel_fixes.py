"""Content-preservation and idempotency tests, independent of the Odoo server."""
import json
from pathlib import Path
import unittest
from lxml import etree
from carousel_markup import upgrade_carousels


class CarouselFixTests(unittest.TestCase):
    def test_live_edits_preserved_and_idempotent(self):
        payload = json.loads((Path(__file__).resolve().parents[1] / 'data/client_refresh_2026.json').read_text())
        for page in payload['pages']:
            if page['url'] not in ('/successes', '/our-board', '/our-patrons', '/associate-members'):
                continue
            with self.subTest(url=page['url']):
                root = etree.fromstring(('<main><div id="wrap">'+page['content']+'</div></main>').encode())
                if page['url'] == '/successes':
                    wrap = root.find('div')
                    sections = root.xpath('.//section[@data-snippet="s_text_block" or @data-snippet="s_picture"]')
                    wrap.clear()
                    wrap.set('id', 'wrap')
                    wrap.extend(sections)
                else:
                    el = root.xpath('.//*[@data-bs-interval]')[0]
                    el.set('class', el.get('class')+' slide')
                # Simulate newer content entered through the live editor.
                root.xpath('.//h2 | .//h1')[0].text = 'Client live edit & Māori text'
                original = etree.tostring(root, encoding='unicode')
                after = upgrade_carousels(original, page['url'])
                updated = etree.fromstring(after.encode())
                self.assertIn('Client live edit &amp; Māori text', after)
                self.assertEqual(root.xpath('.//img/@src'), updated.xpath('.//img/@src'))
                self.assertEqual(root.xpath('.//tbody//text()'), updated.xpath('.//tbody//text()'))
                self.assertEqual(root.xpath('.//p//text()'), updated.xpath('.//p//text()'))
                self.assertFalse(updated.xpath('.//*[contains(concat(" ",@class," ")," slide ")]'))
                self.assertEqual(after, upgrade_carousels(after, page['url']))
                expected = 8 if page['url'] == '/our-board' else 2
                self.assertEqual(expected, len(updated.xpath('.//*[contains(concat(" ",@class," ")," carousel-item ")]')))

    def test_unexpected_live_layout_fails_safely(self):
        with self.assertRaises(ValueError):
            upgrade_carousels('<main><div id="wrap"><p>Unknown design</p></div></main>', '/successes')


if __name__ == '__main__':
    unittest.main()
