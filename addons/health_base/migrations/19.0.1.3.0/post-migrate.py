import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migrate healthcare_role data to access_role flags + boolean qualifiers."""
    _logger.info("Starting healthcare_role → access_role migration")

    # Add new columns if they don't exist yet (ORM may not have run yet)
    for col in ('is_duty_doctor', 'is_head_nurse', 'is_doctor_role', 'is_nurse_role',
                'is_om_role', 'access_role_display', 'access_role_id'):
        cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'hr_employee' AND column_name = %s
        """, (col,))
        if not cr.fetchone():
            if col in ('is_duty_doctor', 'is_head_nurse', 'is_doctor_role', 'is_nurse_role', 'is_om_role'):
                cr.execute(f"ALTER TABLE hr_employee ADD COLUMN {col} BOOLEAN DEFAULT FALSE")
            elif col == 'access_role_display':
                cr.execute(f"ALTER TABLE hr_employee ADD COLUMN {col} VARCHAR")
            elif col == 'access_role_id':
                cr.execute(f"ALTER TABLE hr_employee ADD COLUMN {col} INTEGER")

    for col in ('is_duty_doctor', 'is_head_nurse', 'is_doctor_role', 'is_nurse_role'):
        cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'res_users' AND column_name = %s
        """, (col,))
        if not cr.fetchone():
            cr.execute(f"ALTER TABLE res_users ADD COLUMN {col} BOOLEAN DEFAULT FALSE")

    # 1. Set is_duty_doctor from healthcare_role
    cr.execute("""
        UPDATE hr_employee SET is_duty_doctor = TRUE
        WHERE healthcare_role = 'duty_doctor'
    """)
    _logger.info("Set is_duty_doctor on %d employees", cr.rowcount)

    # 2. Set is_head_nurse from healthcare_role
    cr.execute("""
        UPDATE hr_employee SET is_head_nurse = TRUE
        WHERE healthcare_role = 'head_nurse'
    """)
    _logger.info("Set is_head_nurse on %d employees", cr.rowcount)

    # 3. Propagate to res_users
    cr.execute("""
        UPDATE res_users u SET is_duty_doctor = TRUE
        FROM hr_employee e
        WHERE e.user_id = u.id AND e.is_duty_doctor = TRUE
    """)
    cr.execute("""
        UPDATE res_users u SET is_head_nurse = TRUE
        FROM hr_employee e
        WHERE e.user_id = u.id AND e.is_head_nurse = TRUE
    """)

    # 4. Populate access_role_id on hr_employee from linked user
    cr.execute("""
        UPDATE hr_employee e
        SET access_role_id = u.access_role_id
        FROM res_users u
        WHERE e.user_id = u.id AND u.access_role_id IS NOT NULL
    """)
    _logger.info("Set access_role_id on %d employees", cr.rowcount)

    # 5. Populate computed role flags from access_role name
    cr.execute("""
        SELECT id, name FROM access_role
    """)
    if cr.description:
        roles = cr.fetchall()
        for role_id, role_name in roles:
            name_lower = (role_name or '').lower()
            cr.execute("""
                UPDATE hr_employee
                SET access_role_display = %s,
                    is_doctor_role = %s,
                    is_nurse_role = %s,
                    is_om_role = %s
                WHERE access_role_id = %s
            """, (
                role_name,
                'doctor' in name_lower,
                'nurse' in name_lower,
                'operations manager' in name_lower,
                role_id,
            ))

    # 6. Populate is_doctor_role / is_nurse_role on res_users
    cr.execute("""
        UPDATE res_users u
        SET is_doctor_role = e.is_doctor_role,
            is_nurse_role = e.is_nurse_role
        FROM hr_employee e
        WHERE e.user_id = u.id
    """)

    _logger.info("Healthcare role migration completed")
