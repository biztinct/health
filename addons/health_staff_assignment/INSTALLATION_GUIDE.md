# VAFHS Staff Assignment System - Installation Guide

## 🔧 **Installation Steps**

### **1. Prerequisites Check**
```bash
# Ensure health_calendar module is installed first
# This module extends health_calendar functionality
```

### **2. Install Module**
1. **Via Odoo Interface:**
   - Go to Apps menu
   - Click "Update Apps List" 
   - Search for "VAFHS Staff Assignment"
   - Click Install

2. **Via Command Line:**
   ```bash
   # Install with dependencies
   ./odoo-bin -d your_database -i health_staff_assignment
   ```

### **3. Post-Installation Setup**

#### **Create User Groups:**
- Go to Settings → Users & Companies → Groups
- Verify these groups were created:
  - Healthcare Sales User
  - Operations Manager
  - Head Nurse
  - Healthcare Staff
  - Assignment System Manager

#### **Setup Healthcare Staff:**
1. Go to Employees menu
2. Edit employee records
3. Check "Healthcare Staff" checkbox
4. Select Healthcare Role (Doctor, Nurse, etc.)
5. Add Healthcare Skills
6. Configure service areas

#### **Configure Service Areas:**
1. Go to Staff Assignment → Configuration → Service Areas
2. Review Ho Chi Minh City districts (pre-loaded)
3. Adjust travel fees and coverage areas as needed

### **4. Testing the Installation**

#### **Basic Functionality Test:**
1. **Access Dashboard:**
   - Go to Staff Assignment → Assignment Dashboard
   - Should see Kanban board interface

2. **Create Test Assignment:**
   - Create a test appointment in health_calendar
   - Go through assignment workflow:
     - Sales Review → Ops Review → Head Nurse Assignment

3. **Test AI Suggestions:**
   - When assigning staff, click "Assign Staff" button
   - Should see AI-powered staff suggestions with scores

#### **Mobile Interface Test:**
1. Access dashboard on mobile device or browser dev tools
2. Test touch interactions and responsive design
3. Verify cards stack properly on small screens

### **5. Common Issues & Solutions**

#### **Issue: HR Skills Conflict**
```
ValueError: Wrong value for hr.employee.skill_ids
```
**Solution:** This is fixed in the latest version. The module uses `healthcare_skill_ids` instead of `skill_ids` to avoid conflicts.

#### **Issue: Missing Menus**
**Solution:** Ensure user has proper group permissions:
- Assign users to "Healthcare Staff" or "Assignment System Manager" groups

#### **Issue: JavaScript Not Loading**
**Solution:** Clear browser cache and restart Odoo server:
```bash
# Clear assets
./odoo-bin -d your_database --update=health_staff_assignment
```

### **6. Initial Demo Data**

The module includes demo data:
- **Healthcare Skills:** Medical, Nursing, Technical, Language skills
- **Service Areas:** Ho Chi Minh City districts with travel fees
- **Email Templates:** Professional assignment notifications

### **7. User Roles & Permissions**

| Role | Permissions | Typical Users |
|------|-------------|---------------|
| **Sales User** | Approve appointments for ops review | Sales team members |
| **Operations Manager** | Review and approve for head nurse | Operations managers |
| **Head Nurse** | Assign staff to appointments | Head nurses, supervisors |
| **Healthcare Staff** | View and update own assignments | Doctors, nurses, technicians |
| **Assignment Manager** | Full system access and analytics | IT admins, system managers |

### **8. Configuration Checklist**

- [ ] health_calendar module installed and working
- [ ] User groups created and assigned
- [ ] Healthcare staff records configured
- [ ] Service areas defined for your coverage area  
- [ ] Email server configured for notifications
- [ ] Demo data reviewed and customized
- [ ] Mobile interface tested
- [ ] Assignment workflow tested end-to-end

### **9. Next Steps (Phase 2)**

Once basic installation is working:
1. **Real-time Notifications** - Configure SMS/email providers
2. **Google Maps Integration** - Add API keys for route optimization
3. **Mobile PWA** - Enable push notifications
4. **Analytics Dashboard** - Set up performance monitoring

### **10. Support**

If you encounter issues:
1. Check the error logs in Odoo
2. Verify all dependencies are installed
3. Ensure user permissions are correct
4. Review the `DEVELOPMENT_ROADMAP.md` for known limitations

**The system is designed to be production-ready with enterprise-grade security and performance!** 🚀