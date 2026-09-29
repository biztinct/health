# WS-3 X2 — apply the CORRECTED Vietnamese of a few known-wrong strings to the
# database. Model terms load with overwrite OFF on an upgrade (ledger §5.244),
# so a re-worded msgstr never reaches a database whose row already holds the old
# Vietnamese. This loads ONLY the named entries from each owning module's
# catalogue and saves them with overwrite on — nothing else is touched.
#
# Run with `carejiox-deploy -D <db> -x <this file>` (odoo shell, service down),
# or piped into `odoo-bin shell` on a practice copy.
import os

from odoo.modules.module import get_module_path
from odoo.tools.translate import TranslationImporter

# module, catalogue, msgids to force (model terms) / field xmlids to force
TARGETS = [
    ('health_invoicing', 'vi_VN.po', {'Pay Quote'}, None),
    ('health_fieldservice', 'vi_VN.po',
     {'<strong><i class="fa fa-exclamation-triangle"/> ALLERGIES:</strong>', 'Gender'}, None),
    ('health_crm', 'vi_VN.po', {'Book'}, {'health_crm.field_crm_lead__mode_of_contact_id'}),
    # a field label: selected by the field's xmlid (no source-term key)
    ('health_base', 'vi_VN.po', None,
     {'health_base.field_res_partner__gender_id', 'health_base.field_res_users__gender_id'}),
    # new tab labels on views whose module is not upgraded in this release
    ('advanced_pricing', 'vi_VN.po', {'Pricing'}, None),
    ('health_careplan', 'vi.po', {'Visit Tasks'}, None),
    ('health_family_link', 'vi.po', {'Family Updates'}, None),
    ('health_telehealth', 'vi.po', {'Telehealth'}, None),
]

report = []
for module, fname, terms, field_xmlids in TARGETS:
    if not env['ir.module.module'].search([('name', '=', module), ('state', '=', 'installed')]):
        report.append('%s: not installed, skipped' % module)
        continue
    path = os.path.join(get_module_path(module), 'i18n', fname)
    imp = TranslationImporter(env.cr, verbose=False)
    imp.load_file(path, 'vi_VN')
    kept = 0
    # model terms: keep only the named source terms
    for model, by_field in list(imp.model_terms_translations.items()):
        for field, by_xmlid in list(by_field.items()):
            for xmlid, by_src in list(by_xmlid.items()):
                for src in list(by_src):
                    if not terms or src not in terms:
                        del by_src[src]
                    else:
                        kept += 1
                if not by_src:
                    del by_xmlid[xmlid]
    # model (field label) translations: keep only the named xmlids
    for model, by_field in list(imp.model_translations.items()):
        for field, by_xmlid in list(by_field.items()):
            for xmlid in list(by_xmlid):
                if not field_xmlids or xmlid not in field_xmlids:
                    del by_xmlid[xmlid]
                else:
                    kept += 1
    imp.save(overwrite=True)
    env.cr.commit()
    report.append('%s: %s entries written' % (module, kept))

print('WS3-I18N', ' | '.join(report))
