# Part of the Viet Uc Care white-label layer. License LGPL-3.
"""UAT round 9: an exported list is named after what a person sees —
"Contact.xlsx", never "Contact (res.partner).xlsx"."""
import json
from urllib.parse import unquote

from odoo import http
from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestExportFileName(HttpCase):

    def setUp(self):
        super().setUp()
        self.user = new_test_user(self.env, login="r9_export_probe", password="r9_export_probe!1",
                                  groups="base.group_user,base.group_allow_export")

    def _export(self, fmt):
        user = self.user
        self.authenticate("r9_export_probe", "r9_export_probe!1")
        data = {
            "model": "res.partner", "fields": [{"name": "name", "label": "Name", "type": "char"}],
            "ids": [user.partner_id.id], "domain": [],  # a record this user may read
            "import_compat": False, "context": {},
        }
        res = self.url_open("/web/export/%s" % fmt, data={
            "data": json.dumps(data), "csrf_token": http.Request.csrf_token(self)})
        res.raise_for_status()
        return unquote(res.headers.get("Content-Disposition", ""))

    def test_xlsx_and_csv_names_carry_no_technical_name(self):
        name = self.env["ir.model"]._get("res.partner").name
        for fmt, ext in (("xlsx", ".xlsx"), ("csv", ".csv")):
            disposition = self._export(fmt)
            self.assertNotIn("res.partner", disposition, fmt)
            self.assertIn(name + ext, disposition, fmt)
