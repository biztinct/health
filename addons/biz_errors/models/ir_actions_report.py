# Part of biz_errors — the branded breakdown screen.
# License LGPL-3.
"""A PDF that cannot be produced says so in one plain sentence (UAT round 7).

The PDF engine's failure message carries its command output — server folder
paths with the vendor's name, flags, memory errors — and core shows it to the
person who pressed Print. Engine failures are logged in full here and replaced
by a neutral message; a report's own business message (any other UserError)
passes through untouched. System administrators keep the technical text.
"""
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Markers of a PDF-engine failure in core's messages (never shown to a person).
_ENGINE_MARKERS = ('wkhtmltopdf', 'merge the generated pdfs', 'pdf can not be created',
                   'unpatched qt')


def _is_engine_failure(exc):
    text = str(exc.args[0] if exc.args else exc).lower()
    return any(m in text for m in _ENGINE_MARKERS)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        try:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        except UserError as exc:
            if not _is_engine_failure(exc) or self.env.user.has_group('base.group_system'):
                raise
            _logger.error('PDF creation failed for report %r, records %r (plain message shown): %s',
                          report_ref, res_ids, exc)
            self = self.with_context(lang=self.env.user.lang or self.env.lang)
            raise UserError(_('The PDF could not be created. Please try again in a moment; '
                              'if it keeps failing, contact support.')) from None
