"""Decree 356/2025 Article 5: acknowledgement working days; completion days.

Operational staff verify identity, exceptions, holidays and communications.
No acknowledgement or notification is sent merely by changing a state.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from .assurance import require_manager

BASE_DAYS = {'withdrawal': (15, 20, 15), 'restriction': (15, 20, 15),
             'opposition': (15, 20, 15), 'access': (10, 15, 10),
             'correction': (10, 15, 10), 'provision': (10, 15, 10),
             'deletion': (20, 30, 20), 'protection': (15, 15, 15)}


def working_due(day, holidays, count=2):
    while count:
        day += timedelta(days=1)
        if day.weekday() < 5 and day not in holidays:
            count -= 1
    return day


class Holiday(models.Model):
    _name = 'health.compliance.holiday'
    _description = 'Vietnam Rights Calendar Holiday'
    name = fields.Char(required=True)
    date = fields.Date(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)


class RightsRequest(models.Model):
    _name = 'health.compliance.rights'
    _description = 'Data Subject Rights Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'received_at desc'
    name = fields.Char(required=True)
    patient_id = fields.Many2one('res.partner', required=True, ondelete='restrict')
    kind = fields.Selection([(k, k.title()) for k in BASE_DAYS], required=True)
    received_at = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    processor_required = fields.Boolean(help='Completion requires action by a processor or third party.')
    identity_verification = fields.Text(help='Record verification method/result. Do not duplicate identity document images unnecessarily.')
    owner_id = fields.Many2one('res.users', default=lambda s: s.env.user)
    ack_due = fields.Date(compute='_compute_due')
    completion_due = fields.Date(compute='_compute_due')
    ack_at = fields.Datetime(readonly=True, copy=False)
    ack_proof_id = fields.Many2one('ir.attachment', string='Actual Acknowledgement Proof')
    extension_notice_id = fields.Many2one('ir.attachment', string='Actual Extension Notice Proof')
    extension_reason = fields.Text()
    extended_at = fields.Datetime(readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    outcome = fields.Text()
    legal_exception = fields.Text(help='Document the applicable legal basis for refusal/retention, when needed.')
    outcome_proof_id = fields.Many2one('ir.attachment', string='Actual Outcome Communication Proof')
    overdue = fields.Boolean(compute='_compute_due')
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)

    @api.depends('received_at', 'kind', 'processor_required', 'extended_at', 'ack_at', 'completed_at')
    def _compute_due(self):
        holidays = set(self.env['health.compliance.holiday'].search([
            ('company_id', 'in', self.company_id.ids)]).mapped('date'))
        for row in self:
            if not row.received_at or not row.kind:
                row.ack_due = row.completion_due = False
                row.overdue = False
                continue
            day = row.received_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
            normal, processor, extension = BASE_DAYS[row.kind]
            row.ack_due = working_due(day, holidays)
            row.completion_due = day + timedelta(days=(processor if row.processor_required else normal)
                                                   + (extension if row.extended_at else 0))
            today = fields.Datetime.now().replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
            row.overdue = bool((not row.ack_at and today > row.ack_due)
                               or (not row.completed_at and today > row.completion_due))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(vals.get(k) for k in ('ack_at', 'extended_at', 'completed_at')):
                raise UserError(_('Use the request workflow to record completed actions.'))
        records = super().create(vals_list)
        records._check_clock()
        if any(r.ack_at or r.extended_at or r.completed_at for r in records):
            raise UserError(_('Workflow timestamps cannot be supplied through defaults.'))
        return records

    @api.constrains('received_at')
    def _check_clock(self):
        if any(r.received_at > fields.Datetime.now() for r in self):
            raise UserError(_('A request receipt cannot be in the future.'))

    def write(self, vals):
        if {'ack_at', 'extended_at', 'completed_at'} & vals.keys():
            raise UserError(_('Workflow timestamps are recorded by the corresponding actions.'))
        if any(r.ack_at for r in self) and {'ack_proof_id', 'identity_verification'} & vals.keys():
            raise UserError(_('Recorded acknowledgement proof is immutable.'))
        if any(r.extended_at for r in self) and {'extension_reason', 'extension_notice_id'} & vals.keys():
            raise UserError(_('Recorded extension proof is immutable.'))
        if any(r.ack_at or r.extended_at or r.completed_at for r in self) and {'received_at', 'kind', 'processor_required', 'patient_id'} & vals.keys():
            raise UserError(_('The statutory clock and subject are frozen after action begins.'))
        if any(r.completed_at for r in self):
            raise UserError(_('Completed rights cases are immutable. Open a follow-up case.'))
        return super().write(vals)

    def _record_action(self, values):
        require_manager(self.env)
        if any(r.completed_at for r in self):
            raise UserError(_('This rights request is already complete.'))
        return super(RightsRequest, self).write(values)

    def action_acknowledge(self):
        for row in self:
            if row.ack_at or not row.identity_verification or not row.ack_proof_id:
                raise UserError(_('Record identity verification and the actual acknowledgement communication first.'))
            row._record_action({'ack_at': fields.Datetime.now()})

    def action_extend(self):
        for row in self:
            if row.extended_at or not row.extension_reason or not row.extension_notice_id:
                raise UserError(_('Only one justified extension is allowed; attach the actual notice.'))
            if fields.Date.context_today(row) > row.completion_due:
                raise UserError(_('A late notice cannot retrospectively extend the deadline. Record the breach and remediation.'))
            row._record_action({'extended_at': fields.Datetime.now()})

    def action_complete(self):
        for row in self:
            if not row.ack_at or not row.outcome or not row.outcome_proof_id:
                raise UserError(_('Record acknowledgement, the outcome and actual communication proof first.'))
            row._record_action({'completed_at': fields.Datetime.now()})

    def unlink(self):
        raise UserError(_('Rights requests are accountability records and cannot be deleted.'))


class RetentionHold(models.Model):
    _name = 'health.compliance.hold'
    _description = 'Retention or Legal Hold'
    name = fields.Char(required=True)
    patient_id = fields.Many2one('res.partner', required=True, ondelete='restrict')
    record_class = fields.Char(required=True, help='Custodian-approved retention class; do not infer statutory classification.')
    legal_basis = fields.Text(required=True)
    retain_until = fields.Date(help='Empty means indefinite hold; a date alone does not approve destruction.')
    active = fields.Boolean(default=True, readonly=True)
    release_reason = fields.Text()
    released_at = fields.Datetime(readonly=True)
    released_by_id = fields.Many2one('res.users', readonly=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)

    def action_release(self):
        require_manager(self.env)
        for row in self:
            if not row.release_reason or (row.retain_until and row.retain_until > fields.Date.context_today(row)):
                raise UserError(_('Record an approved release reason after the retention date.'))
            super(RetentionHold, row).write({'active': False, 'released_at': fields.Datetime.now(),
                                            'released_by_id': self.env.uid})

    def write(self, vals):
        if {'active', 'released_at', 'released_by_id'} & vals.keys():
            raise UserError(_('Use the reviewed hold-release action.'))
        if any(not r.active for r in self):
            raise UserError(_('Released hold records are immutable.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('active', True) is False or v.get('released_at') or v.get('released_by_id') for v in vals_list):
            raise UserError(_('New holds must be active.'))
        records = super().create(vals_list)
        if any(not r.active or r.released_at or r.released_by_id for r in records):
            raise UserError(_('New holds must be active.'))
        return records

    def unlink(self):
        raise UserError(_('Hold history cannot be deleted.'))
