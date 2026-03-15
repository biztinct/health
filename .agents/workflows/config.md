---
description: Project browser and deployment configuration
---

## Browser Testing URL
- **Always use**: `https://care.biztinct.com`
- The user will handle login/password entry
- **Default permission: Allow All** for any browser prompts (do NOT ask user for permission)

// turbo-all

## Deployment
- UAT Server: VietUcUAT (via SSH)
- Deploy command: `./rd <module_names>` from `/Users/adity/Documents/GitHub/health19/addons`
- Upgrade: `ssh VietUcUAT "sudo service odoo-server stop && sudo su - odoo -s /bin/bash -c '/odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -u <modules> -d vietuat --stop-after-init' 2>&1 | tail -10 && sudo service odoo-server start"`
