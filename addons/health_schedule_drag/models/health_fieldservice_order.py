# -*- coding: utf-8 -*-
"""Patient reschedule ZNS — mirrors health_family_link._send_zns exactly:
rails-gated (health_messaging.enabled/dry_run), empty template → no row,
search-first dedup on the NEW datetime so a re-fire of the same move is a
no-op but a genuine second reschedule sends again."""
import logging

import pytz

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

_DEFAULT_TZ = 'Asia/Ho_Chi_Minh'


def _safe_phone(phone):
    """normalize_vn_phone raises on a non-empty invalid number; we want
    falsy-on-invalid semantics (conventions §5.15)."""
    from odoo.addons.health_base.models.phone_utils import normalize_vn_phone
    try:
        return normalize_vn_phone(phone) or ''
    except Exception:  # noqa: BLE001
        return ''


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    def _reschedule_tz(self):
        self.ensure_one()
        try:
            return pytz.timezone(self.booking_timezone or _DEFAULT_TZ)
        except pytz.UnknownTimeZoneError:
            return pytz.timezone(_DEFAULT_TZ)

    def _reschedule_wall(self, dt):
        """Naive-UTC → wall-clock in the FSO booking timezone (the +7h class of
        bug is the most-hit mistake in this codebase — conventions ref)."""
        if not dt:
            return None
        return pytz.utc.localize(dt).astimezone(self._reschedule_tz())

    def _rescheduled_zns_params(self):
        self.ensure_one()
        wall = self._reschedule_wall(self.scheduled_datetime)
        staff = self.lead_staff_id or self.primary_nurse_id
        return {
            'patient_name': self.patient_id.name or '',
            'booking_ref': self.name or '',
            'new_date': wall.strftime('%d/%m/%Y') if wall else '',
            'new_time': wall.strftime('%H:%M') if wall else '',
            'staff_name': staff.name if staff else '',
            'facility_name': self.facility_id.name if self.facility_id else '',
        }

    def _send_rescheduled_zns(self):
        """Queue/send one patient reschedule ZNS honoring the messaging rails.
        Returns the message recordset (empty when no template configured)."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        template_id = ICP.get_param(
            'health_schedule_drag.zns_template_rescheduled', '')
        Message = self.env['health.outbound.message'].sudo()
        if not template_id or not self.patient_id:
            return Message
        newdt = self.scheduled_datetime
        dedup_key = 'resched-%s-%s' % (
            self.id, newdt.strftime('%Y%m%d%H%M') if newdt else '0')
        existing = Message.search([('dedup_key', '=', dedup_key)], limit=1)
        if existing:
            return existing

        enabled = ICP.get_param('health_messaging.enabled', 'False') in (
            'True', 'true', '1')
        dry_run = ICP.get_param('health_messaging.dry_run', 'True') in (
            'True', 'true', '1')
        phone = _safe_phone(self.patient_id.mobile or self.patient_id.phone)
        msg = Message.create({
            'purpose': 'booking_rescheduled',
            'channel': 'zns',
            'partner_id': self.patient_id.id,
            'fso_id': self.id,
            'phone': phone,
            'dedup_key': dedup_key,
            'payload_json': self._rescheduled_zns_params(),
            'state': 'queued',
        })
        if not phone:
            msg.write({'state': 'skipped',
                       'error_text': _('No usable phone for the patient.')})
            return msg
        if not enabled:
            msg.state = 'skipped'
            return msg
        if dry_run:
            msg.write({'state': 'simulated', 'sent_at': fields.Datetime.now()})
            return msg
        try:
            from odoo.addons.health_zalo.services.zalo_api import get_api_client
            config = self.env['zalo.config'].search(
                [('active', '=', True)], limit=1)
            result = get_api_client(self.env).send_zns_notification(
                config, phone, template_id, self._rescheduled_zns_params())
            if isinstance(result, dict) and result.get('error') \
                    and result.get('error') != 0:
                msg.write({'state': 'failed', 'error_text': 'ZNS error: %s' % (
                    result.get('message') or result.get('error'))})
            else:
                msg.write({'state': 'sent', 'sent_at': fields.Datetime.now()})
        except Exception as exc:  # noqa: BLE001 — a send must never break the flow
            msg.write({'state': 'failed', 'error_text': 'ZNS: %s' % exc})
        return msg
