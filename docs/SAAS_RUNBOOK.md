# The carejiox platform — operations runbook

**This is the document to read on the day nobody who built the platform is
reachable.** It says what the machine is, how a visitor's request finds the
right clinic, what to do when something is wrong, and what never to do.

Written 2026-09-04 (SAAS H3). Companion: `docs/SAAS_RESIZE_RUNBOOK.md` (making
the machine bigger). Engineering background: `docs/handovers/SAAS_PORT_PROGRAM.md`.

---

## 1. What the platform is, in one page

| | |
|---|---|
| Public address | **https://carejiox.com** (`www.carejiox.com` works too) |
| Old address | `care.biztinct.com` — permanently forwards to carejiox.com, keeps its own certificate |
| A clinic's address | `<slug>.carejiox.com` (e.g. `hhh.carejiox.com`) |
| Machine | AWS EC2 `i-0fb43cd9281f12945`, `t3.small`, Sydney (`ap-southeast-2a`) |
| Address | `54.206.18.111` — an **Elastic IP**, it survives a restart and a resize |
| SSH | `ssh VietUcUAT` (the alias kept its old name) |
| Master database | `carejiox` — the clinic that runs today. Renamed from `vietuat` on 2026-09-04 |
| Golden template | `carejiox_template` — a clean, empty copy of the product, cloned to make a new clinic |
| Deploy command | `carejiox-deploy` (`vietuat-deploy` still works — it is a symlink to it) |
| Application config | `/etc/odoo-server.conf` (pre-platform copy kept at `/etc/odoo-server.conf.pre-saas`) |
| Application log | `/var/log/odoo/odoo-server.log` — read it with `grep -a`, it is treated as binary |
| Web server | nginx 1.18, config in `/etc/nginx/sites-available/`, enabled by symlink from `sites-enabled/` |
| Platform settings | `/etc/biz-tenants.conf` |

### How a request finds the right clinic

This is the one idea the whole platform rests on:

> **The first word of the web address is the name of the database.**

`carejiox.com` → database `carejiox`. `hhh.carejiox.com` → database `hhh`.
`www.carejiox.com` → the application strips `www.` itself, so it also reaches
`carejiox`. That rule is the line `dbfilter = ^%d$` in `/etc/odoo-server.conf`.

Two consequences that bite if you forget them:

* **A clinic's short name must be a legal web address label** — lowercase
  letters, digits and hyphens, starting with a letter. No underscores. (This is
  also the second lock on the golden template: `carejiox_template` has an
  underscore, so no web address can ever reach it.)
* **nginx must pass the real hostname through.** Every block says
  `proxy_set_header Host $host;`. Rewrite that and every address on the box
  lands on the same clinic.

### The web server blocks

Everything lives in `/etc/nginx/sites-available/` and is switched on by a
symlink in `sites-enabled/`. `sudo nginx -t` before every `sudo systemctl reload
nginx`, always.

| File | Serves | What it does |
|---|---|---|
| `carejiox.com` | `carejiox.com`, `www.carejiox.com` | the platform itself, on its own certificate. Also serves `/status`. |
| `biz-wildcard` | `*.carejiox.com` | every clinic that has not been given its own certificate yet. Presents the platform's certificate, so a browser warns until `biz-tenant-cert` has run for that address. |
| `biz-tenant-<host>.conf` | one clinic | written by `biz-tenant-cert`. An exact name beats the wildcard, so this one wins for its own address. |
| `care.biztinct.com` | the old address | forwards everything to carejiox.com, on its own (still renewing) certificate. |
| `_` | anything else, and the bare IP address | closes the connection (`444`). Nothing is served. |
| `conf.d/biz-platform.conf` | — | one shared setting (`$connection_upgrade`) that every block's live-updates section needs. It has to be here: it may only be declared once. |

`nginx.conf` also carries `server_tokens off;`, so error pages and the `Server:`
header say `nginx` and not its exact version. Anyone probing this box for a
known hole now has to guess.

