import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# Backoff schedule in minutes, indexed by retry_count BEFORE increment:
# 5min, 30min, 2h, 6h, 24h (spec E.3).
_RETRY_BACKOFF_MINUTES = [5, 30, 120, 360, 1440]


class RedinvoiceRequest(models.Model):
    _inherit = 'redinvoice.request'

    next_retry_at = fields.Datetime(
        help='When this failed request becomes eligible for the retry cron.')
    max_retries = fields.Integer(
        default=5, help='After this many attempts the request needs a manual issue.')


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # Config / helpers
    # ------------------------------------------------------------------
    @api.model
    def _redinvoice_batch_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'health_workflow_auto.redinvoice_batch_enabled', 'False'
        ) in ('True', 'true', '1')

    def _redinvoice_company_configured(self):
        self.ensure_one()
        company = self.company_id
        return bool(company.red_supplier_tax_code and company.red_invoice_api_base)

    def _redinvoice_latest_request(self):
        """Most recent redinvoice.request for this move (or empty recordset)."""
        self.ensure_one()
        return self.env['redinvoice.request'].search(
            [('move_id', '=', self.id)], order='id desc', limit=1)

    def _redinvoice_mark_retry(self, prev_count):
        """Schedule the next retry on the move's latest request, carrying the
        cumulative attempt count forward.

        _redinvoice_issue creates a FRESH request row on every attempt, so
        retry_count would reset to 0 each time — we carry the prior count so the
        backoff chain and the max_retries cutoff actually accumulate.
        """
        request = self._redinvoice_latest_request()
        if not request:
            return
        idx = min(prev_count, len(_RETRY_BACKOFF_MINUTES) - 1)
        request.write({
            'next_retry_at': fields.Datetime.now() + timedelta(
                minutes=_RETRY_BACKOFF_MINUTES[idx]),
            'retry_count': prev_count + 1,
        })

    def _redinvoice_submit_one(self):
        """Submit a single move in its own savepoint. Returns True on success.

        Reuses the existing single-invoice path move._redinvoice_issue() (which
        writes redinvoice.request rows via mark_sent/mark_success/mark_failed and
        advances red_invoice_state). On any exception, the savepoint is rolled
        back, a failed request row is ensured, and a retry is scheduled.
        """
        self.ensure_one()
        prev = self._redinvoice_latest_request()
        prev_count = prev.retry_count if prev else 0
        try:
            with self.env.cr.savepoint():
                self._redinvoice_issue()
            # _redinvoice_issue swallows HTTP/validation failures and leaves the
            # move in red_invoice_state='failed' rather than raising — treat that
            # as a failure needing a scheduled retry.
            if self.red_invoice_state == 'failed':
                self._redinvoice_mark_retry(prev_count)
                return False
            return True
        except Exception as exc:  # noqa: BLE001 — one bad move must not abort the batch
            _logger.warning('RedInvoice batch: move %s failed: %s', self.name, exc)
            # The savepoint rolled back any request row _redinvoice_issue created,
            # so ensure a failed row exists for the audit + retry queue.
            self.env['redinvoice.request'].create({
                'name': _('Red Invoice for %s') % (self.name or self.id),
                'move_id': self.id,
                'company_id': self.company_id.id,
            }).mark_failed(str(exc))
            self._redinvoice_mark_retry(prev_count)
            return False

    # ------------------------------------------------------------------
    # Crons
    # ------------------------------------------------------------------
    @api.model
    def cron_redinvoice_batch_submit(self, batch_limit=200):
        """Nightly 01:30 — submit all eligible posted invoices.

        Domain: posted out_invoice, red_invoice_state in (pending, failed),
        company red-invoice-configured. Skips moves whose latest request has
        exhausted its retries (retry_count >= max_retries) — those await the
        manual action_redinvoice_generate.
        """
        if not self._redinvoice_batch_enabled():
            _logger.info('RedInvoice batch cron: disabled (config param off).')
            return True

        candidates = self.search([
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
            ('red_invoice_state', 'in', ('pending', 'failed')),
        ], limit=batch_limit, order='invoice_date, id')

        failures = 0
        processed = 0
        for move in candidates:
            if not move._redinvoice_company_configured():
                continue
            request = move._redinvoice_latest_request()
            if request and request.retry_count >= request.max_retries:
                continue  # exhausted — manual queue
            processed += 1
            if not move._redinvoice_submit_one():
                failures += 1

        self._redinvoice_batch_report(processed, failures)
        return True

    @api.model
    def cron_redinvoice_retry(self):
        """Every 30 min — progress the backoff chain for due failed requests."""
        if not self._redinvoice_batch_enabled():
            return True
        now = fields.Datetime.now()
        due = self.env['redinvoice.request'].search([
            ('state', '=', 'failed'),
            ('next_retry_at', '!=', False),
            ('next_retry_at', '<=', now),
        ], order='next_retry_at')
        seen_moves = set()
        failures = 0
        processed = 0
        for request in due:
            move = request.move_id
            if not move or move.id in seen_moves:
                continue
            # Only act on the LATEST request for a move, and only while retries remain.
            if request != move._redinvoice_latest_request():
                continue
            if request.retry_count >= request.max_retries:
                continue
            if not move._redinvoice_company_configured():
                continue
            seen_moves.add(move.id)
            processed += 1
            if not move._redinvoice_submit_one():
                failures += 1
        if processed:
            self._redinvoice_batch_report(processed, failures, retry=True)
        return True

    @api.model
    def _redinvoice_batch_report(self, processed, failures, retry=False):
        label = 'retry' if retry else 'nightly'
        _logger.info('RedInvoice %s batch: processed=%s failures=%s',
                     label, processed, failures)
        if failures > 0:
            # Surface to the accounting manager via a mail.activity on the company.
            manager = self.env.ref('account.group_account_manager', raise_if_not_found=False)
            user = self.env['res.users']
            if manager and manager.user_ids:
                user = manager.user_ids[0]
            try:
                self.env['res.company'].browse(self.env.company.id).activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Red Invoice batch: %s failure(s)') % failures,
                    note=_('%s Red Invoice submissions failed in the %s batch and '
                           'were queued for retry. Check the Red Invoice Requests '
                           'list for details.') % (failures, label),
                    user_id=user.id or self.env.uid,
                )
            except Exception as exc:  # noqa: BLE001 — reporting must never abort the batch
                _logger.warning('RedInvoice batch: could not create manager activity: %s', exc)
