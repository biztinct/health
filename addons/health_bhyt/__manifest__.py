# -*- coding: utf-8 -*-
{
    'name': 'Healthcare BHYT Claims (Spine + Coverage Engine)',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Invoicing',
    'summary': 'Turn a completed, invoiced visit into a structured BHYT (social '
               'health insurance) claim with a transparent BHYT-covered vs '
               'patient-copay split, a claim worklist and an append-only '
               'audit. Reads the posted invoice, never writes accounting. '
               'Phase 1 (claim spine + coverage kernel); Decision-4210 XML / '
               'VSS submission is Phase 2.',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'health_invoicing',
        'health_base',
        'health_fieldservice',
        'account',
        'health_consent',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/bhyt_security.xml',
        'data/ir_sequence.xml',
        'data/bhyt_params.xml',
        'data/bhyt_provider_data.xml',
        'data/bhyt_cron.xml',
        'views/bhyt_claim_views.xml',
        'views/res_partner_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/bhyt_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
