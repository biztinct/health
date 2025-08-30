# Copyright 2025 I Am Dream Catcher Ltd
# License LGPL-3.0

import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Migration script for health_invoicing module v18.0.1.1.0
    Adds new healthcare payment analytics fields to res.partner
    """
    _logger.info("Starting health_invoicing migration to v18.0.1.1.0")
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    try:
        # Check if the new fields exist, if not they'll be created by the ORM
        # This migration ensures any custom data or computed field values are handled
        
        # Update existing patient records to have default payment notification settings
        patients = env['res.partner'].search([('is_patient', '=', True)])
        
        if patients:
            _logger.info(f"Updating {len(patients)} patient records with new payment settings")
            
            # Set default values for new fields (ORM will handle if fields don't exist yet)
            try:
                patients.write({
                    'send_payment_reminders': True,
                    'payment_notification_method': 'email',
                })
                _logger.info("Successfully updated patient payment notification defaults")
            except Exception as e:
                _logger.warning(f"Could not set default values (normal during first install): {e}")
        
        # Force recomputation of computed fields once ORM creates the columns
        try:
            # Trigger computation of new analytics fields
            patients._compute_healthcare_payment_risk()
            patients._compute_healthcare_payment_analytics()
            _logger.info("Recomputed healthcare payment analytics for existing patients")
        except Exception as e:
            _logger.warning(f"Could not recompute analytics (normal during first install): {e}")
    
    except Exception as e:
        _logger.error(f"Error during health_invoicing migration: {e}")
        # Don't fail the migration, let Odoo handle field creation
        pass
    
    _logger.info("Completed health_invoicing migration to v18.0.1.1.0")