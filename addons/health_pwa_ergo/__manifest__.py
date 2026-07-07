{
    'name': 'Health PWA Ergonomic Modes',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Glove mode + sunlight (high-contrast) mode for the field PWA',
    'author': 'Biztinct',
    # Pure front-of-house: CSS + a small JS toggle injected into the PWA shell.
    # No models, no security, no crons, no config params.
    'depends': ['health_pwa'],
    'data': [
        'views/pwa_shell_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'sequence': 146,
    'license': 'LGPL-3',
}
