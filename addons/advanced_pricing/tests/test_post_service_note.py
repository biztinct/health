# -*- coding: utf-8 -*-
"""The post-service price note renders as HTML (UAT round 10, item 6)."""
import importlib.util
import os

from markupsafe import Markup

from odoo.tests import TransactionCase, tagged


def _migration():
    path = os.path.join(os.path.dirname(__file__), '..', 'migrations',
                        '19.0.1.3.4', 'post-migrate.py')
    spec = importlib.util.spec_from_file_location('ap_r10_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged('post_install', '-at_install')
class TestPostServiceNote(TransactionCase):

    def test_note_is_markup_with_a_real_list(self):
        body = self.env['sale.order']._post_service_note_body(
            600000, 550000, -50000,
            [{'desc': '+50,000 đ', 'label': 'Is after hours or weekend'},
             {'desc': '<script>', 'label': 'a & b'}])
        self.assertIsInstance(body, Markup)
        self.assertIn('<br/>', body)
        self.assertIn('<ul><li><b>+50,000 đ</b> Is after hours or weekend</li>', body)
        self.assertIn('&lt;script&gt;', body, 'rule words are escaped')
        self.assertIn('a &amp; b', body)
        self.assertNotIn('&lt;ul&gt;', body)

    def test_note_without_rules(self):
        body = self.env['sale.order']._post_service_note_body(1, 2, 1, [])
        self.assertNotIn('<ul>', body)
        self.assertIn('Post-service price recalculated', body)

    def test_posted_note_keeps_its_html(self):
        order = self.env['sale.order'].create(
            {'partner_id': self.env['res.partner'].create({'name': 'R10 n'}).id})
        msg = order.message_post(body=order._post_service_note_body(
            600000, 550000, -50000, [{'desc': '+50,000 đ', 'label': 'Rule'}]))
        self.assertIn('<ul><li>', msg.body)
        self.assertNotIn('&lt;br/&gt;', msg.body)

    def test_migration_rebuilds_only_the_broken_shape(self):
        mig = _migration()
        broken = ('<span>Post-service price recalculated: 600,000 đ → 550,000 đ '
                  '(-50,000 đ).&lt;br/&gt;Applied rules:&lt;ul&gt;&lt;li&gt;&lt;b&gt;'
                  '+50,000 đ&lt;/b&gt; Is after hours or weekend&lt;/li&gt;&lt;/ul&gt;</span>')
        self.assertEqual(
            mig.rebuild(broken),
            'Post-service price recalculated: 600,000 đ → 550,000 đ (-50,000 đ).'
            '<br/>Applied rules:<ul><li><b>+50,000 đ</b> Is after hours or '
            'weekend</li></ul>')
        self.assertIsNone(mig.rebuild('<p>Some other note &lt;br/&gt;</p>'))
        self.assertIsNone(mig.rebuild(
            '<span>Post-service price recalculated: x&lt;br/&gt;&lt;script&gt;</span>'))
