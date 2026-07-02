# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

REFRESH_LOCK_KEY = "biz_bi_gold_refresh"
MAX_BACKOFF_MINUTES = 24 * 60


class BiRefreshJob(models.Model):
    """One row per gold dataset: owns the materialized view lifecycle and the
    serial refresh queue (single server — never two refreshes at once)."""
    _name = 'bi.refresh.job'
    _description = 'BI Gold Refresh Job'
    _order = 'next_run'

    dataset_id = fields.Many2one('bi.dataset', required=True,
                                 ondelete='cascade', index=True)
    interval_minutes = fields.Selection([
        ('15', 'Every 15 minutes'),
        ('30', 'Every 30 minutes'),
        ('60', 'Every hour'),
        ('1440', 'Daily'),
    ], default='60', required=True)
    state = fields.Selection([
        ('idle', 'Idle'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('error', 'Error'),
    ], default='idle', required=True)
    last_refresh = fields.Datetime(readonly=True)
    last_duration_ms = fields.Integer(readonly=True)
    last_error = fields.Text(readonly=True)
    error_streak = fields.Integer(readonly=True, default=0)
    next_run = fields.Datetime(default=fields.Datetime.now, index=True)
    matview_size = fields.Char(compute='_compute_matview_size')

    _sql_constraints = [
        ('dataset_uniq', 'unique(dataset_id)',
         'A dataset has a single refresh job.'),
    ]

    def _compute_matview_size(self):
        for job in self:
            self.env.cr.execute(
                "SELECT pg_size_pretty(pg_total_relation_size(c.oid)) "
                "FROM pg_class c WHERE c.relname = %s",
                (job.dataset_id._gold_matview_name(),))
            row = self.env.cr.fetchone()
            job.matview_size = row and row[0] or _('not created')

    # ------------------------------------------------------------------
    # Publish: (re)create the materialized view + indexes
    # ------------------------------------------------------------------

    @api.model
    def _publish_gold_for(self, dataset):
        matview = dataset._gold_matview_name()
        silver_sql = dataset._compile_silver_sql()

        cr = self.env.cr
        with cr.savepoint():
            cr.execute(SQL("DROP MATERIALIZED VIEW IF EXISTS %s CASCADE",
                           SQL.identifier(matview)))
            cr.execute(SQL("CREATE MATERIALIZED VIEW %s AS (%s) WITH DATA",
                           SQL.identifier(matview), silver_sql))
            # unique index on the row key — required for REFRESH CONCURRENTLY
            cr.execute(SQL(
                "CREATE UNIQUE INDEX %s ON %s (_bi_row_key)",
                SQL.identifier('%s_pk' % matview),
                SQL.identifier(matview)))
            # secondary indexes: filterable + date fields + company column
            indexed_fields = dataset.field_ids.filtered(
                lambda f: f.origin == 'stored'
                and (f.is_filterable or f.role == 'date'))
            if dataset.company_field_id:
                indexed_fields |= dataset.company_field_id
            for field in indexed_fields:
                cr.execute(SQL(
                    "CREATE INDEX %s ON %s (%s)",
                    SQL.identifier('%s_f%d_idx' % (matview, field.id)),
                    SQL.identifier(matview),
                    SQL.identifier('f_%d' % field.id)))
            cr.execute(SQL("ANALYZE %s", SQL.identifier(matview)))

        job = self.sudo().search([('dataset_id', '=', dataset.id)], limit=1)
        values = {
            'state': 'idle',
            'last_refresh': fields.Datetime.now(),
            'last_error': False,
            'error_streak': 0,
        }
        if job:
            job.write(values)
        else:
            job = self.sudo().create(dict(values, dataset_id=dataset.id))
        job._schedule_next()
        dataset.refresh_job_id = job
        self.env['bi.query.cache'].sudo().invalidate_dataset(dataset.id)
        self.env['bi.audit.log'].sudo().log('gold_publish', dataset=dataset)
        _logger.info("biz_bi: published gold matview %s", matview)
        return job

    # ------------------------------------------------------------------
    # Serial refresh queue
    # ------------------------------------------------------------------

    def action_refresh_now(self):
        """'Refresh now' button: enqueue immediately; run inline when no
        other refresh holds the advisory lock."""
        self.ensure_one()
        self.write({'next_run': fields.Datetime.now(), 'state': 'queued'})
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", (REFRESH_LOCK_KEY,))
        if self.env.cr.fetchone()[0]:
            try:
                self._refresh_one()
            finally:
                self.env.cr.execute(
                    "SELECT pg_advisory_unlock(hashtext(%s))",
                    (REFRESH_LOCK_KEY,))
        return True

    @api.model
    def _process_refresh_queue(self):
        """Cron entry point: drain due jobs one at a time."""
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", (REFRESH_LOCK_KEY,))
        if not self.env.cr.fetchone()[0]:
            _logger.info("biz_bi: refresh already running, skipping this tick")
            return
        try:
            due = self.search([
                ('next_run', '<=', fields.Datetime.now()),
                ('state', 'in', ('idle', 'queued', 'error')),
                ('dataset_id.storage_mode', '=', 'gold'),
                ('dataset_id.state', '=', 'published'),
            ])
            for job in due:
                job._refresh_one()
                # keep the transaction small per matview
                self.env.cr.commit()  # pylint: disable=invalid-commit
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", (REFRESH_LOCK_KEY,))

    def _refresh_one(self):
        self.ensure_one()
        matview = self.dataset_id._gold_matview_name()
        timeout_ms = int(self.env['ir.config_parameter'].sudo().get_param(
            'biz_bi.refresh_timeout_ms', 300000))
        self.write({'state': 'running'})
        started = fields.Datetime.now()
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SET LOCAL statement_timeout = %s", (timeout_ms,))
                self.env.cr.execute(SQL(
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY %s",
                    SQL.identifier(matview)))
            duration = int((fields.Datetime.now() - started).total_seconds()
                           * 1000)
            self.write({
                'state': 'idle',
                'last_refresh': fields.Datetime.now(),
                'last_duration_ms': duration,
                'last_error': False,
                'error_streak': 0,
            })
            self._schedule_next()
            self.env['bi.query.cache'].sudo().invalidate_dataset(
                self.dataset_id.id)
            self.env['bi.audit.log'].sudo().log(
                'gold_refresh', dataset=self.dataset_id,
                payload={'duration_ms': duration})
            if duration > 120000:
                self.dataset_id.message_post(body=_(
                    "Gold refresh took %s seconds — consider a longer "
                    "interval or narrower dataset.", duration // 1000))
        except Exception as exc:  # noqa: BLE001 — job must record any failure
            _logger.exception("biz_bi: refresh failed for %s", matview)
            streak = self.error_streak + 1
            backoff = min(
                int(self.interval_minutes) * (2 ** streak),
                MAX_BACKOFF_MINUTES)
            self.write({
                'state': 'error',
                'last_error': str(exc),
                'error_streak': streak,
                'next_run': fields.Datetime.now() + timedelta(minutes=backoff),
            })
            self.dataset_id.message_post(body=_(
                "Gold refresh failed: %s (retry in %s minutes)",
                exc, backoff))

    def _schedule_next(self):
        for job in self:
            job.next_run = fields.Datetime.now() + timedelta(
                minutes=int(job.interval_minutes))

    def is_healthy(self):
        self.ensure_one()
        return self.state != 'error' and bool(self.last_refresh)
