# -*- coding: utf-8 -*-
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WebhookSubscription(models.Model):
    """Outbound webhook subscription (spec B.2.5)."""
    _name = 'webhook.subscription'
    _description = 'Webhook Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    target_url = fields.Char(required=True, tracking=True,
                             help='HTTPS endpoint that receives event POSTs.')
    event_codes = fields.Char(
        required=True,
        help='Space-separated event codes from the catalog, e.g. '
             '"booking.completed booking.cancelled".')
    secret = fields.Char(
        required=True, copy=False,
        default=lambda self: secrets.token_urlsafe(32),
        groups='health_api_gateway.group_gateway_admin',
        help='HMAC-SHA256 key used to sign delivery bodies '
             '(X-Health19-Signature).')
    active = fields.Boolean(default=True, tracking=True)
    failure_count = fields.Integer(
        default=0, readonly=True,
        help='Consecutive delivery failures; the subscription is '
             'auto-deactivated at 50.')
    delivery_ids = fields.One2many('webhook.delivery', 'subscription_id',
                                   string='Deliveries')

    @api.constrains('target_url')
    def _check_target_url(self):
        for sub in self:
            if not (sub.target_url or '').lower().startswith('https://'):
                raise ValidationError(_('Webhook target URL must use https://'))

    def _matches_event(self, event_code):
        self.ensure_one()
        return event_code in (self.event_codes or '').split()

    def _register_failure(self):
        """Increment consecutive-failure counter; auto-deactivate at 50 and
        schedule an activity for gateway admins (spec B.2.5)."""
        for sub in self:
            count = sub.failure_count + 1
            vals = {'failure_count': count}
            if count >= 50 and sub.active:
                vals['active'] = False
            sub.sudo().write(vals)
            if not vals.get('active', True):
                sub._notify_deactivated()

    def _notify_deactivated(self):
        self.ensure_one()
        try:
            admin_group = self.env.ref(
                'health_api_gateway.group_gateway_admin', raise_if_not_found=False)
            user = admin_group.users[:1] if admin_group and admin_group.users \
                else self.env.ref('base.user_admin', raise_if_not_found=False)
            if user:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Webhook subscription deactivated'),
                    note=_('Subscription "%s" was deactivated after 50 '
                           'consecutive delivery failures. Fix the endpoint '
                           'and re-activate.', self.name),
                    user_id=user.id,
                )
        except Exception:
            # Notification is best-effort — never block the dispatcher.
            pass

    def _register_success(self):
        self.filtered(lambda s: s.failure_count).sudo().write({'failure_count': 0})
