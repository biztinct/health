# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BookingServicesWizard(models.TransientModel):
    _name = 'health.booking.services.wizard'
    _description = 'Add Services & Assignment to Bookings'

    current_step = fields.Selection([
        ('1_services', 'Services'),
        ('2_assignment', 'Assignment'),
    ], default='1_services')

    booking_ids = fields.Many2many(
        'health.fieldservice.order',
        'booking_services_wiz_fso_rel',
        'wizard_id', 'fso_id',
        string='Bookings',
    )
    booking_count = fields.Integer(compute='_compute_booking_count')

    # Quote
    create_quote = fields.Boolean('Create Quote')

    # Computed from bookings
    facility_id = fields.Many2one('health.facility', compute='_compute_from_bookings', store=True)
    client_id = fields.Many2one('res.partner', compute='_compute_from_bookings', store=True)

    # Staff
    assigned_staff_ids = fields.Many2many(
        'hr.employee',
        'services_wiz_staff_rel', 'wizard_id', 'employee_id',
        string='Assigned Staff',
        domain="[('is_healthcare_staff', '=', True), ('employment_status', '=', 'active'), ('is_doctor_role', '=', False)]",
    )
    lead_staff_id = fields.Many2one(
        'hr.employee', string='Lead Staff',
        domain="[('is_healthcare_staff', '=', True), ('employment_status', '=', 'active'), ('is_doctor_role', '=', False)]",
    )

    @api.depends('booking_ids')
    def _compute_booking_count(self):
        for wiz in self:
            wiz.booking_count = len(wiz.booking_ids)

    @api.depends('booking_ids')
    def _compute_from_bookings(self):
        for wiz in self:
            first = wiz.booking_ids[:1]
            wiz.facility_id = first.facility_id if first else False
            wiz.client_id = first.patient_id if first else False

    def _open_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Services & Assignment'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_next_step(self):
        self.ensure_one()
        package = self.package_id if hasattr(self, 'package_id') else False
        if package and package.remaining_services < len(self.booking_ids):
            raise ValidationError(
                _('Services remaining in prepaid package (%d) are less than bookings made (%d).')
                % (package.remaining_services, len(self.booking_ids))
            )
        self.current_step = '2_assignment'
        return self._open_wizard()

    def action_prev_step(self):
        self.ensure_one()
        self.current_step = '1_services'
        return self._open_wizard()

    def action_apply(self):
        self.ensure_one()
        package = self.package_id if hasattr(self, 'package_id') else False

        if package and package.remaining_services < len(self.booking_ids):
            raise ValidationError(
                _('Services remaining in prepaid package (%d) are less than bookings made (%d).')
                % (package.remaining_services, len(self.booking_ids))
            )

        first_booking = self.booking_ids[:1]
        sale_order = False

        # Create quote for first booking if requested
        if self.create_quote and first_booking and not first_booking.sale_order_id:
            first_booking.action_create_and_open_quote()
            sale_order = first_booking.sale_order_id

        for booking in self.booking_ids:
            # Copy quote to other bookings
            if self.create_quote and sale_order and booking != first_booking:
                new_quote = sale_order.copy({
                    'origin': booking.name,
                    'partner_id': booking.patient_id.id,
                })
                booking.sale_order_id = new_quote.id

            if package:
                booking.write({'package_ids': [(4, package.id)]})

            if self.create_quote or package:
                booking.action_confirm_booking()

            # Staff assignment
            staff_update = {}
            if self.assigned_staff_ids:
                staff_ids = set(self.assigned_staff_ids.ids)
                if self.lead_staff_id:
                    staff_ids.add(self.lead_staff_id.id)
                staff_update['assigned_staff_ids'] = [(6, 0, list(staff_ids))]
            elif self.lead_staff_id:
                staff_update['assigned_staff_ids'] = [(6, 0, [self.lead_staff_id.id])]
            if staff_update:
                booking.write(staff_update)

        # If quote was created, open it for editing (non-modal)
        if self.create_quote and first_booking and first_booking.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Healthcare Quote'),
                'res_model': 'sale.order',
                'res_id': first_booking.sale_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Bookings'),
            'res_model': 'health.fieldservice.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.booking_ids.ids)],
            'target': 'current',
        }
