# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import logging
from datetime import timedelta

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Retry backoff schedule (spec B.7): 1m, 5m, 30m, 2h, 12h, 24h then dead.
BACKOFF_SECONDS = [60, 300, 1800, 7200, 43200, 86400]
DELIVERY_TIMEOUT = 10  # seconds


class WebhookDelivery(models.Model):
    """One attempt-tracked delivery of an outbox event to a subscription
    (spec B.2.6 / B.7)."""
    _name = 'webhook.delivery'
    _description = 'Webhook Delivery'
    _order = 'id desc'

    subscription_id = fields.Many2one('webhook.subscription', required=True,
                                      ondelete='cascade', index=True)
    outbox_id = fields.Many2one('integration.outbox', ondelete='set null',
                                index=True, string='Outbox Event')
    state = fields.Selection([
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('dead', 'Dead'),
    ], default='queued', required=True, index=True)
    attempt = fields.Integer(default=0)
    next_attempt_at = fields.Datetime(default=fields.Datetime.now, index=True)
    response_code = fields.Char()
    response_body = fields.Text(help='Truncated to 2000 characters.')
    signature = fields.Char(help='X-Health19-Signature sent with the last attempt.')

    # ------------------------------------------------------------------
    def _body_bytes(self):
        self.ensure_one()
        payload = self.outbox_id.payload if self.outbox_id else {}
        return json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8')

    def _sign(self, body_bytes):
        """Return ``sha256=<hex hmac_sha256(secret, raw_body)>`` (spec B.7)."""
        self.ensure_one()
        secret = (self.subscription_id.sudo().secret or '').encode('utf-8')
        return 'sha256=' + hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()

    def action_replay(self):
        """Re-queue a delivery for immediate re-attempt (spec B.7 UI)."""
        self.sudo().write({
            'state': 'queued',
            'attempt': 0,
            'next_attempt_at': fields.Datetime.now(),
        })
        return True

    # ------------------------------------------------------------------
    @api.model
    def _process_queue(self, limit=100):
        """Attempt every due queued/failed delivery. Called by the outbox
        dispatcher cron — webhook delivery NEVER happens inline in a
        business transaction."""
        now = fields.Datetime.now()
        due = self.sudo().search([
            ('state', 'in', ('queued', 'failed')),
            ('next_attempt_at', '<=', now),
            ('subscription_id.active', '=', True),
        ], limit=limit, order='next_attempt_at asc')
        for delivery in due:
            delivery._attempt_delivery()
        return True

    def _attempt_delivery(self):
        self.ensure_one()
        body = self._body_bytes()
        signature = self._sign(body)
        event_code = self.outbox_id.event_code if self.outbox_id else ''
        headers = {
            'Content-Type': 'application/json',
            'X-Health19-Event': event_code,
            'X-Health19-Delivery': str(self.id),
            'X-Health19-Signature': signature,
        }
        code, text = None, ''
        try:
            resp = requests.post(self.subscription_id.target_url, data=body,
                                 headers=headers, timeout=DELIVERY_TIMEOUT)
            code, text = resp.status_code, (resp.text or '')[:2000]
        except Exception as exc:
            text = str(exc)[:2000]
        vals = {
            'attempt': self.attempt + 1,
            'response_code': str(code) if code is not None else 'error',
            'response_body': text,
            'signature': signature,
        }
        if code is not None and 200 <= code < 300:
            vals['state'] = 'sent'
            self.sudo().write(vals)
            self.subscription_id._register_success()
        else:
            attempt = vals['attempt']
            if attempt >= len(BACKOFF_SECONDS):
                vals['state'] = 'dead'
            else:
                vals['state'] = 'failed'
                vals['next_attempt_at'] = fields.Datetime.now() + timedelta(
                    seconds=BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
            self.sudo().write(vals)
            self.subscription_id._register_failure()
            _logger.warning(
                'Webhook delivery %s to %s failed (attempt %s, status %s)',
                self.id, self.subscription_id.target_url, attempt, code)
