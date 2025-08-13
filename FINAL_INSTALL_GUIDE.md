# FINAL Health Modules Installation Guide

## CRITICAL: Complete Database Cleanup First

**You MUST run this thorough cleanup before attempting installation:**

```bash
# Stop your Odoo server first
sudo systemctl stop odoo  # or however you stop your server

# Run the thorough cleanup
psql -d your_database_name -f thorough_cleanup.sql

# Restart your Odoo server
sudo systemctl start odoo  # or however you start your server
```

## Installation Steps (EXACT ORDER)

### Step 1: Install health_base ONLY
1. Go to Apps → Update Apps List
2. Search for "Healthcare Base"
3. Install it and **WAIT** for it to complete fully
4. **DO NOT** install any other health modules yet

### Step 2: Verify health_base Installation
- Check that there are no errors
- Verify you can see "Healthcare" menu in the main menu
- If there are any errors, **STOP** and run the cleanup again

### Step 3: Install health_calendar (Optional)
1. Only after health_base is working perfectly
2. Search for "Healthcare Calendar"
3. Install it

### Step 4: Install health_staff_assignment (Optional)
1. Only after both previous modules are working
2. Search for "Healthcare Staff Assignment"
3. Install it

## What Was Fixed

1. **Removed duplicate medical specialties** from health_calendar
2. **Removed cross-module dependencies** that caused conflicts
3. **Updated module versions** for clean installation
4. **Created thorough database cleanup** to remove all traces

## Module Versions
- health_base: 18.0.3.0.0
- health_calendar: 18.0.3.1.0 (fixed duplicate data issue)

## If You Still Get Errors

1. **Always run the thorough cleanup first**
2. **Install only health_base initially**
3. **Test that health_base works before adding others**
4. **If health_base fails, the cleanup wasn't thorough enough**

## Success Criteria

After installing health_base, you should see:
- No errors in the log
- "Healthcare" menu appears
- You can create patient categories
- You can create medical specialties
- No "duplicate key" or "field not found" errors

## Emergency Fallback

If nothing works:
1. Create a completely fresh database
2. Install only health_base on the fresh database
3. Test that it works before migrating data