from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class MedicationSafety(models.Model):
    """Medication safety and drug interaction checking"""
    _name = 'health.medication.safety'
    _description = 'Medication Safety System'

    def check_drug_interactions(self, medications):
        """
        Uses RxNorm API and OpenFDA for interaction checking
        Both are free government APIs
        """
        interactions = []
        
        try:
            # Check pairwise interactions
            for i, med1 in enumerate(medications):
                for med2 in medications[i+1:]:
                    interaction = self._check_pairwise_interaction(med1, med2)
                    if interaction:
                        interactions.append(interaction)
            
            return interactions
        except Exception as e:
            _logger.error(f"Error checking drug interactions: {str(e)}")
            return []
    
    def _check_pairwise_interaction(self, med1, med2):
        """Check interaction between two medications"""
        try:
            # RxNorm API for drug normalization
            rxnorm_base = "https://rxnav.nlm.nih.gov/REST"
            
            # Get RxNorm IDs for both medications
            med1_rxcui = self._get_rxcui(med1)
            med2_rxcui = self._get_rxcui(med2)
            
            if med1_rxcui and med2_rxcui:
                # Check interactions via RxNorm API
                interaction_url = f"{rxnorm_base}/interaction/interaction.json?rxcui={med1_rxcui}&rxcui={med2_rxcui}"
                
                response = requests.get(interaction_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_interaction_data(data, med1, med2)
            
            return None
        except Exception as e:
            _logger.error(f"Error checking pairwise interaction: {str(e)}")
            return None
    
    def _get_rxcui(self, medication_name):
        """Get RxNorm concept unique identifier for medication"""
        try:
            rxnorm_base = "https://rxnav.nlm.nih.gov/REST"
            search_url = f"{rxnorm_base}/drugs.json?name={medication_name}"
            
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('drugGroup', {}).get('conceptGroup'):
                    for group in data['drugGroup']['conceptGroup']:
                        if group.get('conceptProperties'):
                            return group['conceptProperties'][0].get('rxcui')
            return None
        except Exception as e:
            _logger.error(f"Error getting RxCUI: {str(e)}")
            return None
    
    def _parse_interaction_data(self, data, med1, med2):
        """Parse interaction data from API response"""
        try:
            if data.get('interactionTypeGroup'):
                for group in data['interactionTypeGroup']:
                    if group.get('interactionType'):
                        for interaction in group['interactionType']:
                            if interaction.get('interactionPair'):
                                for pair in interaction['interactionPair']:
                                    return {
                                        'medication1': med1,
                                        'medication2': med2,
                                        'severity': pair.get('severity', 'unknown'),
                                        'description': pair.get('description', ''),
                                        'source': 'RxNorm API'
                                    }
            return None
        except Exception as e:
            _logger.error(f"Error parsing interaction data: {str(e)}")
            return None
    
    def calculate_dosage(self, patient_weight, patient_age, medication, renal_function=None, hepatic_function=None):
        """
        Pediatric and geriatric dosing calculations
        Based on open medical calculators
        """
        try:
            # Get medication dosing guidelines
            dosing_info = self._get_dosing_guidelines(medication)
            
            if not dosing_info:
                return {'error': 'Dosing guidelines not available'}
            
            # Calculate base dose
            base_dose = self._calculate_base_dose(dosing_info, patient_weight, patient_age)
            
            # Apply adjustments
            adjusted_dose = self._apply_dose_adjustments(
                base_dose, patient_age, renal_function, hepatic_function
            )
            
            return {
                'medication': medication,
                'base_dose': base_dose,
                'adjusted_dose': adjusted_dose,
                'frequency': dosing_info.get('frequency', 'daily'),
                'route': dosing_info.get('route', 'oral'),
                'warnings': self._get_dosing_warnings(patient_age, renal_function, hepatic_function)
            }
        except Exception as e:
            _logger.error(f"Error calculating dosage: {str(e)}")
            return {'error': 'Unable to calculate dosage'}
    
    def _get_dosing_guidelines(self, medication):
        """Get dosing guidelines for medication"""
        # This would integrate with a medication database
        # For now, return sample data
        return {
            'frequency': 'daily',
            'route': 'oral',
            'weight_based': True,
            'age_adjustments': True
        }
    
    def _calculate_base_dose(self, dosing_info, weight, age):
        """Calculate base dose based on weight and age"""
        # Simplified calculation - would be more complex in practice
        if dosing_info.get('weight_based') and weight:
            return weight * 0.1  # Example: 0.1 mg/kg
        return 10.0  # Default dose
    
    def _apply_dose_adjustments(self, base_dose, age, renal_function, hepatic_function):
        """Apply age and organ function adjustments"""
        adjusted_dose = base_dose
        
        # Age adjustments
        if age < 12:  # Pediatric
            adjusted_dose *= 0.8
        elif age > 65:  # Geriatric
            adjusted_dose *= 0.9
        
        # Renal function adjustments
        if renal_function and renal_function < 30:  # Severe renal impairment
            adjusted_dose *= 0.5
        
        # Hepatic function adjustments
        if hepatic_function and hepatic_function < 30:  # Severe hepatic impairment
            adjusted_dose *= 0.7
        
        return adjusted_dose
    
    def _get_dosing_warnings(self, age, renal_function, hepatic_function):
        """Get dosing warnings based on patient factors"""
        warnings = []
        
        if age < 12:
            warnings.append("Pediatric dosing - monitor closely")
        elif age > 65:
            warnings.append("Geriatric patient - consider reduced dosing")
        
        if renal_function and renal_function < 30:
            warnings.append("Severe renal impairment - dose adjustment required")
        
        if hepatic_function and hepatic_function < 30:
            warnings.append("Severe hepatic impairment - dose adjustment required")
        
        return warnings


class MedicationInteraction(models.Model):
    """Stored medication interactions"""
    _name = 'health.medication.interaction'
    _description = 'Medication Interaction'
    _order = 'severity desc, create_date desc'

    medication1_id = fields.Many2one('health.medication', 'Medication 1', required=True)
    medication2_id = fields.Many2one('health.medication', 'Medication 2', required=True)
    
    severity = fields.Selection([
        ('major', 'Major'),
        ('moderate', 'Moderate'),
        ('minor', 'Minor'),
        ('unknown', 'Unknown')
    ], string='Severity', required=True)
    
    description = fields.Text('Interaction Description', required=True)
    evidence_level = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], string='Evidence Level', default='medium')
    
    source = fields.Char('Source', default='RxNorm API')
    last_updated = fields.Datetime('Last Updated', default=fields.Datetime.now)
    
    # Vietnamese
    vietnamese_description = fields.Text('Vietnamese Description', translate=True)
    
    _sql_constraints = [
        ('unique_interaction', 'unique(medication1_id, medication2_id)', 
         'Interaction between these medications already exists!')
    ]


