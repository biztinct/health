# Quick Installation Test Guide

## ✅ **Fixed Issues for Clean Installation**

### **1. CSV File Format Fixed**
- Removed empty lines and comments from `ir.model.access.csv`
- Clean CSV format without parsing issues

### **2. Simplified Manifest**
- Commented out complex data files temporarily  
- Removed non-existent demo files
- Simplified asset loading
- Minimal appointment extension

### **3. HR Skills Conflict Resolved**
- Uses `healthcare_skill_ids` instead of `skill_ids`
- No conflicts with existing HR modules

## 🚀 **Installation Steps**

### **Step 1: Basic Installation**
```bash
# Install the core module
./odoo-bin -d your_database -i health_staff_assignment

# Or via Odoo UI:
# Apps → Update Apps List → Search "VAFHS Staff Assignment" → Install
```

### **Step 2: Verify Installation**
1. **Check for Errors**: Look for any installation errors in logs
2. **Menu Access**: Should see "Staff Assignment" in main menu
3. **Basic Models**: Should be able to access:
   - Staff Assignment → Staff Assignments
   - Staff Assignment → Staff Availability
   - Staff Assignment → Assignment Dashboard

### **Step 3: Basic Testing**
1. **Create Healthcare Staff**:
   - Go to Employees
   - Edit an employee
   - Check "Healthcare Staff" checkbox
   - Select Healthcare Role

2. **Create Basic Assignment**:
   - Go to Staff Assignment → Staff Assignments
   - Create new record
   - Select appointment and staff

3. **View Dashboard**:
   - Go to Staff Assignment → Assignment Dashboard  
   - Should see Kanban board interface

## 🔧 **If Installation Still Fails**

### **Most Common Issues & Solutions:**

**Issue 1: Model Access Errors**
```
Solution: Check user has "Assignment System Manager" group
```

**Issue 2: View Inheritance Errors**  
```
Solution: Ensure health_calendar module is installed first
```

**Issue 3: Field Errors**
```
Solution: Check if health.appointment model has required fields
```

**Issue 4: JavaScript Errors**
```
Solution: Clear browser cache, restart Odoo server
```

### **Emergency Minimal Installation:**
If still having issues, try installing with only core models:

1. Comment out ALL view files in manifest except core models
2. Install just the Python models first
3. Add views back one by one

## 📋 **Post-Installation Checklist**

- [ ] Module installed without errors
- [ ] "Staff Assignment" menu appears
- [ ] Can create staff assignment records
- [ ] Can view assignment dashboard
- [ ] Healthcare staff fields work
- [ ] No conflicts with existing modules

## 🎯 **Success Indicators**

✅ **Installation Complete When:**
- No error messages in Odoo logs
- Staff Assignment menu visible
- Can create and view assignments
- Dashboard loads without JavaScript errors
- Healthcare staff can be configured

## 🔄 **Next Steps After Successful Installation**

1. **Re-enable Advanced Features**:
   - Uncomment data files in manifest
   - Re-enable full appointment views
   - Add demo data

2. **Configure System**:
   - Set up user groups
   - Configure healthcare staff
   - Test assignment workflow

3. **Phase 2 Development**:
   - Real-time notifications
   - Google Maps integration  
   - Mobile PWA features
   - Analytics dashboard

The module is now optimized for clean installation! 🚀