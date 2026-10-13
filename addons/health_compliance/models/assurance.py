"""Evidence tracks a release and scope; it never equates software with approval."""
import base64
import hashlib
import json
from contextvars import ContextVar
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_APPROVING = ContextVar('health_compliance_approving', default=False)


def require_manager(env):
    if not (env.user.has_group('health_base.group_healthcare_admin')
            or env.user.has_group('health_base.group_healthcare_manager')
            or env.user.has_group('health_base.group_healthcare_owner')):
        raise UserError(_('A healthcare compliance manager must perform this action.'))


class Requirement(models.Model):
    _name = 'health.compliance.requirement'
    _description = 'Compliance Requirement'
    _order = 'code'
    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    package = fields.Char(required=True)
    original_text = fields.Text(string='Assessment Requirement (baseline)', readonly=True, help='Assessment wording. The unchanged client document remains the source of original supplied text.')
    source = fields.Char(readonly=True)
    effective_date_note = fields.Char(readonly=True)
    applicability = fields.Text()
    technical_status = fields.Selection([('pending', 'Pending'), ('partial', 'Partially verified'),
                                         ('verified', 'Verified in stated scope')], default='pending', required=True)
    manual_status = fields.Selection([('pending', 'Pending'), ('done', 'Completed with evidence'),
                                     ('na', 'Not applicable with justification')], default='pending', required=True)
    authority_status = fields.Selection([('pending', 'Pending'), ('approved', 'Authority approved with proof'),
                                        ('na', 'Not applicable with justification')], default='pending', required=True)
    manual_action = fields.Text()
    external_dependency = fields.Text()
    owner_id = fields.Many2one('res.users')
    decision_reason = fields.Text()
    evidence_ids = fields.One2many('health.compliance.evidence', 'requirement_id')
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)

    def write(self, vals):
        for row in self:
            approved = row.evidence_ids.filtered(lambda e: e.state == 'approved' and
                (not e.expires_on or e.expires_on >= fields.Date.context_today(e)))
            if vals.get('technical_status') in ('verified', 'partial') and not approved.filtered(lambda e: e.kind == 'technical'):
                raise UserError(_('Attach independently reviewed technical evidence first.'))
            if vals.get('manual_status') == 'done' and not approved.filtered(lambda e: e.kind == 'manual'):
                raise UserError(_('Attach independently reviewed operational evidence first.'))
            if vals.get('authority_status') == 'approved' and not approved.filtered(lambda e: e.kind == 'authority'):
                raise UserError(_('Attach the real authority decision; a submission receipt is insufficient.'))
            if (vals.get('manual_status') == 'na' or vals.get('authority_status') == 'na') and not (vals.get('decision_reason') or row.decision_reason):
                raise UserError(_('Record the applicability justification.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(vals.get(k, 'pending') != 'pending' for k in ('technical_status', 'manual_status', 'authority_status')):
                raise UserError(_('New requirements start pending.'))
        rows = super().create(vals_list)
        for row in rows:
            if any(row[k] != 'pending' for k in ('technical_status', 'manual_status', 'authority_status')):
                raise UserError(_('New requirements start pending.'))
        return rows

    def export_register(self):
        require_manager(self.env)
        rows = self.search([])
        content = json.dumps({'environment': self.env.cr.dbname,
                              'exported_at': fields.Datetime.to_string(fields.Datetime.now()),
                              'notice': 'Scoped evidence register. No blanket compliance or MPS approval is implied.',
                              'requirements': rows.read(['code', 'name', 'package', 'technical_status',
                                  'manual_status', 'authority_status', 'manual_action', 'external_dependency',
                                  'decision_reason']),
                              'evidence': rows.evidence_ids.read(['name', 'state', 'sha256', 'release_commit',
                                  'environment_scope', 'kind', 'reviewed_at', 'reviewer_id'])},
                             ensure_ascii=False, default=str, indent=2).encode()
        attachment = self.env['ir.attachment'].create({'name': 'VN-compliance-register.json',
            'raw': content, 'mimetype': 'application/json', 'res_model': self._name,
            'res_id': rows[:1].id if rows else 0})
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'download'}


class Evidence(models.Model):
    _name = 'health.compliance.evidence'
    _description = 'Compliance Evidence Artifact'
    _order = 'create_date desc'
    name = fields.Char(required=True)
    requirement_id = fields.Many2one('health.compliance.requirement', required=True, ondelete='restrict')
    kind = fields.Selection([('technical', 'Technical test'), ('manual', 'Operational proof'),
                             ('authority', 'Authority decision')], required=True, default='technical')
    file = fields.Binary(required=True, attachment=True)
    filename = fields.Char(required=True)
    sha256 = fields.Char(readonly=True, copy=False)
    release_commit = fields.Char(required=True)
    environment_scope = fields.Char(required=True, help='Exact database, configuration and synthetic/live data scope tested.')
    result_summary = fields.Text(required=True)
    limitations = fields.Text(required=True)
    expires_on = fields.Date()
    state = fields.Selection([('draft', 'Awaiting review'), ('approved', 'Reviewed')], required=True, default='draft', copy=False)
    reviewer_id = fields.Many2one('res.users', readonly=True, copy=False)
    reviewed_at = fields.Datetime(readonly=True, copy=False)
    company_id = fields.Many2one(related='requirement_id.company_id', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft' or {'sha256', 'reviewer_id', 'reviewed_at'} & vals.keys():
                raise UserError(_('Evidence must be submitted for independent review.'))
            vals['sha256'] = hashlib.sha256(base64.b64decode(vals.get('file') or b'', validate=True)).hexdigest()
        records = super().create(vals_list)
        if any(r.state != 'draft' or r.reviewer_id or r.reviewed_at for r in records):
            raise UserError(_('Evidence cannot be approved through defaults.'))
        return records

    def write(self, vals):
        if any(r.state == 'approved' for r in self):
            raise UserError(_('Reviewed evidence is immutable. Submit a new artifact for a new release.'))
        if {'sha256', 'state', 'reviewer_id', 'reviewed_at'} & vals.keys() and not _APPROVING.get():
            raise UserError(_('Use independent review to approve evidence.'))
        if 'file' in vals:
            vals['sha256'] = hashlib.sha256(base64.b64decode(vals['file'] or b'', validate=True)).hexdigest()
        return super().write(vals)

    def unlink(self):
        if any(r.state == 'approved' for r in self):
            raise UserError(_('Reviewed evidence is immutable.'))
        return super().unlink()

    def action_review(self):
        require_manager(self.env)
        for row in self:
            if row.create_uid.id == self.env.uid:
                raise UserError(_('The uploader cannot independently review their own evidence.'))
            if row.expires_on and row.expires_on < fields.Date.context_today(row):
                raise UserError(_('Expired evidence cannot be approved.'))
            if hashlib.sha256(base64.b64decode(row.file or b'')).hexdigest() != row.sha256:
                raise UserError(_('Evidence digest verification failed.'))
            token = _APPROVING.set(True)
            try:
                row.write({'state': 'approved', 'reviewer_id': self.env.uid,
                           'reviewed_at': fields.Datetime.now()})
            finally:
                _APPROVING.reset(token)
