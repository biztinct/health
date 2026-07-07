import hashlib
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HealthFieldServiceOrderOneTap(models.Model):
    """E.2 — Exception-only one-tap visit completion.

    When a quote is unchanged since booking confirmation, a nurse can complete
    the visit with one tap: the quote is auto-verified, a placeholder clinical
    note satisfies the completion gate, and the visit closes exactly like the
    normal path (invoice/payment tail lives in the PWA controller).
    """
    _inherit = 'health.fieldservice.order'

    quote_snapshot_hash = fields.Char(
        size=64, readonly=True, copy=False,
        help='SHA-256 of the sale order lines captured at booking confirmation.',
    )
    # Companion to the hash so the /onetap endpoint can produce a human-readable
    # diff (added / removed / qty-changed) when the quote HAS changed. The hash
    # alone is one-way and cannot be diffed — see deviation note in the report.
    quote_snapshot_json = fields.Text(readonly=True, copy=False)
    quote_is_unchanged = fields.Boolean(
        compute='_compute_quote_is_unchanged',
        help='True when the current quote lines match the confirmation snapshot.',
    )

    def _quote_lines_tuples(self):
        """Sorted, normalized line tuples for the linked sale order ('' when none)."""
        self.ensure_one()
        if not self.sale_order_id:
            return []
        return sorted(
            (l.product_id.id, float(l.product_uom_qty), float(l.price_unit),
             float(l.discount))
            for l in self.sale_order_id.order_line
        )

    def _quote_lines_hash(self):
        self.ensure_one()
        if not self.sale_order_id:
            return ''
        payload = json.dumps(self._quote_lines_tuples(), separators=(',', ':'))
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def _quote_lines_snapshot(self):
        """Rich snapshot (with product names/qty/price) for later diffing."""
        self.ensure_one()
        if not self.sale_order_id:
            return []
        return [{
            'product_id': l.product_id.id,
            'name': l.product_id.display_name or '',
            'qty': float(l.product_uom_qty),
            'price': float(l.price_unit),
            'discount': float(l.discount),
        } for l in self.sale_order_id.order_line]

    @api.depends('sale_order_id', 'sale_order_id.order_line',
                 'sale_order_id.order_line.product_uom_qty',
                 'sale_order_id.order_line.price_unit',
                 'sale_order_id.order_line.discount',
                 'sale_order_id.order_line.product_id',
                 'quote_snapshot_hash')
    def _compute_quote_is_unchanged(self):
        for o in self:
            o.quote_is_unchanged = (
                bool(o.quote_snapshot_hash)
                and o._quote_lines_hash() == o.quote_snapshot_hash
            )

    def action_confirm_booking(self):
        res = super().action_confirm_booking()
        for o in self:
            o.quote_snapshot_hash = o._quote_lines_hash()
            o.quote_snapshot_json = json.dumps(o._quote_lines_snapshot())
        return res

    # ------------------------------------------------------------------
    # Public helpers used by the PWA one-tap controller
    # ------------------------------------------------------------------
    def _onetap_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'health_workflow_auto.onetap_enabled', 'True'
        ) not in ('False', 'false', '0', '')

    def onetap_eligibility(self):
        """Return {eligible, reason, changed} describing whether one-tap is allowed.

        reason values: ok / disabled / not_in_progress / no_quote / needs_review.
        `changed` is only populated on needs_review.
        """
        self.ensure_one()
        if not self._onetap_enabled():
            return {'eligible': False, 'reason': 'disabled', 'changed': {}}
        if self.state != 'in_progress':
            return {'eligible': False, 'reason': 'not_in_progress', 'changed': {}}
        if not self.sale_order_id:
            return {'eligible': False, 'reason': 'no_quote', 'changed': {}}
        # No snapshot recorded (booking confirmed before this module shipped) —
        # treat the current lines as the baseline and allow one-tap.
        if not self.quote_snapshot_hash:
            return {'eligible': True, 'reason': 'ok', 'changed': {}}
        if self.quote_is_unchanged:
            return {'eligible': True, 'reason': 'ok', 'changed': {}}
        return {'eligible': False, 'reason': 'needs_review',
                'changed': self._quote_diff()}

    def _quote_diff(self):
        """Diff current sale-order lines against the confirmation snapshot.

        Aggregated per product (a quote can carry the same product on several
        lines), comparing total quantity and total subtotal per product.
        """
        self.ensure_one()
        try:
            snap = json.loads(self.quote_snapshot_json or '[]')
        except (ValueError, TypeError):
            snap = []

        def _agg(lines):
            agg = {}
            for l in lines:
                pid = l['product_id']
                e = agg.setdefault(pid, {'name': l['name'], 'qty': 0.0, 'amount': 0.0})
                e['qty'] += l['qty']
                e['amount'] += l['qty'] * l['price'] * (1.0 - l.get('discount', 0.0) / 100.0)
            return agg

        snap_agg = _agg(snap)
        cur_agg = _agg(self._quote_lines_snapshot())

        added, removed, qty_changed = [], [], []
        for pid, cur in cur_agg.items():
            if pid not in snap_agg:
                added.append({'product': cur['name'], 'qty': cur['qty']})
            else:
                old = snap_agg[pid]
                if old['qty'] != cur['qty'] or old['amount'] != cur['amount']:
                    qty_changed.append({
                        'product': cur['name'],
                        'old_qty': old['qty'], 'new_qty': cur['qty'],
                        'old_amount': round(old['amount'], 2),
                        'new_amount': round(cur['amount'], 2),
                    })
        for pid, old in snap_agg.items():
            if pid not in cur_agg:
                removed.append({'product': old['name'], 'qty': old['qty']})
        return {'added': added, 'removed': removed, 'qty_changed': qty_changed}

    def action_one_tap_complete(self, service_notes=''):
        """Complete a visit in one step when the quote is unchanged.

        PRECONDITIONS: state == 'in_progress', sale_order_id set, quote unchanged.
        Steps: (1) auto-verify quote (confirm the SO — same as the PWA complete
        endpoint), (2) create a placeholder clinical note when none exists so the
        completion gate passes, (3) call action_complete_service().
        Returns {'completed': True}.
        """
        self.ensure_one()
        elig = self.onetap_eligibility()
        if not elig['eligible']:
            raise UserError(_(
                'One-tap completion is not available for this visit (%s).'
            ) % elig['reason'])

        # (1) auto-verify quote — mirror health_pwa complete endpoint (api.py:836)
        if self.sale_order_id.state in ('draft', 'sent'):
            self.sale_order_id.action_confirm()

        # (2) placeholder clinical note satisfies the L2762 completion gate
        if not self.clinical_notes_submitted:
            self.env['health.clinical.note'].create({
                'order_id': self.id,
                'clinical_notes': service_notes or _(
                    'Visit completed - no exceptions reported (one-tap complete)'),
            })

        # (3) run the normal completion workflow (fires the same hooks:
        #     timecard fill E.4, outbox events, family snapshot, etc.)
        self.action_complete_service()
        return {'completed': True}
