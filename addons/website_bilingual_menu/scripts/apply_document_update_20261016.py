"""Publish the supplied October documents without replacing live client edits.

Run in Odoo shell -d thhs after backing up the DB, filestore and module.
THHS_DOCUMENT_APPLY=1 is required. THHS_DOCUMENT_DRYRUN=1 rolls back.
THHS_DOCUMENT_MODULE can point to a staged copy for pre-deployment validation.
The seven existing pages are patched in place; website 2 is never written.
"""
import base64
import copy
import hashlib
import json
import mimetypes
import os
from pathlib import Path

from lxml import etree

PAGE_URLS = ('/news', '/projects', '/incorporated-society', '/annual-report',
             '/successes', '/how-can-i-help', '/')


def cls(name):
    return "contains(concat(' ',normalize-space(@class),' '),' %s ')" % name


def one(nodes, description):
    if len(nodes) != 1:
        raise RuntimeError(f'Expected one {description}, found {len(nodes)}')
    return nodes[0]


def pdf_link(anchor, href):
    anchor.set('href', href)
    anchor.set('target', '_blank')
    anchor.set('rel', 'noopener')


def transform_page(url, arch, links):
    root = etree.fromstring(arch.encode())
    if url == '/news':
        marker = 'university-training'
        existing = root.xpath('//*[@data-thhs-document="%s"]' % marker)
        if not existing:
            sections = root.xpath('//section[%s]' % cls('thhs26-news'))
            if not sections:
                raise RuntimeError('Latest News sections not found')
            section = copy.deepcopy(sections[0])
            section.set('data-thhs-document', marker)
            # Keep the sole Latest News heading in its original section.
            for heading in section.xpath('.//h2'):
                heading.getparent().remove(heading)
            card = one(section.xpath('.//*[%s]' % cls('thhs26-news-item')), 'news card')
            card.clear()
            card.set('class', 'thhs26-news-item')
            meta = etree.SubElement(card, 'div', {'class': 'thhs26-news-meta'})
            etree.SubElement(meta, 'span').text = 'News Update'
            etree.SubElement(meta, 'time', {'datetime': '2026-09-01'}).text = '1 September 2026'
            headline = 'Taupō Hospital joins university training programme'
            etree.SubElement(card, 'h3').text = headline
            paragraph = etree.SubElement(card, 'p', {'class': 'text-end'})
            anchor = etree.SubElement(paragraph, 'a', {
                'class': 'thhs26-read-more', 'aria-label': 'Read ' + headline})
            anchor.text = 'READ MORE'
            pdf_link(anchor, links['university_training'])
            older = next((s for s in sections if s.xpath('.//time/@datetime')
                          and s.xpath('.//time/@datetime')[0] < '2026-09-01'), None)
            if older is not None:
                older.addprevious(section)
            else:
                sections[-1].addnext(section)
        else:
            section = one(existing, 'university training news section')
            pdf_link(one(section.xpath('.//a'), 'training news link'), links['university_training'])
    elif url == '/projects':
        track = one(root.xpath('//*[%s]' % cls('thhs26-film-track')), 'testimonial track')
        cards = track.xpath('./a[@data-thhs-document="inpatient-tv-units"]')
        if cards:
            card = one(cards, 'TV testimonial')
        else:
            card = etree.Element('a', {'class': 'thhs26-film-card',
                                     'data-thhs-document': 'inpatient-tv-units'})
            track.insert(0, card)
        card.set('aria-label', 'Read Taupō Inpatient TV Units testimonial')
        pdf_link(card, links['inpatient_tv'])
        if not card.xpath('./img'):
            etree.SubElement(card, 'img', {'class': 'img img-fluid', 'loading': 'lazy'})
            etree.SubElement(card, 'span', {'class': 'thhs26-caption'}).text = 'Taupō Inpatient TV Units'
        image = one(card.xpath('./img'), 'TV testimonial photo')
        image.set('src', links['inpatient_tv_photo'])
        image.set('alt', 'Taupō Inpatient TV Units')
    elif url == '/incorporated-society':
        anchor = one(root.xpath('//a[@aria-label="Read the Society constitution"]'), 'Rules link')
        pdf_link(anchor, links['constitution'])
    elif url == '/annual-report':
        # The client explicitly supplied the constitution for the 2024 icon.
        for year, key in [(2023, 'annual_2023'), (2024, 'constitution'), (2025, 'annual_2025')]:
            anchor = one(root.xpath('//a[@aria-label="Open %s Annual Report"]' % year), f'{year} report link')
            pdf_link(anchor, links[key])
    elif url == '/how-can-i-help':
        # Both icons use the same membership AND donation form.
        for label in ['Become a member', 'Donate']:
            anchor = one(root.xpath('//a[@aria-label="%s"]' % label), label + ' link')
            pdf_link(anchor, links['membership'])
    elif url == '/successes':
        section = one(root.xpath('//section[%s]' % cls('thhs26-successes')), 'Successes section')
        image = one(section.xpath('.//img[%s]' % cls('thhs26-thermometer')), 'grants gauge')
        table = one(section.xpath('.//table[%s]' % cls('thhs26-grants')), 'grants table')
        if image.getparent().tag != 'a':
            column = image.getparent()
            column.set('class', 'col-12 text-center o_colored_level')
            column.remove(image)
            anchor = etree.SubElement(column, 'a', {
                'class': 'thhs26-gauge-link', 'href': '#thhs-grants-table',
                'aria-label': 'View grants and purchases table'})
            anchor.append(image)
            etree.SubElement(anchor, 'span', {'class': 'd-block mt-2'}).text = 'View grants and purchases'
        else:
            image.getparent().set('href', '#thhs-grants-table')
        panel = table.getparent().getparent()
        panel.set('class', 'col-12 o_colored_level')
        panel.set('id', 'thhs-grants-table')
        panel.set('tabindex', '-1')
        panel.set('role', 'region')
        panel.set('aria-labelledby', 'thhs-grants-heading')
        if not panel.xpath('./h2[@id="thhs-grants-heading"]'):
            heading = etree.Element('h2', {'id': 'thhs-grants-heading', 'class': 'thhs26-label'})
            heading.text = 'Grants and purchases'
            panel.insert(0, heading)
        if not image.getparent().getparent().getnext() == panel:
            raise RuntimeError('Gauge must immediately precede the table panel')
    elif url == '/':
        image = one(root.xpath('//img[%s]' % cls('thhs26-welcome-photo')), 'homepage photo')
        if image.getparent().tag != 'picture':
            frame = image.getparent()
            index = frame.index(image)
            frame.remove(image)
            picture = etree.Element('picture', {'data-thhs-document': 'welcome-wide'})
            frame.insert(index, picture)
            picture.append(image)
        picture = image.getparent()
        sources = picture.xpath('./source')
        source = one(sources, 'landscape photo source') if sources else etree.Element('source')
        source.set('media', '(min-width: 768px) and (min-aspect-ratio: 4/3)')
        source.set('srcset', links['welcome_wide'])
        if not sources:
            picture.insert(0, source)
        image.set('loading', 'eager')
        image.set('fetchpriority', 'high')
    return etree.tostring(root, encoding='unicode')


