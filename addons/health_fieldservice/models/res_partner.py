from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    """Extend res.partner with assignment-related patient data"""
    _inherit = 'res.partner'

    last_visit_date = fields.Datetime('Last Visit', readonly=True)

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

    # Client timeline
    timeline_html = fields.Html(
        'Client Timeline',
        compute='_compute_timeline_html'
    )

    @api.depends('name')
    def _compute_timeline_html(self):
        """Generate HTML timeline of upcoming appointments and key events"""
        for partner in self:
            if hasattr(partner, 'is_patient') and partner.is_patient:
                timeline_events = []

                # Get upcoming FSOs (scheduled bookings)
                upcoming_fsos = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id),
                    ('state', 'in', ['draft', 'assigned', 'confirmed', 'in_progress']),
                    ('scheduled_datetime', '!=', False)
                ], order='scheduled_datetime ASC', limit=10)

                for fso in upcoming_fsos:
                    date_str = fso.scheduled_datetime.strftime('%d %b %Y at %H:%M') if fso.scheduled_datetime else 'TBD'
                    status_color = 'primary' if fso.state == 'confirmed' else 'secondary'
                    # Map state to display name
                    state_display = dict(fso._fields['state'].selection).get(fso.state, fso.state)
                    timeline_events.append({
                        'type': 'appointment',
                        'date': date_str,
                        'title': f'📅 {fso.name}',
                        'description': f'Service: {fso.service_type} | Staff: {fso.lead_staff_id.name if fso.lead_staff_id else "Not assigned"} | Status: {state_display}',
                        'color': status_color
                    })

                # Get completed services (past FSOs) for recent activity
                completed_fsos = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id),
                    ('state', '=', 'completed'),
                    ('actual_end_datetime', '!=', False)
                ], order='actual_end_datetime DESC', limit=5)

                for fso in completed_fsos:
                    date_str = fso.actual_end_datetime.strftime('%d %b %Y') if fso.actual_end_datetime else 'TBD'
                    timeline_events.append({
                        'type': 'completed',
                        'date': date_str,
                        'title': f'✓ {fso.name}',
                        'description': f'Service completed: {fso.service_type}',
                        'color': 'success'
                    })

                # Generate HTML timeline
                if timeline_events:
                    html = '<div style="padding: 10px; background: #f8f9fa; border-radius: 5px;"><ul style="list-style: none; padding: 0;">'
                    for event in timeline_events:
                        icon = '📅' if event['type'] == 'appointment' else '✓'
                        color_class = f'badge-{event["color"]}'
                        html += f'''
                        <li style="margin-bottom: 15px; padding-left: 20px; border-left: 3px solid #ddd;">
                            <strong>{event['title']}</strong><br/>
                            <small style="color: #666;">{event['date']}</small><br/>
                            <small>{event['description']}</small>
                        </li>
                        '''
                    html += '</ul></div>'
                    partner.timeline_html = html
                else:
                    partner.timeline_html = '<p style="color: #999; text-align: center; padding: 20px;">No upcoming appointments scheduled</p>'
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
        total_visits = FSO.search_count(fso_domain + [('state', 'in', ['completed', 'completed_pending_invoice'])])

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

    def action_create_fso(self):
        """Open quick booking wizard (2-step: Services + Booking) with client pre-filled"""
        if not self.is_patient:
            raise UserError(_('Only patients can have Bookings created.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Booking'),
            'res_model': 'health.quick.booking.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_client_id': self.id,
            }
        }
    
    def action_view_fso_orders(self):
        """View all Bookings for this patient"""
        if not self.is_patient:
            raise UserError(_('Only patients can have Bookings.'))
        
        fso_orders = self.env['health.fieldservice.order'].search([
            ('patient_id', '=', self.id)
        ])
        
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Bookings'),
            'res_model': 'health.fieldservice.order',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('patient_id', '=', self.id)],
            'context': {
                'default_patient_id': self.id,
                'default_customer_id': self.id,
            }
        }
        
        if len(fso_orders) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = fso_orders.id
        
        return action