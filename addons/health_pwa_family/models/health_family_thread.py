# -*- coding: utf-8 -*-
"""FB-047 one-tap post-visit family update — the ZNS ping leg.

Mirrors ``health.family.thread._send_reply_zns`` but for the human post-visit
update purpose (``family_update``). Empty template param ⇒ NO row (the standing
no-phantom posture); dedup ``famupd-<fso>-<relation>``.
"""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

_UPDATE_TEMPLATE_PARAM = 'health_pwa_family.zns_template_update'


class HealthFamilyThread(models.Model):
    _inherit = 'health.family.thread'

    def _send_update_zns(self, message, relation, fso):
        """Log + (respecting the rails) send one post-visit family-update ZNS.
        No template configured ⇒ the row is silently NOT created."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        template_id = ICP.get_param(_UPDATE_TEMPLATE_PARAM, '')
        if not template_id:
            return self.env['health.outbound.message']
        partner = relation.sudo().representative_id
        if not partner:
            return self.env['health.outbound.message']
        dedup_key = 'famupd-%s-%s' % (fso.id, relation.id)
        Message = self.env['health.outbound.message'].sudo()
        existing = Message.search([('dedup_key', '=', dedup_key)], limit=1)
        if existing:
            return existing

        enabled = ICP.get_param('health_messaging.enabled', 'False') in (
            'True', 'true', '1')
        dry_run = ICP.get_param('health_messaging.dry_run', 'True') in (
            'True', 'true', '1')
        params = {'patient_name': self.sudo().patient_id.name or ''}
        link = self.env['health.family.link'].sudo()._get_or_create_link(
            fso, relation)
        if link:
            params['link'] = link._page_url()
        phone = self._safe_phone(partner.mobile or partner.phone)
        msg = Message.create({
            'purpose': 'family_update',
            'channel': 'zns',
            'partner_id': partner.id,
            'fso_id': fso.id,
            'phone': phone,
            'dedup_key': dedup_key,
            'payload_json': params,
            'state': 'queued',
        })
        if not phone:
            msg.write({'state': 'skipped',
                       'error_text': 'No usable phone for the recipient.'})
            return msg
        if not enabled:
            msg.state = 'skipped'
            return msg
        if dry_run:
            msg.write({'state': 'simulated', 'sent_at': fields.Datetime.now()})
            return msg
        try:
            from odoo.addons.health_zalo.services.zalo_api import get_api_client
            config = self.env['zalo.config'].search([('active', '=', True)], limit=1)
            result = get_api_client(self.env).send_zns_notification(
                config, phone, template_id, params)
            if isinstance(result, dict) and result.get('error') \
                    and result.get('error') != 0:
                msg.write({'state': 'failed',
                           'error_text': 'ZNS error: %s' % (
                               result.get('message') or result.get('error'))})
            else:
                msg.write({'state': 'sent', 'sent_at': fields.Datetime.now()})
        except Exception as exc:  # noqa: BLE001 — a send must never break flow
            msg.write({'state': 'failed', 'error_text': 'ZNS: %s' % exc})
        return msg
