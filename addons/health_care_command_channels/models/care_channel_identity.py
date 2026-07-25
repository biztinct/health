# -*- coding: utf-8 -*-
"""The external peer registry (architecture §5.6, phase6 §2.2).

One row per *person as the provider knows them*: a WhatsApp wa_id, a Messenger
PSID, a Telegram chat id, a web-chat session uuid. It is the ONE anchor a
FB/Telegram/webchat conversation has at first contact — those payloads carry no
phone, no email and no partner — which is why ``care.conversation`` grows a
``channel_identity_id`` anchor rather than trying to synthesise one.

Deliberately thin: no PHI, no message content, no profile enrichment. The name
is whatever the provider volunteered, refreshed on every inbound so a renamed
peer does not go stale.

``peer_name`` holds that raw provider name; ``display_name`` is the stored
compute over it (falling back to the external id). Keeping the raw value in its
own column is deliberate: redefining Odoo's built-in ``display_name`` as a
plain stored Char merges with the base field definition and can silently
inherit its ``compute=``, which would drop every write.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CareChannelIdentity(models.Model):
    _name = 'care.channel.identity'
    _description = 'Care Channel Identity'
    _order = 'last_seen_at desc, id desc'
    _rec_name = 'display_name'

    connection_id = fields.Many2one(
        'care.channel.connection', required=True, index=True,
        ondelete='restrict',
        help='Deleting a connection must never orphan the peers it served: '
             'disconnect is a state, not a delete.')
    channel = fields.Selection(
        related='connection_id.channel', store=True, index=True, readonly=True)
    company_id = fields.Many2one(
        related='connection_id.company_id', store=True, index=True,
        readonly=True)
    external_id = fields.Char(
        required=True, index=True,
        help='wa_id / PSID / Telegram chat id / web-chat session uuid.')
    peer_name = fields.Char(
        string='Name from provider',
        help='Whatever the provider volunteered — never trusted as identity.')
    peer_phone = fields.Char(
        string='Volunteered phone',
        help='Web chat pre-chat form only: the phone a visitor typed. '
             'DISPLAY-ONLY for ops — never an anchor and never trusted as '
             'identity: an anonymous visitor claiming a patient\'s number '
             'must not be merged onto the patient\'s thread (CC-B review).')
    display_name = fields.Char(compute='_compute_display_name', store=True)
    last_seen_at = fields.Datetime()

    def init(self):
        # §5.1 — _sql_constraints are not materialised on Odoo 19, and this
        # uniqueness is the dedupe contract the whole ingest funnel rests on.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                care_channel_identity_conn_ext_uniq
            ON care_channel_identity (connection_id, external_id)
        """)

    @api.depends('peer_name', 'external_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.peer_name or rec.external_id or ''

    @api.model
    def _upsert(self, connection, external_id, peer_name=None, when=None):
        """Get-or-create the peer, refreshing name + last-seen.

        Pre-checks the unique index rather than relying on it (ledger §5.3):
        an IntegrityError here would poison the whole webhook transaction.
        """
        connection.ensure_one()
        external_id = (external_id or '').strip()
        if not external_id:
            return self.browse()
        rec = self.sudo().search([
            ('connection_id', '=', connection.id),
            ('external_id', '=', external_id)], limit=1)
        vals = {'last_seen_at': when or fields.Datetime.now()}
        if peer_name:
            vals['peer_name'] = peer_name[:120]
        if rec:
            rec.write(vals)
            return rec
        vals.update({'connection_id': connection.id, 'external_id': external_id})
        return self.sudo().create(vals)
