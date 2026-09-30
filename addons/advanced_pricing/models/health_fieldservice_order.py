# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HealthFieldserviceOrder(models.Model):
    """Surface the advanced-pricing breakdown of the linked quote directly on the
    booking record, so staff see which rules shaped the price without opening the
    quote."""
    _inherit = 'health.fieldservice.order'

    pricing_breakdown_html = fields.Html(
        string='Pricing Breakdown',
        related='sale_order_id.pricing_breakdown_html',
        readonly=True,
    )

    # Price-list condition warnings (owner, 2026-09-30: warn, never block,
    # and keep the warning on the booking so it can be reviewed later).
    # Stored so the bookings list can filter on them.
    has_pricing_warnings = fields.Boolean(
        'Price Warnings', related='sale_order_id.has_pricing_warnings', store=True,
        help='The booking breaks one of the price list conditions.')
    pricing_warnings = fields.Text(
        'Price Warning Details', related='sale_order_id.pricing_warnings')

    # Extra facts some price conditions need, kept on the quote (where the
    # procedure counts already live) and editable from the booking.
    pricing_doctor_ordered = fields.Boolean(
        related='sale_order_id.doctor_ordered', readonly=False)
    pricing_other_service_failed = fields.Boolean(
        related='sale_order_id.other_service_failed', readonly=False)

    # --- Quick booking: same facts, context and warnings as the saved quote ---
    @api.model
    def _quick_booking_booking_facts(self, partner, product_lines, vals, date_obj, time_hour):
        facts = super()._quick_booking_booking_facts(partner, product_lines, vals, date_obj, time_hour)
        products = self.env['product.product'].browse(
            [pl['product_id'] for pl in product_lines if pl.get('product_id')]).exists()
        scheduled_dt = False
        if date_obj is not None:
            import pytz
            from datetime import datetime, time as dtime
            hours = float(time_hour or 0)
            local = datetime.combine(date_obj, dtime(int(hours) % 24, int(round((hours % 1) * 60)) % 60))
            try:
                facility = self.env['health.facility'].browse(vals.get('facility_id') or [])
                tz = pytz.timezone((facility.exists() and facility.timezone)
                                   or self.env.company.partner_id.tz or 'Asia/Ho_Chi_Minh')
                scheduled_dt = tz.localize(local).astimezone(pytz.UTC).replace(tzinfo=None)
            except Exception:
                scheduled_dt = local
        facts.update(self.env['advanced.pricing.engine']._booking_facts(
            partner, products.mapped('product_tmpl_id'),
            scheduled_dt=scheduled_dt,
            address=partner.contact_address if partner else False,
            staff_ids=[i for i in (vals.get('staff_ids') or []) if i],
        ))
        return facts

    @api.model
    def _quick_booking_line_context(self, engine, product, qty, base_context):
        return self.env['advanced.pricing.engine']._line_pricing_context(product, qty, base_context)

    @api.model
    def _quick_booking_line_warnings(self, engine, product, qty, ctx):
        try:
            return engine.booking_warnings(product, qty, ctx)
        except Exception:
            return []

    def _pricing_staff_ids(self):
        """Every employee on this booking: primary doctor/nurse plus the
        non-template staff assignments."""
        self.ensure_one()
        staff = self.primary_nurse_id | self.primary_doctor_id
        staff |= self.assignment_ids.filtered(
            lambda a: a.state != 'template' and a.staff_id).mapped('staff_id')
        return staff.ids

    def _pricing_address(self):
        self.ensure_one()
        return (self.service_address or self.visit_address
                or self.patient_id.contact_address or '')
