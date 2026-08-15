---
description: Deploy modules to VietUc UAT server and restart Odoo
---

// turbo-all

# Deploy to VietUc UAT

> **AUTO-DEPLOY RULE**: Every time you make code changes to any `health_*` module, you MUST automatically deploy, upgrade, and restart WITHOUT the user asking. Do not wait for the user to say "deploy" — just do it as part of completing the task.

Use this workflow whenever you modify any `health_*` modules. This runs automatically after every change.

## USE `vietuat-deploy` — DO NOT STOP/START ODOO BY HAND

The server hosts ONE Odoo, ONE addons directory and ONE `vietuat` database, and
more than one session works on it. `sudo service odoo-server stop` is global:
run it while somebody else is upgrading and their run dies mid-way. Odoo commits
per module, so an interrupted upgrade leaves a **half-migrated database** — on
2026-08-13 that cost four aborted runs, a deadlock and a column of live
crm.lead data.

`/usr/local/bin/vietuat-deploy` wraps the whole stop → upgrade → start sequence
in a `flock`, so concurrent callers queue instead of colliding. Source of truth
is `.agent/workflows/vietuat-deploy.sh` in this repo; reinstall with:

```bash
scp .agent/workflows/vietuat-deploy.sh VietUcUAT:/tmp/vietuat-deploy
ssh VietUcUAT "sudo install -m 0755 /tmp/vietuat-deploy /usr/local/bin/vietuat-deploy"
```

### The one command you need

```bash
# 1. ship the files
cd addons && scp -qr health_base health_crm VietUcUAT:/tmp/

# 2. install + upgrade + restart, serialized
ssh VietUcUAT "vietuat-deploy -d -m health_base,health_crm"

# with tests
ssh VietUcUAT "vietuat-deploy -d -m health_base -t /health_base:TestLookupValues"

# restart only
ssh VietUcUAT "vietuat-deploy -s"
```

It prints `odoo-bin exit=N`, the resulting `http=` code, and — on failure — the
last few real errors from the log. Exit code is odoo-bin's, so `|| echo FAILED`
works.

### Rules

* **Never** run `service odoo-server stop/start` or `odoo-bin -u` outside this
  wrapper. **Never** `pkill -f odoo-bin` — you will kill another session's run.
* `-u health_base` cascades to every dependent module, so "we'll upgrade
  different modules" is not isolation on this codebase.
* If you need true parallelism, give each session its own database, port and
  addons path — and neutralize the clone first (`odoo-bin neutralize`), because
  this system sends real ZNS messages and calls Viettel/MISA/OpenAI.
* Two sessions on one working tree should use `git worktree`, one branch each.

## Steps (legacy manual sequence — prefer the wrapper above)

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
