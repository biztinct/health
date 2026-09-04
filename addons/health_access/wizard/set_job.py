# -*- coding: utf-8 -*-
"""Change what somebody is employed as, from their passport.

ONE FIELD AND A SENTENCE. The passport already answers "what does this person
have"; this answers the other half — "what is this person" — and it is a
separate question because holding a role and being employed as one are
different facts. An owner holds the Doctor bundle; the owner is not a doctor,
and the roster must not put them on a ward round.

IT SAYS WHAT WILL HAPPEN BEFORE IT HAPPENS. Setting a job also gives that role,
and takes back the one it replaces, so the form says so in the words somebody
would use rather than leaving them to find out from the audit trail.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HealthAccessSetJob(models.TransientModel):
    _name = 'health.access.set.job'
    _description = 'Change their job'

    user_id = fields.Many2one('res.users', string='Who', required=True,
                              readonly=True)
    user_name = fields.Char(related='user_id.name', readonly=True)
    current_job_id = fields.Many2one(
        'biz.access.role', string='Employed as today',
        related='user_id.job_role_id', readonly=True)
    job_role_id = fields.Many2one(
        'biz.access.role', string='Employed as',
        domain="[('active', '=', True)]",
        help='It decides what the schedule, the pickers and the reports call '
             'them — and it gives them that role.')
    job_description = fields.Text(
        string='What that lets them do', related='job_role_id.description',
        readonly=True)
    counts_as = fields.Selection(
        related='job_role_id.clinical_kind', string='Counts as', readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        user_id = self.env.context.get('default_user_id') or \
            self.env.context.get('active_id')
        if user_id and 'user_id' in fields_list:
            values.setdefault('user_id', user_id)
        user = self.env['res.users'].sudo().browse(
            values.get('user_id') or 0).exists()
        if user and 'job_role_id' in fields_list:
            values.setdefault('job_role_id', user.job_role_id.id or False)
        return values

    def action_apply(self):
        self.ensure_one()
        if not self.env['biz.access'].can_manage():
            raise UserError(_(
                "Saying what somebody's job is also gives them that role, so "
                "it is something the access team does."))
        target = self.user_id.sudo()
        if target.job_role_id == self.job_role_id:
            raise UserError(_(
                "%(who)s is already employed as %(what)s.",
                who=target.name or '',
                what=self.job_role_id.name or _('nothing in particular')))
        was = target.job_role_id
        target.job_role_id = self.job_role_id
        if self.job_role_id:
            message = _(
                "%(who)s is now employed as \"%(what)s\", and holds it.",
                who=target.name or '', what=self.job_role_id.name or '')
        else:
            message = _(
                "%(who)s has no job on their record any more, and \"%(what)s\" "
                "was taken back.",
                who=target.name or '', what=was.name or '')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
