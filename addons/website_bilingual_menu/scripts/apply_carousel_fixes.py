"""Run explicitly in Odoo shell after backup; no broad content re-import.

THHS_CAROUSEL_APPLY=1 commits, otherwise dry-runs and rolls back.
"""
import os
import sys
from pathlib import Path
from odoo.modules.module import get_module_path

sys.path.insert(0, str(Path(get_module_path('website_bilingual_menu')) / 'scripts'))
from carousel_markup import upgrade_carousels

if env.cr.dbname != 'thhs':
    raise RuntimeError('This migration is scoped to database thhs')
website = env['website'].browse(1).exists()
if not website or 'Society' not in website.name:
    raise RuntimeError('Expected Taupō Hospital & Health Society website 1')

for url in ('/successes', '/our-patrons', '/associate-members', '/our-board'):
    pages = env['website.page'].with_context(active_test=False).search([
        ('website_id', '=', website.id), ('url', '=', url),
    ])
    if len(pages) != 1:
        raise RuntimeError(f'Expected exactly one page for {url}')
    view = pages.view_id.with_context(lang='en_US')
    updated = upgrade_carousels(view.arch_db, url)
    if updated != view.arch_db:
        view.write({'arch_db': updated})
        print('Updated carousel, preserving live content:', url)
    else:
        print('Already current:', url)
env.flush_all()
if os.environ.get('THHS_CAROUSEL_APPLY') == '1':
    env.cr.commit()
    print('COMMITTED carousel fixes to thhs / website 1')
else:
    env.cr.rollback()
    print('DRY RUN PASSED; rolled back')