Three rules those blocks all keep, and that any new one must keep:

1. `location ^~ /web/database/ { return 404; }` — **there is no database
   manager on this platform, on any address.** The `^~` matters.
2. `location /websocket { ... }` forwarded to port **8072** — that is the
   process that does live updates. (`/longpolling` is gone; this build does not
   use it.)
3. Any redirect goes **inside `location /`**, never at the top of a `server`
   block. A top-level `return` runs before nginx picks a location, so it would
   also swallow the certificate-renewal check and the certificate would quietly
   stop renewing. That is not theoretical — it is why `care.biztinct.com` is
   shaped the way it is.

---

## 2. Certificates

Every address has **its own** certificate, obtained over HTTP-01, and they
renew themselves.

* **certbot is the snap, not the apt package** (`certbot 5.8.0`,
  `/snap/bin/certbot`, symlinked to `/usr/bin/certbot`). The apt package was
  removed on 2026-09-04: it had been dead since 2026-08-26 because newer
  `cryptography` / `pyOpenSSL` libraries the product needs shadow the ones it
  was built against. **Do not "fix" that by downgrading those libraries** — the
  product's own encryption and health-data modules need the new ones, and
  downgrading that chain has taken this server down before.
* **Renewal runs on `snap.certbot.renew.timer`.** The old `certbot.timer` is
  masked and must stay that way.
* **There is deliberately no wildcard certificate.** A `*.carejiox.com`
  certificate can only be issued by proving control through a DNS record, and
  that flow cannot renew unattended — it stops and waits for a person, forever.
  Per-address certificates renew on their own. This costs one command per new
  clinic and is worth it.

```bash
sudo certbot certificates          # what exists, and when each expires
sudo certbot renew --dry-run       # the real check — run it after ANY nginx change
```

**If `--dry-run` fails, fix it that week.** A certificate that stops renewing
gives every visitor a browser warning about seventy days later.

---

## 3. Making a new clinic

> The buttons for this arrive with the tenants cockpit (H4). Until then it is
> this, by hand, in this order.

1. **Point the address at us.** `<slug>.carejiox.com` already resolves —
   `*.carejiox.com` is a wildcard record at the registrar. Confirm:
   `dig +short @8.8.8.8 <slug>.carejiox.com` → `54.206.18.111`.
2. **Clone the template:**
   ```bash
   ssh VietUcUAT
   sudo -u postgres psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='carejiox_template';"
   sudo -u postgres createdb -T carejiox_template <slug>
   sudo cp -a /odoo/.local/share/Odoo/filestore/carejiox_template \
              /odoo/.local/share/Odoo/filestore/<slug>
   sudo chown -R odoo:odoo /odoo/.local/share/Odoo/filestore/<slug>
   ```
3. **Turn its scheduled jobs back on.** The template's jobs are all switched
   off on purpose (§5). The list of the ones that were on when it was built is
   stored in the template itself, under the setting key
   `biz_tenants.template_active_crons`:
   ```bash
   sudo -u postgres psql -d <slug> -c \
     "UPDATE ir_cron SET active = true WHERE id::text = ANY(string_to_array(
        (SELECT value FROM ir_config_parameter WHERE key='biz_tenants.template_active_crons'), ','));"
   ```
4. **Set the clinic's own address:**
   ```bash
   sudo -u postgres psql -d <slug> -c \
     "UPDATE ir_config_parameter SET value='https://<slug>.carejiox.com' WHERE key='web.base.url';"
   ```
   (If the row is missing, insert it, along with `web.base.url.freeze` = `True`.)
5. **Give it its own certificate — before you tell anybody the address:**
   ```bash
   sudo /usr/local/bin/biz-tenant-cert <slug>.carejiox.com <slug>
   ```
   Until this runs, the address works but the browser shows a name-mismatch
   warning, because the wildcard block serves the platform's certificate.
6. **Check it:** open `https://<slug>.carejiox.com` — sign-in page, no warning,
   and `https://<slug>.carejiox.com/web/database/manager` gives `404`.

