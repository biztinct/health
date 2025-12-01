import logging
import re

_logger = logging.getLogger(__name__)

_AMP_PATTERN = re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;)')


def _sanitize_translation_column(cr, column):
    query = f"""
        SELECT id, {column}
          FROM ir_translation
         WHERE name LIKE %s
           AND {column} LIKE %s
    """
    cr.execute(query, ('ir.ui.view,arch_db,health_fieldservice%', '%&%'))
    rows = cr.fetchall()
    updated = 0
    for record_id, value in rows:
        if not value:
            continue
        cleaned = _AMP_PATTERN.sub('&amp;', value)
        if cleaned != value:
            cr.execute(
                f"UPDATE ir_translation SET {column}=%s WHERE id=%s",
                (cleaned, record_id),
            )
            updated += 1
    if updated:
        _logger.info(
            "Sanitized %s translations in column %s for health_fieldservice views",
            updated,
            column,
        )


def pre_init_hook(cr):
    """Ensure existing translations do not contain raw ampersands."""
    _sanitize_translation_column(cr, 'value')
    _sanitize_translation_column(cr, 'src')


def post_init_hook(env):
    """Migrate users from obsolete roles to new health_base roles."""
    _logger.info("Starting migration of obsolete healthcare roles...")

    # Map Old Group Name -> New Group External ID
    role_mapping = {
        # Staff Assignment Roles
        'Assignment System Manager': 'health_base.group_healthcare_operations_manager',
        'Healthcare Sales User': 'health_base.group_healthcare_sales',
        'Operations Manager': 'health_base.group_healthcare_operations_manager',
        'Head Nurse': 'health_base.group_healthcare_head_nurse',
        'Healthcare Staff': 'health_base.group_healthcare_nurse',
        
        # Field Service Manager Roles
        'Field Service Manager': 'health_base.group_healthcare_operations_manager',
        'Equipment Manager': 'health_base.group_healthcare_operations_manager',
        'Clinical Protocol Manager': 'health_base.group_healthcare_operations_manager',
        
        # Field Service Staff Roles
        'Field Service User': 'health_base.group_healthcare_nurse',
        'Field Service Staff': 'health_base.group_healthcare_nurse',
        'Field Service Dispatcher': 'health_base.group_healthcare_operations_manager',
    }

    for old_name, new_xml_id in role_mapping.items():
        # 1. Find the old group
        old_group = env['res.groups'].search([('name', '=', old_name)], limit=1)
        if not old_group:
            continue

        # 2. Find the new group
        new_group = env.ref(new_xml_id, raise_if_not_found=False)
        if not new_group:
            _logger.warning(f"New group {new_xml_id} not found. Skipping migration for {old_name}.")
            continue

        # 3. Migrate users
        users_to_migrate = old_group.users - new_group.users
        if users_to_migrate:
            _logger.info(f"Migrating {len(users_to_migrate)} users from '{old_name}' to '{new_group.name}'")
            new_group.write({'users': [(4, user.id) for user in users_to_migrate]})

        # 4. Delete the old group
        _logger.info(f"Deleting obsolete group '{old_name}'")
        old_group.unlink()

    _logger.info("Role migration completed successfully.")
