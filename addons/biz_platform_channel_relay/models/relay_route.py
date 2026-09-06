# -*- coding: utf-8 -*-
"""Who owns which Page and which WhatsApp number.

One row per (channel, provider resource id). It is the whole of the routing
decision: an event whose resource id is not in this table and does not belong
to the platform's own clinic is an unknown contact, never a guess.

The pair is unique across the WHOLE table, not per customer, and that is the
point — two customers claiming one Page is a configuration mistake that must be
reported, never resolved silently in favour of whoever the query happened to
return first.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

CHANNELS = [('whatsapp', 'WhatsApp'), ('fb', 'Messenger')]


class ChannelRelayRoute(models.Model):
    _name = 'channel.relay.route'
    _description = 'Relay route (Page or WhatsApp number)'
    _order = 'channel, resource_external_id'

    tenant_id = fields.Many2one(
        'channel.relay.tenant', string='Customer', required=True,
        ondelete='cascade', index=True)
    channel = fields.Selection(CHANNELS, string='Channel', required=True)
    resource_external_id = fields.Char(
        string='Page or number', required=True, index=True,
        help='The identifier the provider addresses this customer by.')
    seen_at = fields.Datetime(
        string='Last read', readonly=True,
        help='When this was last confirmed by reading the customer\'s system.')

    # ------------------------------------------------------------------
    # DB constraints (ledger §5.1) + the pre-check that keeps the
    # IntegrityError from poisoning the transaction (ledger §5.3)
    # ------------------------------------------------------------------
    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS channel_relay_route_resource_uniq
            ON channel_relay_route (channel, resource_external_id)
        """)

    @api.model
    def _check_resource_unique(self, channel, resource_external_id,
                               exclude_id=None):
        if not channel or not resource_external_id:
            return
        domain = [('channel', '=', channel),
                  ('resource_external_id', '=', resource_external_id)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        clash = self.sudo().search(domain, limit=1)
        if clash:
            raise ValidationError(_(
                'This page or number is already connected by another '
                'customer (%s).', clash.tenant_id.slug or ''))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_resource_unique(vals.get('channel'),
                                        vals.get('resource_external_id'))
        return super().create(vals_list)

    def write(self, vals):
        if 'channel' in vals or 'resource_external_id' in vals:
            for rec in self:
                self._check_resource_unique(
                    vals.get('channel', rec.channel),
                    vals.get('resource_external_id', rec.resource_external_id),
                    exclude_id=rec.id)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Upsert used by the reconcile
    # ------------------------------------------------------------------
    @api.model
    def _upsert(self, tenant, channel, resource_external_id):
        row = self.sudo().search(
            [('channel', '=', channel),
             ('resource_external_id', '=', resource_external_id)], limit=1)
        now = fields.Datetime.now()
        if row:
            vals = {'seen_at': now}
            if row.tenant_id != tenant:
                vals['tenant_id'] = tenant.id
            row.write(vals)
            return row
        return self.sudo().create({
            'tenant_id': tenant.id, 'channel': channel,
            'resource_external_id': resource_external_id, 'seen_at': now})

    @api.model
    def _find(self, channel, resource_external_id):
        """The active customer that owns this Page or number, or None."""
        if not channel or not resource_external_id:
            return None
        row = self.sudo().search(
            [('channel', '=', channel),
             ('resource_external_id', '=', str(resource_external_id)),
             ('tenant_id.active', '=', True)], limit=1)
        return row.tenant_id if row else None
