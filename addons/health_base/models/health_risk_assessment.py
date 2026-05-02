from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class FallRiskAssessment(models.Model):
    """Morse Fall Scale Implementation"""
    _name = 'health.fall.risk'
    _description = 'Fall Risk Assessment'
    _order = 'create_date desc'

    active = fields.Boolean('Active', default=True)

    patient_id = fields.Many2one('res.partner', 'Patient', required=True, 
                                domain=[('is_patient', '=', True)])
    assessment_date = fields.Datetime('Assessment Date', default=fields.Datetime.now, required=True)
    assessed_by = fields.Many2one('res.users', 'Assessed By', default=lambda self: self.env.user)
    
    # Morse Fall Scale Components
    history_of_falling = fields.Boolean('History of Falling (25 points)')
    secondary_diagnosis = fields.Boolean('Secondary Diagnosis (15 points)')
    ambulatory_aid = fields.Selection([
        ('none', 'None/Bed rest/Nurse assist (0 points)'),
        ('crutches', 'Crutches/Cane/Walker (15 points)'),
        ('furniture', 'Furniture (30 points)')
    ], string='Ambulatory Aid', required=True, default='none')
    
    iv_therapy = fields.Boolean('IV Therapy/Heparin Lock (20 points)')
    gait_transfer = fields.Selection([
        ('normal', 'Normal/Bed rest/Immobile (0 points)'),
        ('weak', 'Weak (10 points)'),
        ('impaired', 'Impaired (20 points)')
    ], string='Gait/Transfer', required=True, default='normal')
    
    mental_status = fields.Selection([
        ('oriented', 'Oriented to own ability (0 points)'),
        ('overestimates', 'Overestimates/Forgets limitations (15 points)')
    ], string='Mental Status', required=True, default='oriented')
    
    # Calculated Fields
    morse_score = fields.Integer('Morse Fall Score', compute='_compute_morse_score', store=True)
    risk_level = fields.Selection([
        ('low', 'Low Risk (0-24)'),
        ('medium', 'Medium Risk (25-44)'),
        ('high', 'High Risk (≥45)')
    ], string='Risk Level', compute='_compute_risk_level', store=True)
    
    # Additional Assessment
    environmental_hazards = fields.Text('Home Environment Assessment', translate=True)
    intervention_plan = fields.Html('Personalized Fall Prevention Plan', translate=True)
    
    # Vietnamese
    vietnamese_environmental_hazards = fields.Text('Vietnamese Environmental Hazards', translate=True)
    vietnamese_intervention_plan = fields.Html('Vietnamese Intervention Plan', translate=True)
    
    @api.depends('history_of_falling', 'secondary_diagnosis', 'ambulatory_aid', 
                'iv_therapy', 'gait_transfer', 'mental_status')
    def _compute_morse_score(self):
        """Calculate Morse Fall Scale score"""
        for record in self:
            score = 0
            
            # History of falling
            if record.history_of_falling:
                score += 25
            
            # Secondary diagnosis
            if record.secondary_diagnosis:
                score += 15
            
            # Ambulatory aid
            if record.ambulatory_aid == 'crutches':
                score += 15
            elif record.ambulatory_aid == 'furniture':
                score += 30
            
            # IV therapy
            if record.iv_therapy:
                score += 20
            
            # Gait/transfer
            if record.gait_transfer == 'weak':
                score += 10
            elif record.gait_transfer == 'impaired':
                score += 20
            
            # Mental status
            if record.mental_status == 'overestimates':
                score += 15
            
            record.morse_score = score
    
    @api.depends('morse_score')
    def _compute_risk_level(self):
        """Determine risk level based on Morse score"""
        for record in self:
            if record.morse_score <= 24:
                record.risk_level = 'low'
            elif record.morse_score <= 44:
                record.risk_level = 'medium'
            else:
                record.risk_level = 'high'
    
    def generate_intervention_plan(self):
        """Generate personalized fall prevention plan"""
        for record in self:
            plan = "<h3>Fall Prevention Plan</h3><ul>"
            
            if record.risk_level == 'high':
                plan += "<li><strong>High Risk Interventions:</strong></li>"
                plan += "<li>24-hour supervision or bed alarm</li>"
                plan += "<li>Non-slip footwear</li>"
                plan += "<li>Bed rails up when in bed</li>"
                plan += "<li>Call bell within reach</li>"
                plan += "<li>Frequent safety checks</li>"
            elif record.risk_level == 'medium':
                plan += "<li><strong>Medium Risk Interventions:</strong></li>"
                plan += "<li>Assist with ambulation</li>"
                plan += "<li>Clear pathways</li>"
                plan += "<li>Proper lighting</li>"
                plan += "<li>Regular safety assessments</li>"
            else:
                plan += "<li><strong>Low Risk Interventions:</strong></li>"
                plan += "<li>Standard fall precautions</li>"
                plan += "<li>Regular reassessment</li>"
            
            plan += "</ul>"
            record.intervention_plan = plan


