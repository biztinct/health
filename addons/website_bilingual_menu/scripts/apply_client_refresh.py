"""Explicit Odoo-shell import of the approved client pages.

THHS_CLIENT_APPLY=1 is required. Imports only website 1 in database thhs;
never runs as a module hook. Back up the DB and filestore before running.
The original client documents remain byte-for-byte intact as attachments.
"""
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
from lxml import etree
from odoo.modules.module import get_module_path

if os.environ.get('THHS_CLIENT_APPLY') != '1':
    raise RuntimeError('Set THHS_CLIENT_APPLY=1 after taking a database and filestore backup.')
if env.cr.dbname != 'thhs':
    raise RuntimeError('This client import is scoped to database thhs.')

dryrun = os.environ.get('THHS_CLIENT_DRYRUN') == '1'
module = Path(os.environ.get('THHS_CLIENT_MODULE') or get_module_path('website_bilingual_menu'))
payload = json.loads((module/'data/client_refresh_2026.json').read_text())
website = env['website'].browse(1).exists()
if not website or 'Society' not in website.name:
    raise RuntimeError('Expected Taupō Hospital & Health Society website 1.')
attachments = {}
for name, spec in payload['assets'].items():
    data = (module/'static/client_2026'/spec['file']).read_bytes()
    if hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise RuntimeError(f'Asset checksum mismatch: {name}')
    domain = [('url', '=', '/thhs-client-2026/'+name), ('website_id','=',website.id)]
    attachment = env['ir.attachment'].search(domain,limit=1)
    vals = {'name':name, 'type':'binary','datas':base64.b64encode(data),
            'mimetype':mimetypes.guess_type(name)[0] or 'application/octet-stream',
            'public':True,'website_id':website.id,'url':'/thhs-client-2026/'+name}
    if attachment:
        attachment.write(vals)
    else:
        attachment=env['ir.attachment'].create(vals)
    attachments[name]=attachment

params = env['ir.config_parameter'].sudo()
links = {key:params.get_param('thhs.client_2026.'+key,'') for key in ['constitution','facebook','givealittle']}
links['facebook'] = links['facebook'] or 'https://www.facebook.com/TaupoHospitalHealthSociety'
missing = [key for key,value in links.items() if not value]
if missing and not dryrun:
    raise RuntimeError('Missing approved link configuration: '+', '.join(missing))
if dryrun:
    links = {key:value or '/contactus' for key,value in links.items()}
    from odoo.tools.convert import convert_xml_import
    with (module/'views/client_snippets.xml').open('rb') as source:
        convert_xml_import(env,'website_bilingual_menu',source,{},mode='update',noupdate=False)

def replace_assets(match):
    attachment=attachments[match.group(1)]
    route='image' if attachment.mimetype.startswith('image/') else 'content'
    return f'/web/{route}/{attachment.id}'

for spec in payload['pages']:
    page = env['website.page'].with_context(active_test=False).search([('url','=',spec['url']),('website_id','=',website.id)],limit=1)
    content = re.sub(r'@@ASSET:([^@]+)@@',replace_assets,spec['content'])
    for key,value in links.items():
        content = content.replace('@@'+key.upper()+'@@', __import__('html').escape(value,quote=True))
    if '@@' in content:
        raise RuntimeError('Unresolved content token: '+spec['url'])
    key=page.view_id.key if page else 'website.thhs26_'+(spec['url'].strip('/').replace('-','_') or 'home')
    arch=f'<t t-name="{key}"><t t-call="website.layout"><div id="wrap" class="oe_structure oe_empty thhs26">{content}</div></t></t>'
    etree.fromstring(arch.encode())
    if page:
        page.view_id.with_context(lang='en_US').write({'arch_db':arch})
        page.write({'name':spec['name'],'is_published':True})
    else:
        view=env['ir.ui.view'].create({'name':spec['name'],'key':key,'type':'qweb','arch_db':arch,'website_id':website.id})
        page=env['website.page'].create({'name':spec['name'],'url':spec['url'],'view_id':view.id,'website_id':website.id,'is_published':True})
    print('Imported page',page.id,spec['url'])

root=website.menu_id
existing=list(root.child_id.sorted('sequence'))
for index,(name,children) in enumerate(payload['menus']):
    parent=existing[index] if index<len(existing) else env['website.menu'].create({'name':name,'parent_id':root.id,'website_id':website.id})
    parent.write({'name':name,'url':'#','sequence':index})
    current=list(parent.child_id.sorted('sequence'))
    for sequence,(label,url) in enumerate(children):
        menu=current[sequence] if sequence<len(current) else env['website.menu'].create({'name':label,'parent_id':parent.id,'website_id':website.id})
        menu.write({'name':label,'url':url,'sequence':sequence,'page_id':False})
    # These are obsolete links in the five explicitly replaced menu groups only.
    for menu in current[len(children):]:
        menu.unlink()
website.write({'social_facebook':links['facebook']})
params.set_param('thhs.client_2026.imported','2026-09-28')
if dryrun:
    env.flush_all()
    env.cr.rollback()
    print('DRY RUN PASSED and rolled back: %s pages, %s assets, snippet templates and menu entries' % (len(payload['pages']),len(attachments)))
else:
    env.cr.commit()
    print('Committed client refresh: %s pages, %s assets' % (len(payload['pages']),len(attachments)))
