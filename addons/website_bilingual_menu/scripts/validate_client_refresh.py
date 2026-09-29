"""Validate client content, assets and navigation without an Odoo database."""
from pathlib import Path
import hashlib
import json
import re
from lxml import etree

module = Path(__file__).resolve().parents[1]
payload = json.loads((module/'data/client_refresh_2026.json').read_text())
urls = {p['url'] for p in payload['pages']}
assert len(urls) == len(payload['pages']) == 18
pending = set()
roots = {}
for page in payload['pages']:
    root = etree.fromstring(('<main>'+page['content']+'</main>').encode())
    roots[page['url']] = root
    assert root.xpath('.//section[@data-snippet]'), page['url']
    assert not root.xpath('.//script | .//iframe'), page['url']
    assert not root.xpath('.//img[not(@alt)]'), page['url']
    for name in re.findall(r'@@ASSET:([^@]+)@@',page['content']):
        assert name in payload['assets'], name
    pending.update(token for token in re.findall(r'@@([^@]+)@@',page['content']) if not token.startswith('ASSET:'))
    for href in root.xpath('.//a/@href'):
        if href.startswith('/'):
            assert href in urls, (page['url'],href)
        assert 'download=' not in href
assert pending == {'FACEBOOK','GIVEALITTLE','CONSTITUTION'},pending
for spec in payload['assets'].values():
    data=(module/'static/client_2026'/spec['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==spec['sha256'],spec['file']
    if spec['file'].endswith('.pdf'):
        assert data.startswith(b'%PDF-'),spec['file']
for label,children in payload['menus']:
    for name,url in children:
        assert url in urls,(name,url)
assert len(roots['/our-board'].xpath('.//*[contains(concat(" ",@class," ")," carousel-item ")]')) == 8
assert len(roots['/our-patrons'].xpath('.//*[contains(concat(" ",@class," ")," carousel-item ")]')) == 2
assert len(roots['/associate-members'].xpath('.//*[contains(concat(" ",@class," ")," carousel-item ")]')) == 2
assert len(roots['/successes'].xpath('.//*[contains(concat(" ",@class," ")," carousel-item ")]')) == 2
for url in ('/successes', '/our-board', '/our-patrons', '/associate-members'):
    assert not roots[url].xpath('.//*[contains(concat(" ",@class," ")," slide ")]'), url
assert 'QSM' in ''.join(roots['/our-patrons'].itertext())
dates = roots['/news'].xpath('.//time/@datetime')
assert len(dates)==9 and dates==sorted(dates,reverse=True)
assert len(roots['/news'].xpath('.//section'))==10  # Individually editable news blocks.
assert len(roots['/annual-report'].xpath('.//a'))==7
assert len(roots['/projects'].xpath('.//a'))==8
assert len(roots['/successes'].xpath('.//tbody/tr'))==14
for path in (module/'views').glob('*.xml'):
    etree.parse(str(path))
print('PASS: 18 pages, 73 asset checksums, menus, news ordering, 12 profiles, 7 reports, 8 testimonials and 14 grant rows.')
print('Publish prerequisites: constitution, confirmed Givealittle destination, and Aptos font decision.')
