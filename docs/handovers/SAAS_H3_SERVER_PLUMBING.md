# SAAS H3 — the server becomes a platform: carejiox.com, one database per hostname, certificates that renew, a golden template

Read FIRST: `docs/handovers/SAAS_PORT_PROGRAM.md` (decisions incl. the H3 answers of 2026-09-04,
plumbing, rails, ledger H1–H32+), then `from_payobook/SAAS_RUNBOOK.md` (the architecture this phase
reproduces: renamed apex DB, `dbfilter = ^%d$`, wildcard block, per-host HTTP-01 certs, template
with crons recorded + disabled, backups dir, status page nginx block), `SAAS_RESIZE_RUNBOOK.md`
(the shape of the resize doc you will write for EC2), FLEET ledger F5, F6, F9, F13, F19, F20, F25,
F27, F34, F44, F59, and ACCESS ledger F6/F7 (test runs stealing port 8069; orphan odoo-bin), P7
G1–G10 (what a fresh install of a whole product breaks on).

Design bar (verbatim, binding): **"Extreme WOW, intuitive, out-of-this-world experience, best in
class."** H3 has no screens; the bar lands on the runbook — `docs/SAAS_RUNBOOK.md` for this product
must be the document a stranger can operate the platform from on the day nobody who built it is
reachable — and on ZERO user-visible breakage: the site moves domain with a redirect, not a 404.

White-label rule (binding): "Odoo" never in anything a user reads — including the maintenance
notice, nginx error pages, the status page and the certificate's organisation fields if you set any.
The system account name `odoo` is technical and stays.

---

## 0. Owner decisions that shape H3 (2026-09-04)

1. **New static IP `54.206.18.111`** (EC2 `i-0fb43cd9281f12945`, `t3.small`, `ap-southeast-2a`,
   2 GB RAM + 2 GB swapfile, 58 GB disk). The owner is repointing `care.biztinct.com` A and
   `carejiox.com` A `@` to it; `*.carejiox.com` already resolves there (GoDaddy, `ns47/48.domaincontrol.com`).
   **Nothing in H3 that needs DNS starts until `dig` agrees** (§4 step 0).
2. **Rename the master database `vietuat` → `carejiox`** (5 minutes of downtime, users signed out once).
3. **Delete the stale databases** `bi_test`, `care`, `care_biztinct`, `vietuc_uat` — dump each to
   `/var/backups/stale_dbs/<name>_<UTC>.dump` first, keep 30 days (write the date in a README there).
4. **Repair certbot** (apt `certbot 1.21` is dead: `/usr/local` pip `cryptography 49.0.0` +
   `pyOpenSSL 26.3.0` shadow the apt `python3-openssl 21.0.0`; every timer run since 2026-08-26
   fails with `OpenSSL.crypto has no attribute X509Req`; `care.biztinct.com` expires **2026-09-25**)
   and **restrict the `odoo` system account's sudo** (today `(ALL : ALL) ALL` via some file — find
   it; `sudo -l -U odoo` shows it) to exactly the three platform scripts, as Payobook does.
