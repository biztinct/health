---
description: Deploy modules to VietUc UAT server and restart Odoo
---

// turbo-all

# Deploy to VietUc UAT

> **AUTO-DEPLOY RULE**: Every time you make code changes to any `health_*` module, you MUST automatically deploy, upgrade, and restart WITHOUT the user asking. Do not wait for the user to say "deploy" — just do it as part of completing the task.

Use this workflow whenever you modify any `health_*` modules. This runs automatically after every change.

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
- Multiple modules: `./rd health_crm health_landing`

2. Stop the Odoo service, upgrade modules via command line, then restart:
// turbo
```bash
ssh VietUcUAT "sudo service odoo-server stop && sudo su - odoo -s /bin/bash -c '/odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -u <module_name> -d vietuat --stop-after-init' 2>&1 | tail -20 && sudo service odoo-server start"
```

Replace `<module_name>` with the comma-separated list of modules, e.g. `health_landing,health_crm`.
This stops the service, runs the upgrade (which applies XML/data changes), and restarts.

3. Wait for the server to come back up and verify:
// turbo
```bash
sleep 15 && ssh VietUcUAT "sudo service odoo-server status" | head -5
```

Confirm output shows `Active: active (running)`.

## Server Details

| Item | Value |
|------|-------|
| SSH alias | `VietUcUAT` |
| Database | `vietuat` |
| Odoo bin | `/odoo/odoo-server/odoo-bin` |
| Config | `/etc/odoo-server.conf` |
| Addons path | `/odoo/odoo-server/addons` |
| UAT URL | `https://care.biztinct.com` |

## Combined One-Liner Example

For deploying and upgrading multiple modules in one go:
```bash
cd /Users/adity/Documents/GitHub/health19/addons && ./rd health_crm health_landing && ssh VietUcUAT "sudo service odoo-server stop && sudo su - odoo -s /bin/bash -c '/odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -u health_landing,health_crm -d vietuat --stop-after-init' 2>&1 | tail -20 && sudo service odoo-server start"
```

## Quick Deploy (Python-only changes, no XML)

If you only changed `.py` files (no XML views/data), a simple restart is enough:
```bash
cd /Users/adity/Documents/GitHub/health19/addons && ./rd <module_name> && ssh VietUcUAT "sudo service odoo-server restart"
```

## Quick Deploy (single file via SCP)

When deploying individual files outside of the `rd` script, copy to `/tmp/` first then move with correct ownership:
```bash
scp /path/to/file VietUcUAT:/tmp/ && ssh VietUcUAT "sudo cp /tmp/<filename> /odoo/odoo-server/addons/<module>/path/to/<filename> && sudo chown odoo:odoo /odoo/odoo-server/addons/<module>/path/to/<filename>"
```

> **Important**: The `chown odoo:odoo` step is required for ALL file types (.py, .js, .xml, .css).
> The Odoo process runs as user `odoo`. Files copied via `sudo cp` are owned by `root:root`,
> which the Odoo process cannot read — causing silent failures or import errors.

## Notes
- The `rd` script uses `scp` to copy files to `VietUcUAT:/odoo/odoo-server/addons/`
- **XML/data changes** require the `-u` upgrade step; a simple restart is NOT enough
- **Python changes** take effect after server restart (no `-u` needed)
- **JavaScript/CSS changes** may need a browser hard refresh (Ctrl+Shift+R)
- Use `./rd list` to see available health modules
- The upgrade command exits with code 0 on success; RST warnings are harmless
