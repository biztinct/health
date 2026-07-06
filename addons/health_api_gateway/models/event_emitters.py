# -*- coding: utf-8 -*-
"""Event catalog emitters (spec B.6).

Every hook writes ``integration.outbox`` rows in the SAME transaction as the
business write (transactional outbox); webhook DELIVERY happens only from
the dispatcher cron. A failing emitter must NEVER block the business write —
every emission is wrapped in try/except.

Payloads are PHI-minimized: no clinical narrative, no phone numbers.
Consumers fetch details via the API with their own scopes.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


def _iso(dt):
    return dt.isoformat() + 'Z' if dt else None


class HealthFieldserviceOrderEmitter(models.Model):
    _inherit = 'health.fieldservice.order'

    def _gateway_snapshot(self):
        """Compact PHI-minimized snapshot for outbox payloads (spec B.6)."""
        self.ensure_one()
        return {
            'name': self.name,
            'state': self.state,
            'patient_id': self.patient_id.id or None,
            'patient_name': self.patient_id.name or None,
            'scheduled_datetime': _iso(self.scheduled_datetime),
            'actual_start_datetime': _iso(self.actual_start_datetime),
            'actual_end_datetime': _iso(self.actual_end_datetime),
            'facility_id': self.facility_id.id or None,
            'staff_ids': self.assignment_ids.mapped('staff_id').ids,
        }

    def _gateway_emit(self, event_code):
        for order in self:
            try:
                self.env['integration.outbox'].emit(
                    event_code, order, order._gateway_snapshot())
            except Exception:
                _logger.exception(
                    'Gateway emitter %s failed for FSO %s (business write unaffected)',
                    event_code, order.id)

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._gateway_emit('booking.created')
        return orders

    def action_confirm_booking(self):
        res = super().action_confirm_booking()
        try:
            self.filtered(lambda o: o.state == 'confirmed')._gateway_emit(
                'booking.confirmed')
        except Exception:
            _logger.exception('booking.confirmed emitter failed')
        return res

    def action_complete_service(self):
        res = super().action_complete_service()
        try:
            # Covers both full-time (completed) and part-time
            # (completed_pending_invoice) outcomes.
            self.filtered(
                lambda o: o.state in ('completed', 'completed_pending_invoice')
            )._gateway_emit('booking.completed')
        except Exception:
            _logger.exception('booking.completed emitter failed')
        return res

    def cancel_with_reason(self, cancellation_reason_id, cancellation_notes):
        res = super().cancel_with_reason(cancellation_reason_id, cancellation_notes)
        try:
            self.filtered(lambda o: o.state == 'cancelled')._gateway_emit(
                'booking.cancelled')
        except Exception:
            _logger.exception('booking.cancelled emitter failed')
        return res

    @api.model
    def action_reschedule_from_wizard(self, booking_id, new_date, new_time_hour,
                                      new_staff_ids, duration_hours=None):
        res = super().action_reschedule_from_wizard(
            booking_id, new_date, new_time_hour, new_staff_ids,
            duration_hours=duration_hours)
        try:
            if isinstance(res, dict) and res.get('success'):
                order = self.browse(booking_id).exists()
                order._gateway_emit('booking.rescheduled')
        except Exception:
            _logger.exception('booking.rescheduled emitter failed')
        return res


class ResPartnerEmitter(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        try:
            # Same patient predicate as PWA sync _get_patient_changes
            # (sync.py:175): is_patient flag.
            for partner in partners.filtered(lambda p: p.is_patient):
                self.env['integration.outbox'].emit('patient.created', partner, {
                    'name': partner.name,
                    'patient_code': getattr(partner, 'patient_code', None) or None,
                    'catchment_province_id':
                        partner.catchment_province_id.id
                        if 'catchment_province_id' in partner._fields
                        and partner.catchment_province_id else None,
                    'primary_facility_id':
                        partner.primary_facility_id.id
                        if 'primary_facility_id' in partner._fields
                        and partner.primary_facility_id else None,
                })
        except Exception:
            _logger.exception('patient.created emitter failed')
        return partners


class AccountMoveEmitter(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super().action_post()
        try:
            for move in self.filtered(
                    lambda m: m.move_type == 'out_invoice'
                    and m.state == 'posted'
                    and m.partner_id
                    and getattr(m.partner_id, 'is_patient', False)):
                self.env['integration.outbox'].emit('invoice.posted', move, {
                    'name': move.name,
                    'state': move.state,
                    'patient_id': move.partner_id.id,
                    'amount_total': move.amount_total,
                    'currency': move.currency_id.name or None,
                    'invoice_date': move.invoice_date.isoformat()
                        if move.invoice_date else None,
                })
        except Exception:
            _logger.exception('invoice.posted emitter failed')
        return res


class HealthPaymentTransactionEmitter(models.Model):
    _inherit = 'health.payment.transaction'

    @api.model_create_multi
    def create(self, vals_list):
        transactions = super().create(vals_list)
        try:
            for tx in transactions:
                self.env['integration.outbox'].emit('payment.received', tx, {
                    'patient_id': tx.patient_id.id if tx.patient_id else None,
                    'fso_id': tx.fso_id.id
                        if 'fso_id' in tx._fields and tx.fso_id else None,
                    'amount': getattr(tx, 'amount', 0.0),
                    'payment_method': getattr(tx, 'payment_method', None),
                    'status': getattr(tx, 'status', None),
                })
        except Exception:
            _logger.exception('payment.received emitter failed')
        return transactions


class HealthStaffAssignmentEmitter(models.Model):
    _inherit = 'health.staff.assignment'

    def _gateway_emit_assignment(self):
        for assignment in self:
            try:
                self.env['integration.outbox'].emit(
                    'assignment.changed', assignment, {
                        'fso_id': assignment.fso_id.id
                            if assignment.fso_id else None,
                        'staff_id': assignment.staff_id.id
                            if assignment.staff_id else None,
                        'assignment_role':
                            getattr(assignment, 'assignment_role', None),
                        'state': getattr(assignment, 'state', None),
                    })
            except Exception:
                _logger.exception('assignment.changed emitter failed')

    @api.model_create_multi
    def create(self, vals_list):
        assignments = super().create(vals_list)
        assignments._gateway_emit_assignment()
        return assignments

    def write(self, vals):
        res = super().write(vals)
        if 'staff_id' in vals:
            self._gateway_emit_assignment()
        return res
