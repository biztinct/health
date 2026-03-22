# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.fields import Domain

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    # Get FSO that created this quote (reverse relationship)
    fso_id = fields.Many2one('health.fieldservice.order',
                            string='Booking',
                            compute='_compute_fso_id',
                            store=True,
                            help='Booking that created this quote')
    
    # Pricing configuration
    use_advanced_pricing = fields.Boolean('Use Advanced Pricing', 
                                         compute='_compute_use_advanced_pricing')
    advanced_pricing_details = fields.Text('Pricing Calculation Details')
    
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
    
    def _compute_fso_id(self):
        """Find FSO that created this quote using reverse relationship"""
        for order in self:
            fso = self.env['health.fieldservice.order'].search([('sale_order_id', '=', order.id)], limit=1)
            order.fso_id = fso.id if fso else False
    
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
            self._compute_fso_id()
            self._compute_time_factors()  # Skip _compute_fso_fields temporarily
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
        self._update_pricing_notes()
        
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
    
    def _update_pricing_notes(self):
        """Update sale order note with user-friendly pricing rule explanations"""
        self.ensure_one()
        
        if not self.use_advanced_pricing or not self.order_line:
            return
        
        # Start building the note with HTML formatting
        note_parts = []
        note_parts.append("<strong>=== HEALTHCARE PRICING BREAKDOWN ===</strong><br/><br/>")
        note_parts.append("<strong>PRICING SUMMARY:</strong><br/><br/>")
        
        # Process each order line
        for line_idx, line in enumerate(self.order_line, 1):
            if not line.product_id:
                continue
                
            base_price = line.base_price or line.product_id.list_price or 0
            final_price = line.price_unit or 0
            line_total_final = final_price * line.product_uom_qty
            
            note_parts.append(f"<strong>ITEM {line_idx}: {line.product_id.name}</strong><br/>")
            note_parts.append(f"• Base Price: ${base_price:,.2f} per unit<br/>")
            note_parts.append(f"• Quantity: {line.product_uom_qty}<br/>")
            
            # Calculate adjustment and show reason if there's a difference
            price_difference = final_price - base_price
            if abs(price_difference) > 0.01:  # Only show if there's a meaningful difference
                adjustment_total = price_difference * line.product_uom_qty
                
                # Determine pricing factor reason
                pricing_reason = ""
                if hasattr(self, 'is_after_hours') and self.is_after_hours:
                    pricing_reason = "After hours service"
                elif hasattr(self, 'is_weekend') and self.is_weekend:
                    pricing_reason = "Weekend service"
                elif hasattr(self, 'is_holiday') and self.is_holiday:
                    pricing_reason = "Holiday service"
                elif hasattr(self, 'fso_urgency') and self.fso_urgency in ['urgent', 'emergency']:
                    urgency_label = dict(self._fields['fso_urgency'].selection).get(self.fso_urgency, self.fso_urgency)
                    pricing_reason = f"{urgency_label.title()} priority"
                elif hasattr(line, 'applied_rules') and line.applied_rules:
                    pricing_reason = line.applied_rules
                else:
                    pricing_reason = "Special pricing applied"
                
                note_parts.append(f"• Adjustment Total: ${adjustment_total:+,.2f} ({pricing_reason})<br/>")
            
            note_parts.append(f"• Final Total: ${line_total_final:,.2f}<br/><br/>")
        
        # Update the note field with HTML content
        self.note = ''.join(note_parts)
    
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
                 'order_id.is_weekend', 'order_id.is_holiday', 'order_id.service_units')
    def _compute_advanced_price(self):
        """Compute price using advanced pricing engine with FSO context"""
        for line in self:
            if not line.order_id.use_advanced_pricing:
                continue
            
            if not line.order_id.pricelist_id.advanced_engine_id:
                continue
            
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
                }
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