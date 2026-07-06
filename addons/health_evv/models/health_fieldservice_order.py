# -*- coding: utf-8 -*-
"""FSO EVV layer (spec A.2.3 / A.2.4).

EVV is a PWA-attested verification layer, NOT a state gate: check-in/out
hooks append events after super() and never change or block the visit
workflow (``evv_verified`` does not block completion in v1).
"""
import logging
import math

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    evv_event_ids = fields.One2many(
        'health.evv.event', 'fso_id', string='EVV Events')
    evv_event_count = fields.Integer(compute='_compute_evv_event_count')
    evv_checkin_event_id = fields.Many2one(
        'health.evv.event', compute='_compute_evv_boundary_events',
        string='EVV Check-in Event')
    evv_checkout_event_id = fields.Many2one(
        'health.evv.event', compute='_compute_evv_boundary_events',
        string='EVV Check-out Event')
    evv_signature_attachment_id = fields.Many2one(
        'ir.attachment', string='EVV Signature', copy=False)
    evv_signer_name = fields.Char(string='Signer Name', copy=False)
    evv_signer_relationship = fields.Selection([
        ('client', 'Client'),
        ('family', 'Family Member'),
        ('caregiver', 'Caregiver'),
        ('other', 'Other'),
    ], string='Signer Relationship', copy=False)
    evv_signed_at = fields.Datetime(string='Signed At', copy=False)
    evv_chain_valid = fields.Boolean(
        compute='_compute_evv_status', store=True,
        string='EVV Chain Valid')
    evv_verified = fields.Boolean(
        compute='_compute_evv_status', store=True, string='EVV Verified')
    evv_verified_units = fields.Float(
        compute='_compute_evv_status', store=True,
        string='EVV Verified Units (h)',
        help='Verified service hours: check-in to check-out, floored to '
             '0.25h, capped at scheduled duration + 0.5h; 0.0 when the '
             'visit is not verified.')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    def _compute_evv_event_count(self):
        counts = {}
        for group in self.env['health.evv.event'].read_group(
                [('fso_id', 'in', self.ids)], ['fso_id'], ['fso_id']):
            counts[group['fso_id'][0]] = group['fso_id_count']
        for order in self:
            order.evv_event_count = counts.get(order.id, 0)

    def _compute_evv_boundary_events(self):
        for order in self:
            events = order.evv_event_ids.sorted(
                key=lambda event: (event.sequence, event.id))
            checkins = events.filtered(
                lambda event: event.event_type == 'checkin')
            checkouts = events.filtered(
                lambda event: event.event_type == 'checkout')
            order.evv_checkin_event_id = checkins[:1]
            order.evv_checkout_event_id = checkouts[-1:]

    @api.depends('evv_event_ids', 'evv_event_ids.inside_geofence',
                 'evv_event_ids.chain_valid', 'evv_event_ids.event_type',
                 'evv_event_ids.event_datetime', 'scheduled_duration',
                 'actual_start_datetime', 'actual_end_datetime')
    def _compute_evv_status(self):
        """evv_verified = chain valid AND check-in inside geofence AND
        check-out inside geofence AND a signature event exists.
        evv_verified_units = hours between checkin.event_datetime and
        checkout.event_datetime, rounded DOWN to 0.25h, capped at
        scheduled duration + 0.5h; 0.0 when not verified."""
        for order in self:
            events = order.evv_event_ids.sorted(
                key=lambda event: (event.sequence, event.id))
            chain_valid = bool(
                all(event.chain_valid for event in events))
            checkin = events.filtered(
                lambda event: event.event_type == 'checkin')[:1]
            checkout = events.filtered(
                lambda event: event.event_type == 'checkout')[-1:]
            signature = events.filtered(
                lambda event: event.event_type == 'signature')[:1]
            verified = bool(
                events and chain_valid
                and checkin and checkin.inside_geofence
                and checkout and checkout.inside_geofence
                and signature)
            order.evv_chain_valid = chain_valid
            order.evv_verified = verified
            units = 0.0
            if verified and checkout.event_datetime and checkin.event_datetime:
                hours = (checkout.event_datetime
                         - checkin.event_datetime).total_seconds() / 3600.0
                units = math.floor(max(hours, 0.0) * 4.0) / 4.0
                if order.scheduled_duration:
                    units = min(
                        units, order.scheduled_duration / 60.0 + 0.5)
            order.evv_verified_units = units

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view_evv_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('EVV Events'),
            'res_model': 'health.evv.event',
            'view_mode': 'list,form',
            'domain': [('fso_id', '=', self.id)],
            'context': {'default_fso_id': self.id},
        }

    def action_evv_report(self):
        self.ensure_one()
        return self.env.ref(
            'health_evv.action_report_evv_verification').report_action(self)

    # ------------------------------------------------------------------
    # Wire into existing check-in / check-out (spec A.2.4)
    # ------------------------------------------------------------------
    def action_start_service(self):
        result = super().action_start_service()
        self._evv_capture_from_context('checkin')
        return result

    def action_complete_service(self):
        result = super().action_complete_service()
        self._evv_capture_from_context('checkout')
        return result

    def _evv_capture_from_context(self, event_type):
        """Auto-emit an EVV event when the transition carries the PWA GPS
        context keys (evv_lat/evv_lng/evv_accuracy/evv_device_uuid/
        evv_client_uuid). Desktop transitions carry no context and emit
        nothing. EVV failure NEVER blocks the visit workflow."""
        context = self.env.context
        if not context.get('evv_client_uuid'):
            return
        try:
            employee = self.env.user.employee_id
            if not employee:
                _logger.warning(
                    'EVV %s capture skipped: user %s has no employee.',
                    event_type, self.env.user.login)
                return
            Event = self.env['health.evv.event']
            for order in self:
                if Event.search_count([
                        ('fso_id', '=', order.id),
                        ('event_type', '=', event_type)]):
                    continue
                Event.append_event(order, {
                    'event_type': event_type,
                    'event_datetime': (context.get('evv_event_datetime')
                                       or fields.Datetime.now()),
                    'lat': context.get('evv_lat') or 0.0,
                    'lng': context.get('evv_lng') or 0.0,
                    'accuracy_m': context.get('evv_accuracy') or 0.0,
                    'staff_id': employee.id,
                    'device_uuid': context.get('evv_device_uuid') or '',
                    'client_event_uuid': context.get('evv_client_uuid'),
                    'payload': context.get('evv_payload') or {},
                    'origin': context.get('evv_origin') or 'online',
                }, client_hash=context.get('evv_client_hash'))
        except Exception as exc:  # noqa: BLE001 — never block the workflow
            _logger.error(
                'EVV %s capture failed (non-blocking): %s', event_type, exc)
