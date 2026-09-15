# -*- coding: utf-8 -*-
"""Choosing which advertising account this system reports on.

Google's permission covers the WHOLE of the signed-in person's Google Ads
access — there is no narrower scope to ask for. This screen is where that
breadth is made honest: it says so in one sentence, it lists only real
advertising accounts (a manager account is filtered out by the client, and
cannot be chosen even by a hand-built RPC — `_validate_reporting_access`
refuses it), and the binding is proven against Google before anything is
stored.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class GoogleAdsAccountSelect(models.TransientModel):
    _name = 'google.ads.account.select'
    _description = 'Choose the Advertising Account'

    account_id = fields.Many2one(
        'google.ads.account', string='Google Ads entry', required=True,
        ondelete='cascade')
    line_ids = fields.One2many(
        'google.ads.account.select.line', 'wizard_id', string='Accounts')

    def action_refresh(self):
        """Ask Google again — an account added minutes ago will now appear."""
        self.ensure_one()
        return self.account_id.action_list_reporting_accounts()

    def action_use(self):
        self.ensure_one()
        chosen = self.line_ids.filtered('selected')
        if not chosen:
            raise UserError(_('Tick the advertising account to use.'))
        if len(chosen) > 1:
            raise UserError(_(
                'Tick exactly one advertising account. Add a second entry if '
                'this clinic advertises through more than one.'))
        return self.account_id.action_select_reporting_account(
            chosen.customer_id, chosen.login_customer_id or None)


class GoogleAdsAccountSelectLine(models.TransientModel):
    _name = 'google.ads.account.select.line'
    _description = 'Advertising Account Candidate'
    _order = 'name, customer_id'

    wizard_id = fields.Many2one(
        'google.ads.account.select', required=True, ondelete='cascade')
    selected = fields.Boolean(string='Use this one')
    customer_id = fields.Char(string='Account Number', readonly=True)
    login_customer_id = fields.Char(string='Manager Number', readonly=True)
    name = fields.Char(string='Account Name', readonly=True)
    currency = fields.Char(string='Currency', readonly=True)
    time_zone = fields.Char(string='Time Zone', readonly=True)
    status = fields.Char(string='Status in Google', readonly=True)
    # Always False after the client's filtering — kept so the screen can never
    # imply "we checked nothing" and so a future manager-aware listing has a
    # column to fill rather than a migration to write.
    is_manager = fields.Boolean(string='Manager Account', readonly=True)
    test_account = fields.Boolean(string='Test Account', readonly=True)

    @api.onchange('selected')
    def _onchange_selected(self):
        """One tick at a time — the binding is one account, not a basket."""
        for line in self:
            if line.selected:
                (line.wizard_id.line_ids - line).selected = False