def apply_update(env):
    if os.environ.get('THHS_DOCUMENT_APPLY') != '1' or env.cr.dbname != 'thhs':
        raise RuntimeError('Requires THHS_DOCUMENT_APPLY=1 and database thhs')
    from odoo.modules.module import get_module_path

    module = Path(os.environ.get('THHS_DOCUMENT_MODULE') or get_module_path('website_bilingual_menu'))
    specs = json.loads((module / 'data/document_update_20261016.json').read_text())['assets']
    website = env['website'].browse(1).exists()
    if not website or 'Society' not in website.name:
        raise RuntimeError('Expected Taupō Society website 1')
    pages = env['website.page'].search([('website_id', '=', 1), ('url', 'in', PAGE_URLS)])
    if len(pages) != len(PAGE_URLS) or set(pages.mapped('url')) != set(PAGE_URLS):
        raise RuntimeError('Expected all seven existing target pages')
    links = {}
    for key, spec in specs.items():
        data = (module / 'static/client_updates_20261016' / spec['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != spec['sha256']:
            raise RuntimeError('Asset checksum mismatch: ' + key)
        url = '/thhs-client-20261016/' + spec['file']
        attachment = env['ir.attachment'].search([('website_id', '=', 1), ('url', '=', url)])
        if len(attachment) > 1:
            raise RuntimeError('Duplicate attachment: ' + key)
        values = {'name': spec['name'], 'type': 'binary', 'datas': base64.b64encode(data),
                  'mimetype': mimetypes.guess_type(spec['file'])[0], 'public': True,
                  'website_id': 1, 'url': url}
        if attachment:
            if attachment.checksum != hashlib.sha1(data).hexdigest():
                attachment.write(values)
        else:
            attachment = env['ir.attachment'].create(values)
        route = 'image' if values['mimetype'].startswith('image/') else 'content'
        links[key] = f'/web/{route}/{attachment.id}'
    changed = []
    for url in PAGE_URLS:
        view = pages.filtered(lambda page: page.url == url).view_id.with_context(lang='en_US')
        original = view.arch_db
        updated = transform_page(url, original, links)
        if transform_page(url, updated, links) != updated:
            raise RuntimeError('Non-idempotent update: ' + url)
        if updated != original:
            view.write({'arch_db': updated})
            changed.append(url)
    params = env['ir.config_parameter'].sudo()
    params.set_param('thhs.client_2026.constitution', links['constitution'])
    pending = params.get_param('thhs.client_2026.pending_links', '')
    params.set_param('thhs.client_2026.pending_links', ','.join(
        key for key in pending.split(',') if key and 'constitution' not in key.lower()))
    env.flush_all()
    print('Document update pages:', changed)
    print('Published asset routes:', json.dumps(links, sort_keys=True))
    if os.environ.get('THHS_DOCUMENT_DRYRUN') == '1':
        env.cr.rollback()
        print('DRY RUN PASSED; transaction rolled back')
    else:
        env.cr.commit()
        print('Document update committed; other pages and website 2 unchanged')


if 'env' in globals():
    apply_update(env)
