# -*- coding: utf-8 -*-
"""FS-H4: every Studio field gets the health-information flag its settings
say (`ir.model.fields.fs_phi`, which keeps it out of exports), and the
mobile-app switch goes off where the new rules do not allow it.

An `end-` step on purpose: writing a field row rebuilds the record type it
belongs to, and only once every module is loaded is that record type whole.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'fs.studio' in env:
        env['fs.studio']._reapply_flags()
