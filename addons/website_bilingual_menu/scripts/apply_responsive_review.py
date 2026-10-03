"""Apply the client's screenshot corrections to current website 1 content.
Run in Odoo shell, database thhs. Idempotent; never replaces unrelated copy.
"""
from lxml import etree

def cls(name):
    return "contains(concat(' ',normalize-space(@class),' '),' %s ')" % name

for url in ['/projects', '/incorporated-society', '/how-can-i-help', '/our-hospital']:
    page = env['website.page'].search([('website_id', '=', 1), ('url', '=', url)], limit=1)
    if not page:
        raise RuntimeError('Missing page: ' + url)
    view = page.view_id.with_context(lang='en_US')
    root = etree.fromstring(view.arch_db.encode())
    dirty = False
    if url == '/projects':
        if len(root.xpath('//*[%s]//a[img]' % cls('thhs26-film-track'))) < 8:
            raise RuntimeError('Published rolling testimonials must exist before removing static duplicates')
        for node in root.xpath('//*[%s]//div[%s] | //*[%s]' % (cls('thhs26-testimonials'), cls('row'), cls('thhs26-film-controls'))):
            node.getparent().remove(node)
            dirty = True
    for section in root.xpath('//div[@id="wrap"]/section[position()>1]'):
        if url != '/projects':
            classes = section.get('class','').split()
            updated = ['pt16' if c == 'pt32' else 'pb16' if c == 'pb32' else c for c in classes]
            if updated != classes:
                section.set('class', ' '.join(updated))
                dirty = True
    if dirty:
        view.write({'arch_db': etree.tostring(root, encoding='unicode')})
        print('Updated', url)
env.cr.commit()
print('Responsive review committed; other pages and website 2 unchanged')
