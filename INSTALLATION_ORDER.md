# VAFHS Healthcare Module Installation Order

## Critical Installation Sequence

**NEVER install modules out of order** - this will cause field definition errors like:
```
psycopg2.errors.UndefinedColumn: column res_partner.is_caregiver does not exist
```

### Required Installation Sequence

1. **health_base** - MUST INSTALL FIRST
   - Defines foundational healthcare fields on res.partner
   - Contains: is_patient, is_caregiver, is_payer, is_referrer, etc.

2. **health_fieldservice** - Install after health_base
   - Depends on health_base healthcare classifications
   - Contains appointment and service delivery models

3. **health_crm** - Install after health_base AND health_fieldservice  
   - References health_base fields in views and security rules
   - Integrates with health_fieldservice for appointments

4. **health_invoicing** - Install LAST
   - Depends on all previous modules
   - Integrates billing across the entire system

### Installation Commands
```bash
# Install in this exact order:
odoo-bin -i health_base -d your_database
odoo-bin -i health_fieldservice -d your_database  
odoo-bin -i health_crm -d your_database
odoo-bin -i health_invoicing -d your_database
```

### If You Get Field Definition Errors

If you see errors like:
```
psycopg2.errors.UndefinedColumn: column res_partner.is_caregiver does not exist
```

**IMMEDIATE FIX:**

1. **Run the schema fix SQL script**:
   ```bash
   psql -d your_database -f fix_database_schema.sql
   ```

2. **Update health_base module**:
   ```bash
   odoo-bin -u health_base -d your_database
   ```

**ALTERNATIVE: Manual module reinstall:**

1. **Uninstall all health modules** in reverse order:
   ```bash
   odoo-bin -u health_invoicing -d your_database
   odoo-bin -u health_crm -d your_database  
   odoo-bin -u health_fieldservice -d your_database
   odoo-bin -u health_base -d your_database
   ```

2. **Update the database schema**:
   ```bash
   odoo-bin -u base -d your_database
   ```

3. **Reinstall in correct order** (see above)

### Database Schema Dependencies

**health_base extends res.partner with:**
- is_caregiver, is_payer, is_referrer (referenced by health_crm)
- patient_code, patient_status (referenced by health_fieldservice)
- Healthcare classification fields (referenced by health_invoicing)

**Never modify health_base.res.partner fields without updating dependent modules!**