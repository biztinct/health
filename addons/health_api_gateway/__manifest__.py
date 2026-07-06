# -*- coding: utf-8 -*-
{
    'name': 'Health API Gateway',
    'summary': 'API keys/OAuth2 client-credentials, /api/v1 REST surface, OpenAPI 3.1, webhooks, PHI access audit',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'depends': [
        'base', 'web', 'mail',
        'health_base', 'health_fieldservice', 'health_pwa', 'health_invoicing',
    ],
    # authlib/pydantic are used opportunistically (graceful degradation when
    # missing) so they are intentionally NOT declared as hard external
    # dependencies; deployment should still `pip install authlib pydantic`.
    'data': [
        'security/gateway_security.xml',
        'security/ir.model.access.csv',
        'data/api_scopes.xml',
        'data/gateway_cron.xml',
        'views/api_key_views.xml',
        'views/oauth_client_views.xml',
        'views/webhook_views.xml',
        'views/audit_log_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