### Removing a clinic

```bash
sudo /usr/local/bin/biz-domain-detach <slug>.carejiox.com   # block + certificate
sudo -u postgres pg_dump -Fc -Z1 <slug> -f /odoo/backups/tenants/<slug>/final_$(date -u +%Y%m%dT%H%M%SZ).dump
sudo -u postgres dropdb <slug>
sudo mv /odoo/.local/share/Odoo/filestore/<slug> /odoo/backups/tenants/<slug>/filestore
```
**Take the final backup before dropping, and keep it.**

### A clinic on its own domain (e.g. `booking.someclinic.com`)

**This does not work yet, and the tooling refuses rather than pretending.**
Routing is by the first word of the address, and `booking.someclinic.com`'s
first word is `booking`, which is not the clinic's database. Pinning it needs
the application to read a header naming the database, and this build does not.
`biz-domain-attach` therefore stops with an explanation and changes nothing.
The honest answer to a client asking today is: use `<slug>.carejiox.com`, or
point your own domain at it as a redirect. Revisit when the application is
upgraded — then set `CUSTOM_DOMAIN_PINNING=1` in `/etc/biz-tenants.conf`.

---

## 4. Deploying code

**Always through `carejiox-deploy`.** Everything it does runs inside one lock,
so two people deploying at once queue instead of colliding — an interrupted
upgrade leaves a half-migrated database.

```bash
cd addons && scp -qr health_base VietUcUAT:/tmp/
ssh VietUcUAT 'carejiox-deploy -d -m health_base'            # copy, upgrade, restart
ssh VietUcUAT 'carejiox-deploy -s'                           # just restart
ssh VietUcUAT 'carejiox-deploy -D carejiox_template -m health_base'   # the template
```

**The addons folder is shared by every database on this machine.** Copying files
changes the code under all of them at once; `-m`/`-i` only *migrates* the one
named by `-D`. So the ritual for a release is:

1. copy the files once (`-d`),
2. `-m` the master,
3. `-m` the **template** (`-D carejiox_template`),
4. `-m` each live clinic (`-D <slug>`),
5. **check the template's jobs are still off** — an upgrade can switch them back
   on:
   ```bash
   sudo -u postgres psql -d carejiox_template -Atc "select count(*) from ir_cron where active"   # must be 0
   ```
6. check nothing was skipped, on every database:
   ```bash
   sudo grep -a "some depends are not loaded\|Some modules are not loaded" /var/log/odoo/odoo-server.log | tail
   ```
   A skipped module is invisible in the module list and shows up later as a
   failing scheduled job. **Adding a `depends` to a module is a deploy step on
   every database, not just the one you were working on.**

### Never

* **Never** `systemctl restart odoo-server` — the start script races on the port
  and the new process dies silently. Use `carejiox-deploy -s`.
* **Never** `pkill -f odoo-bin` — it kills somebody else's upgrade.
* **Never** run `odoo-bin` by hand with the service up. If you need a shell with
  the service down, that is what `carejiox-deploy -x <script.py>` is for.
* **Never** recreate `/odoo/custom/addons`. There is one addons folder,
  `/odoo/odoo-server/addons`. The second one existed for years holding one
  stale, shadowed copy of a module and fooled every "is the server in step with
  the repo" check.
* **Never** point `tools/ci_fhir_local.sh` at a real database. It drops what it
  is given; it refuses the known names, but it cannot know a new clinic's.

---

## 5. The golden template

`carejiox_template` is a **fresh, empty install** of the product — never a copy
of a clinic. A copy of a clinic is that clinic's patient data, and it must never
become the starting point for another clinic.

What makes it a template rather than just another database:

* **Every scheduled job is switched off**, and the list of the ones that were on
  is recorded inside it under `biz_tenants.template_active_crons`. Provisioning
  turns exactly those back on for the new clinic. This matters because the
  application now serves *every* database on the machine: a template with live
  jobs would sit there sending things, all day, for a clinic that does not exist.
  **Re-check this after every upgrade of the template.**
