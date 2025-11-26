
odoo.define('web_pdfjs_18_full.PDFViewer', function (require) {
    "use strict";
    const AbstractAction = require('web.AbstractAction');
    const core = require('web.core');

    const PDFViewer = AbstractAction.extend({
        template: 'PDFJSFullViewer',
        init: function (parent, action) {
            this._super(parent, action);
            this.pdf_url = action.params.pdf_url;
        },
        start: function () {
            const iframe = this.$('.o_pdf_frame');
            iframe.attr('src', `/web_pdfjs_18_full/static/lib/pdfjs/web/viewer.html?file=${this.pdf_url}`);
            return this._super();
        },
    });

    core.action_registry.add('pdf_js_full_viewer', PDFViewer);
    return PDFViewer;
});