5. Machine resize: **runbook only** (§3.9); the owner schedules it.
6. Never-list for the template (draft, confirmed in H4's report): `biz_tenants` (H4, not yet
   written), `health_migration`, `health_catchment_backfill`, `health_web_leads` (the
   pkgdvietuc.com lead funnel — one customer's site), `access_roles`/`health_user_admin` (gone).
   Everything else installed on the master is the product.

## 1. Scope

1. Certbot repair + `certbot renew --dry-run` green + the `care.biztinct.com` cert renewed (§3.1).
2. sudoers for `odoo`: the three scripts only (§3.2). The three scripts themselves, generic
   (`biz-tenant-cert`, `biz-domain-attach`, `biz-domain-detach`) + `/etc/biz-tenants.conf` (§3.3).
3. nginx: apex block for `carejiox.com` (443, own HTTP-01 cert), `care.biztinct.com` → 301 to
   `carejiox.com` (keeps its cert so the redirect is trusted), wildcard block `*.carejiox.com`
   (serving the apex cert until a tenant has its own — every provisioned tenant gets its own via
   `biz-tenant-cert`), `/web/database/` → 404 on EVERY block, `/websocket` upgrade headers,
   `/status` + `/status/` served from `/var/www/carejiox-status/` (owned by `odoo`) (§3.4).
4. The Odoo config: `db_name` removed, `dbfilter = ^%d$`, `list_db = False` stays, the second
   addons path removed after the shadowed `advanced_pricing` copy is deleted (§3.5).
5. The rename `vietuat` → `carejiox` (database + filestore dir + `web.base.url` + the deploy wrapper
   + HANDOVER-CONVENTIONS §2 + every doc/memory that names it) (§3.6).
6. Stale databases dumped and dropped (§3.7).
7. The golden template `carejiox_template` (§3.8) — fresh install, crons recorded + disabled
   (`biz_tenants.template_active_crons` on the TEMPLATE's own `ir_config_parameter`, F20), admin
   user archived, recovery account created (E5 pattern), unreachable by hostname (underscore).
8. Backups dir `/odoo/backups/tenants/`, `/var/backups/saas_*` retention note.
9. `docs/SAAS_RUNBOOK.md` (this product's), `docs/SAAS_RESIZE_RUNBOOK.md` (EC2 version), ledger
   entries from H33, memory note for the session lead to update (§7.9), commits (§6).

## 2. Binding NON-goals

- No `biz_tenants` / `biz_tenancy` code (H4). No provisioning of `hhh` (H4). No alerts, no mail.
- No change to `workers = 2` (record the memory implication in the ledger: every registry loads in
  every worker; the template + a tenant ≈ 3× the F34 cost; the resize runbook is the answer).
- No wildcard DNS-01 certificate (it never auto-renews — pb-tenant-cert's header explains why).
  Per-host HTTP-01 only.
- Do not touch `care.biztinct.com`'s registrar records yourself; do not create DNS anywhere.
- Do not delete `advanced_pricing` from the FIRST addons path (it is the loaded copy, 19.0.1.2.0);
  only the stale `/odoo/custom/addons/advanced_pricing` (19.0.1.1.1) goes, after a tarball.
- Do not run the rename while another `odoo-bin` is alive (F7) or while the H2b agent's work is
  unfinished — check `pgrep -af odoo-bin` shows the service's ~5 processes only.

## 3. Architecture

### 3.1 Certbot
Replace the broken apt certbot with the snap (the EFF-maintained route, and `snapd` is active):
`sudo apt-get remove -y certbot python3-certbot-nginx` (KEEP `/etc/letsencrypt` — apt remove does
not touch it), `sudo snap install --classic certbot`, `sudo ln -sf /snap/bin/certbot
/usr/bin/certbot`, `sudo snap set certbot trust-plugin-with-root=ok`, then `sudo certbot renew
--dry-run` must pass for `care.biztinct.com` (its renewal conf uses `authenticator = nginx` —
the snap ships the nginx plugin). Then `sudo certbot renew` for real (it is inside the 30-day
window) and `openssl x509 -enddate` proves the new date. The snap installs its own timer
(`snap.certbot.renew.timer`); disable the dead `certbot.timer`. Record the pip/apt clash in the
ledger so nobody "fixes" it by downgrading `cryptography` (Odoo's own `requirements.txt` on this
box wants the new one — check before claiming that).

### 3.2 sudoers
`/etc/sudoers.d/biz-tenants` (mode 0440, `visudo -cf` before installing):
```
odoo ALL=(root) NOPASSWD: /usr/local/bin/biz-tenant-cert, /usr/local/bin/biz-domain-attach, /usr/local/bin/biz-domain-detach
```
and REMOVE whatever grants `odoo` `ALL` today (find it: `sudo grep -rn odoo /etc/sudoers
/etc/sudoers.d/`; if it is the `odoo` user in a group with sudo, `gpasswd -d odoo sudo`). Prove
with `sudo -l -U odoo` (exactly three lines) and by running `sudo -u odoo sudo -n /bin/true`
(refused). Check nothing in the product calls `sudo` (the design session grepped `addons/` for
`subprocess`/`sudo` — nothing outside stock modules; re-grep and say so).

### 3.3 The three scripts (generic, in the repo at `tools/saas/`, installed at `/usr/local/bin/`)
Clone `gitlocal/pb_tenants/tools/{pb-tenant-cert,pb-domain-attach,pb-domain-detach}` → 
`biz-tenant-cert`, `biz-domain-attach`, `biz-domain-detach`. Changes: read `APEX_DOMAIN`,
`BLOCK_PREFIX` (`biz-tenant-`), `STATUS_DIR` from `/etc/biz-tenants.conf` (root-owned, 0644;
`APEX_DOMAIN=carejiox.com`); the "refusing to manage a payobook.com hostname" guard becomes
"refusing to manage a hostname under the apex domain" for `attach`, and `tenant-cert` keeps its
"hostname must be the slug's own subdomain" guard against `APEX_DOMAIN`; generated blocks carry
`location ^~ /web/database/ { return 404; }` and the `/websocket` upgrade block; every comment
says "Managed by the platform" not "pb_tenants". **`biz-domain-attach` pins the database with
`X-Odoo-dbfilter` — verify this build honours it** (`grep -rn "dbfilter" /odoo/odoo-server/odoo/http.py`
— on Payobook's build `db_filter` reads `HTTP_X_ODOO_DBFILTER`); if this older build does not,
say so in the report and leave the attach script installed but documented as "custom domains need
the header support — H4/H5 decides", never silently shipping a script that pins nothing.
Validation regexes stay strict (they are interpolated into root-owned config). A test in the repo
(`tools/saas/test_scripts.sh`, bash) feeds each script bad hostnames/slugs and asserts exit 2.

### 3.4 nginx (all under `sites-available/`, symlinked; `nginx -t` before every reload)
- `carejiox.com` — clone of today's `care.biztinct.com` block with `server_name carejiox.com
  www.carejiox.com`, cert `/etc/letsencrypt/live/carejiox.com/` obtained with `certbot certonly
  --nginx -d carejiox.com -d www.carejiox.com --deploy-hook "systemctl reload nginx"` (certonly —
  the installer rewrites blocks, pb-tenant-cert's header says why), `/web/database/` 404,
  `/websocket` upgrade, `/status` + `/status/` alias blocks (runbook text, `^~` load-bearing),
  `proxy_set_header Host $host` (Odoo needs the real host for `^%d$`), `client_max_body_size
  128M`, port 80 → 301 https.
- `care.biztinct.com` — becomes `return 301 https://carejiox.com$request_uri` on 443 (own cert
  kept + renewing) and on 80. Nothing else on that hostname.
- `biz-wildcard` — `server_name *.carejiox.com`, ssl_certificate = the apex cert (a hostname
  without its own block gets a name-mismatch warning until `biz-tenant-cert` gives it one, which
  provisioning does before announcing the tenant), same proxy/websocket/database-404 body; port 80
  → 301.
- `_` (catch-all, port 80): keep, but make it `return 444` for hostnames nobody claims (today it
  proxies everything on 80 to Odoo, which with `^%d$` would 404 anyway; 444 is quieter) — or
  delete it and let `default` stand; say which and why.

### 3.5 The Odoo config (`/etc/odoo-server.conf`, back it up as `.pre-saas`)
`db_name` line removed; `dbfilter = ^%d$`; `list_db = False`; `addons_path =
/odoo/odoo-server/addons` (single path — after `tar czf /var/backups/stale_addons_advanced_pricing.tgz
/odoo/custom/addons/advanced_pricing && rm -rf /odoo/custom/addons/advanced_pricing`; if
`/odoo/custom/addons` is then empty, remove the path; if not, list what is left and keep it);
everything else unchanged. Consequence to write in the ledger: with `db_name` gone the cron worker
serves EVERY database (ledger H2 reversed) — hence the template's crons must be disabled (R8) and
scratch clones must be dropped promptly (A8 applies from now on).

### 3.6 The rename (the ONE downtime; do it inside the deploy wrapper's lock)
Sequence, with the service stopped by `vietuat-deploy -s`-style stop/start (extend the wrapper
with `-r <newname>`? No — the wrapper is renamed too; do the rename by hand under
`flock /tmp/vietuat-deploy.lock`, then update the wrapper):
1. `pg_dump -Fc -Z1 vietuat -f /var/backups/saas_h3/vietuat_pre_rename_<UTC>.dump` + `pg_restore -l`.
2. stop the service (`sudo service odoo-server stop`, wait for 8069 to free — the wrapper's loop);
   `pg_terminate_backend` for `vietuat`; `ALTER DATABASE vietuat RENAME TO carejiox;`
   `mv /odoo/.local/share/Odoo/filestore/vietuat /odoo/.local/share/Odoo/filestore/carejiox`.
3. conf (§3.5); nginx blocks live (§3.4); start; `curl -H "Host: carejiox.com"` → 200 and the
   login page; `curl -H "Host: care.biztinct.com"` → 301; `curl -H "Host: nothere.carejiox.com"`
   → the wildcard block → Odoo answers 404/"no database" (expected — no such DB).
4. `web.base.url` → `https://carejiox.com`, `web.base.url.freeze = True` (shell, F19: restart after).
5. The wrapper: rename to `carejiox-deploy` (keep `vietuat-deploy` as a symlink for one phase),
   `DB=carejiox`, and the header comments; `.agent/workflows/` same; HANDOVER-CONVENTIONS §2 same;
   `tools/ci_fhir_local.sh`/`fhir_deploy_smoke.sh` if they name the DB; docs that say
   "-d vietuat" (grep the repo; comments/QA notes may stay historical if they read as history).
6. Chrome: `https://carejiox.com/bizapp` signs in and shows the CMS; `https://care.biztinct.com/x`
   lands on `https://carejiox.com/x`. Screenshots.

### 3.7 Stale databases
For each of `bi_test`, `care`, `care_biztinct`, `vietuc_uat`: `pg_dump -Fc -Z1` to
`/var/backups/stale_dbs/`, `pg_restore -l | wc -l` recorded, `dropdb`; remove their filestore dirs
(`/odoo/.local/share/Odoo/filestore/<name>`, plus the orphan `gc3_ci_probe`) after a tarball into
the same folder. README with "delete after 2026-10-04".

### 3.8 The golden template `carejiox_template`
A **fresh install** on an empty database (never a scrubbed clone — a copy of a clinic's database
is PHI): `odoo-bin -c /etc/odoo-server.conf -d carejiox_template -i <the module set>
--stop-after-init --workers=0 --max-cron-threads=0 --http-port=8169 --gevent-port=8168 --logfile=…`
with `HOME=/odoo`. The module set = every custom module installed on the master (`ir_module_module
state='installed'` and `name` in the custom families — the program doc's H0 list plus the H1/H2
modules: `biz_kit`, `biz_access`, `health_access`) minus the never-list (§0.6); Odoo pulls the
standard dependencies itself. Expect packaging faults (ACCESS P7 G1–G10 is the precedent; the FHIR
CI proves a SUBSET installs cleanly) — fix each in the repo as its own small commit (a missing
`depends`, a data file referencing a demo record, a forward reference) and deploy the fix to the
master too through the wrapper (a `depends` change lands via `update_list` on every DB — G5). Then:
- `INSERT INTO ir_config_parameter(key,value) SELECT 'biz_tenants.template_active_crons',
  string_agg(id::text, ',') FROM ir_cron WHERE active; UPDATE ir_cron SET active=false;` on the
  TEMPLATE (F20/R8) — and re-check after any later `-u` on it (F9).
- The template's admin user: archived (comment E4/E5 — a template with an active admin is a
  template someone can sign into if a hostname ever matched; `carejiox_template` cannot be a
  hostname label, which is the second lock).
- A recovery account `platform.recovery@carejiox.com`: active, no password, no email,
  `base.group_system` — H4's break-glass (F pattern `_ensure_break_glass`).
- `biz_debranding.brand_name` on the template = the master's value; `web.base.url` unset (the
  provisioning step sets it per tenant).
- A registry load with zero skipped modules (F7) and the Access home reachable on it (an odoo
  shell: `env['biz.access'].get_board()` returns 0 roles… no: `health_access` seeds the clinic
  catalogue on install, so 9 roles — assert 9). `health_access`'s legacy migration must log
  "nothing to migrate" on the template (it never had the old app) — assert the line.
- Size and RSS: record `pg_database_size` and the RSS delta of loading its registry in a shell
  (F34's measurement, this box).

### 3.9 Docs
- `docs/SAAS_RUNBOOK.md` — this product's, written from Payobook's with our values (domain, DB
  names, paths, script names, the wildcard-cert decision, the `workers=2` note, the never-list,
  the "template crons" rule, the deploy ritual now looping over the template + tenants).
- `docs/SAAS_RESIZE_RUNBOOK.md` — EC2 version: stop instance → change type `t3.small` →
  `t3.medium` (4 GB) → start; the Elastic IP stays; `shared_buffers 128MB → 1GB`,
  `effective_cache_size 2GB`, keep the 2 GB swapfile; verify list.
- `docs/strategy/HANDOVER-CONVENTIONS.md` §2 updated for `carejiox-deploy` and `-d carejiox`.

## 4. Order of execution on the live box (every step reversible or backed up; stop at a surprise)

0. **Preconditions**: `pgrep -af odoo-bin` = the service only; `free -m` ≥ 800 MB available;
   `dig +short carejiox.com` = `dig +short care.biztinct.com` = `54.206.18.111` (if care.biztinct.com
   still points at the old IP, do steps 1–2 and 7–9 and STOP before 3 — report; the owner is
   repointing it).
1. Certbot (§3.1) — no downtime. Prove renewal.
2. Scripts + sudoers (§3.2, §3.3) — no downtime. Prove the refusals.
3. Apex cert for `carejiox.com` (needs DNS) + the nginx blocks staged in `sites-available` but
   the carejiox block enabled on 80/443 pointing at Odoo with the OLD conf (`dbfilter ^vietuat$`
   still routes everything to `vietuat`) — users can already reach `https://carejiox.com`. Chrome.
4. **The rename** (§3.6) — 5 minutes. Then care.biztinct.com → 301.
5. Stale databases (§3.7).
6. Wildcard block + `/status` dir + backups dir; `curl -sI https://carejiox.com/status` shows
   nginx's `Last-Modified` once a placeholder page exists (write a plain "All systems normal — this
   page is refreshed by the platform" placeholder; H4 overwrites it).
7. Template (§3.8) — long; run detached (`systemd-run --uid=odoo --setenv=HOME=/odoo …`, H2a's
   ledger has the invocation) with a sentinel; the live service keeps running (spare ports).
8. Docs, ledger, commits.
9. Final checks: `/web/login` 200 on carejiox.com; `/web/database/manager` 404 on every hostname;
   `care.biztinct.com` 301; `sudo -l -U odoo` = 3 lines; `certbot renew --dry-run` green;
   `pgrep` = service only; 15-minute log watch (F25's noise list applies).

## 5. Numbered test cases

1. `certbot renew --dry-run` passes; `openssl x509 -enddate` on `care.biztinct.com` shows a date
   ≥ 2026-11-20 after the real renewal; `snap.certbot.renew.timer` active, `certbot.timer` gone.
2. `sudo -l -U odoo` lists exactly the three scripts; `sudo -u odoo sudo -n /bin/true` is refused.
3. `tools/saas/test_scripts.sh`: bad hostname → exit 2, bad slug → exit 2, apex-domain hostname to
   `attach` → exit 2, `tenant-cert` with a hostname not under the slug → exit 2 (all WITHOUT
   touching certbot — the guards fire first).
4. Routing after the rename: `curl -H Host:` for `carejiox.com` (200, login), `www.carejiox.com`
   (200 or 301 to apex — say which), `care.biztinct.com` (301 → carejiox.com), `nothere.carejiox.com`
   (no database → whatever Odoo answers with `list_db=False`; must NOT be a database manager
   page), `54.206.18.111` bare (444 or 404, not the app), `/web/database/manager` on every one → 404.
5. `psql -l` shows `carejiox`, `carejiox_template`, `postgres` only; filestore dirs match.
6. Template: installed module list == master's custom set − never-list (print the diff, must be
   exactly the never-list); `ir_cron` 0 active and the recorded id list present; admin archived;
   recovery user present and passwordless; registry load 0 skipped; 9 roles on the Access home;
   `pg_database_size` + RSS delta recorded.
7. The wrapper: `carejiox-deploy -s` restarts; `carejiox-deploy -m health_theme` upgrades the
   master (a harmless module) and prints `http=200`; the old name still works as a symlink.
8. Chrome: `https://carejiox.com/bizapp` sign-in → CMS home (screenshot); old URL redirects
   (screenshot of the address bar after landing); the PWA (`/pwa` or whatever `health_pwa` serves —
   check its manifest URL) loads on the new host (its manifest and service worker are
   host-relative; `health_pwa` pins a version — memory `feedback_pwa_version_bump` — do NOT bump
   it unless a file changes).
9. 15-minute watch clean; boot time recorded.

## 6. Commits (explicit staging, no push)

1. `chore(saas): platform scripts biz-tenant-cert / biz-domain-attach / biz-domain-detach + tests`
2. `chore(deploy): carejiox-deploy — the master is carejiox now` (wrapper, conventions §2, tools)
3. any packaging fix the template surfaced — one commit each, `fix(<module>): …`
4. `docs(saas): SAAS_RUNBOOK + SAAS_RESIZE_RUNBOOK for carejiox; H3 handover; ledger H33+`

## 7. Report back

1. **Owner summary (6 lines)**: the new address, what happens to old links, the certificate now
   renews itself, the account lock-down, the template exists, the resize is a 10-minute EC2 step
   whenever they choose.
2. Per numbered test with evidence.
3. The exact conf diff (`diff /etc/odoo-server.conf.pre-saas /etc/odoo-server.conf`) and the nginx
   blocks as installed.
4. Certbot: what was broken, what you installed, the dry-run output's last lines.
5. Template: the module set (count), the packaging faults you fixed (each with its commit), the
   cron id list length, size and RSS.
6. The `X-Odoo-dbfilter` finding (§3.3).
7. Backups: every dump path + object count; the stale-DB README.
8. Downtime measured for the rename (stop → first 200).
9. Ledger entries (from H33); commit hashes; **the memory notes the session lead must update**:
   the DB name (`feedback_database_name` says `vietuat`), the deploy workflow memory (wrapper name),
   the ssh alias IP.
10. Decisions the handover did not cover.
