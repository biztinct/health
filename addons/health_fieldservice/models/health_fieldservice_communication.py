from odoo import models, fields, api, _
from datetime import datetime, timedelta


class HealthFieldServiceCommunication(models.Model):
    """
    Real-time Field Service Communication - Your highest priority requirement
    Enables real-time communication between field staff, supervisors, and patients
    """
    _name = 'health.fieldservice.communication'
    _description = 'Field Service Real-time Communication'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'subject'
    
    # Core communication fields
    fieldservice_order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        ondelete='cascade'
    )
    
    subject = fields.Char('Subject', compute='_compute_subject', store=True)
    
    message_type = fields.Selection([
        ('status_update', 'Status Update'),
        ('urgent_request', 'Urgent Request'),
        ('clinical_question', 'Clinical Question'),
        ('equipment_issue', 'Equipment Issue'),
        ('patient_concern', 'Patient Concern'),
        ('navigation_help', 'Navigation Assistance'),
        ('schedule_change', 'Schedule Change'),
        ('safety_incident', 'Safety Incident'),
        ('completion_report', 'Service Completion Report')
    ], string='Message Type', required=True, tracking=True)
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency')
    ], string='Priority', default='normal', required=True, tracking=True)
    
    message = fields.Text('Message', required=True)
    
    # Sender and recipient information
    sender_id = fields.Many2one('res.users', string='Sender', 
                               default=lambda self: self.env.user, required=True)
    
    recipient_ids = fields.Many2many('res.users', string='Recipients',
                                    help="Specific users to receive this message")
    
    recipient_role = fields.Selection([
        ('field_staff', 'Field Staff'),
        ('supervisor', 'Supervisor'),
        ('dispatcher', 'Dispatcher'),
        ('patient_family', 'Patient/Family'),
        ('emergency_contact', 'Emergency Contact'),
        ('all_team', 'All Team Members')
    ], string='Recipient Role', help="Send to all users with this role")
    
    # Communication status
    is_read = fields.Boolean('Is Read', default=False)
    read_date = fields.Datetime('Read Date')
    read_by_ids = fields.Many2many('res.users', 'communication_read_rel',
                                  string='Read By')
    
    requires_response = fields.Boolean('Requires Response', default=False)
    response_deadline = fields.Datetime('Response Deadline')
    response_received = fields.Boolean('Response Received', default=False)
    
    # Location and context
    gps_latitude = fields.Float('GPS Latitude', digits=(10, 6))
    gps_longitude = fields.Float('GPS Longitude', digits=(10, 6))
    location_description = fields.Char('Location Description')
    
    # Attachments and media
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    has_photo = fields.Boolean('Has Photo', compute='_compute_has_media')
    has_audio = fields.Boolean('Has Audio', compute='_compute_has_media')
    
    # Response and follow-up
    parent_communication_id = fields.Many2one('health.fieldservice.communication',
                                             string='Reply To')
    response_ids = fields.One2many('health.fieldservice.communication',
                                  'parent_communication_id',
                                  string='Responses')
    
    # Automatic escalation
    escalation_level = fields.Integer('Escalation Level', default=0)
    escalated_to_ids = fields.Many2many('res.users', 'communication_escalation_rel',
                                       string='Escalated To')
    auto_escalate = fields.Boolean('Auto-escalate if no response', default=False)
    escalation_minutes = fields.Integer('Escalate after (minutes)', default=30)
    
    # System fields
    communication_channel = fields.Selection([
        ('mobile_app', 'Mobile App'),
        ('web_portal', 'Web Portal'),
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('phone', 'Phone Call'),
        ('system', 'System Generated')
    ], string='Channel', default='mobile_app')
    
    is_system_generated = fields.Boolean('System Generated', default=False)
    
    # Computed fields
    response_time_minutes = fields.Integer('Response Time (minutes)',
                                          compute='_compute_response_time', store=True)
    is_overdue = fields.Boolean('Is Overdue', compute='_compute_overdue_status', store=True)
    urgency_score = fields.Integer('Urgency Score', compute='_compute_urgency_score', store=True)
    
    @api.depends('message_type', 'fieldservice_order_id.name')
    def _compute_subject(self):
        """Generate subject line based on message type and FSO"""
        for comm in self:
            type_labels = dict(self._fields['message_type'].selection)
            fso_name = comm.fieldservice_order_id.name or 'FSO'
            comm.subject = f"{type_labels.get(comm.message_type, 'Message')} - {fso_name}"
    
    @api.depends('attachment_ids')
    def _compute_has_media(self):
        """Check if communication has photo or audio attachments"""
        for comm in self:
            if comm.attachment_ids:
                photo_types = ['jpg', 'jpeg', 'png', 'gif', 'bmp']
                audio_types = ['mp3', 'wav', 'ogg', 'm4a', 'aac']
                
                photo_attachments = comm.attachment_ids.filtered(
                    lambda a: any(a.name.lower().endswith(ext) for ext in photo_types)
                )
                audio_attachments = comm.attachment_ids.filtered(
                    lambda a: any(a.name.lower().endswith(ext) for ext in audio_types)
                )
                
                comm.has_photo = len(photo_attachments) > 0
                comm.has_audio = len(audio_attachments) > 0
            else:
                comm.has_photo = False
                comm.has_audio = False
    
    @api.depends('create_date', 'response_ids.create_date')
    def _compute_response_time(self):
        """Calculate response time in minutes"""
        for comm in self:
            if comm.response_ids:
                first_response = min(comm.response_ids.mapped('create_date'))
                delta = first_response - comm.create_date
                comm.response_time_minutes = int(delta.total_seconds() / 60)
            else:
                comm.response_time_minutes = 0
    
    @api.depends('requires_response', 'response_deadline', 'response_received')
    def _compute_overdue_status(self):
        """Check if response is overdue"""
        now = fields.Datetime.now()
        for comm in self:
            comm.is_overdue = (
                comm.requires_response and 
                not comm.response_received and 
                comm.response_deadline and 
                comm.response_deadline < now
            )
    
    @api.depends('priority', 'message_type', 'requires_response', 'is_overdue')
    def _compute_urgency_score(self):
        """Calculate urgency score for prioritization"""
        for comm in self:
            score = 0
            
            # Priority weight
            priority_weights = {'low': 1, 'normal': 2, 'high': 3, 'urgent': 4, 'emergency': 5}
            score += priority_weights.get(comm.priority, 2) * 2
            
            # Message type weight
            type_weights = {
                'safety_incident': 5,
                'urgent_request': 4,
                'clinical_question': 3,
                'equipment_issue': 3,
                'patient_concern': 3,
                'status_update': 1,
                'completion_report': 1
            }
            score += type_weights.get(comm.message_type, 2)
            
            # Response requirements
            if comm.requires_response:
                score += 2
            
            if comm.is_overdue:
                score += 5
            
            comm.urgency_score = score
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set response deadline and trigger notifications"""
        for vals in vals_list:
            # Set response deadline based on priority
            if vals.get('requires_response') and not vals.get('response_deadline'):
                priority = vals.get('priority', 'normal')
                minutes_map = {
                    'emergency': 5,
                    'urgent': 15,
                    'high': 30,
                    'normal': 60,
                    'low': 120
                }
                deadline = fields.Datetime.now() + timedelta(minutes=minutes_map[priority])
                vals['response_deadline'] = deadline
        
        records = super().create(vals_list)
        
        # Send notifications
        for record in records:
            record._send_notifications()
            
        return records
    
    def _send_notifications(self):
        """Send notifications to recipients"""
        self.ensure_one()
        
        # Determine recipients
        recipients = self.recipient_ids
        
        if self.recipient_role and not recipients:
            recipients = self._get_recipients_by_role()
        
        if not recipients:
            # Default recipients based on message type
            recipients = self._get_default_recipients()
        
        # Send notifications
        if recipients:
            self._create_odoo_notifications(recipients)
            
            # Send SMS for urgent messages
            if self.priority in ['urgent', 'emergency']:
                self._send_sms_notifications(recipients)
    
    def _get_recipients_by_role(self):
        """Get recipients based on role"""
        fso = self.fieldservice_order_id
        recipients = self.env['res.users']
        
        if self.recipient_role == 'field_staff':
            recipients = fso.assigned_staff_ids.mapped('user_id')
        elif self.recipient_role == 'supervisor':
            # Get supervisors from team or assignment
            if fso.team_id and fso.team_id.leader_id:
                recipients = fso.team_id.leader_id
            elif fso.staff_assignment_id and fso.staff_assignment_id.assigned_by:
                recipients = fso.staff_assignment_id.assigned_by
        elif self.recipient_role == 'dispatcher':
            # Get users with dispatcher role (implement based on your groups)
            dispatcher_group = self.env.ref('health_fieldservice.group_fieldservice_dispatcher', 
                                          raise_if_not_found=False)
            if dispatcher_group:
                recipients = dispatcher_group.users
        
        return recipients
    
    def _get_default_recipients(self):
        """Get default recipients based on sender and message type"""
        fso = self.fieldservice_order_id
        
        # If sender is field staff, notify supervisors
        if self.sender_id in fso.assigned_staff_ids.mapped('user_id'):
            return self._get_recipients_by_role() or self.env['res.users']
        
        # If sender is supervisor, notify field staff
        else:
            self.recipient_role = 'field_staff'
            return self._get_recipients_by_role()
    
    def _create_odoo_notifications(self, recipients):
        """Create Odoo inbox notifications"""
        for recipient in recipients:
            self.message_post(
                body=self.message,
                subject=self.subject,
                partner_ids=[recipient.partner_id.id],
                subtype_xmlid='mail.mt_comment',
                raise_on_email=False
            )
    
    def _send_sms_notifications(self, recipients):
        """Send SMS notifications for urgent messages"""
        # This would integrate with SMS gateway
        # Implementation depends on SMS provider (Twilio, local Vietnamese SMS service, etc.)
        pass
    
    def action_mark_read(self):
        """Mark communication as read"""
        self.ensure_one()
        
        if not self.is_read:
            self.is_read = True
            self.read_date = fields.Datetime.now()
            self.read_by_ids = [(4, self.env.user.id)]
    
    def action_reply(self):
        """Open reply form"""
        self.ensure_one()
        
        return {
            'name': f'Reply to {self.subject}',
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.communication',
            'view_mode': 'form',
            'context': {
                'default_fieldservice_order_id': self.fieldservice_order_id.id,
                'default_parent_communication_id': self.id,
                'default_message_type': self.message_type,
                'default_recipient_ids': [(6, 0, [self.sender_id.id])]
            },
            'target': 'new'
        }
    
    def action_escalate(self):
        """Escalate communication to higher level"""
        self.ensure_one()
        
        # Increase escalation level
        self.escalation_level += 1
        
        # Find escalation recipients (supervisors, managers)
        escalation_group = self.env.ref('health_fieldservice.group_fieldservice_manager', 
                                      raise_if_not_found=False)
        if escalation_group:
            self.escalated_to_ids = [(6, 0, escalation_group.users.ids)]
            
            # Create escalation communication
            escalation_msg = f"""