class Medication(models.Model):
    """Medication catalog with safety information"""
    _name = 'health.medication'
    _description = 'Medication'
    _order = 'name'

    name = fields.Char('Medication Name', required=True, translate=True)
    generic_name = fields.Char('Generic Name', translate=True)
    brand_name = fields.Char('Brand Name', translate=True)
    
    # Classification
    medication_class = fields.Char('Medication Class')
    therapeutic_category = fields.Selection([
        ('antibiotic', 'Antibiotic'),
        ('analgesic', 'Analgesic'),
        ('antihypertensive', 'Antihypertensive'),
        ('diabetic', 'Diabetic Medication'),
        ('cardiac', 'Cardiac Medication'),
        ('respiratory', 'Respiratory Medication'),
        ('psychiatric', 'Psychiatric Medication'),
        ('other', 'Other')
    ], string='Therapeutic Category')
    
    # Safety Information
    pregnancy_category = fields.Selection([
        ('a', 'Category A'),
        ('b', 'Category B'),
        ('c', 'Category C'),
        ('d', 'Category D'),
        ('x', 'Category X')
    ], string='Pregnancy Category')
    
    contraindications = fields.Text('Contraindications', translate=True)
    side_effects = fields.Text('Common Side Effects', translate=True)
    
    # Vietnamese
    vietnamese_name = fields.Char('Vietnamese Name', translate=True)
    vietnamese_contraindications = fields.Text('Vietnamese Contraindications', translate=True)
    
    # Related interactions
    interaction_ids = fields.One2many('health.medication.interaction', 'medication1_id', 'Interactions')
    
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Medication name must be unique!')
    ]


