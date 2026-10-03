"""Targeted approved October review; run inside Odoo shell -d thhs.

Reads current website 1 views, never reruns the replacement importer. Repeated
runs preserve editable strip/captions. Set THHS_REVIEW_DRYRUN=1 to roll back.
"""
import copy
import os
from lxml import etree

DONATION = 'https://givealittle.co.nz/org/taupo-hospital-and-health-society-inc'

def has_class(name):
    return "contains(concat(' ', normalize-space(@class), ' '), ' %s ')" % name

pages = env['website.page'].search([('website_id', '=', 1)])
changed = []
for page in pages:
    view = page.view_id.with_context(lang='en_US')
    original = view.arch_db
    root = etree.fromstring(original.encode())
    dirty = False
    if page.url == '/our-patrons':
        for node in root.xpath('//p'):
            if node.text and '105th birthday' in node.text:
                node.text = node.text.replace('105th birthday', '106th birthday')
                dirty = True
    # Identify the Givealittle CTA by its image, never the separate Donate PDF.
    for anchor in root.xpath('//a[.//img]'):
        description = ' '.join(anchor.itertext()) + ' ' + anchor.get('aria-label', '')
        description += ' ' + ' '.join(i.get('alt', '') for i in anchor.xpath('.//img'))
        if 'givealittle' in description.lower().replace(' ', '') and anchor.get('href') != DONATION:
            anchor.set('href', DONATION)
            anchor.set('target', '_blank')
            anchor.set('rel', 'noopener')
            dirty = True
    if page.url == '/news':
        for node in root.xpath('//*[%s]/span[1]' % has_class('thhs26-news-meta')):
            label = 'Media Update' if 'media' in (node.text or '').lower() else 'News Update'
            if node.text != label:
                node.text = label
                dirty = True
    if page.url == '/social-media' and not root.xpath('//*[%s]' % has_class('thhs26-instagram')):
        destination = root.xpath('//*[%s]//p' % has_class('thhs26-social'))[0]
        icon = etree.SubElement(destination, 'span', {'class': 'thhs26-instagram', 'role': 'img', 'aria-label': 'Instagram'})
        etree.SubElement(icon, 'span', {'class': 'fa fa-instagram', 'aria-hidden': 'true'})
        etree.SubElement(icon, 'span', {'aria-hidden': 'true'}).text = 'Instagram'
        dirty = True
    if page.url == '/projects':
        anchors = root.xpath('//*[%s]//div[%s]//a[img]' % (has_class('thhs26-testimonials'), has_class('row')))
        for anchor in anchors:
            if not anchor.xpath('./span[%s]' % has_class('thhs26-caption')):
                etree.SubElement(anchor, 'span', {'class': 'thhs26-caption'}).text = anchor.find('img').get('alt', '')
                dirty = True
        if not root.xpath('//*[%s]' % has_class('thhs26-film')):
            if not anchors:
                raise RuntimeError('No approved testimonial cards found')
            wrap = root.xpath('//div[@id="wrap"]')[0]
            section = etree.SubElement(wrap, 'section', {'class': 's_text_block thhs26-film o_colored_level pt32 pb32', 'data-snippet': 's_text_block', 'data-name': 'Rolling testimonials'})
            container = etree.SubElement(section, 'div', {'class': 'container'})
            etree.SubElement(container, 'h2', {'class': 'thhs26-label'}).text = 'TESTIMONIAL STORIES'
            controls = etree.SubElement(container, 'div', {'class': 'thhs26-film-controls o_not_editable', 'contenteditable': 'false'})
            for action, label in [('previous', 'Previous testimonials'), ('pause', 'Pause testimonials'), ('next', 'Next testimonials')]:
                etree.SubElement(controls, 'button', {'type': 'button', 'class': 'btn btn-outline-primary', 'data-film': action, 'aria-controls': 'thhs-testimonial-window'}).text = label
            window = etree.SubElement(container, 'div', {'id': 'thhs-testimonial-window', 'class': 'thhs26-film-window', 'tabindex': '0', 'role': 'region', 'aria-label': 'Rolling testimonial stories'})
            track = etree.SubElement(window, 'div', {'class': 'thhs26-film-track'})
            for anchor in anchors:
                card = copy.deepcopy(anchor)
                card.set('class', 'thhs26-film-card')
                track.append(card)
            dirty = True
    if dirty:
        view.write({'arch_db': etree.tostring(root, encoding='unicode')})
        changed.append(page.url)
params = env['ir.config_parameter'].sudo()
params.set_param('thhs.client_2026.givealittle', DONATION)
pending = params.get_param('thhs.client_2026.pending_links', '')
# Preserve constitution's pending status while removing the now-confirmed link.
if pending:
    params.set_param('thhs.client_2026.pending_links', ','.join(x for x in pending.split(',') if 'givealittle' not in x.lower()))
print('Targeted review updated:', changed)
if os.environ.get('THHS_REVIEW_DRYRUN') == '1':
    env.cr.rollback()
    print('DRY RUN rolled back')
else:
    env.cr.commit()
    print('Review committed; website 2 unchanged')
