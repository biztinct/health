# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.fields import Domain

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    active = fields.Boolean(default=True)
    
    # Get FSO that created this quote
    fso_id = fields.Many2one('health.fieldservice.order',
                            string='Booking',
                            store=True,
                            copy=False,
                            help='Booking that created this quote')

    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Area',
        compute='_compute_catchment_province_id',
        store=True,
        readonly=True,
        help='Catchment area used for filtering and access control'
    )

    @api.depends('fso_id.catchment_province_id',
                 'partner_id.catchment_province_id',
                 'partner_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for order in self:
            partner_catchment = order.partner_id._get_health_catchment_province() if order.partner_id else False
            order.catchment_province_id = (
                order.fso_id.catchment_province_id
                or partner_catchment
                or False
            )
    
    # Pricing configuration
    use_advanced_pricing = fields.Boolean('Use Advanced Pricing', 
                                         compute='_compute_use_advanced_pricing')
    advanced_pricing_details = fields.Text('Pricing Calculation Details')
    pricing_breakdown_html = fields.Html('Pricing Breakdown', sanitize=False, readonly=True,
                                         compute='_compute_pricing_breakdown_html',
                                         help='Shows applied pricing rules and calculations (auto-refreshes on line/qty/discount changes)')
    pre_service_amount = fields.Float('Pre-Service Amount', readonly=True,
                                      help='Quote total at time of advance payment, used to calculate post-service delta')

    # Post-service procedure counts (source of truth for pricing)
    injection_count = fields.Integer('Injections Given', default=1,
                                     help='Number of injections administered. First is included in base price.')
    medication_count = fields.Integer('Medications Given', default=1,
                                      help='Number of medications administered. First is included in base price.')
    wound_count = fields.Integer('Wounds Treated', default=1,
                                 help='Number of wounds treated. First is included in base price.')
    iv_fluid_count = fields.Integer('IV Fluid Bags', default=0,
                                    help='Number of IV fluid bags used. Not included in base price.')
    
    # Computed fields from FSO for pricing rules
    fso_distance = fields.Float('Distance (km)', 
                               compute='_compute_fso_fields', 
                               store=True, readonly=True,
                               help='Travel distance from FSO for pricing rules')
    
    fso_appointment_time = fields.Datetime('Appointment Time', 
                                          compute='_compute_fso_fields',
                                          store=True, readonly=True,
                                          help='Scheduled appointment time from FSO')
    
    fso_service_type = fields.Selection([
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('telemedicine', 'Telemedicine'),
        ('emergency', 'Emergency'),
        ('routine_checkup', 'Routine Checkup'),
        ('follow_up', 'Follow-up'),
        ('vaccination', 'Vaccination'),
        ('consultation', 'Consultation')
    ], string='Service Type', 
       compute='_compute_fso_fields',
       store=True, readonly=True,
       help='Service type from FSO for pricing rules')
    
    fso_service_location = fields.Selection([
        ('home', 'Home'),
        ('clinic', 'Clinic'),
        ('hospital', 'Hospital'),
        ('care_facility', 'Care Facility'),
        ('remote', 'Remote/Online')
    ], string='Service Location',
       compute='_compute_fso_fields',
       store=True, readonly=True,
       help='Service location from FSO')
    
    fso_urgency = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency')
    ], string='Urgency Level',
       compute='_compute_fso_fields',
       store=True, readonly=True,
       help='Urgency level from FSO for pricing rules')
    
    fso_priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Very High')
    ], string='Priority',
       compute='_compute_fso_fields',
       store=True, readonly=True,
       help='Priority from FSO for pricing rules')
    
    # Computed time-based fields for pricing rules
    is_weekend = fields.Boolean('Weekend Service', 
                               compute='_compute_time_factors', 
                               store=True,
                               help='True if appointment is on weekend')
    
    is_holiday = fields.Boolean('Holiday Service',
                               compute='_compute_time_factors',
                               store=True,
                               help='True if appointment is on holiday')

    holiday_type = fields.Selection([
        ('national', 'National Holiday'),
        ('tet', 'TET Holiday'),
        ('regional', 'Regional Holiday'),
        ('observance', 'Observance'),
    ], string='Holiday Type',
       compute='_compute_time_factors',
       store=True,
       help='Type of holiday for pricing calculations')

    holiday_multiplier = fields.Float('Holiday Price Multiplier',
                                     compute='_compute_time_factors',
                                     store=True,
                                     help='Price multiplier for holiday (e.g., 3.0 for TET)')
    
    is_after_hours = fields.Boolean('After Hours Service', 
                                   compute='_compute_time_factors', 
                                   store=True,
                                   help='True if appointment is after business hours')
    
    appointment_hour = fields.Integer('Appointment Hour', 
                                     compute='_compute_time_factors', 
                                     store=True,
                                     help='Hour of appointment (0-23) for time-based rules')
    
    # Service quantity fields for quantity-based rules
    service_units = fields.Integer('Service Units', 
                                  compute='_compute_service_units', 
                                  store=True,
                                  help='Total service units/quantity for bulk pricing rules')
    
    # Location-based fields for regional pricing
    service_city = fields.Char('Service City', 
                              compute='_compute_service_city', 
                              store=True,
                              help='Service city for location-based pricing rules')
    
    def _populate_fso_id(self):
        """Populate fso_id from reverse relationship if not already set.
        
        Called as a fallback during recalculation when fso_id wasn't
        set at quote creation time (legacy quotes).
        """
        for order in self:
            if not order.fso_id:
                fso = self.env['health.fieldservice.order'].search([('sale_order_id', '=', order.id)], limit=1)
                if fso:
                    order.fso_id = fso.id
    
    @api.depends('fso_id')
    def _compute_fso_fields(self):
        """Compute FSO-related fields for pricing rules"""
        for order in self:
            if order.fso_id:
                fso = order.fso_id
                order.fso_distance = fso.travel_distance or 0.0
                order.fso_appointment_time = fso.scheduled_datetime
                order.fso_service_type = fso.service_type
                order.fso_service_location = fso.service_location
                # Map urgency levels (FSO uses different values than sale order)
                try:
                    urgency_mapping = {
                        'routine': 'normal',
                        'urgent': 'urgent', 
                        'emergency': 'emergency',
                        'critical': 'emergency'  # Map critical to emergency
                    }
                    order.fso_urgency = urgency_mapping.get(fso.urgency_level, 'normal')
                except Exception as e:
                    # Fallback if mapping fails
                    order.fso_urgency = 'normal'
                order.fso_priority = fso.priority
            else:
                order.fso_distance = 0.0
                order.fso_appointment_time = False
                order.fso_service_type = False
                order.fso_service_location = False
                order.fso_urgency = False
                order.fso_priority = False
    
    @api.depends('pricelist_id.use_advanced_pricing', 'fso_id')
    def _compute_use_advanced_pricing(self):
        """Check if order uses advanced pricing"""
        for order in self:
            # Auto-enable advanced pricing for FSO-related quotes
            if order.fso_id:
                order.use_advanced_pricing = True
            else:
                order.use_advanced_pricing = order.pricelist_id.use_advanced_pricing
    
    @api.depends('fso_id', 'fso_appointment_time')
    def _compute_time_factors(self):
        """Compute time-based factors for pricing rules"""
        for order in self:
            if order.fso_appointment_time:
                dt = order.fso_appointment_time
                
                # Convert to local timezone if needed
                import pytz
                try:
                    # If dt is naive (no timezone), it's stored as UTC in database
                    if dt.tzinfo is None:
                        # Assume database stores UTC time as naive datetime
                        dt_utc = pytz.UTC.localize(dt)
                    else:
                        dt_utc = dt.astimezone(pytz.UTC)
                    
                    # Convert to company timezone for business hour calculations
                    company_tz = pytz.timezone(order.company_id.partner_id.tz or 'UTC')
                    dt_local = dt_utc.astimezone(company_tz)
                except:
                    # Fallback to original datetime if timezone conversion fails
                    dt_local = dt
                
                # Weekend check (Saturday=5, Sunday=6)
                order.is_weekend = dt_local.weekday() >= 5

                # Holiday check using resource.calendar.leaves with pricing info
                holiday_info = order._check_holiday(dt_local.date())
                order.is_holiday = holiday_info['is_holiday']
                order.holiday_type = holiday_info.get('holiday_type', False)
                order.holiday_multiplier = holiday_info.get('multiplier', 1.0)

                # After hours check (before 8 AM or after 6 PM)
                order.is_after_hours = dt_local.hour < 8 or dt_local.hour >= 18

                # Appointment hour for time-based rules
                order.appointment_hour = dt_local.hour
            else:
                order.is_weekend = False
                order.is_holiday = False
                order.holiday_type = False
                order.holiday_multiplier = 1.0
                order.is_after_hours = False
                order.appointment_hour = 0
    
    def _check_holiday(self, date):
        """Check if date is a holiday and return pricing information

        Returns:
            dict: {
                'is_holiday': Boolean,
                'holiday_type': Selection value or False,
                'multiplier': Float (1.0 if not a pricing holiday),
                'holiday_name': String or False
            }
        """
        result = {
            'is_holiday': False,
            'holiday_type': False,
            'multiplier': 1.0,
            'holiday_name': False
        }

        try:
            # Check if resource.calendar.leaves model is available
            if 'resource.calendar.leaves' not in self.env:
                return result

            # Search for holidays on this date
            # Priority: province-specific holidays first, then national holidays
            holidays = self.env['resource.calendar.leaves'].search([
                ('date_from', '<=', date),
                ('date_to', '>=', date),
                ('resource_id', '=', False),  # Not employee-specific
                ('calendar_id', '=', False),  # Company-wide holidays
                ('is_pricing_holiday', '=', True),  # Only pricing holidays
            ], order='price_multiplier desc')  # Highest multiplier first (TET > National)

            # If province filtering is implemented, add province check here
            # For now, use first matching holiday (highest multiplier)
            if holidays:
                holiday = holidays[0]
                result.update({
                    'is_holiday': True,
                    'holiday_type': holiday.holiday_type,
                    'multiplier': holiday.price_multiplier or 1.0,
                    'holiday_name': holiday.name
                })
        except Exception as e:
            # If any error occurs, return default (no holiday)
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Holiday check failed: {e}")

        return result
    
    @api.depends('order_line', 'order_line.product_uom_qty')
    def _compute_service_units(self):
        """Compute total service units from order lines"""
        for order in self:
            total_units = sum(line.product_uom_qty for line in order.order_line)
            order.service_units = int(total_units)
    
    @api.depends('partner_id', 'fso_id')  
    def _compute_service_city(self):
        """Compute service city for location-based pricing"""
        for order in self:
            if order.fso_id:
                # Use partner city as service city (FSO patient location)
                order.service_city = order.partner_id.city or ''
            elif order.partner_id:
                order.service_city = order.partner_id.city or ''
            else:
                order.service_city = ''
    
    def action_recalculate_advanced_prices(self):
        """Recalculate prices using advanced pricing engine"""
        self.ensure_one()

        # Ensure fso_id is populated (for legacy quotes created before this fix)
        if not self.fso_id:
            self._populate_fso_id()

        if not self.use_advanced_pricing:
            # Show message if advanced pricing is not enabled
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Advanced pricing is not enabled for this quote.',
                    'type': 'warning',
                }
            }
        
        # Debug information
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info(f"=== PRICING DEBUG for {self.name} ===")
        _logger.info(f"FSO ID: {self.fso_id} (exists: {bool(self.fso_id)})")
        _logger.info(f"FSO Name: {self.fso_id.name if self.fso_id else 'None'}")
        
        # Debug FSO fields directly
        if self.fso_id:
            _logger.info(f"FSO scheduled_datetime: {self.fso_id.scheduled_datetime}")
            _logger.info(f"FSO scheduled_start_time: {getattr(self.fso_id, 'scheduled_start_time', 'Not found')}")
            _logger.info(f"FSO appointment_time: {getattr(self.fso_id, 'appointment_time', 'Not found')}")
        
        _logger.info(f"Sale Order fso_appointment_time: {self.fso_appointment_time} (timezone: {self.fso_appointment_time.tzinfo if self.fso_appointment_time else 'None'})")
        _logger.info(f"Company Timezone: {self.company_id.partner_id.tz or 'UTC'}")
        _logger.info(f"Is After Hours: {self.is_after_hours}")
        _logger.info(f"Appointment Hour: {self.appointment_hour}")
        _logger.info(f"Use Advanced Pricing: {self.use_advanced_pricing}")
        _logger.info(f"Pricelist: {self.pricelist_id.name} (ID: {self.pricelist_id.id})")
        _logger.info(f"Pricelist has advanced pricing: {self.pricelist_id.use_advanced_pricing}")
        
        # Force recompute FSO fields (skip problematic ones for now)
        _logger.info("=== Recomputing FSO fields ===")
        try:
            self._populate_fso_id()
            self._compute_fso_fields()
            self._compute_time_factors()
            _logger.info(f"After recompute - FSO ID: {self.fso_id}, Is After Hours: {self.is_after_hours}, Hour: {self.appointment_hour}")
        except Exception as e:
            _logger.error(f"Error during FSO field computation: {e}")
            _logger.info("Using existing FSO field values")
        
        # Force recompute advanced pricing flag
        self._compute_use_advanced_pricing()
        
        if not self.use_advanced_pricing:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Please enable "Use Advanced Pricing Engine" on pricelist: {self.pricelist_id.name}. Go to Sales → Pricelists → {self.pricelist_id.name}',
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        for line in self.order_line:
            _logger.info(f"Recalculating price for line: {line.product_id.name}")
            _logger.info(f"  Product ID: {line.product_id.id}")
            _logger.info(f"  Quantity: {line.product_uom_qty}")
            old_price = line.price_unit
            line._compute_advanced_price()
            _logger.info(f"  Price changed from {old_price} to {line.price_unit}")
        
        _logger.info("=== END PRICING DEBUG ===")
        
        # Generate user-friendly pricing rule notes
        self._compute_pricing_breakdown_html()
        
        # Force UI refresh to show updated prices immediately
        self.env.cr.commit()  # Commit changes to database
        
        # Return to the correct form view (FSO custom form if FSO order, regular form otherwise)
        if self.fso_id:
            # Return to healthcare custom quote form for FSO orders (as popup modal)
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.id,
                'view_mode': 'form',
                'view_id': self.env.ref('health_fieldservice.view_healthcare_quote_form_custom').id,
                'target': 'new',  # Open as popup modal
                'context': {
                    'healthcare_context': True,
                    'fso_id': self.fso_id.id,
                    'show_notification': True,
                    'notification_message': 'Prices recalculated successfully!',
                    'notification_type': 'success'
                }
            }
        else:
            # Return to standard sale order form for regular orders
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {
                    'show_notification': True,
                    'notification_message': 'Prices recalculated successfully!',
                    'notification_type': 'success'
                }
            }
    
    def action_post_service_recalc(self):
        """Recalculate pricing with post-service procedure counts and handle delta.
        
        Called automatically before final invoice creation. Compares the new total
        against pre_service_amount (set at advance payment). If delta > 0, creates
        a supplementary invoice. If delta < 0, creates a credit note.
        """
        self.ensure_one()
        
        if not self.fso_id:
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': 'No Booking', 'message': 'No booking linked to this quote.',
                               'type': 'warning', 'sticky': False}}
        
        # Store current total before recalc (if pre_service_amount not yet set)
        original_total = self.pre_service_amount or self.amount_total
        
        # Force recompute FSO fields
        self._populate_fso_id()
        if hasattr(self, '_compute_fso_fields'):
            self._compute_fso_fields()
        if hasattr(self, '_compute_use_advanced_pricing'):
            self._compute_use_advanced_pricing()
        
        # Recalculate prices with current FSO data (including updated procedure counts)
        for line in self.order_line:
            if line.product_id:
                line._compute_advanced_price()
        
        # Update pricing breakdown
        self._compute_pricing_breakdown_html()
        
        new_total = self.amount_total
        delta = new_total - original_total
        
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info('Post-service recalc: original=%.2f, new=%.2f, delta=%.2f', original_total, new_total, delta)
        
        if abs(delta) < 0.01:
            # No difference — just return notification
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': 'Pricing Up-to-Date',
                               'message': f'No change in pricing. Total remains {new_total:,.0f} đ.',
                               'type': 'info', 'sticky': False}}
        
        if delta > 0 and self.pre_service_amount > 0:
            # Client owes more — create supplementary invoice
            try:
                supp_invoice = self._create_supplementary_invoice(delta)
                if supp_invoice:
                    return {'type': 'ir.actions.client', 'tag': 'display_notification',
                            'params': {'title': 'Supplementary Invoice Created',
                                       'message': f'Post-service adjustment: +{delta:,.0f} đ. Supplementary invoice {supp_invoice.name} created.',
                                       'type': 'warning', 'sticky': True}}
            except Exception as e:
                _logger.warning('Failed to create supplementary invoice: %s', e)
        
        elif delta < 0 and self.pre_service_amount > 0:
            # Overpayment — create credit note
            try:
                credit_note = self._create_credit_note(abs(delta))
                if credit_note:
                    return {'type': 'ir.actions.client', 'tag': 'display_notification',
                            'params': {'title': 'Credit Note Created',
                                       'message': f'Post-service adjustment: {delta:,.0f} đ. Credit note {credit_note.name} created.',
                                       'type': 'info', 'sticky': True}}
            except Exception as e:
                _logger.warning('Failed to create credit note: %s', e)
        
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Pricing Recalculated',
                           'message': f'New total: {new_total:,.0f} đ (was {original_total:,.0f} đ, delta: {delta:+,.0f} đ)',
                           'type': 'success', 'sticky': False}}
    
    def _create_supplementary_invoice(self, delta_amount):
        """Create a supplementary invoice for the post-service excess amount"""
        self.ensure_one()
        fso = self.fso_id
        
        # Build description of what changed
        changes = []
        if self.injection_count > 1:
            changes.append(f'{self.injection_count - 1} extra injection(s)')
        if self.medication_count > 1:
            changes.append(f'{self.medication_count - 1} extra medication(s)')
        if self.wound_count > 1:
            changes.append(f'{self.wound_count - 1} extra wound treatment(s)')
        if self.iv_fluid_count > 0:
            changes.append(f'{self.iv_fluid_count} IV fluid bag(s)')
        
        description = ', '.join(changes) if changes else 'Post-service adjustment'
        
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': f'Supplementary: {fso.name}',
            'ref': f'{fso.name} - Post-Service Adjustment',
            'invoice_line_ids': [(0, 0, {
                'name': f'Post-Service Adjustment ({description})',
                'quantity': 1,
                'price_unit': delta_amount,
            })],
        }
        
        # Link to FSO if field exists
        if 'fieldservice_order_id' in self.env['account.move']._fields:
            invoice_vals['fieldservice_order_id'] = fso.id
        
        invoice = self.env['account.move'].create(invoice_vals)
        return invoice
    
    def _create_credit_note(self, credit_amount):
        """Create a credit note for post-service overpayment"""
        self.ensure_one()
        fso = self.fso_id
        
        invoice_vals = {
            'move_type': 'out_refund',
            'partner_id': self.partner_id.id,
            'invoice_origin': f'Credit: {fso.name}',
            'ref': f'{fso.name} - Post-Service Credit',
            'invoice_line_ids': [(0, 0, {
                'name': 'Post-Service Credit (service cost less than prepaid amount)',
                'quantity': 1,
                'price_unit': credit_amount,
            })],
        }
        
        if 'fieldservice_order_id' in self.env['account.move']._fields:
            invoice_vals['fieldservice_order_id'] = fso.id
        
        credit = self.env['account.move'].create(invoice_vals)
        return credit

    # Inline SVG glyphs for the pricing breakdown (modern SVG icons, not emoji).
    # Self-contained so they render in the backend form and any portal/report
    # without depending on backend CSS; inherit text color via currentColor.
    _FACTOR_ICON_PATHS = {
        'home': '<path d="M3 11l9-7 9 7"/><path d="M5 10v9h14v-9"/>',
        'clinic': '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M12 8v8M8 12h8"/>',
        'pin': '<path d="M12 21s7-6.5 7-12a7 7 0 1 0-14 0c0 5.5 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
        'moon': '<path d="M21 12.8A8 8 0 1 1 11.2 3 6.5 6.5 0 0 0 21 12.8z"/>',
        'calendar': '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 9h17M8 3v4M16 3v4"/>',
        'flag': '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
        'clipboard': '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4V3h6v1M9 9h6M9 13h6M9 17h4"/>',
    }

    def _factor_icon(self, name, size=13):
        """Return a self-contained inline SVG glyph (currentColor) for the breakdown."""
        paths = self._FACTOR_ICON_PATHS.get(name, '')
        return (
            f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px;">'
            f'{paths}</svg>'
        )

    @api.depends('order_line', 'order_line.product_id', 'order_line.product_uom_qty',
                 'order_line.price_unit', 'order_line.discount', 'use_advanced_pricing',
                 'fso_distance', 'is_weekend', 'is_after_hours', 'is_holiday',
                 'fso_service_location', 'injection_count', 'medication_count',
                 'wound_count', 'iv_fluid_count')
    def _compute_pricing_breakdown_html(self):
        """Reactively rebuild the breakdown so it refreshes on catalog adds and
        line/qty/discount edits (no manual Recalc click needed)."""
        for record in self:
            try:
                record.pricing_breakdown_html = record._build_pricing_breakdown_html()
            except Exception:  # never let a display build break the form/onchange
                record.pricing_breakdown_html = False

    def _build_pricing_breakdown_html(self):
        """Build HTML pricing breakdown showing applied rules and calculations.
        Returns the HTML string (or False) — assignment is done by the compute."""
        self.ensure_one()

        if not self.use_advanced_pricing or not self.order_line:
            return False

        def fmt(amount):
            """Format number as VND with thousand separators"""
            return f"{amount:,.0f}"

        # Get the engine to find which rules matched
        engine = None
        if self.pricelist_id.advanced_engine_id:
            engine = self.pricelist_id.advanced_engine_id
        else:
            config = self.env['advanced.pricing.config'].get_config()
            if config.default_engine_id:
                engine = config.default_engine_id

        html = []
        html.append('<div style="margin-top:12px;">')
        html.append(f'<h4 style="margin-bottom:8px;">{self._factor_icon("clipboard", 16)} Pricing Breakdown</h4>')

        # Context factors summary
        factors = []
        if self.fso_id:
            fso = self.fso_id
            loc = self.fso_service_location
            if loc == 'home':
                factors.append(f'{self._factor_icon("home")} Home Visit')
            elif loc == 'clinic':
                factors.append(f'{self._factor_icon("clinic")} Clinic Visit')
            if self.fso_distance and self.fso_distance > 0:
                factors.append(f'{self._factor_icon("pin")} Distance: {self.fso_distance:.1f} km')
            if self.is_after_hours:
                factors.append(f'{self._factor_icon("moon")} After Hours')
            if self.is_weekend:
                factors.append(f'{self._factor_icon("calendar")} Weekend')
            if self.is_holiday:
                factors.append(f'{self._factor_icon("flag")} Holiday ({self.holiday_type or "Public"})')

        if factors:
            html.append('<div style="background:#f0f4ff;padding:8px 12px;border-radius:6px;margin-bottom:10px;font-size:13px;">')
            html.append(' &nbsp;|&nbsp; '.join(factors))
            html.append('</div>')

        # Table header
        html.append('<table style="width:100%;border-collapse:collapse;font-size:13px;">')
        html.append('<thead><tr style="background:#f8f9fa;">')
        html.append('<th style="padding:6px 8px;text-align:left;border-bottom:2px solid #dee2e6;">Product</th>')
        html.append('<th style="padding:6px 8px;text-align:right;border-bottom:2px solid #dee2e6;">Base Price</th>')
        html.append('<th style="padding:6px 8px;text-align:left;border-bottom:2px solid #dee2e6;">Rules Applied</th>')
        html.append('<th style="padding:6px 8px;text-align:right;border-bottom:2px solid #dee2e6;">Final Price</th>')
        html.append('<th style="padding:6px 8px;text-align:right;border-bottom:2px solid #dee2e6;">Qty</th>')
        html.append('<th style="padding:6px 8px;text-align:right;border-bottom:2px solid #dee2e6;">Subtotal</th>')
        html.append('</tr></thead>')
        html.append('<tbody>')

        grand_total = 0
        for line in self.order_line:
            if not line.product_id:
                continue

            base_price = line.base_price or line.product_id.list_price or 0
            final_price = line.price_unit or 0
            qty = line.product_uom_qty
            subtotal = final_price * qty
            grand_total += subtotal
            diff = final_price - base_price

            # Find matching rules for this product
            rules_text = []
            if engine and engine.rule_ids:
                # Build context for evaluation
                ctx = {
                    'distance': self.fso_distance or 0,
                    'appointment_hour': self.appointment_hour or 0,
                    'is_weekend': self.is_weekend,
                    'is_holiday': self.is_holiday,
                    'holiday_type': self.holiday_type,
                    'is_after_hours': self.is_after_hours,
                    'service_type': self.fso_service_type,
                    'service_location': self.fso_service_location,
                    'urgency': self.fso_urgency,
                    'priority': self.fso_priority,
                    'region': '',
                    # Post-service procedure counts (from quote itself)
                    'injection_count': self.injection_count or 0,
                    'medication_count': self.medication_count or 0,
                    'wound_count': self.wound_count or 0,
                    'iv_fluid_count': self.iv_fluid_count or 0,
                }
                # Determine region from product code
                code = line.product_id.default_code or ''
                if '_tphcm' in code:
                    ctx['region'] = 'HCMC'
                elif '_hanoi' in code:
                    ctx['region'] = 'Hanoi'

                approved_rules = engine.rule_ids.filtered(
                    lambda r: r.active and r.approval_status == 'approved'
                )
                for rule in approved_rules.sorted('sequence'):
                    try:
                        if rule.evaluate_condition(line.product_id.id, self.partner_id.id, qty, ctx):
                            # Format the rule description
                            action_desc = ''
                            if rule.action_type == 'add':
                                action_desc = f'+{fmt(rule.action_value)} đ'
                            elif rule.action_type == 'fixed':
                                action_desc = f'→ {fmt(rule.action_value)} đ'
                            elif rule.action_type == 'multiply':
                                action_desc = f'×{rule.action_value}'
                            elif rule.action_type == 'discount':
                                action_desc = f'-{rule.action_value*100:.0f}%'
                            elif rule.action_type == 'per_unit':
                                action_desc = f'+{fmt(rule.action_value)} đ/unit'
                            elif rule.action_type == 'percentage':
                                action_desc = f'+{rule.action_value}%'

                            # Short trigger name from rule name
                            short_name = rule.name
                            # Strip region prefix like "HCMC - Product Name - "
                            parts = short_name.split(' - ')
                            if len(parts) >= 3:
                                short_name = parts[-1]  # Last segment is the trigger
                            elif len(parts) == 2:
                                short_name = parts[-1]

                            rules_text.append(f'{short_name} <b>{action_desc}</b>')
                    except Exception:
                        pass

            # Row color based on adjustment
            row_style = ''
            if abs(diff) > 0.01:
                row_style = ' style="background:#fff8e1;"' if diff > 0 else ' style="background:#e8f5e9;"'

            html.append(f'<tr{row_style}>')
            html.append(f'<td style="padding:6px 8px;border-bottom:1px solid #eee;">{line.product_id.default_code or ""}<br/><small style="color:#666">{line.product_id.name}</small></td>')
            html.append(f'<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #eee;">{fmt(base_price)} đ</td>')

            if rules_text:
                rules_html = '<br/>'.join(rules_text)
                html.append(f'<td style="padding:6px 8px;border-bottom:1px solid #eee;font-size:12px;">{rules_html}</td>')
            elif abs(diff) < 0.01:
                html.append(f'<td style="padding:6px 8px;border-bottom:1px solid #eee;color:#999;">No adjustments</td>')
            else:
                html.append(f'<td style="padding:6px 8px;border-bottom:1px solid #eee;">{fmt(diff):>+} đ adjustment</td>')

            html.append(f'<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #eee;font-weight:bold;">{fmt(final_price)} đ</td>')
            html.append(f'<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #eee;">{qty:.0f}</td>')
            html.append(f'<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #eee;font-weight:bold;">{fmt(subtotal)} đ</td>')
            html.append('</tr>')

        html.append('</tbody>')
        html.append(f'<tfoot><tr style="background:#f8f9fa;font-weight:bold;">')
        html.append(f'<td colspan="5" style="padding:6px 8px;text-align:right;border-top:2px solid #dee2e6;">Total</td>')
        html.append(f'<td style="padding:6px 8px;text-align:right;border-top:2px solid #dee2e6;">{fmt(grand_total)} đ</td>')
        html.append('</tr></tfoot>')
        html.append('</table>')
        html.append('</div>')

        return ''.join(html)
    
    def _get_action_add_from_catalog_extra_context(self):
        """Override to ensure catalog returns to Healthcare Quote form for FSO orders"""
        context = super()._get_action_add_from_catalog_extra_context()
        
        # For FSO quotes, ensure we return to Healthcare Quote form, not FSO form
        if self.fso_id:
            context.update({
                'active_model': 'sale.order',
                'active_id': self.id,
                'active_ids': [self.id],
                'return_to_form': True,
                'form_view_ref': 'health_fieldservice.view_healthcare_quote_form_custom',
                'healthcare_context': True,
                'catalog_source': 'healthcare_quote',
                # Use our custom healthcare catalog view
                'catalog_view_type': 'healthcare_product_catalog'
            })
        
        return context

    def _get_product_catalog_domain(self):
        """Override to filter catalog products by booking's catchment province.

        Products have region suffixes in their default_code (e.g. _hanoi, _tphcm).
        When opened from a booking with a catchment province, only show products
        matching that province's region.
        """
        domain = super()._get_product_catalog_domain()

        # Find the FSO booking linked to this sale order
        fso = self.fso_id
        if not fso and self.id:
            # Fallback: reverse search if fso_id computed field isn't stored yet
            fso = self.env['health.fieldservice.order'].search(
                [('sale_order_id', '=', self.id)], limit=1
            )

        if fso and fso.patient_catchment_province_id:
            province = fso.patient_catchment_province_id
            # Map province name to product default_code suffix
            province_to_suffix = {
                'Hanoi': 'hanoi',
                'Ho Chi Minh City': 'tphcm',
            }
            suffix = province_to_suffix.get(province.name)
            if suffix:
                domain = domain & Domain('default_code', '=like', f'%_{suffix}')

        return domain

    def action_add_from_catalog(self):
        """Add context marker for FSO quotes to enable auto-redirect after catalog"""
        # For FSO quotes, add healthcare context to standard catalog
        if self.fso_id:
            action = super().action_add_from_catalog()
            
            # Add healthcare context to make our patch work
            if isinstance(action, dict):
                action.setdefault('context', {}).update({
                    'catalog_return_to_quote': True,
                    'quote_order_id': self.id,
                    'healthcare_context': True,
                    'catalog_source': 'healthcare_quote',
                })
            
            return action
        
        # For regular quotes, use standard behavior
        return super().action_add_from_catalog()

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    base_price = fields.Float('Base Price', readonly=True)
    price_calculation_log = fields.Text('Price Calculation Log')
    applied_rules = fields.Text('Applied Rules')
    
    @api.depends('product_id', 'product_uom_qty', 'order_id.fso_id', 'order_id.fso_distance',
                 'order_id.is_weekend', 'order_id.is_holiday', 'order_id.is_after_hours',
                 'order_id.appointment_hour', 'order_id.fso_service_type',
                 'order_id.fso_service_location', 'order_id.fso_urgency',
                 'order_id.fso_priority', 'order_id.service_units')
    def _compute_advanced_price(self):
        """Compute price using advanced pricing engine with FSO context"""
        for line in self:
            if not line.order_id.use_advanced_pricing:
                continue
            
            if not line.order_id.pricelist_id.advanced_engine_id:
                # Fallback to default engine from pricing configuration
                config = self.env['advanced.pricing.config'].get_config()
                if not config.default_engine_id:
                    continue
                engine = config.default_engine_id
            else:
                engine = line.order_id.pricelist_id.advanced_engine_id
            
            # Build context data with FSO fields for pricing rules
            context_data = {
                'order_id': line.order_id.id,
                'partner_id': line.order_id.partner_id.id,
                'date_order': line.order_id.date_order,
                'product_id': line.product_id.id,
                'quantity': line.product_uom_qty,
            }
            
            # Add FSO-based context for pricing rules
            if line.order_id.fso_id:
                fso_context = {
                    'fso_id': line.order_id.fso_id.id,
                    'distance': line.order_id.fso_distance or 0,
                    'appointment_hour': line.order_id.appointment_hour or 0,
                    'is_weekend': line.order_id.is_weekend,
                    'is_holiday': line.order_id.is_holiday,
                    'holiday_type': line.order_id.holiday_type,
                    'holiday_multiplier': line.order_id.holiday_multiplier,
                    'is_after_hours': line.order_id.is_after_hours,
                    'service_type': line.order_id.fso_service_type,
                    'service_location': line.order_id.fso_service_location,
                    'urgency': line.order_id.fso_urgency,
                    'priority': line.order_id.fso_priority,
                    'service_units': line.order_id.service_units,
                    'service_city': line.order_id.service_city,
                    # Post-service procedure counts (from quote itself)
                    'injection_count': line.order_id.injection_count or 0,
                    'medication_count': line.order_id.medication_count or 0,
                    'wound_count': line.order_id.wound_count or 0,
                    'iv_fluid_count': line.order_id.iv_fluid_count or 0,
                }
                # Determine region from product code suffix
                code = line.product_id.default_code or ''
                if '_tphcm' in code:
                    fso_context['region'] = 'HCMC'
                elif '_hanoi' in code:
                    fso_context['region'] = 'Hanoi'
                else:
                    fso_context['region'] = ''
                context_data.update(fso_context)
            
            # Calculate price using pricing engine
            try:
                # Store base price before calculation
                line.base_price = line.product_id.list_price or 0
                
                # Calculate price and get detailed results if available
                if hasattr(engine, 'calculate_price_with_details'):
                    result = engine.calculate_price_with_details(
                        line.product_id.id,
                        line.product_uom_qty,
                        line.order_id.partner_id.id,
                        context_data
                    )
                    line.price_unit = result.get('final_price', line.base_price)
                    line.applied_rules = result.get('applied_rules', '')
                    line.price_calculation_log = result.get('calculation_log', '')
                else:
                    # Fallback to basic calculation
                    price = engine.calculate_price(
                        line.product_id.id,
                        line.product_uom_qty,
                        line.order_id.partner_id.id,
                        context_data
                    )
                    line.price_unit = price
                    
            except Exception as e:
                # Log error but don't break the order
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Advanced pricing calculation failed for line {line.id}: {e}")
                # Fall back to standard pricing
                line.base_price = line.product_id.list_price or 0
                line.price_unit = line.base_price
