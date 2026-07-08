from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # A6 — auto-invite writes nothing until a human opts in.
    sb_auto_invite_after_completion = fields.Boolean(
        string='Auto-send Rebook Link After Visit',
        config_parameter='health_self_booking.auto_invite_after_completion',
        default=False)
    # A6 — ZNS template id (rides messaging enabled/dry_run; empty => no row).
    sb_zns_template_invite = fields.Char(
        string='Self-Booking ZNS Template ID',
        config_parameter='health_self_booking.zns_template_invite')
    # A3.3 — fallback billable service when no package / no last-visit service.
    sb_fallback_service_product_id = fields.Many2one(
        'product.product', string='Fallback Rebook Service',
        config_parameter='health_self_booking.fallback_service_product_id',
        domain=[('sale_ok', '=', True)],
        help='Billable service line used when a client has no active package '
             'and no previous booked service to rebook.')
    # A4 — slot proposal knobs.
    sb_slot_count = fields.Integer(
        string='Rebook Slots Offered',
        config_parameter='health_self_booking.slot_count', default=6)
    sb_horizon_days = fields.Integer(
        string='Rebook Slot Horizon (days)',
        config_parameter='health_self_booking.horizon_days', default=10)
    sb_invite_ttl_days = fields.Integer(
        string='Rebook Link Lifetime (days)',
        config_parameter='health_self_booking.invite_ttl_days', default=14)
