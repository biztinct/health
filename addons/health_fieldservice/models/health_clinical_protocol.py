from odoo import models, fields, api, _
import json


class HealthClinicalProtocol(models.Model):
    """
    Clinical Protocol Templates - Dynamic action steps for different healthcare services
    Your key requirement: Single FSO model with different templates based on service type
    """
    _name = 'health.clinical.protocol'
    _description = 'Healthcare Clinical Protocol Templates'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    
    # translate=True is load-bearing here: health_base declares the same model
    # with a translatable `name`, but this module loads AFTER it, so this
    # definition is the one that wins. Dropping the flag silently un-translates
    # the protocol names shown in every dropdown.
    name = fields.Char('Protocol Name', required=True, tracking=True,
                      translate=True,
                      help="e.g., 'Blood Draw Protocol', 'Wound Care Protocol'")
    
    description = fields.Text('Protocol Description', translate=True)
    
    # Service type mapping
    service_type_ids = fields.Many2many('health.service.type',
                                       string='Applicable Service Types',
                                       help="Service types that use this protocol")
    
    # Dynamic action steps template (Your core requirement)
    action_steps_template = fields.Json(
        'Action Steps Template',
        help="JSON template defining step-by-step actions for field staff"
    )
    
    # Equipment requirements
    required_equipment_ids = fields.Many2many('health.portable.equipment',
                                             string='Required Equipment',
                                             help="Equipment needed for this protocol")
    
    # Protocol metadata
    version = fields.Char('Protocol Version', default='1.0', tracking=True)
    effective_date = fields.Date('Effective Date', default=fields.Date.today, required=True)
    expiry_date = fields.Date('Expiry Date')
    
    # Protocol classification
    complexity_level_id = fields.Many2one(
        'health.lookup.value',
        string='Complexity Level',
        domain="[('category_code', '=', 'protocol_complexity'), ('active', '=', True)]",
        ondelete='restrict',
        required=True,
        default=lambda self: self.env['health.lookup.value']._default_for('protocol_complexity', 'basic'))
    # Companion for view expressions and domains: an Odoo view attribute
    # (invisible=, decoration-, domain=) cannot traverse a many2one, and
    # this keeps every existing comparison a one-word change.
    complexity_level_code = fields.Char(
        related='complexity_level_id.code', string='Complexity Level Code', readonly=True)
    
    duration_estimate_minutes = fields.Integer('Estimated Duration (minutes)', default=30)
    
    # Safety and compliance
    safety_requirements = fields.Text('Safety Requirements',
                                     help="Special safety considerations for this protocol")
    
    infection_control_level_id = fields.Many2one(
        'health.lookup.value',
        string='Infection Control Level',
        domain="[('category_code', '=', 'infection_control_level'), ('active', '=', True)]",
        ondelete='restrict',
        default=lambda self: self.env['health.lookup.value']._default_for('infection_control_level', 'standard'))
    # Companion for view expressions and domains: an Odoo view attribute
    # (invisible=, decoration-, domain=) cannot traverse a many2one, and
    # this keeps every existing comparison a one-word change.
    infection_control_level_code = fields.Char(
        related='infection_control_level_id.code', string='Infection Control Level Code', readonly=True)
    
    # Required qualifications
    required_qualifications = fields.Text('Required Staff Qualifications',
                                         help="Minimum qualifications needed to perform this protocol")
    
    # Documentation requirements
    documentation_required = fields.Boolean('Documentation Required', default=True)
    documentation_template = fields.Text('Documentation Template',
                                        help="Template for required documentation")
    
    # Usage tracking
    usage_count = fields.Integer('Usage Count', readonly=True,
                                help="Number of times this protocol has been used")
    
    active = fields.Boolean('Active', default=True)
    
    # Computed fields
    sample_action_steps = fields.Text('Sample Action Steps', compute='_compute_sample_steps',
                                     help="Human-readable preview of action steps")
    
    @api.depends('action_steps_template')
    def _compute_sample_steps(self):
        """Generate human-readable preview of action steps"""
        for protocol in self:
            if protocol.action_steps_template:
                try:
                    steps = protocol.action_steps_template
                    if isinstance(steps, dict) and 'steps' in steps:
                        step_list = steps['steps']
                    elif isinstance(steps, list):
                        step_list = steps
                    else:
                        step_list = []
                    
                    preview = []
                    for i, step in enumerate(step_list[:5], 1):  # Show first 5 steps
                        if isinstance(step, dict):
                            action = step.get('action', 'No action defined')
                            preview.append(f"{i}. {action}")
                        else:
                            preview.append(f"{i}. {step}")
                    
                    if len(step_list) > 5:
                        preview.append(f"... and {len(step_list) - 5} more steps")
                    
                    protocol.sample_action_steps = '\n'.join(preview)
                    
                except (TypeError, ValueError, KeyError):
                    protocol.sample_action_steps = "Invalid action steps format"
            else:
                protocol.sample_action_steps = "No action steps defined"
    
    @api.model
    def get_protocol_for_service(self, service_type_id):
        """Get the appropriate protocol for a service type"""
        protocol = self.search([
            ('service_type_ids', 'in', service_type_id),
            ('active', '=', True),
            ('effective_date', '<=', fields.Date.today()),
            '|', ('expiry_date', '=', False), ('expiry_date', '>', fields.Date.today())
        ], limit=1)
        
        return protocol
    
    def create_default_protocols(self):
        """Create default clinical protocols for common healthcare services"""
        default_protocols = [
            {
                'name': 'Blood Draw Protocol',
                'description': 'Standard protocol for phlebotomy services',
                'complexity_level_id': self.env['health.lookup.value']._default_for('protocol_complexity', 'basic'),
                'duration_estimate_minutes': 15,
                'infection_control_level_id': self.env['health.lookup.value']._default_for('infection_control_level', 'standard'),
                'action_steps_template': {
                    'steps': [
                        {'step': 1, 'action': 'Verify patient identity using two identifiers', 'required': True, 'time_minutes': 2},
                        {'step': 2, 'action': 'Review doctor orders and fasting requirements', 'required': True, 'time_minutes': 2},
                        {'step': 3, 'action': 'Explain procedure to patient and obtain consent', 'required': True, 'time_minutes': 3},
                        {'step': 4, 'action': 'Prepare and check phlebotomy equipment', 'required': True, 'time_minutes': 2},
                        {'step': 5, 'action': 'Select appropriate venipuncture site', 'required': True, 'time_minutes': 1},
                        {'step': 6, 'action': 'Perform hand hygiene and don gloves', 'required': True, 'time_minutes': 1},
                        {'step': 7, 'action': 'Perform venipuncture using sterile technique', 'required': True, 'time_minutes': 3},
                        {'step': 8, 'action': 'Label specimens correctly and immediately', 'required': True, 'time_minutes': 2},
                        {'step': 9, 'action': 'Apply pressure and bandage puncture site', 'required': True, 'time_minutes': 2},
                        {'step': 10, 'action': 'Provide patient aftercare instructions', 'required': True, 'time_minutes': 2},
                        {'step': 11, 'action': 'Document procedure and any complications', 'required': True, 'time_minutes': 3},
                        {'step': 12, 'action': 'Prepare specimens for transport', 'required': True, 'time_minutes': 2}
                    ],
                    'total_estimated_minutes': 25,
                    'critical_steps': [1, 2, 7, 8],
                    'safety_checks': ['Patient identity', 'Equipment sterility', 'Proper labeling']
                }
            },
            {
                'name': 'Wound Care Protocol',
                'description': 'Standard protocol for home wound care services',
                'complexity_level_id': self.env['health.lookup.value']._default_for('protocol_complexity', 'intermediate'),
                'duration_estimate_minutes': 45,
                'infection_control_level_id': self.env['health.lookup.value']._default_for('infection_control_level', 'contact'),
                'action_steps_template': {
                    'steps': [
                        {'step': 1, 'action': 'Verify patient identity and review care plan', 'required': True, 'time_minutes': 3},
                        {'step': 2, 'action': 'Assess patient pain level and administer analgesics if ordered', 'required': True, 'time_minutes': 5},
                        {'step': 3, 'action': 'Prepare sterile field and wound care supplies', 'required': True, 'time_minutes': 5},
                        {'step': 4, 'action': 'Perform hand hygiene and don sterile gloves', 'required': True, 'time_minutes': 2},
                        {'step': 5, 'action': 'Remove old dressing using sterile technique', 'required': True, 'time_minutes': 5},
                        {'step': 6, 'action': 'Assess wound characteristics (size, depth, drainage)', 'required': True, 'time_minutes': 5},
                        {'step': 7, 'action': 'Clean wound according to physician orders', 'required': True, 'time_minutes': 10},
                        {'step': 8, 'action': 'Apply prescribed topical medications', 'required': False, 'time_minutes': 3},
                        {'step': 9, 'action': 'Apply new dressing using sterile technique', 'required': True, 'time_minutes': 8},
                        {'step': 10, 'action': 'Secure dressing and check for proper fit', 'required': True, 'time_minutes': 3},
                        {'step': 11, 'action': 'Educate patient/caregiver on wound care', 'required': True, 'time_minutes': 10},
                        {'step': 12, 'action': 'Document wound assessment and care provided', 'required': True, 'time_minutes': 5},
                        {'step': 13, 'action': 'Schedule next visit and provide contact information', 'required': True, 'time_minutes': 3}
                    ],
                    'total_estimated_minutes': 67,
                    'critical_steps': [1, 4, 5, 6, 7, 9],
                    'safety_checks': ['Sterile technique', 'Pain assessment', 'Infection signs', 'Patient education']
                }
            },
            {
                'name': 'Medication Administration Protocol',
                'description': 'Protocol for home medication administration',
                'complexity_level_id': self.env['health.lookup.value']._default_for('protocol_complexity', 'intermediate'),
                'duration_estimate_minutes': 20,
                'infection_control_level_id': self.env['health.lookup.value']._default_for('infection_control_level', 'standard'),
                'action_steps_template': {
                    'steps': [
                        {'step': 1, 'action': 'Verify patient identity using two identifiers', 'required': True, 'time_minutes': 2},
                        {'step': 2, 'action': 'Review medication orders and allergies', 'required': True, 'time_minutes': 3},
                        {'step': 3, 'action': 'Check medication five rights (patient, drug, dose, route, time)', 'required': True, 'time_minutes': 5},
                        {'step': 4, 'action': 'Assess patient vital signs if required', 'required': False, 'time_minutes': 5},
                        {'step': 5, 'action': 'Prepare medication using aseptic technique', 'required': True, 'time_minutes': 3},
                        {'step': 6, 'action': 'Administer medication via prescribed route', 'required': True, 'time_minutes': 5},
                        {'step': 7, 'action': 'Monitor patient for immediate adverse reactions', 'required': True, 'time_minutes': 10},
                        {'step': 8, 'action': 'Document administration and patient response', 'required': True, 'time_minutes': 3},
                        {'step': 9, 'action': 'Educate patient/caregiver about medication', 'required': True, 'time_minutes': 5},
                        {'step': 10, 'action': 'Dispose of supplies safely', 'required': True, 'time_minutes': 2}
                    ],
                    'total_estimated_minutes': 43,
                    'critical_steps': [1, 2, 3, 5, 6, 7],
                    'safety_checks': ['Five rights verification', 'Allergy check', 'Vital signs', 'Adverse reactions']
                }
            },
            {
                'name': 'Vital Signs Assessment Protocol',
                'description': 'Standard protocol for comprehensive vital signs assessment',
                'complexity_level_id': self.env['health.lookup.value']._default_for('protocol_complexity', 'basic'),
                'duration_estimate_minutes': 15,
                'infection_control_level_id': self.env['health.lookup.value']._default_for('infection_control_level', 'standard'),
                'action_steps_template': {
                    'steps': [
                        {'step': 1, 'action': 'Verify patient identity and explain procedure', 'required': True, 'time_minutes': 2},
                        {'step': 2, 'action': 'Ensure patient has rested for 5 minutes', 'required': True, 'time_minutes': 5},
                        {'step': 3, 'action': 'Check and calibrate equipment', 'required': True, 'time_minutes': 2},
                        {'step': 4, 'action': 'Measure blood pressure (two readings if elevated)', 'required': True, 'time_minutes': 5},
                        {'step': 5, 'action': 'Measure pulse rate and rhythm', 'required': True, 'time_minutes': 2},
                        {'step': 6, 'action': 'Measure respiratory rate', 'required': True, 'time_minutes': 2},
                        {'step': 7, 'action': 'Measure temperature', 'required': True, 'time_minutes': 2},
                        {'step': 8, 'action': 'Measure oxygen saturation if indicated', 'required': False, 'time_minutes': 2},
                        {'step': 9, 'action': 'Document all measurements accurately', 'required': True, 'time_minutes': 3},
                        {'step': 10, 'action': 'Report abnormal findings to physician', 'required': True, 'time_minutes': 2}
                    ],
                    'total_estimated_minutes': 27,
                    'critical_steps': [1, 3, 4, 9, 10],
                    'safety_checks': ['Equipment calibration', 'Abnormal value recognition', 'Physician notification']
                }
            }
        ]
        
        created_protocols = []
        for protocol_data in default_protocols:
            existing = self.search([('name', '=', protocol_data['name'])], limit=1)
            if not existing:
                protocol = self.create(protocol_data)
                created_protocols.append(protocol)
        
        return created_protocols
    
    def action_preview_steps(self):
        """Preview action steps in a popup"""
        self.ensure_one()
        
        return {
            'name': f'Protocol Steps - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'health.clinical.protocol',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_fieldservice.view_clinical_protocol_preview_form').id,
            'target': 'new'
        }
    
    def action_duplicate_protocol(self):
        """Create a copy of this protocol with new version"""
        self.ensure_one()
        
        copy_vals = {
            'name': f"{self.name} (Copy)",
            'version': f"{self.version}.1",
            'effective_date': fields.Date.today()
        }
        
        new_protocol = self.copy(copy_vals)
        
        return {
            'name': 'Edit New Protocol Version',
            'type': 'ir.actions.act_window',
            'res_model': 'health.clinical.protocol',
            'res_id': new_protocol.id,
            'view_mode': 'form',
            'target': 'current'
        }