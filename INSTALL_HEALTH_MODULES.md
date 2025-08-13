# Health Modules Installation Guide

## Step 1: Clean Database (IMPORTANT!)

Before installing the health modules, you MUST clean the database of any previous health module traces:

```sql
-- Connect to your database and run:
psql -d your_database_name -f complete_health_cleanup.sql
```

## Step 2: Restart Odoo Server

After running the cleanup, restart your Odoo server completely.

## Step 3: Install Modules in Correct Order

**CRITICAL**: Install modules in this exact order to avoid dependency issues:

1. **First**: Install `health_base` 
   - Go to Apps → Update Apps List
   - Search for "Healthcare Base"  
   - Click Install

2. **Second**: Install `health_calendar` (only after health_base is fully installed)
   - Search for "Healthcare Calendar"
   - Click Install

3. **Third**: Install `health_staff_assignment` (only after both above are installed)
   - Search for "Healthcare Staff Assignment" 
   - Click Install

## Step 4: If You Get Errors

If you encounter any errors during installation:

1. **Stop the Odoo server**
2. **Run the cleanup SQL again**
3. **Restart Odoo server**
4. **Try installing modules one by one in the correct order**

## Common Issues & Solutions

### "duplicate key value violates unique constraint"
- **Solution**: Run the cleanup SQL script again and restart Odoo

### "No matching record found for external id"
- **Solution**: Make sure you're installing modules in the correct order (base → calendar → staff_assignment)

### "Invalid field res.partner.is_patient"
- **Solution**: Run the cleanup SQL script to remove leftover field references

## Module Versions
- health_base: 18.0.3.0.0
- health_calendar: 18.0.3.0.0  
- health_staff_assignment: (original version)

## Support

If you still encounter issues, the modules have been designed to be independent. You can:
1. Install only `health_base` first and test
2. Then add `health_calendar` if base works
3. Finally add `health_staff_assignment` if needed