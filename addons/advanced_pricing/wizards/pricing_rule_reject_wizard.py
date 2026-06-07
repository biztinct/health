# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

class PricingRuleRejectWizard(models.TransientModel):
    _name = 'pricing.rule.reject.wizard'
    _description = 'Reject Pricing Rule with Mandatory Reason'

    rule_id = fields.Many2one('advanced.pricing.rule', 'Pricing Rule', required=True)
    rejection_reason = fields.Text('Rejection Reason', required=True,
                                   help='Explain why this pricing rule is being rejected (minimum 10 characters)')

    def action_confirm_reject(self):
        """Confirm rejection with reason"""
        if not self.rejection_reason or len(self.rejection_reason.strip()) < 10:
            raise UserError(
                _('Please provide a detailed rejection reason (minimum 10 characters).')
            )

        self.rule_id.write({
            'approval_status': 'rejected',
            'rejection_reason': self.rejection_reason,
        })

        self.rule_id.message_post(
            body=_(
                "Rule rejected by <b>%(user)s</b><br/><b>Reason:</b> %(reason)s",
                user=self.env.user.name,
                reason=self.rejection_reason,
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

        # Mark activities as done
        self.rule_id.activity_ids.action_done()
