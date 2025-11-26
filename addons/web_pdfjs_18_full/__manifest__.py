{
    'name': 'Web PDF.js Full Viewer (Odoo 18 CE)',
    'version': '1.1',
    'category': 'Web',
    'summary': 'Full PDF.js inline viewer with controls for Odoo 18 Community',
    'description': 'Displays PDF inline with zoom, page navigation, and full controls using Mozilla PDF.js',
    'author': 'Custom',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'web_pdfjs_18_full/static/src/js/pdf_viewer.js',
            'web_pdfjs_18_full/static/src/xml/pdf_viewer.xml',
            'web_pdfjs_18_full/static/lib/pdfjs/pdf.js',
            'web_pdfjs_18_full/static/lib/pdfjs/pdf.worker.js',
            'web_pdfjs_18_full/static/lib/pdfjs/viewer.css',
        ],
    },
    'installable': False,
    'application': False,
    'license': 'LGPL-3',
}
