---
description: Deploy modules to VietUc UAT server and restart Odoo
---

// turbo-all

# Deploy to VietUc UAT

Use this workflow whenever you modify any `health_*` modules and need to deploy changes to the UAT server.

## Steps

1. Copy the modified module(s) to the UAT server using the `rd` script:
// turbo
```bash
cd /Users/adity/Documents/GitHub/health19/addons && ./rd <module_name>
```

Replace `<module_name>` with the actual module(s) modified, e.g.:
- `health_landing` - for landing dashboard changes
- `health_crm` - for CRM lead changes  
- `health_base` - for base model changes
- `all` - to copy all health_* modules

2. Restart the Odoo service on the UAT server:
// turbo
```bash
ssh VietUcUAT "sudo service odoo-server restart"
```

3. Wait for the server to come back up:
// turbo
```bash
sleep 15 && ssh VietUcUAT "sudo service odoo-server status" | head -10
```

4. Upgrade the module in Odoo (if XML views or data files changed):
   - Open browser and navigate to: https://care.biztinct.com/odoo/apps
   - Search for the module name (e.g., "health_base")
   - Click on the module dropdown (three dots or menu icon)
   - Click "Upgrade"
   - Wait for the upgrade to complete (page will reload)
   - If an error occurs, note the error message and fix the issue

## Combined Command Example

For a single module:
```bash
cd /Users/adity/Documents/GitHub/health19/addons && ./rd health_landing && ssh VietUcUAT "sudo service odoo-server restart"
```

For multiple modules:
```bash
cd /Users/adity/Documents/GitHub/health19/addons && ./rd health_crm health_landing && ssh VietUcUAT "sudo service odoo-server restart"
```

## Quick Deploy with Direct SCP (for single files)

If you need to deploy a single file quickly:
```bash
scp /path/to/file VietUcUAT:/odoo/odoo-server/addons/<module>/path/to/file
```

Example:
```bash
scp /Users/adity/Documents/GitHub/health19/addons/health_base/views/health_audit_log_views.xml VietUcUAT:/odoo/odoo-server/addons/health_base/views/
```

## Notes
- The `rd` script uses `scp` to copy files to `VietUcUAT:/odoo/odoo-server/addons/`
- After restart, verify changes in browser at the UAT URL
- Use `./rd list` to see available health modules
- **IMPORTANT**: If you modified XML views, you MUST upgrade the module in Odoo Apps for changes to take effect
- Python file changes take effect after server restart
- JavaScript/CSS changes may need a browser hard refresh (Ctrl+Shift+R)
