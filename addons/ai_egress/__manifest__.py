# -*- coding: utf-8 -*-
{
    'name': 'AI Egress Guard',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'What may leave this server, and to whom',
    'description': """
One gate every AI prompt passes through before it reaches a provider.

Records may only reach a model running on infrastructure we control. Schema and
aggregates may go anywhere. The classification is declared where the prompt is
built, and a pattern backstop refuses prompts whose contents contradict the
declaration.

Deliberately tiny and dependency-free so that anything which talks to a model
can depend on it — see egress.py for the policy and its stated limits.
    """,
    'author': 'Biztinct',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_egress_log_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
