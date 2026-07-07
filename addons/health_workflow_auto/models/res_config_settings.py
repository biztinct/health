from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # E.2 — only adds a button, safe by default.
    wf_onetap_enabled = fields.Boolean(
        string='One-Tap Visit Completion',
        config_parameter='health_workflow_auto.onetap_enabled', default=True)
    # E.3 — talks to Viettel production; off by default.
    wf_redinvoice_batch_enabled = fields.Boolean(
        string='Nightly Red Invoice Batch',
        config_parameter='health_workflow_auto.redinvoice_batch_enabled', default=False)
    # E.4 — writes payroll-adjacent hr.attendance; off by default.
    wf_timecard_sync_enabled = fields.Boolean(
        string='Timecard Auto-Fill from Visits',
        config_parameter='health_workflow_auto.timecard_sync_enabled', default=False)
    # E.5 — ZNS template ids for the first-visit offer (rides messaging enabled/dry_run).
    wf_zns_template_visit_offer = fields.Char(
        string='Visit Offer ZNS Template ID',
        config_parameter='health_workflow_auto.zns_template_visit_offer')
    wf_offer_service_product_id = fields.Many2one(
        'product.product', string='First-Visit Offer Service',
        config_parameter='health_workflow_auto.offer_service_product_id',
        domain=[('sale_ok', '=', True)],
        help='Billable service line attached to a booking created from a first-visit offer.')
