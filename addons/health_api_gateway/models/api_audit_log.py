# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ApiAuditLog(models.Model):
    """Append-only PHI access audit (spec B.2.8). Rows are created by the
    gateway middleware via sudo; nobody — admin included — can write or
    unlink them. Request/response bodies are never logged."""
    _name = 'api.audit.log'
    _description = 'API Access Audit Log'
    _log_access = False  # volume; ts field below is the timestamp
    _order = 'ts desc, id desc'
    _rec_name = 'route'

    ts = fields.Datetime(default=fields.Datetime.now, index=True, string='Timestamp')
    auth_kind = fields.Selection([
        ('apikey', 'API Key'),
        ('oauth', 'OAuth2 Token'),
        ('session', 'Session'),
    ], string='Auth Kind')
    key_or_client = fields.Char(
        help='API key id or OAuth client_id — never the secret.')
    user_id = fields.Many2one('res.users', string='Service User')
    route = fields.Char(index=True)
    method = fields.Char()
    status_code = fields.Integer()
    latency_ms = fields.Integer()
    ip = fields.Char(string='IP Address')
    resource_type = fields.Char(help='e.g. Patient, health.fieldservice.order')
    resource_ids = fields.Char(help='Comma-separated ids returned/affected.')
    patient_ids = fields.Char(index=True,
                              help='PHI subjects touched — required for FHIR reads.')

    # ------------------------------------------------------------------
    @staticmethod
    def _join_ids(values):
        if not values:
            return False
        if isinstance(values, str):
            return values
        try:
            return ','.join(str(v) for v in values)
        except TypeError:
            return str(values)

    @api.model
    def log_access(self, user_id=None, client=None, route=None, method=None,
                   model=None, record_ids=None, patient_ids=None, status=None,
                   latency_ms=None, ip=None, auth_kind=None):
        """Append one audit row. Interface contract used by health_fhir_core:
        env['api.audit.log'].sudo().log_access(user_id, client, route, method,
        model, record_ids, patient_ids, status)."""
        return self.sudo().with_context(gateway_audit_append=True).create({
            'user_id': user_id or False,
            'key_or_client': client or False,
            'route': route or False,
            'method': method or False,
            'resource_type': model or False,
            'resource_ids': self._join_ids(record_ids),
            'patient_ids': self._join_ids(patient_ids),
            'status_code': status or 0,
            'latency_ms': latency_ms or 0,
            'ip': ip or False,
            'auth_kind': auth_kind or False,
        })

    # ------------------------------------------------------------------
    # Append-only enforcement — for everyone, superuser included.
    # ------------------------------------------------------------------
    def write(self, vals):
        raise UserError(_('API audit log entries are append-only and can never be modified.'))

    def unlink(self):
        raise UserError(_('API audit log entries are append-only and can never be deleted.'))