class ReadmissionRisk(models.Model):
    """Readmission risk prediction model"""
    _name = 'health.readmission.risk'
    _description = 'Readmission Risk Assessment'
    _order = 'create_date desc'

    active = fields.Boolean('Active', default=True)

    patient_id = fields.Many2one('res.partner', 'Patient', required=True,
                                domain=[('is_patient', '=', True)])
    assessment_date = fields.Datetime('Assessment Date', default=fields.Datetime.now)
    
    # Risk Factors
    age = fields.Integer('Age', related='patient_id.age', store=True)
    gender = fields.Selection('Gender', related='patient_id.gender', store=True)
    
    # Medical History
    chronic_conditions = fields.Integer('Number of Chronic Conditions', default=0)
    prior_admissions = fields.Integer('Prior Admissions (Last 12 Months)', default=0)
    emergency_visits = fields.Integer('Emergency Visits (Last 12 Months)', default=0)
    
    # Social Factors
    lives_alone = fields.Boolean('Lives Alone')
    has_caregiver = fields.Boolean('Has Caregiver')
    transportation_issues = fields.Boolean('Transportation Issues')
    financial_constraints = fields.Boolean('Financial Constraints')
    
    # Medication Factors
    medication_count = fields.Integer('Number of Medications', default=0)
    medication_compliance = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor')
    ], string='Medication Compliance', default='good')
    
    # Functional Status
    adl_score = fields.Integer('Activities of Daily Living Score (0-6)', default=6)
    mobility_issues = fields.Boolean('Mobility Issues')
    cognitive_impairment = fields.Boolean('Cognitive Impairment')
    
    # Calculated Risk
    risk_score = fields.Float('Risk Score (0-100)', compute='_compute_risk_score', store=True)
    risk_level = fields.Selection([
        ('low', 'Low Risk (0-30)'),
        ('medium', 'Medium Risk (31-60)'),
        ('high', 'High Risk (61-100)')
    ], string='Risk Level', compute='_compute_risk_level', store=True)
    
    # Interventions
    recommended_interventions = fields.Html('Recommended Interventions', translate=True)
    
    @api.depends('age', 'chronic_conditions', 'prior_admissions', 'emergency_visits',
                'lives_alone', 'medication_count', 'medication_compliance', 'adl_score')
    def _compute_risk_score(self):
        """Calculate readmission risk score"""
        for record in self:
            score = 0
            
            # Age factor
            if record.age > 75:
                score += 15
            elif record.age > 65:
                score += 10
            
            # Medical history
            score += record.chronic_conditions * 5
            score += record.prior_admissions * 8
            score += record.emergency_visits * 6
            
            # Social factors
            if record.lives_alone:
                score += 10
            if not record.has_caregiver:
                score += 8
            if record.transportation_issues:
                score += 5
            if record.financial_constraints:
                score += 7
            
            # Medication factors
            if record.medication_count > 5:
                score += 8
            if record.medication_compliance == 'poor':
                score += 15
            elif record.medication_compliance == 'fair':
                score += 8
            
            # Functional status
            score += (6 - record.adl_score) * 3
            if record.mobility_issues:
                score += 5
            if record.cognitive_impairment:
                score += 10
            
            # Cap at 100
            record.risk_score = min(score, 100)
    
    @api.depends('risk_score')
    def _compute_risk_level(self):
        """Determine risk level"""
        for record in self:
            if record.risk_score <= 30:
                record.risk_level = 'low'
            elif record.risk_score <= 60:
                record.risk_level = 'medium'
            else:
                record.risk_level = 'high'
    
    def generate_interventions(self):
        """Generate recommended interventions based on risk level"""
        for record in self:
            interventions = "<h3>Recommended Interventions</h3><ul>"
            
            if record.risk_level == 'high':
                interventions += "<li><strong>High Risk Interventions:</strong></li>"
                interventions += "<li>Enhanced care coordination</li>"
                interventions += "<li>Home health services</li>"
                interventions += "<li>Medication reconciliation</li>"
                interventions += "<li>Follow-up within 48 hours</li>"
                interventions += "<li>Caregiver education and support</li>"
            elif record.risk_level == 'medium':
                interventions += "<li><strong>Medium Risk Interventions:</strong></li>"
                interventions += "<li>Standard care coordination</li>"
                interventions += "<li>Medication review</li>"
                interventions += "<li>Follow-up within 1 week</li>"
                interventions += "<li>Patient education</li>"
            else:
                interventions += "<li><strong>Low Risk Interventions:</strong></li>"
                interventions += "<li>Standard discharge planning</li>"
                interventions += "<li>Routine follow-up</li>"
            
            interventions += "</ul>"
            record.recommended_interventions = interventions