* **Its administrator account is archived**, and there is a passwordless
  break-glass account (`platform.recovery@carejiox.com`) for the day a clinic
  locks itself out.
* **It cannot be reached from a browser.** Its name has an underscore, which is
  not legal in a web address, so no hostname can ever route to it.
* **It does not contain**: the data-migration tools, the one-off catchment
  backfill, or the website lead funnel — those are one customer's, not the
  product's. The list is in `docs/handovers/SAAS_PORT_PROGRAM.md`.

Rebuilding it from scratch is rarely needed — a normal deploy upgrades it like
any other database. If you must, the build command is in the H3 handover.

---

## 6. Backups

**Nothing writes automatic backups yet.** The folder and the rule exist; the
nightly job arrives with the tenants cockpit (H4). Until then a backup is
something a person takes, and the one that matters is the final backup before
you drop a clinic.

| What | Where | Kept |
|---|---|---|
| Per-clinic | `/odoo/backups/tenants/<slug>/` | intended: last 14 nightly, manual and final forever. **Empty today.** |
| Before the platform change | `/var/backups/saas_h3/` | the master's pre-rename dump, the old nginx and certificate folders, the old application config |
| Deleted stale databases | `/var/backups/stale_dbs/` | **delete after 2026-10-04** — see the README in that folder |

A dump on its own is not a restore. A restore is the dump **plus** the
attachments folder (`/odoo/.local/share/Odoo/filestore/<db>`), and both have to
come from the same moment.

```bash
# restore a clinic into a scratch database to check a backup is good
sudo -u postgres createdb <slug>_staging
sudo -u postgres pg_restore -d <slug>_staging /odoo/backups/tenants/<slug>/<file>.dump
# then DROP IT when you are done — every database on this machine costs memory
```

---

## 7. The status page

`https://carejiox.com/status` is **a file that nginx hands out itself**. That is
the whole point: it is readable on the day the application is not.

* The file is `/var/www/carejiox-status/index.html`, owned by `odoo` so the
  application can rewrite it.
* Proof it is really the file and not the application:
  ```bash
  curl -sI https://carejiox.com/status | grep -i "last-modified\|etag"
  ```
  Only a file served off disk gets those headers.
* If the folder goes missing:
  ```bash
  sudo mkdir -p /var/www/carejiox-status && sudo chown odoo:odoo /var/www/carejiox-status
  ```

Today it is a fixed placeholder. The platform starts writing it in H4.

---

## 8. Who can do what on the machine

The `odoo` account runs the application. **It is not an administrator.** Until
2026-09-04 it was in the `sudo` group and could run anything as root, which
meant a flaw anywhere in the product was a flaw with root behind it. It now has
exactly three permissions, in `/etc/sudoers.d/biz-tenants`:

```
odoo ALL=(root) NOPASSWD: /usr/local/bin/biz-tenant-cert, /usr/local/bin/biz-domain-attach, /usr/local/bin/biz-domain-detach
```

Check it with `sudo -l -U odoo` — three lines, nothing else. Those three scripts
are root-owned, validate every argument against a strict pattern before it
reaches a config file, and read their settings from `/etc/biz-tenants.conf`.
`tools/saas/test_scripts.sh` in the repo proves the refusals.

Anything else on this box — reloading nginx, editing config, restarting the
service — is an SSH job for a person, on purpose.

---

## 9. When something is wrong

**Start here.** Work down; each line tells you which of the next sections to read.

```bash
ssh VietUcUAT
pgrep -cf '^python3 /odoo/odoo-server/odoo-bin'    # expect 4. 0 = the app is down (§9.1)
free -m                                            # "available" under ~150 MB = §9.2
df -h /                                            # over 90 % = §9.3
sudo -u postgres psql -Atc "select datname from pg_database order by 1;"
curl -sk -o /dev/null -w '%{http_code}\n' -H 'Host: carejiox.com' http://127.0.0.1:8069/web/login
sudo grep -a "$(date -u +%Y-%m-%d)" /var/log/odoo/odoo-server.log | grep -aE "CRITICAL|ERROR" | tail -20
```

