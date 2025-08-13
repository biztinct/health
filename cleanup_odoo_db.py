#!/usr/bin/env python3
"""
Clean up health module references from Odoo database
Run this with Odoo shell access
"""

import odoo
from odoo import api, SUPERUSER_ID

def cleanup_health_modules(database_name):
    """Clean up health module leftovers"""
    
    # Initialize Odoo registry
    registry = odoo.registry(database_name)
    
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        print("Starting health module cleanup...")
        
        # 1. Remove health module records
        modules = env['ir.module.module'].search([
            ('name', 'in', ['health_base', 'health_calendar', 'health_staff_assignment'])
        ])
        if modules:
            print(f"Removing {len(modules)} module records...")
            modules.unlink()
        
        # 2. Remove health model definitions
        health_models = env['ir.model'].search([('model', 'like', 'health.%')])
        if health_models:
            print(f"Removing {len(health_models)} model definitions...")
            health_models.unlink()
            
        # 3. Remove security rules with is_patient
        patient_rules = env['ir.rule'].search([('domain_force', 'like', '%is_patient%')])
        if patient_rules:
            print(f"Removing {len(patient_rules)} security rules...")
            patient_rules.unlink()
            
        # 4. Remove health model data
        health_data = env['ir.model.data'].search([
            ('module', 'in', ['health_base', 'health_calendar', 'health_staff_assignment'])
        ])
        if health_data:
            print(f"Removing {len(health_data)} data records...")
            health_data.unlink()
            
        # 5. Remove health model fields
        health_fields = env['ir.model.fields'].search([
            '|', ('model', 'like', 'health.%'),
            '|', ('name', 'like', '%patient%'),
            ('name', 'like', '%health%')
        ])
        if health_fields:
            print(f"Removing {len(health_fields)} field definitions...")
            health_fields.unlink()
        
        # Commit the changes
        cr.commit()
        print("✅ Health module cleanup completed successfully!")
        print("Please restart your Odoo server.")

if __name__ == "__main__":
    database_name = input("Enter your database name: ")
    cleanup_health_modules(database_name)