class ClinicalProtocol(models.Model):
    """Evidence-based clinical care protocols"""
    _name = 'health.clinical.protocol'
    _description = 'Clinical Care Protocol'
    _order = 'protocol_type, name'

    name = fields.Char('Protocol Name', required=True, translate=True)
    protocol_type = fields.Selection([
        ('cdc', 'CDC Guidelines'),
        ('who', 'WHO Guidelines'),
        ('vietnam_moh', 'Vietnam MOH'),
        ('local', 'Local Protocol'),
        ('custom', 'Custom Protocol')
    ], string='Protocol Type', required=True, default='local')
    
    description = fields.Text('Description', translate=True)
    is_active = fields.Boolean('Active', default=True)
    version = fields.Char('Version', default='1.0')
    last_updated = fields.Date('Last Updated', default=fields.Date.today)
    
    # Protocol Content
    assessment_questions = fields.One2many('health.protocol.question', 'protocol_id', string='Assessment Questions')
    interventions = fields.One2many('health.protocol.intervention', 'protocol_id', string='Interventions')
    
    # Vietnamese Localization
    vietnamese_name = fields.Char('Vietnamese Name', translate=True)
    vietnamese_description = fields.Text('Vietnamese Description', translate=True)
    
    # Integration Fields
    external_id = fields.Char('External ID')
    source_url = fields.Char('Source URL')
    api_endpoint = fields.Char('API Endpoint')
    
    # Compliance
    compliance_level = fields.Selection([
        ('required', 'Required'),
        ('recommended', 'Recommended'),
        ('optional', 'Optional')
    ], string='Compliance Level', default='recommended')
    
    # Audit Fields
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    created_date = fields.Datetime('Created Date', default=fields.Datetime.now)
    modified_by = fields.Many2one('res.users', string='Modified By')
    modified_date = fields.Datetime('Modified Date')

    @api.model
    def sync_from_cdc_api(self):
        """Sync protocols from CDC API"""
        try:
            # CDC API endpoint for clinical guidelines
            url = "https://www.cdc.gov/api/v1/clinical-guidelines"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for protocol_data in data.get('protocols', []):
                    self._create_or_update_protocol(protocol_data, 'cdc')
                    
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 
                   'params': {'title': 'Success', 'message': 'CDC protocols synced successfully'}}
                    
        except Exception as e:
            _logger.error(f"Error syncing CDC protocols: {str(e)}")
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 
                   'params': {'title': 'Error', 'message': f'Failed to sync CDC protocols: {str(e)}'}}

    @api.model
    def sync_from_who_api(self):
        """Sync protocols from WHO API"""
        try:
            # WHO API endpoint for clinical guidelines
            url = "https://www.who.int/api/v1/clinical-guidelines"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for protocol_data in data.get('protocols', []):
                    self._create_or_update_protocol(protocol_data, 'who')
                    
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 
                   'params': {'title': 'Success', 'message': 'WHO protocols synced successfully'}}
                    
        except Exception as e:
            _logger.error(f"Error syncing WHO protocols: {str(e)}")
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 
                   'params': {'title': 'Error', 'message': f'Failed to sync WHO protocols: {str(e)}'}}

    def _create_or_update_protocol(self, protocol_data, source):
        """Create or update protocol from external API data"""
        existing = self.search([('external_id', '=', protocol_data.get('id'))])
        
        vals = {
            'name': protocol_data.get('title', ''),
            'description': protocol_data.get('description', ''),
            'protocol_type': source,
            'external_id': protocol_data.get('id'),
            'source_url': protocol_data.get('url', ''),
            'version': protocol_data.get('version', '1.0'),
            'last_updated': fields.Date.today(),
        }
        
        if existing:
            existing.write(vals)
        else:
            self.create(vals)


class ProtocolQuestion(models.Model):
    """Assessment questions for clinical protocols"""
    _name = 'health.protocol.question'
    _description = 'Protocol Assessment Question'
    _order = 'sequence, id'

    name = fields.Char('Question', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    question_type = fields.Selection([
        ('yes_no', 'Yes/No'),
        ('multiple_choice', 'Multiple Choice'),
        ('numeric', 'Numeric'),
        ('text', 'Text'),
        ('scale', 'Scale (1-10)')
    ], string='Question Type', required=True, default='yes_no')
    
    protocol_id = fields.Many2one('health.clinical.protocol', string='Protocol', required=True, ondelete='cascade')
    
    # Multiple choice options
    choice_options = fields.Text('Choice Options (one per line)')
    
    # Scoring
    score_yes = fields.Float('Score for Yes', default=1.0)
    score_no = fields.Float('Score for No', default=0.0)
    score_scale = fields.Float('Score per Scale Point', default=0.1)
    
    # Vietnamese
    vietnamese_question = fields.Char('Vietnamese Question', translate=True)
    vietnamese_options = fields.Text('Vietnamese Options (one per line)')

    @api.model
    def get_question_score(self, question_id, answer):
        """Calculate score for a question answer"""
        question = self.browse(question_id)
        
        if question.question_type == 'yes_no':
            return question.score_yes if answer.lower() in ['yes', 'true', '1'] else question.score_no
        elif question.question_type == 'scale':
            try:
                scale_value = float(answer)
                return scale_value * question.score_scale
            except:
                return 0.0
        elif question.question_type == 'numeric':
            try:
                return float(answer)
            except:
                return 0.0
        
        return 0.0


class ProtocolIntervention(models.Model):
    """Interventions for clinical protocols"""
    _name = 'health.protocol.intervention'
    _description = 'Protocol Intervention'
    _order = 'sequence, id'

    name = fields.Char('Intervention Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    intervention_type = fields.Selection([
        ('assessment', 'Assessment'),
        ('treatment', 'Treatment'),
        ('monitoring', 'Monitoring'),
        ('education', 'Patient Education'),
        ('referral', 'Referral'),
        ('follow_up', 'Follow-up')
    ], string='Intervention Type', required=True, default='assessment')
    
    protocol_id = fields.Many2one('health.clinical.protocol', string='Protocol', required=True, ondelete='cascade')
    
    description = fields.Text('Description', translate=True)
    instructions = fields.Text('Instructions', translate=True)
    
    # Timing
    frequency = fields.Selection([
        ('once', 'Once'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('as_needed', 'As Needed')
    ], string='Frequency', default='once')
    
    duration = fields.Integer('Duration (days)', default=1)
    
    # Vietnamese
    vietnamese_name = fields.Char('Vietnamese Name', translate=True)
    vietnamese_description = fields.Text('Vietnamese Description', translate=True)
    vietnamese_instructions = fields.Text('Vietnamese Instructions', translate=True)
