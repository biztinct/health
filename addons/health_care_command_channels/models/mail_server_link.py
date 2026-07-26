# -*- coding: utf-8 -*-
"""The seam between a channel connection and Odoo's own mail plumbing (CC-F).

Email is the one channel where the protocol already belongs to Odoo:
``ir.mail_server`` sends, ``fetchmail.server`` polls IMAP, and the
Gmail/Outlook mixins own the XOAUTH2 token dance. CC-F does not reimplement
any of that — it adds exactly two things those models cannot express:

1. **Ownership.** A plain Many2one from each server row to the connection that
   created it. Matching on the mailbox string instead would break the moment a
   deployment has two companies using the same address, and would silently
   adopt a server some administrator made by hand.
2. **Traffic → truth.** Odoo sets ``default_fetchmail_server_id`` in the
   context around every message it processes from an incoming server
   (mail/models/fetchmail.py:278). That context flag is the honest signal that
   a REAL message arrived, so it is what flips ``inbound_ok``.

The one rule that governs this file (ledger §5.78): **nothing here ever lowers
a readiness check.** Inbound is a poll, and a mailbox that is simply quiet —
or one fetch that failed — must never demote a ``ready`` connection to
``action_required``, which is not ingestable and would drop the very inbox the
check exists to protect. Every write below is a promotion.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    care_connection_id = fields.Many2one(
        'care.channel.connection', string='Channel connection',
        index='btree_not_null', ondelete='set null', copy=False,
        help='Set when the Channel Connection Center created this server for '
             'an email channel. Cleared, never cascaded: deleting a '
             'connection must not silently delete a working mail server.')

    def _find_mail_server_allowed_domain(self):
        """A tenant's connected mailbox is NEVER the deployment's default.

        This is the hazard that makes CC-F's email half dangerous if ignored.
        ``_find_mail_server`` walks the active servers and, at step 4, returns
        **the first one even when its from_filter matches nothing** — so on a
        database with no other ``ir.mail_server`` row (which is vietuat today),
        the mailbox one clinic connects here would silently become the sender
        of every outgoing email in the system: invoices, password resets,
        another tenant's notifications.

        Core provides this exact override point for it. A channel-owned server
        stays fully usable — ``send_email(..., mail_server_id=...)`` addresses
        it directly, which is how the connection test proves ``outbound_ok`` —
        it is simply never *inferred*.
        """
        domain = super()._find_mail_server_allowed_domain()
        return domain & fields.Domain('care_connection_id', '=', False)


class FetchmailServer(models.Model):
    _inherit = 'fetchmail.server'

    care_connection_id = fields.Many2one(
        'care.channel.connection', string='Channel connection',
        index='btree_not_null', ondelete='set null', copy=False,
        help='Set when the Channel Connection Center created this incoming '
             'server for an email channel.')

    def _care_note_inbound(self):
        """A real message came in on this mailbox. Promote, never demote.

        Best effort by construction: a bookkeeping failure must never abort
        the fetch loop and lose a customer email. ``_note_inbound`` is already
        savepoint-wrapped, and ``webhook=False`` keeps the webhook vocabulary
        off a channel that has no webhook.
        """
        for server in self:
            conn = server.sudo().care_connection_id
            if not conn or not conn.active:
                continue
            if not conn._may_ingest():
                self.env['care.channel.audit']._log(
                    'webhook_ignored', connection=conn,
                    detail='email inbound while %s' % conn.state)
                continue
            conn._note_inbound(webhook=False)
        return True


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def message_process(self, model, message, custom_values=None,
                        save_original=False, strip_attachments=False,
                        thread_id=None):
        """Note the inbound AFTER core has actually accepted the message.

        Ordering is deliberate: if ``super()`` raises, the message was not
        processed and there is nothing to claim. The bookkeeping is then
        wrapped so it can never turn a delivered email into a failed fetch —
        Odoo's loop counts an exception here as a failed message and moves on,
        which would be a real customer email lost to a readiness write.
        """
        result = super().message_process(
            model, message, custom_values=custom_values,
            save_original=save_original, strip_attachments=strip_attachments,
            thread_id=thread_id)
        server_id = self.env.context.get('default_fetchmail_server_id')
        if server_id:
            try:
                with self.env.cr.savepoint():
                    self.env['fetchmail.server'].sudo().browse(
                        server_id).exists()._care_note_inbound()
            except Exception:  # noqa: BLE001 — never lose a message over this
                _logger.exception(
                    'care_channels: could not note email inbound for '
                    'fetchmail server %s', server_id)
        return result
