# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api, fields, models
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


class IntegrationOutbox(models.Model):
    """Transactional outbox (spec B.2.7, architecture §6.1 slim v1).

    Emitter hooks create rows IN the business transaction (that is the outbox
    pattern — rollback removes the event with the write). Delivery fan-out
    happens only from the dispatcher cron / post-commit kick, never inline.
    """
    _name = 'integration.outbox'
    _description = 'Integration Outbox Event'
    _order = 'id desc'
    _rec_name = 'event_code'

    event_code = fields.Char(required=True, index=True,
                             help='e.g. booking.completed')
    res_model = fields.Char(required=True, string='Model')
    res_id = fields.Integer(required=True, string='Record ID')
    payload = fields.Json(required=True,
                          help='Serialized snapshot at emit time.')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('dispatched', 'Dispatched'),
        ('error', 'Error'),
    ], default='pending', required=True, index=True)
    created_at = fields.Datetime(default=fields.Datetime.now)
    dispatched_at = fields.Datetime()

    # ------------------------------------------------------------------
    # Emission (called from event_emitters.py hooks, in-transaction)
    # ------------------------------------------------------------------
    @api.model
    def emit(self, event_code, record, data):
        """Create one outbox row for `record` with uniform payload shape
        (spec B.6). PHI minimization is the caller's duty — no clinical
        narrative or phone numbers belong in `data`."""
        row = self.sudo().create({
            'event_code': event_code,
            'res_model': record._name,
            'res_id': record.id,
            'payload': {
                'event': event_code,
                'occurred_at': fields.Datetime.now().isoformat() + 'Z',
                'model': record._name,
                'id': record.id,
                'data': data or {},
            },
        })
        self._register_postcommit_kick()
        return row

    def _register_postcommit_kick(self):
        """Immediate best-effort dispatch after commit (spec B.7). Safe: runs
        only if the business transaction actually commits."""
        dbname = self.env.cr.dbname
        def _kick():
            try:
                with Registry(dbname).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    env['integration.outbox']._cron_dispatch(limit=50)
            except Exception:
                _logger.exception('Post-commit outbox kick failed (cron will retry)')
        try:
            self.env.cr.postcommit.add(_kick)
        except Exception:
            # e.g. test cursors without postcommit — dispatcher cron covers it
            _logger.debug('Could not register post-commit outbox kick', exc_info=True)

    # ------------------------------------------------------------------
    # Dispatch (cron, every minute)
    # ------------------------------------------------------------------
    @api.model
    def _cron_dispatch(self, limit=200):
        """Fan pending rows out to matching webhook subscriptions, then run
        the delivery queue. Row selection uses FOR UPDATE SKIP LOCKED so
        parallel workers never double-dispatch (spec B.2.7)."""
        self.env.cr.execute(
            "SELECT id FROM integration_outbox WHERE state = 'pending' "
            "ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED", (limit,))
        ids = [r[0] for r in self.env.cr.fetchall()]
        if ids:
            subscriptions = self.env['webhook.subscription'].sudo().search(
                [('active', '=', True)])
            Delivery = self.env['webhook.delivery'].sudo()
            now = fields.Datetime.now()
            for row in self.sudo().browse(ids):
                try:
                    for sub in subscriptions:
                        if sub._matches_event(row.event_code):
                            Delivery.create({
                                'subscription_id': sub.id,
                                'outbox_id': row.id,
                                'state': 'queued',
                                'next_attempt_at': now,
                            })
                    row.write({'state': 'dispatched', 'dispatched_at': now})
                except Exception:
                    _logger.exception('Outbox dispatch failed for row %s', row.id)
                    row.write({'state': 'error'})
        self.env['webhook.delivery']._process_queue()
        return True
