"""Configuration evidence, separate from clinical content and existing logs."""
import json
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class Audit(models.Model):
    _name = 'health.workspace.audit'
    _description = 'Workspace change history'
    _order = 'id desc'

    company_id = fields.Many2one('res.company', required=True, ondelete='restrict')
    actor_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    happened_at = fields.Datetime(required=True)
    subject = fields.Char(required=True)
    detail = fields.Text(required=True)

    @api.model_create_multi
    def create(self, values):
        if not self.env.su:
            raise AccessError(_('History is recorded by the application.'))
        return super().create([dict(v, actor_id=self.env.uid, happened_at=fields.Datetime.now()) for v in values])

    def write(self, values):
        raise AccessError(_('History cannot be changed.'))

    def unlink(self):
        raise AccessError(_('History cannot be deleted.'))

    @api.model
    def _record(self, subject, changes, company=None):
        return self.sudo().create({'company_id': (company or self.env.user.company_id).id,
            'subject': subject, 'detail': json.dumps(changes, ensure_ascii=False, default=str)})
