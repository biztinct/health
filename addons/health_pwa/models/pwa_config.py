# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class HealthPWAConfig(models.Model):
    """Health PWA Configuration Model"""
    _name = 'health.pwa.config'
    _description = 'Health PWA Configuration'

    name = fields.Char('Name', required=True, default='Health PWA Configuration')
    clinic_phone_number = fields.Char('Clinic Phone Number', required=True)
    clinic_name = fields.Char('Clinic Name', required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, required=True)
    active = fields.Boolean('Active', default=True)
    notes = fields.Text('Notes')

    # Push Notification Configuration
    vapid_public_key = fields.Char(
        'VAPID Public Key',
        help='Public key for Web Push VAPID authentication. Generate with: vapid --applicationServerKey')
    vapid_private_key = fields.Text(
        'VAPID Private Key',
        help='Private key in PEM format for Web Push VAPID authentication. Keep this secret!')
    vapid_contact_email = fields.Char(
        'VAPID Contact Email',
        default='admin@biztinct.com',
        help='Contact email for VAPID claims (mailto: format). Used by push services to contact you.')
    push_notifications_enabled = fields.Boolean(
        'Enable Push Notifications', default=False,
        help='Enable push notifications for booking assignments and updates')

    def get_clinic_phone(self):
        """Get clinic phone number for API calls"""
        self.ensure_one()
        return self.clinic_phone_number

    def get_clinic_name(self):
        """Get clinic name for API calls"""
        self.ensure_one()
        return self.clinic_name

    @api.model
    def get_push_config(self):
        """Get the active push notification config"""
        config = self.search([('active', '=', True), ('push_notifications_enabled', '=', True)], limit=1)
        if not config:
            return None
        if not config.vapid_public_key or not config.vapid_private_key:
            _logger.warning('Push notifications enabled but VAPID keys not configured')
            return None
        return config

    def send_push_notification(self, user_id, title, body, data=None, tag=None):
        """Send push notification to a specific user via all their subscribed devices.
        
        Args:
            user_id: res.users ID to send notification to
            title: Notification title
            body: Notification body text
            data: Optional dict with extra data (e.g. fso_id, url)
            tag: Optional notification tag for grouping/replacing
        """
        self.ensure_one()
        
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            _logger.error('pywebpush not installed. Run: pip install pywebpush')
            return False

        # Convert PEM private key to raw base64url format (what pywebpush expects)
        try:
            from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PublicFormat, PrivateFormat, NoEncryption
            import base64
            pem_key = load_pem_private_key(self.vapid_private_key.encode(), password=None)
            # Extract raw 32-byte private key value
            raw_private = pem_key.private_numbers().private_value.to_bytes(32, byteorder='big')
            vapid_key_b64 = base64.urlsafe_b64encode(raw_private).decode().rstrip('=')
        except Exception as ex:
            _logger.error('Failed to parse VAPID private key: %s', ex)
            return False

        subscriptions = self.env['health.pwa.push.subscription'].sudo().search([
            ('user_id', '=', user_id),
            ('active', '=', True),
        ])

        if not subscriptions:
            _logger.info('No push subscriptions found for user %s', user_id)
            return False

        payload = json.dumps({
            'title': title,
            'body': body,
            'icon': '/health_pwa/static/icons/icon-192.png',
            'badge': '/health_pwa/static/icons/icon-96.png',
            'tag': tag or 'health-pwa-notification',
            'data': data or {},
        })

        vapid_claims = {
            "sub": f"mailto:{self.vapid_contact_email}",
        }

        success_count = 0
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info=sub.get_subscription_info(),
                    data=payload,
                    vapid_private_key=vapid_key_b64,
                    vapid_claims=vapid_claims,
                )
                success_count += 1
                _logger.info('Push notification sent to user %s (endpoint: %s...)',
                             user_id, sub.endpoint[:50])
            except WebPushException as ex:
                _logger.warning('Push notification failed for user %s: %s', user_id, ex)
                # If endpoint is gone (410 Gone or 404), deactivate subscription
                if hasattr(ex, 'response') and ex.response is not None:
                    if ex.response.status_code in (403, 404, 410):
                        _logger.info('Deactivating stale push subscription %s (HTTP %d)', sub.id, ex.response.status_code)
                        sub.active = False
            except Exception as ex:
                _logger.error('Unexpected push error for user %s: %s', user_id, ex)

        return success_count > 0