ESCALATED COMMUNICATION (Level {self.escalation_level})

Original Message: {self.subject}
From: {self.sender_id.name}
Priority: {self.priority.upper()}
FSO: {self.fieldservice_order_id.name}

{self.message}

Response required by: {self.response_deadline}
            """
            
            self.env['health.fieldservice.communication'].create({
                'fieldservice_order_id': self.fieldservice_order_id.id,
                'message_type': 'urgent_request',
                'priority': 'urgent',
                'message': escalation_msg,
                'recipient_ids': [(6, 0, escalation_group.users.ids)],
                'requires_response': True,
                'parent_communication_id': self.id
            })
    
    @api.model
    def auto_escalate_overdue(self):
        """Cron job to auto-escalate overdue communications"""
        overdue_comms = self.search([
            ('requires_response', '=', True),
            ('response_received', '=', False),
            ('auto_escalate', '=', True),
            ('response_deadline', '<', fields.Datetime.now()),
            ('escalation_level', '<', 3)  # Maximum 3 escalation levels
        ])
        
        for comm in overdue_comms:
            comm.action_escalate()
    
    def action_quick_status_update(self, status):
        """Quick status update from mobile app"""
        self.ensure_one()
        
        status_messages = {
            'en_route': "🚗 En route to patient location",
            'arrived': "📍 Arrived at patient location", 
            'started': "🏥 Service started",
            'completed': "✅ Service completed successfully",
            'delayed': "⏰ Running behind schedule",
            'need_help': "🆘 Need assistance"
        }
        
        message = status_messages.get(status, f"Status update: {status}")
        
        return self.env['health.fieldservice.communication'].create({
            'fieldservice_order_id': self.fieldservice_order_id.id,
            'message_type': 'status_update',
            'priority': 'high' if status == 'need_help' else 'normal',
            'message': message,
            'is_system_generated': True,
            'communication_channel': 'mobile_app'
        })