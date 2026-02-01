---
description: Deploy modules to VietUc UAT server and restart Odoo
---

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

## Combined Command Example

For a single module:
```bash
cd /Users/adity/Documents/GitHub/health19/addons && ./rd health_landing && ssh VietUcUAT "sudo service odoo-server restart"
```

For multiple modules:
```bash
cd /Users/adity/Documents/GitHub/health19/addons && ./rd health_crm health_landing && ssh VietUcUAT "sudo service odoo-server restart"
```

## Notes
- The `rd` script uses `scp` to copy files to `VietUcUAT:/odoo/odoo-server/addons/`
- After restart, verify changes in browser at the UAT URL
- Use `./rd list` to see available health modules
