# Part of the Viet Uc Care white-label layer. License LGPL-3.
"""Exported files are named after what a person sees (UAT round 9).

Core names every list export "<model name> (<technical model>)", e.g.
"AR Transaction Log (health.ar.transaction.log).xlsx", so the platform's
internal names travel with every file a customer downloads. The readable
name alone is used here ("AR Transaction Log.xlsx"), in the user's language.
"""
from odoo.http import request

from odoo.addons.web.controllers.export import CSVExport, ExcelExport


def readable_export_name(base):
    """File name (no extension) for an export of model `base`."""
    if not request or base not in request.env:
        return base
    return request.env['ir.model']._get(base).name or base


class BrandedCSVExport(CSVExport):
    def filename(self, base):
        return readable_export_name(base)


class BrandedExcelExport(ExcelExport):
    def filename(self, base):
        return readable_export_name(base)
