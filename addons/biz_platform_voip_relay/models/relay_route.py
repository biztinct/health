# -*- coding: utf-8 -*-
"""Who owns which call-back address and which hotline number.

One row per (kind, key). It is the whole of the routing decision: a call-back
whose key is not in this table and does not belong to the platform's own clinic
is handled locally by the route that was already there, which refuses it — never
a guess, and never a fallback to "probably the biggest customer".

Two kinds, and the difference matters:

* ``receiver`` — the public half of a customer's call-back address, READ out of
  that customer's own system every ten minutes. Never typed, never editable:
  the customer's system is the author of this fact and the platform is only
  caching it. It is not a secret; it is the part of the address that appears in
  any web-server log, and the secret half of the address is never held here at
  all.
* ``hotline`` — a published phone number, TYPED by an operator. Only needed
  when several customers share one account with the phone supplier, so every
  call arrives on one address and the address can no longer tell them apart.

The pair is unique across the WHOLE table, not per customer, and that is the
point — two customers claiming one address or one hotline is a configuration
mistake that must be reported, never resolved silently in favour of whoever the
query happened to return first. Getting it wrong sends one clinic's patient
calls into another clinic's system.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

KINDS = [
    ('receiver', 'Call-back address'),
    ('hotline', 'Hotline number'),
]


class VoipRelayRoute(models.Model):
    _name = 'voip.relay.route'
    _description = 'Phone relay route'
    _order = 'kind, key'

    tenant_id = fields.Many2one(
        'voip.relay.tenant', string='Customer', required=True,
        ondelete='cascade', index=True)
    kind = fields.Selection(
        KINDS, string='Matched on', required=True, default='hotline',
        help='Whether calls reach this customer because of the address the '
             'phone supplier calls, or because of the hotline number dialled.')
    key = fields.Char(
        string='Address or number', required=True, index=True,
        help='The public half of the call-back address, or the hotline number.')
    seen_at = fields.Datetime(
        string='Last read', readonly=True,
        help="When this was last confirmed by reading the customer's system. "
             'Empty for a hotline somebody typed here.')

    # ------------------------------------------------------------------
    # DB constraints (ledger §5.1 — _sql_constraints are not materialised)
    # plus the pre-check that keeps an IntegrityError from poisoning the
    # transaction (ledger §5.3).
    # ------------------------------------------------------------------
    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_relay_route_key_uniq
            ON voip_relay_route (kind, key)
        """)

    @api.model
    def _check_key_unique(self, kind, key, exclude_id=None):
        if not kind or not key:
            return
        domain = [('kind', '=', kind), ('key', '=', key)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        clash = self.sudo().search(domain, limit=1)
        if clash:
            raise ValidationError(_(
                'This address or number is already connected by another '
                'customer (%s).', clash.tenant_id.slug or ''))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_key_unique(vals.get('kind'), vals.get('key'))
        return super().create(vals_list)

    def write(self, vals):
        if 'kind' in vals or 'key' in vals:
            for rec in self:
                self._check_key_unique(vals.get('kind', rec.kind),
                                       vals.get('key', rec.key),
                                       exclude_id=rec.id)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Upsert used by the reconcile (receiver rows only)
    # ------------------------------------------------------------------
    @api.model
    def _upsert(self, tenant, kind, key):
        row = self.sudo().search(
            [('kind', '=', kind), ('key', '=', key)], limit=1)
        now = fields.Datetime.now()
        if row:
            vals = {'seen_at': now}
            if row.tenant_id != tenant:
                vals['tenant_id'] = tenant.id
            row.write(vals)
            return row
        return self.sudo().create({
            'tenant_id': tenant.id, 'kind': kind, 'key': key, 'seen_at': now})

    @api.model
    def _find(self, kind, key):
        """The active customer that owns this address or number, or None."""
        if not kind or not key:
            return None
        row = self.sudo().search(
            [('kind', '=', kind), ('key', '=', str(key)),
             ('tenant_id.active', '=', True)], limit=1)
        return row.tenant_id if row else None