### 9.1 The application is down
```bash
carejiox-deploy -s
```
If it does not come back, the reason is in the log — look for `Failed to load
registry` and read the traceback above it. Do **not** restart in a loop.

### 9.2 It ran out of memory
Symptoms: workers restarting, requests timing out, `Killed` in
`sudo dmesg | tail`. Immediate relief is to stop using databases you do not
need — drop any `_staging` or scratch database, since every database in use
holds a copy of the product in memory in each of the three processes. The real
answer is `docs/SAAS_RESIZE_RUNBOOK.md`.

### 9.3 The disk is filling
Nearly always old backups. `sudo du -sh /var/backups/* /odoo/backups/*` and
delete what is past its keep-until date. Never delete
`/odoo/.local/share/Odoo/filestore/*` — those are live attachments.

### 9.4 One clinic's address shows a certificate warning
It has no certificate of its own yet and is falling through to the wildcard
block. `sudo /usr/local/bin/biz-tenant-cert <slug>.carejiox.com <slug>`.

### 9.5 An address says "no database" or bounces to a database selector
The first word of the address does not match a database name. Check the spelling
against `psql -l`. A clinic whose short name is not exactly the first word of
its address cannot work — that is the rule in §1.

### 9.6 The whole site is unreachable but the machine is fine
Usually nginx.
```bash
sudo nginx -t                  # says exactly which file and line
sudo systemctl status nginx
```
If a change broke it, back the file out and reload. Every generated block is
also self-healing: the three scripts run `nginx -t` and remove what they wrote
if it fails.

### 9.7 Rolling the whole platform change back
Only if the platform itself is the problem — a single bad nginx block is §9.6.
There is **no tenant data to lose** while `carejiox` is the only clinic; the day
there is one, this rollback is no longer the right move.

```bash
ssh VietUcUAT
sudo service odoo-server stop
sudo -u postgres psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='carejiox';"
sudo -u postgres psql -d postgres -c 'ALTER DATABASE carejiox RENAME TO vietuat;'
sudo mv /odoo/.local/share/Odoo/filestore/carejiox /odoo/.local/share/Odoo/filestore/vietuat
sudo cp /etc/odoo-server.conf.pre-saas /etc/odoo-server.conf     # db_name + ^vietuat$ come back
sudo rm -f /etc/nginx/sites-enabled/carejiox.com /etc/nginx/sites-enabled/biz-wildcard
sudo tar xzf /var/backups/saas_h3/nginx_pre_saas_*.tgz -C /etc nginx/sites-available/care.biztinct.com nginx/sites-available/_
sudo nginx -t && sudo systemctl reload nginx
sudo service odoo-server start
```

**Then fix the wrapper**, or the next deploy fails on a database that no longer
exists: `sudo sed -i 's/^DB=carejiox$/DB=vietuat/' /usr/local/bin/carejiox-deploy`
and change `HEALTH_HOST` to `care.biztinct.com`. The pre-change copy is kept at
`/var/backups/saas_h3/vietuat-deploy.pre-saas` if you would rather restore it.

The last-resort copy of the database itself is
`/var/backups/saas_h3/vietuat_pre_rename_*.dump` (24,339 objects, taken with
the service up immediately before the rename).

---

## 10. Known noise (not faults)

* `WARNING ... unknown parameter 'states' / 'tracking' / 'placeholder'` on
  startup — old field options this Odoo version no longer reads. Harmless.
* `WARNING ... Missing not-null constraint on hr.skill...` — same class.
* `ERROR ... odoo.sql_db: bad query ... website_visitor ...` — search-engine
  crawlers hitting leftover demo pages of the built-in website. Pre-existing
  since 2026-07-24, unrelated to the platform work.
* The browser tab says `Odoo` for a moment while the screen loads, then settles
  to the product name. The first word comes from the raw page before the app
  starts. Worth fixing; not a fault.
