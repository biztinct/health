"""Center section headings above current news content, preserving live articles.
Run in Odoo shell for thhs; changes only website 1 /news and /archive-news.
"""
from lxml import etree

for url, label in [('/news', 'LATEST NEWS'), ('/archive-news', 'ARCHIVED NEWS')]:
    page = env['website.page'].search([('website_id', '=', 1), ('url', '=', url)], limit=1)
    if not page:
        raise RuntimeError('Missing page: ' + url)
    view = page.view_id.with_context(lang='en_US')
    root = etree.fromstring(view.arch_db.encode())
    headings = root.xpath('//h2[normalize-space(.)=$label]', label=label)
    if len(headings) != 1:
        raise RuntimeError('Expected one section heading on ' + url)
    heading = headings[0]
    container = next((p for p in heading.iterancestors() if 'container' in p.get('class', '').split()), None)
    if container is None:
        raise RuntimeError('Missing editable container on ' + url)
    classes = heading.get('class', '').split()
    dirty = False
    if 'text-center' not in classes:
        heading.set('class', ' '.join(classes + ['text-center']))
        dirty = True
    if heading.getparent() is not container:
        heading.getparent().remove(heading)
        container.insert(0, heading)
        dirty = True
    if dirty:
        view.write({'arch_db': etree.tostring(root, encoding='unicode')})
        print('Centered heading:', url)
env.cr.commit()
