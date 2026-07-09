# -*- coding: utf-8 -*-
"""Re-apply the bi_margin_visit view on every module update.

The post_init hook (which also executes this SQL before seeding) only runs at
INSTALL — a view edit deployed with ``-u biz_bi_margin`` would otherwise never
reach the database. ``init()`` runs on each update; CREATE OR REPLACE VIEW is
idempotent.
"""
import os

from odoo import models

_SQL_PATH = os.path.join(os.path.dirname(__file__), '..',
                         'data', 'bi_margin_visit_view.sql')


class BiMarginView(models.AbstractModel):
    _name = 'bi.margin.view'
    _description = 'Margin view DDL (re-applied on update)'

    def init(self):
        with open(_SQL_PATH, encoding='utf-8') as handle:
            self.env.cr.execute(handle.read())
