# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class HealthPWAPushSubscription(models.Model):
    """Store browser push notification subscriptions per user"""
    _name = 'health.pwa.push.subscription'
    _description = 'PWA Push Notification Subscription'
    _order = 'create_date desc'

    user_id = fields.Many2one(
        'res.users', string='User', required=True, ondelete='cascade',
        index=True, default=lambda self: self.env.uid)
    endpoint = fields.Text('Push Endpoint', required=True)
    p256dh_key = fields.Char('P256DH Key', required=True)
    auth_key = fields.Char('Auth Key', required=True)
    browser_info = fields.Char('Browser Info', help='User agent string')
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('endpoint_unique', 'unique(endpoint)', 'This push endpoint is already registered.'),
    ]

    def get_subscription_info(self):
        """Return subscription info dict for pywebpush"""
        self.ensure_one()
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh_key,
                "auth": self.auth_key,
            }
        }
