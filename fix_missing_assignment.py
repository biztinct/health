#!/usr/bin/env python3
"""
Script to clean up orphaned references to deleted health.staff.assignment records

Usage:
    python3 fix_missing_assignment.py

Or run directly in Odoo shell:
    odoo-bin shell -d your_database -c your_config.conf
"""

# If running in Odoo shell, you already have 'env' available
# Otherwise, you need to set up the Odoo environment

def cleanup_orphaned_assignment_references(env):
    """Clean up orphaned references to deleted staff assignments"""

    print("Cleaning up orphaned staff assignment references...")

    # 1. Clear user actions/filters that might reference deleted records
    print("\n1. Checking user filters...")
    filters = env['ir.filters'].search([
        ('model_id', '=', 'health.staff.assignment')
    ])
    for filter_rec in filters:
        try:
            # Try to evaluate the domain - if it fails, delete the filter
            if filter_rec.domain:
                env['health.staff.assignment'].search_count(eval(filter_rec.domain))
        except Exception as e:
            print(f"   Removing broken filter: {filter_rec.name} - {e}")
            filter_rec.unlink()

    # 2. Clear any actions that reference specific deleted records
    print("\n2. Checking actions...")
    actions = env['ir.actions.act_window'].search([
        ('res_model', '=', 'health.staff.assignment')
    ])
    for action in actions:
        if action.res_id and action.res_id not in env['health.staff.assignment'].search([]).ids:
            print(f"   Clearing res_id from action: {action.name}")
            action.write({'res_id': False})

    # 3. Check for orphaned references in related models
    print("\n3. Checking related models...")

    # Check FSO assignments
    if env['ir.model'].search([('model', '=', 'health.fieldservice.order')]):
        fsos = env['health.fieldservice.order'].search([
            ('assignment_id', '!=', False)
        ])
        valid_assignment_ids = env['health.staff.assignment'].search([]).ids
        for fso in fsos:
            if fso.assignment_id.id not in valid_assignment_ids:
                print(f"   Clearing orphaned assignment from FSO: {fso.name}")
                fso.write({'assignment_id': False})

    print("\n✓ Cleanup complete!")
    print("\nPlease clear your browser cache and refresh the page.")

# If running in Odoo shell:
# cleanup_orphaned_assignment_references(env)
