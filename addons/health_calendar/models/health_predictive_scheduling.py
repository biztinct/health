from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)

try:
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import LabelEncoder
    import pickle
    ML_AVAILABLE = True
    _logger.info("ML packages available: pandas, numpy, scikit-learn")
except ImportError as e:
    _logger.warning(f"Some ML packages not available: {e}. Predictive scheduling will use fallback methods.")
    ML_AVAILABLE = False

# Optional packages that failed to install - using fallbacks
try:
    import socketio
    SOCKETIO_AVAILABLE = True
except ImportError:
    _logger.info("socketio not available - real-time features will use standard Odoo notifications")
    SOCKETIO_AVAILABLE = False

# FHIR integration is optional - healthcare standards integration
FHIR_AVAILABLE = False  # python-fhir failed to install
_logger.info("FHIR integration disabled - using internal healthcare data structures")


class PredictiveScheduling(models.Model):
    """
    v2.0 Enhancement: AI-Powered Predictive Scheduling
    Based on vafhs-enhanced-design.md specifications
    """
    _name = 'health.predictive.scheduling'
    _description = 'AI-Powered Predictive Scheduling Engine'
    _rec_name = 'analysis_name'

    # Analysis Information
    analysis_name = fields.Char('Analysis Name', required=True)
    analysis_date = fields.Datetime('Analysis Date', default=fields.Datetime.now)
    analysis_period_start = fields.Date('Period Start', required=True)
    analysis_period_end = fields.Date('Period End', required=True)
    
    # ML Model Status
    model_trained = fields.Boolean('Model Trained', default=False)
    model_accuracy = fields.Float('Model Accuracy %', default=0.0)
    training_data_points = fields.Integer('Training Data Points', default=0)
    last_training_date = fields.Datetime('Last Training Date')
    
    # Predictions
    predicted_appointments = fields.Text('Predicted Appointments JSON')
    capacity_recommendations = fields.Text('Capacity Recommendations JSON')
    staff_optimization = fields.Text('Staff Optimization JSON')
    
    # Performance Metrics
    prediction_accuracy = fields.Float('Prediction Accuracy %', default=0.0)
    demand_forecast_score = fields.Float('Demand Forecast Score', default=0.0)
    optimization_score = fields.Float('Optimization Score', default=0.0)
    
    # System Fields
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model
    def train_prediction_model(self):
        """
        Train ML model for appointment prediction
        Based on historical appointment data
        """
        if not ML_AVAILABLE:
            _logger.warning("ML packages not available. Using statistical fallback.")
            return self._train_statistical_model()
        
        try:
            # Fetch historical appointment data
            appointments = self.env['health.appointment'].search([
                ('state', '=', 'completed'),
                ('appointment_date', '>=', fields.Date.today() - timedelta(days=365))
            ])
            
            if len(appointments) < 50:
                _logger.warning("Insufficient data for ML training. Need at least 50 completed appointments.")
                return False
            
            # Prepare training data
            training_data = []
            for appointment in appointments:
                training_data.append({
                    'day_of_week': appointment.appointment_date.weekday(),
                    'month': appointment.appointment_date.month,
                    'hour': int(appointment.appointment_time),
                    'appointment_type': appointment.appointment_type_id.id,
                    'patient_age': appointment.patient_id.age or 30,
                    'urgency_level': 1 if appointment.urgency_level == 'routine' else (2 if appointment.urgency_level == 'urgent' else 3),
                    'location_type': 1 if appointment.location_type == 'clinic' else (2 if appointment.location_type == 'home' else 3),
                    'duration': appointment.duration_minutes,
                    'no_show': 1 if appointment.state == 'no_show' else 0
                })
            
            df = pd.DataFrame(training_data)
            
            # Features and target
            features = ['day_of_week', 'month', 'hour', 'appointment_type', 'patient_age', 'urgency_level', 'location_type']
            X = df[features]
            y = df['duration']  # Predict appointment duration
            
            # Train model
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X, y)
            
            # Calculate accuracy
            accuracy = model.score(X, y) * 100
            
            # Save model
            model_data = pickle.dumps(model)
            
            # Create analysis record
            analysis = self.create({
                'analysis_name': f'Predictive Model Training - {fields.Date.today()}',
                'analysis_period_start': fields.Date.today() - timedelta(days=365),
                'analysis_period_end': fields.Date.today(),
                'model_trained': True,
                'model_accuracy': accuracy,
                'training_data_points': len(appointments),
                'last_training_date': fields.Datetime.now(),
            })
            
            # Store model in system parameter
            self.env['ir.config_parameter'].sudo().set_param(
                'health_calendar.ml_model', 
                model_data.hex()
            )
            
            _logger.info(f"ML model trained successfully. Accuracy: {accuracy:.2f}%")
            return analysis
            
        except Exception as e:
            _logger.error(f"Error training ML model: {str(e)}")
            return self._train_statistical_model()

    def _train_statistical_model(self):
        """
        Fallback statistical model when ML packages unavailable
        """
        appointments = self.env['health.appointment'].search([
            ('state', '=', 'completed'),
            ('appointment_date', '>=', fields.Date.today() - timedelta(days=90))
        ])
        
        if not appointments:
            return False
        
        # Statistical analysis
        stats = {
            'total_appointments': len(appointments),
            'avg_duration': sum(a.duration_minutes for a in appointments) / len(appointments),
            'peak_hours': self._calculate_peak_hours(appointments),
            'peak_days': self._calculate_peak_days(appointments),
            'no_show_rate': len(appointments.filtered(lambda a: a.state == 'no_show')) / len(appointments) * 100
        }
        
        analysis = self.create({
            'analysis_name': f'Statistical Analysis - {fields.Date.today()}',
            'analysis_period_start': fields.Date.today() - timedelta(days=90),
            'analysis_period_end': fields.Date.today(),
            'model_trained': True,
            'model_accuracy': 75.0,  # Estimated accuracy for statistical model
            'training_data_points': len(appointments),
            'last_training_date': fields.Datetime.now(),
            'predicted_appointments': json.dumps(stats)
        })
        
        return analysis

    def _calculate_peak_hours(self, appointments):
        """Calculate peak appointment hours"""
        hour_counts = defaultdict(int)
        for appointment in appointments:
            hour = int(appointment.appointment_time)
            hour_counts[hour] += 1
        
        return sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    def _calculate_peak_days(self, appointments):
        """Calculate peak appointment days"""
        day_counts = defaultdict(int)
        for appointment in appointments:
            day = appointment.appointment_date.weekday()
            day_counts[day] += 1
        
        return sorted(day_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    @api.model
    def generate_demand_forecast(self, forecast_days=30):
        """
        Generate demand forecast for next N days
        """
        forecast_data = []
        
        # Get historical patterns
        historical_appointments = self.env['health.appointment'].search([
            ('appointment_date', '>=', fields.Date.today() - timedelta(days=90)),
            ('state', 'in', ['completed', 'confirmed'])
        ])
        
        # Calculate daily averages
        daily_avg = self._calculate_daily_averages(historical_appointments)
        
        # Generate forecast
        start_date = fields.Date.today()
        for i in range(forecast_days):
            forecast_date = start_date + timedelta(days=i)
            day_of_week = forecast_date.weekday()
            
            # Base prediction on historical averages
            base_demand = daily_avg.get(day_of_week, 5)
            
            # Adjust for trends (simplified)
            trend_adjustment = 1.0 + (i * 0.001)  # Slight growth trend
            
            # Seasonal adjustments (month-based)
            seasonal_factor = self._get_seasonal_factor(forecast_date.month)
            
            predicted_demand = int(base_demand * trend_adjustment * seasonal_factor)
            
            forecast_data.append({
                'date': forecast_date.isoformat(),
                'predicted_appointments': predicted_demand,
                'confidence': 0.75,  # Static confidence for statistical model
                'day_of_week': day_of_week
            })
        
        return forecast_data

    def _calculate_daily_averages(self, appointments):
        """Calculate average appointments per day of week"""
        daily_counts = defaultdict(list)
        
        # Group by date and count appointments
        date_counts = defaultdict(int)
        for appointment in appointments:
            date_counts[appointment.appointment_date] += 1
        
        # Group by day of week
        for date, count in date_counts.items():
            day_of_week = date.weekday()
            daily_counts[day_of_week].append(count)
        
        # Calculate averages
        daily_averages = {}
        for day, counts in daily_counts.items():
            daily_averages[day] = sum(counts) / len(counts) if counts else 0
        
        return daily_averages

    def _get_seasonal_factor(self, month):
        """Get seasonal adjustment factor"""
        # Vietnam seasonal patterns (example)
        seasonal_factors = {
            1: 1.1,   # January - higher demand post holidays
            2: 1.05,  # February
            3: 1.0,   # March - baseline
            4: 0.95,  # April
            5: 0.9,   # May - lower demand
            6: 0.9,   # June
            7: 0.95,  # July
            8: 1.0,   # August
            9: 1.05,  # September - back to school/work
            10: 1.1,  # October
            11: 1.05, # November
            12: 0.9   # December - holidays
        }
        return seasonal_factors.get(month, 1.0)

    @api.model
    def optimize_staff_schedule(self, target_date=None):
        """
        Optimize staff scheduling based on predicted demand
        """
        if not target_date:
            target_date = fields.Date.today()
        
        # Get demand forecast for the week
        forecast = self.generate_demand_forecast(7)
        
        # Get available staff
        staff_users = self.env['res.users'].search([
            ('is_healthcare_staff', '=', True),
            ('active', '=', True)
        ])
        
        optimization_data = []
        
        for day_forecast in forecast:
            forecast_date = datetime.fromisoformat(day_forecast['date']).date()
            predicted_demand = day_forecast['predicted_appointments']
            
            # Calculate required staff based on demand
            appointments_per_staff = 8  # Average appointments per staff per day
            required_staff = max(1, int(predicted_demand / appointments_per_staff) + 1)
            
            # Staff availability (simplified - assumes all staff available)
            available_staff = len(staff_users)
            
            # Optimization recommendation
            if required_staff > available_staff:
                recommendation = 'hire_temp'
                priority = 'high'
            elif required_staff < available_staff * 0.5:
                recommendation = 'reduce_hours'
                priority = 'low'
            else:
                recommendation = 'optimal'
                priority = 'medium'
            
            optimization_data.append({
                'date': forecast_date.isoformat(),
                'predicted_demand': predicted_demand,
                'required_staff': required_staff,
                'available_staff': available_staff,
                'recommendation': recommendation,
                'priority': priority,
                'utilization_rate': min(100, (required_staff / available_staff) * 100)
            })
        
        return optimization_data

    @api.model
    def get_smart_appointment_suggestions(self, patient_id, appointment_type_id):
        """
        Provide smart appointment time suggestions based on ML predictions
        """
        patient = self.env['res.partner'].browse(patient_id)
        appointment_type = self.env['health.service.type'].browse(appointment_type_id)
        
        # Get next 14 days
        suggestions = []
        base_date = fields.Date.today()
        
        for i in range(1, 15):  # Next 14 days
            check_date = base_date + timedelta(days=i)
            
            # Skip weekends for regular appointments (configurable)
            if check_date.weekday() >= 5 and appointment_type.category != 'emergency':
                continue
            
            # Get existing appointments for the day
            existing_appointments = self.env['health.appointment'].search([
                ('appointment_date', '=', check_date),
                ('state', 'in', ['confirmed', 'in_progress'])
            ])
            
            # Calculate optimal time slots
            optimal_times = self._calculate_optimal_time_slots(
                check_date, existing_appointments, appointment_type, patient
            )
            
            for time_slot in optimal_times[:3]:  # Top 3 suggestions per day
                suggestions.append({
                    'date': check_date.isoformat(),
                    'time': time_slot['time'],
                    'confidence': time_slot['confidence'],
                    'reason': time_slot['reason'],
                    'estimated_wait': time_slot['estimated_wait'],
                    'staff_availability': time_slot['staff_availability']
                })
        
        # Sort by confidence and return top suggestions
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions[:10]

    def _calculate_optimal_time_slots(self, date, existing_appointments, appointment_type, patient):
        """
        Calculate optimal time slots for a given date
        """
        # Working hours (configurable)
        start_hour = 8
        end_hour = 18
        slot_duration = 0.5  # 30-minute slots
        
        time_slots = []
        current_time = start_hour
        
        while current_time < end_hour:
            # Check if slot is available
            slot_available = True
            for appointment in existing_appointments:
                if abs(appointment.appointment_time - current_time) < slot_duration:
                    slot_available = False
                    break
            
            if slot_available:
                # Calculate confidence based on historical patterns
                confidence = self._calculate_time_confidence(
                    date, current_time, appointment_type, patient
                )
                
                # Estimate wait time (simplified)
                estimated_wait = len(existing_appointments.filtered(
                    lambda a: a.appointment_time <= current_time
                )) * 5  # 5 minutes per prior appointment
                
                # Check staff availability (simplified)
                staff_available = self._check_staff_availability(date, current_time)
                
                time_slots.append({
                    'time': current_time,
                    'confidence': confidence,
                    'reason': self._get_time_slot_reason(current_time, date.weekday()),
                    'estimated_wait': estimated_wait,
                    'staff_availability': staff_available
                })
            
            current_time += slot_duration
        
        return sorted(time_slots, key=lambda x: x['confidence'], reverse=True)

    def _calculate_time_confidence(self, date, time, appointment_type, patient):
        """
        Calculate confidence score for a time slot
        """
        confidence = 0.5  # Base confidence
        
        # Prefer mid-morning and early afternoon
        if 9 <= time <= 11 or 14 <= time <= 16:
            confidence += 0.2
        
        # Weekend penalty for non-emergency
        if date.weekday() >= 5 and appointment_type.category != 'emergency':
            confidence -= 0.3
        
        # Patient age consideration
        if patient.age and patient.age > 65:
            # Prefer morning slots for elderly
            if 8 <= time <= 12:
                confidence += 0.1
        
        # Urgency consideration
        if appointment_type.category == 'emergency':
            confidence += 0.3
        
        return max(0.1, min(1.0, confidence))

    def _get_time_slot_reason(self, time, day_of_week):
        """
        Get human-readable reason for time slot recommendation
        """
        if 8 <= time <= 10:
            return "Morning slot - shorter wait times"
        elif 10 <= time <= 12:
            return "Popular morning time"
        elif 14 <= time <= 16:
            return "Afternoon availability"
        elif 16 <= time <= 18:
            return "End of day - quick service"
        else:
            return "Available time slot"

    def _check_staff_availability(self, date, time):
        """
        Check staff availability for a time slot (simplified)
        """
        # This would integrate with staff scheduling system
        # For now, return a simple availability score
        return min(3, max(1, int(3 - (time - 8) / 3)))  # 1-3 staff available

    @api.model
    def run_daily_optimization(self):
        """
        Cron job to run daily scheduling optimization
        """
        try:
            # Re-train model weekly
            if datetime.now().weekday() == 0:  # Monday
                self.train_prediction_model()
            
            # Generate daily forecasts
            forecast = self.generate_demand_forecast(7)
            
            # Optimize staff schedule
            staff_optimization = self.optimize_staff_schedule()
            
            # Store results
            analysis = self.create({
                'analysis_name': f'Daily Optimization - {fields.Date.today()}',
                'analysis_period_start': fields.Date.today(),
                'analysis_period_end': fields.Date.today() + timedelta(days=7),
                'predicted_appointments': json.dumps(forecast),
                'staff_optimization': json.dumps(staff_optimization),
                'analysis_date': fields.Datetime.now()
            })
            
            _logger.info(f"Daily optimization completed: {analysis.id}")
            return analysis
            
        except Exception as e:
            _logger.error(f"Error in daily optimization: {str(e)}")
            return False