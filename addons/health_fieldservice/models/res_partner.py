from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    """Extend res.partner with assignment-related patient data"""
    _inherit = 'res.partner'

    last_visit_date = fields.Datetime('Last Visit', compute='_compute_last_visit_date')

    booking_ids = fields.One2many(
        'health.fieldservice.order', 'patient_id',
        string='Bookings',
    )

    # Assignment preferences for patients
    preferred_staff_id = fields.Many2one(
        'hr.employee',
        string='Preferred Healthcare Staff',
        domain=[('is_healthcare_staff', '=', True)],
        help='client\'s preferred healthcare professional'
    )
    
    assignment_notes = fields.Text(
        'Assignment Notes',
        help='Special notes for staff assignment (accessibility, language preferences, etc.)'
    )
    
    # Assignment history
    total_assignments = fields.Integer(
        'Total Assignments',
        compute='_compute_assignment_stats'
    )
    
    last_assignment_date = fields.Datetime(
        'Last Assignment Date',
        compute='_compute_assignment_stats'
    )

    has_pending_collection = fields.Boolean(
        compute='_compute_collection_payment_flags', store=False,
    )
    has_outstanding_invoice = fields.Boolean(
        compute='_compute_collection_payment_flags', store=False,
    )

    def _compute_collection_payment_flags(self):
        for partner in self:
            if partner.is_patient:
                partner.has_pending_collection = bool(self.env['health.payment.transaction'].search_count([
                    ('patient_id', '=', partner.id),
                    ('status', '=', 'pending_delivery'),
                ], limit=1))
                partner.has_outstanding_invoice = bool(self.env['account.move'].search_count([
                    ('partner_id', '=', partner.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ('not_paid', 'partial')),
                ], limit=1))
            else:
                partner.has_pending_collection = False
                partner.has_outstanding_invoice = False

    # Client timeline
    timeline_html = fields.Html(
        'Client Timeline',
        compute='_compute_timeline_html'
    )

    def _compute_last_visit_date(self):
        for partner in self:
            if partner.is_patient:
                last_fso = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id),
                    ('state', 'in', ['completed', 'completed_pending_invoice']),
                    ('actual_end_datetime', '!=', False),
                ], order='actual_end_datetime desc', limit=1)
                partner.last_visit_date = last_fso.actual_end_datetime if last_fso else False
            else:
                partner.last_visit_date = False

    @api.depends('name')
    def _compute_timeline_html(self):
        """Generate HTML timeline of upcoming + recent completed bookings"""
        for partner in self:
            if hasattr(partner, 'is_patient') and partner.is_patient:
                timeline_events = []

                upcoming_fsos = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id),
                    ('state', 'in', ['draft', 'assigned', 'confirmed', 'in_progress']),
                    ('scheduled_datetime', '!=', False)
                ], order='scheduled_datetime ASC', limit=10)

                for fso in upcoming_fsos:
                    date_str = fso.scheduled_datetime.strftime('%d %b %Y, %H:%M') if fso.scheduled_datetime else 'TBD'
                    state_display = dict(fso._fields['state'].selection).get(fso.state, fso.state)
                    staff = fso.lead_staff_id.name if fso.lead_staff_id else 'Unassigned'
                    timeline_events.append({
                        'type': 'upcoming',
                        'date': date_str,
                        'title': fso.name,
                        'staff': staff,
                        'state': state_display,
                        'service': dict(fso._fields['service_type'].selection).get(fso.service_type, fso.service_type or ''),
                    })

                completed_fsos = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id),
                    ('state', 'in', ['completed', 'completed_pending_invoice']),
                ], order='actual_end_datetime DESC, scheduled_datetime DESC', limit=8)

                for fso in completed_fsos:
                    date_str = (fso.actual_end_datetime or fso.scheduled_datetime or fso.create_date).strftime('%d %b %Y')
                    timeline_events.append({
                        'type': 'completed',
                        'date': date_str,
                        'title': fso.name,
                        'staff': fso.lead_staff_id.name if fso.lead_staff_id else '',
                        'state': 'Completed',
                        'service': dict(fso._fields['service_type'].selection).get(fso.service_type, fso.service_type or ''),
                    })

                if timeline_events:
                    html = '<ul>'
                    for event in timeline_events:
                        icon = '<i class="fa fa-calendar text-primary"></i>' if event['type'] == 'upcoming' else '<i class="fa fa-check-circle text-success"></i>'
                        html += f'<li>{icon} <strong>{event["title"]}</strong> — {event["service"]}<br/>'
                        html += f'<small>{event["date"]} &middot; {event["staff"]} &middot; {event["state"]}</small></li>'
                    html += '</ul>'
                    partner.timeline_html = html
                else:
                    partner.timeline_html = '<p class="text-muted text-center p-4">No booking history yet</p>'
            else:
                partner.timeline_html = False

    @api.depends('name')
    def _compute_assignment_stats(self):
        """Calculate assignment statistics for patients"""
        for partner in self:
            if hasattr(partner, 'is_patient') and partner.is_patient:
                # Count assignments through unified FSO system
                fso_records = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id)
                ])
                
                assignments = self.env['health.staff.assignment'].search([
                    ('fso_id', 'in', fso_records.ids)
                ])
                
                partner.total_assignments = len(assignments)
                partner.last_assignment_date = max(
                    assignments.mapped('assignment_date')
                ) if assignments else False
            else:
                partner.total_assignments = 0
                partner.last_assignment_date = False
    
    @api.model
    def get_client_profile_data(self, partner_id):
        """Single RPC returning all client profile data for the OWL component."""
        partner = self.browse(partner_id)
        if not partner.exists():
            return {}

        # Basic info
        initials = ''
        name_parts = (partner.name or '').split()
        if name_parts:
            initials = ''.join(p[0] for p in name_parts if p)[:2].upper()

        gender_map = {'male': 'M', 'female': 'F', 'other': 'O'}
        age_gender = ''
        if partner.age:
            age_gender = f"{partner.age} years old"
            if partner.gender and partner.gender in gender_map:
                age_gender += f" ({gender_map[partner.gender]})"

        profile = {
            'id': partner.id,
            'name': partner.name or '',
            'initials': initials,
            'patient_code': partner.patient_code or '',
            'phone': partner.mobile or partner.phone or '',
            'email': partner.email or '',
            'address': partner.vietnamese_address if hasattr(partner, 'vietnamese_address') and partner.vietnamese_address else (partner.contact_address_complete or ''),
            'age_gender': age_gender,
            'patient_status': partner.patient_status or 'active',
            'is_vip': bool(partner.patient_category_id and 'vip' in (partner.patient_category_id.name or '').lower()),
            'is_referrer': partner.is_referrer,
            'category_name': partner.patient_category_id.name if partner.patient_category_id else '',
        }

        # Stats
        FSO = self.env['health.fieldservice.order']
        fso_domain = [('patient_id', '=', partner.id)]
        total_visits = FSO.search_count(fso_domain)

        Package = self.env['health.service.package']
        active_packages = Package.search_count([('patient_id', '=', partner.id), ('state', '=', 'active')])

        # Outstanding = unpaid invoices for this partner
        outstanding = 0.0
        total_spent = 0.0
        try:
            invoices = self.env['account.move'].search([
                ('partner_id', '=', partner.id),
                ('move_type', '=', 'out_invoice'),
            ])
            for inv in invoices:
                if inv.payment_state in ('paid', 'in_payment'):
                    total_spent += inv.amount_total
                elif inv.state == 'posted':
                    outstanding += inv.amount_residual
                    total_spent += (inv.amount_total - inv.amount_residual)
        except Exception:
            pass

        referral_count = 0
        if partner.is_referrer:
            referral_count = self.search_count([('primary_referrer_id', '=', partner.id)])

        stats = {
            'total_visits': total_visits,
            'active_packages': active_packages,
            'total_spent': total_spent,
            'outstanding': outstanding,
            'satisfaction': 0,
            'referrals': referral_count,
        }

        # Recent bookings (last 10)
        bookings = []
        fsos = FSO.search(fso_domain, order='scheduled_datetime desc', limit=10)
        for f in fsos:
            dt = f.scheduled_datetime
            bookings.append({
                'id': f.id,
                'name': f.name or '',
                'date_label': dt.strftime('%b %d') if dt else '',
                'time_label': dt.strftime('%H:%M') if dt else '',
                'service_type': dict(f._fields['service_type'].selection).get(f.service_type, f.service_type or ''),
                'staff_name': f.lead_staff_id.name if f.lead_staff_id else '',
                'has_staff': f.has_staff_assigned,
                'state': f.state or 'draft',
                'state_label': dict(f._fields['state'].selection).get(f.state, f.state or ''),
            })

        # Active packages
        packages = []
        pkgs = Package.search([('patient_id', '=', partner.id), ('state', '=', 'active')], limit=5)
        for p in pkgs:
            pct = int((p.consumed_services / p.total_services * 100)) if p.total_services else 0
            packages.append({
                'id': p.id,
                'name': p.name or '',
                'total': p.total_services,
                'used': p.consumed_services,
                'remaining': p.remaining_services,
                'progress_pct': pct,
                'expiry': p.expiration_date.strftime('%b %d, %Y') if p.expiration_date else '',
                'state': p.state,
            })

        # Recent payments
        payments = []
        try:
            inv_lines = self.env['account.move'].search([
                ('partner_id', '=', partner.id),
                ('move_type', '=', 'out_invoice'),
            ], order='invoice_date desc', limit=8)
            for inv in inv_lines:
                is_paid = inv.payment_state in ('paid', 'in_payment')
                payments.append({
                    'id': inv.id,
                    'description': inv.name or '',
                    'date': inv.invoice_date.strftime('%b %d, %Y') if inv.invoice_date else '',
                    'amount': inv.amount_total,
                    'is_paid': is_paid,
                    'payment_state': inv.payment_state or 'not_paid',
                })
        except Exception:
            pass

        # Activity timeline (recent chatter messages)
        timeline = []
        try:
            messages = self.env['mail.message'].search([
                ('res_id', '=', partner.id),
                ('model', '=', 'res.partner'),
                ('message_type', 'in', ['comment', 'notification']),
            ], order='date desc', limit=10)
            for msg in messages:
                timeline.append({
                    'id': msg.id,
                    'body': msg.body or '',
                    'date': msg.date.strftime('%b %d, %H:%M') if msg.date else '',
                    'author': msg.author_id.name if msg.author_id else '',
                    'subtype': msg.subtype_id.name if msg.subtype_id else '',
                })
        except Exception:
            pass

        return {
            'profile': profile,
            'stats': stats,
            'bookings': bookings,
            'packages': packages,
            'payments': payments,
            'timeline': timeline,
            'total_bookings': FSO.search_count(fso_domain),
            'total_packages': Package.search_count([('patient_id', '=', partner.id)]),
            'total_payments': len(payments),
        }

    def get_booking_timeline_data(self):
        self.ensure_one()
        FSO = self.env['health.fieldservice.order']
        bookings_raw = FSO.search(
            [('patient_id', '=', self.id)],
            order='scheduled_datetime desc',
            limit=50,
        )

        SERVICE_ICONS = {
            'home_visit': 'fa-home',
            'clinic_visit': 'fa-hospital-o',
            'telemedicine': 'fa-video-camera',
            'emergency': 'fa-ambulance',
            'follow_up': 'fa-refresh',
        }

        bookings = []
        calendar_dots = {}
        for b in bookings_raw:
            dt = b.scheduled_datetime
            if not dt:
                continue
            date_str = dt.strftime('%Y-%m-%d')
            month_key = dt.strftime('%Y-%m')
            day_key = str(dt.day)

            bookings.append({
                'id': b.id,
                'name': b.name or '',
                'date': date_str,
                'date_display': dt.strftime('%b %d, %Y'),
                'time': dt.strftime('%I:%M %p'),
                'service_type': b.service_type or '',
                'service_label': dict(b._fields['service_type'].selection).get(b.service_type, ''),
                'service_icon': SERVICE_ICONS.get(b.service_type, 'fa-calendar'),
                'duration': b.estimated_duration or b.scheduled_duration or 0,
                'state': b.state or '',
                'state_label': dict(b._fields['state'].selection).get(b.state, ''),
                'staff_name': b.lead_staff_id.name if b.lead_staff_id else None,
                'staff_initials': (b.lead_staff_id.name or '')[:1].upper() if b.lead_staff_id else None,
            })

            calendar_dots.setdefault(month_key, {})
            calendar_dots[month_key].setdefault(day_key, [])
            calendar_dots[month_key][day_key].append(b.state or 'draft')

        return {
            'bookings': bookings,
            'calendar_dots': calendar_dots,
        }

    def action_create_fso(self):
        """Open OWL Quick Booking wizard with client pre-filled"""
        if not self.is_patient:
            raise UserError(_('Only patients can have Bookings created.'))

        return {
            'type': 'ir.actions.client',
            'tag': 'ops_quick_booking',
            'name': _('Quick Booking'),
            'target': 'current',
            'context': {
                'active_id': self.id,
                'default_patient_id': self.id,
            }
        }
    
    def action_view_fso_orders(self):
        """View all Bookings for this patient using Ops Booking List"""
        if not self.is_patient:
            raise UserError(_('Only patients can have Bookings.'))

        action = self.env['ir.actions.act_window']._for_xml_id(
            'health_fieldservice.action_ops_booking_list_native'
        )
        action['domain'] = [('patient_id', '=', self.id)]
        action['context'] = {
            'default_patient_id': self.id,
            'default_customer_id': self.id,
        }
        action['name'] = _('Bookings - %s', self.name)
        return action

    def action_open_recurring_booking(self):
        if not self.is_patient:
            raise UserError(_('Only patients can have bookings created.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'ops_recurring_booking',
            'name': _('Recurring Booking'),
            'target': 'current',
            'context': {
                'active_id': self.id,
                'default_patient_id': self.id,
            },
        }

    def action_open_quick_booking_owl(self):
        if not self.is_patient:
            raise UserError(_('Only patients can have bookings created.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'ops_quick_booking',
            'name': _('Quick Booking'),
            'target': 'current',
            'context': {
                'active_id': self.id,
                'default_patient_id': self.id,
            },
        }

    def action_collect_cash(self):
        if not self.is_patient:
            raise UserError(_('Only patients have payment transactions.'))
        transactions = self.env['health.payment.transaction'].search([
            ('patient_id', '=', self.id),
            ('status', '=', 'pending_delivery'),
        ])
        if not transactions:
            raise UserError(_('No cash pending delivery for this client.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cash Pending Delivery'),
            'res_model': 'health.payment.transaction',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('patient_id', '=', self.id), ('status', '=', 'pending_delivery')],
        }

    def action_register_client_payment(self):
        if not self.is_patient:
            raise UserError(_('Only patients have invoices.'))
        invoices = self.env['account.move'].search([
            ('partner_id', '=', self.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ])
        if not invoices:
            raise UserError(_('No outstanding invoices for this client.'))
        if len(invoices) == 1:
            return invoices.action_register_payment()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Outstanding Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [
                ('partner_id', '=', self.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('not_paid', 'partial')),
            ],
        }