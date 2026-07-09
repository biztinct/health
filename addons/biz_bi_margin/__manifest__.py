# -*- coding: utf-8 -*-
{
    'name': 'BIZ BI — Margin per Visit',
    'version': '19.0.1.0.0',
    'category': 'Analytics',
    'summary': 'Revenue minus direct cost (labor + travel + commission) for '
               'every completed visit, on the BIZ BI platform.',
    'description': """
Margin-per-Visit BI (biz_bi_margin)
===================================

For every completed field-service visit: revenue (quote or package + travel)
minus direct cost (labor + travel + commission) → margin, rolled up by service
type / staff / facility / client / month on a seeded Finance dashboard.

* ``bi_margin_visit`` SQL view — ONE ROW PER COMPLETED FSO, pre-aggregated so
  the BI join graph never fans out over multi-staff attendance.
* Cost-rate config (the two numbers the data lacks): hourly labor cost fallback
  + per-km travel cost, with a per-employee wage override from the active
  hr.version when present. These are COSTING ASSUMPTIONS, labeled as such.
* A ``bi.dataset`` rooted on the view (gold, daily refresh) + a "Visit Margin"
  dashboard, seeded idempotently in the Finance workspace like biz_bi_health.

v1 is rate × time with clearly-labeled assumptions — not payroll-grade costing.
Only completed visits; VND single-currency; no write-back to FSOs.
""",
    'author': 'Biztinct',
    'website': 'https://biztinct.com',
    'license': 'LGPL-3',
    'sequence': 167,
    'depends': [
        'biz_bi',
        'biz_bi_health',
        'health_invoicing',
        'health_workflow_auto',
        'health_evv',
    ],
    'data': [
        'data/bi_margin_config_params.xml',
        'views/res_config_settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
