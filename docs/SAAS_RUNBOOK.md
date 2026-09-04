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
| Master database | `carejiox` — the clinic that runs today, and the platform. Renamed from `vietuat` on 2026-09-04 |
| Customer systems | one database per clinic. Today: `hhh` (HHH Clinic), created 2026-09-04 |
| Where clinics are made | **Customers**, at the bottom of the left menu under ADMIN, on https://carejiox.com |
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
  letters, digits and hyphens, starting with a letter. No underscores.
* **The wildcard block drops any hostname containing an underscore** (`444`).
  This is not tidiness. The golden template is called `carejiox_template`, and
  the plan was that the underscore made it unreachable — but the registrar's
  `*.carejiox.com` record resolves `carejiox_template.carejiox.com` to this box,
  nginx's own `*.carejiox.com` matches it, and the application maps the first
  word straight to a database. The template was answering its sign-in page on
  the public internet until 2026-09-04. Nobody could get in (its administrator
  is archived and the only other account has no password), but it was a door
  nobody had decided to open. **Do not remove that rule**, and do not give a
  clinic a name with an underscore in it.
* **A practice copy is not on the internet either.** Putting a clinic's copy
  back to check it is good makes a whole second system called
  `<slug>-staging`, with that clinic's own data and passwords in it. A hyphen
  is a perfectly legal web address, so `hhh-staging.carejiox.com` resolved and
  reached it. The wildcard block now drops any address whose first word ends in
  `-staging`, exactly as it drops one containing an underscore. **Do not remove
  that rule either**, and do not give a clinic a short name ending in
  `-staging`.
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

**This is now a screen, not a runbook.** Sign in to https://carejiox.com, open
**Customers** at the bottom of the left menu (under ADMIN — only the Owner role
sees it), and press **New customer**.

### What you type, and what happens

You give four things: the clinic's name, their short name, their
administrator's name and their administrator's email address. The short name is
the important one — **it becomes both their web address and the name of their
system on this machine**, so it is small letters and digits only, starting with
a letter, no underscores. The screen checks it while you type and says why if
it cannot be used.

Then press **Show me what would happen**. Nothing has been written yet: you get
the six steps in plain words, the size of what is about to be copied, and a
refusal with a reason if anything is wrong — a name in use, no email, or not
enough memory on the machine.

Then press **Create**, and watch. The six steps are:

| Step | What it does |
|---|---|
| Copy the blank system | Copies `carejiox_template`, database and attachments together, as the account the application runs as |
| Set its address and its settings | `https://<short name>.carejiox.com`, locked; their name; the top-bar rule; and their scheduled jobs switched back on |
| Create the administrator | A **new** account — never the blank system's own — with the Owner role, the clinic-administrator tier, and a one-time password |
| Secure the address | Runs `biz-tenant-cert` so a browser trusts the name |
| Check everything answers | The address returns a sign-in page, nothing was skipped, they have every part of the product, and their access home has its roles |
| Hand it over | Marks them live and shows you the address, the sign-in name and the password |

It takes about a minute. **The password is shown once and stored nowhere** —
not on this machine, not in the log — and **no email is sent**, because this
platform still has no outgoing mail account. Copy the three lines off the end
card and hand them over yourself.

### If a step fails

The screen says what failed, what it left behind, and offers two buttons: **try
this step again** (everything before it is done and still there), or **undo the
whole thing** (the system is removed and the address comes down; nothing is
left behind, because nobody has signed in yet). There is no state it can reach
where the answer is "go and look at the machine".

**Securing the address is the one step that is never fatal.** If the
certificate cannot be issued the clinic still goes live — their address works
and a browser warns about the name — and the end card gives you the exact
command to run by hand:
`sudo /usr/local/bin/biz-tenant-cert <slug>.carejiox.com <slug>`. Press that
step again afterwards.

### Doing it by hand

Only if the screen itself is unavailable. The order matters and step 2's `-O
odoo` is **not** optional: the application lists only the databases owned by the
account it connects as, so a system owned by anybody else answers a redirect to
a database chooser instead of a sign-in page — and looks, from outside, exactly
like a routing fault.

```bash
ssh VietUcUAT
dig +short @8.8.8.8 <slug>.carejiox.com            # must be 54.206.18.111
sudo -u postgres psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='carejiox_template';"
sudo -u postgres createdb -T carejiox_template -O odoo <slug>
sudo cp -a /odoo/.local/share/Odoo/filestore/carejiox_template \
           /odoo/.local/share/Odoo/filestore/<slug>
sudo chown -R odoo:odoo /odoo/.local/share/Odoo/filestore/<slug>
# their scheduled jobs — the list lives in the TEMPLATE's own settings, and
# came across with the copy
sudo -u postgres psql -d <slug> -c \
  "UPDATE ir_cron SET active = true WHERE id::text = ANY(string_to_array(
     (SELECT value FROM ir_config_parameter WHERE key='biz_tenants.template_active_crons'), ','));"
sudo -u postgres psql -d <slug> -c \
  "UPDATE ir_config_parameter SET value='https://<slug>.carejiox.com' WHERE key='web.base.url';"
sudo /usr/local/bin/biz-tenant-cert <slug>.carejiox.com <slug>
```
If you hit the wrong-owner symptom:
`sudo -u postgres psql -d postgres -c 'ALTER DATABASE <slug> OWNER TO odoo;'`

Then check: `https://<slug>.carejiox.com` gives a sign-in page with no warning,
and `https://<slug>.carejiox.com/web/database/manager` gives `404`.

### Removing a clinic

**Also a screen.** Open the clinic on the Customers screen, go to **Closing
down**, and type their short name to confirm. It takes a final copy FIRST and
refuses to remove anything if that copy fails; then the address comes down and
the system is removed.

A clinic **nobody has ever signed in to** can instead simply be undone, which
the same tab offers.

**Building a closed clinic's system again.** Their record stays on the list with
their short name on it, so the New customer screen will refuse that name — which
is right, and which is why the same **Closing down** tab offers **Build their
system again**. It puts them back at the start of the six steps on their own
record, so their copies (including the final one) and their whole history stay
in one place, and gives them their address back. It refuses while anything of
that name is still on the machine.

By hand, only if the screen is unavailable:
```bash
sudo /usr/local/bin/biz-domain-detach <slug>.carejiox.com   # block + certificate
sudo -u postgres pg_dump -Fc -Z1 <slug> -f /odoo/backups/tenants/<slug>/final_$(date -u +%Y%m%dT%H%M%SZ).dump
sudo -u postgres dropdb <slug>
sudo mv /odoo/.local/share/Odoo/filestore/<slug> /odoo/backups/tenants/<slug>/filestore
```
**Take the final backup before dropping, and keep it.**

### Telling a clinic something

On the Customers screen, the envelope on a row (or **Tell their people
something** on a clinic's Overview) puts a bar at the top of every page in that
clinic. It has a window, **you type it in your own clock**, and it is drawn
again in each reader's — so nobody's morning is announced as somebody else's
evening. The bar comes down on its own when the window ends; nobody has to
remember to clear it.

### Keeping clinics in step

**In step with master** at the top of the Customers screen shows every system —
the blank one included — against what the platform runs. **Nothing is ever
installed on a clinic by a schedule.** The nightly job only reads, so the
morning screen is honest; a person presses the button, and there is a rehearsal
button beside it that changes nothing.

**Cut a release** freezes what the platform runs today and gives it a dated
name, with a note you write. That note is what every clinic reads on their own
**About Viet Uc Care** screen when they are moved onto it — so write it for the
person using the product, not for an engineer.

After any upgrade of the blank system, press **Quieten the blank system**: an
upgrade switches its scheduled jobs back on, and a blank system with live jobs
is a hot registry sitting there for a clinic that does not exist.

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

> ⚠ **FINISH THE WHOLE LOOP IN ONE SITTING.** There is ONE folder of code on
> this machine and every system on it runs from that folder — but `-m` only
> applies the change to the one system named by `-D`. So the moment new code
> lands, every OTHER system is running new code against its old database. For
> most changes that is harmless. For a change that adds a new kind of record it
> is not: on 2026-09-05 the master was upgraded, `hhh` was not, and `hhh`'s site
> answered an error page for four minutes until it was. **Deploy to the master,
> then the blank system, then every clinic, back to back — do not stop in the
> middle to look at something.**
>
> If you are only REHEARSING a change, do not copy it into the shared folder at
> all: give the practice copy its own folder instead. That is
> `--addons-path=/odoo/<yours>/addons,/odoo/odoo-server/addons` on the practice
> run's own command, and the live systems never see the new code.

```bash
cd addons && scp -qr health_base VietUcUAT:/tmp/
ssh VietUcUAT 'carejiox-deploy -d -m health_base'            # copy, upgrade, restart
ssh VietUcUAT 'carejiox-deploy -s'                           # just restart
ssh VietUcUAT 'carejiox-deploy -D carejiox_template -m health_base'   # the template
ssh VietUcUAT 'carejiox-deploy -D hhh -m health_base'                # one clinic
ssh VietUcUAT 'carejiox-deploy -m health_base -t /health_base'        # with tests
```

**Tests must name the database, and the wrapper now does it for you.** Routing
is by hostname, and a browser-style test calls `127.0.0.1` — which the
application reads as a database called `127`, so every request comes back 404
from somewhere that never reached the app. It looks exactly like a broken
feature. If you ever run `odoo-bin` by hand with `--test-enable`, pass
`--db-filter=^<database>$` with it.

> ⚠ **NEVER RUN `-t` AGAINST A PRACTICE COPY. IT TAKES THE WHOLE PLATFORM
> DOWN.** `carejiox-deploy -t` stops the service for the length of the test
> run, whatever `-D` says — and a test run cannot use `--no-http`, so if it
> hangs (it did, on 2026-09-04, when an internet scanner hit the test server)
> the platform stays down until somebody notices. It cost 27 minutes.
> Test a practice copy like this instead — spare ports, its own log, and the
> live service left running:
> ```bash
> sudo systemd-run --unit=mytests --uid=odoo --gid=odoo --setenv=HOME=/odoo \
>   /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d <clone> \
>   --stop-after-init -u <modules> --test-enable --test-tags '/<module>' \
>   --workers=0 --http-port=8199 --gevent-port=8299 \
>   --db-filter='^<clone>$' --logfile=/var/log/odoo/mytests.log
> # then: grep -a 'odoo.tests.result' /var/log/odoo/mytests.log
> ```
> And **switch the practice copy's scheduled jobs off again straight after any
> upgrade of it** — an upgrade creates a new release's jobs switched ON, and
> every database on this machine is a job target, so a practice copy will
> happily rewrite the real public page from made-up data:
> ```bash
> sudo -u postgres psql -d <clone> -c 'UPDATE ir_cron SET active = false'
> ```

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
* **It cannot be reached from a browser** — but only because the web server is
  told to refuse it. The original reasoning (an underscore is illegal in a
  hostname, so no address can reach it) turned out to be false: the wildcard DNS
  record resolves it and the wildcard server block matched it, and the template
  served its sign-in page publicly until this was found. See §1. If you ever
  rebuild the wildcard block, keep the underscore rule.
* **It is Vietnamese-ready** (since 2026-09-05). Vietnamese AND English are
  both switched on, the company is set to Vietnam, and it carries the
  **Vietnamese chart of accounts** — 275 accounts, 15 taxes, 6 journals —
  instead of the generic one it had before. A clinic copied from it can be used
  in Vietnamese from its first minute, and its books are already the right
  shape. A person still picks their own language on their own preferences
  screen; English is what a brand-new account opens in.
* **It does not contain**: the data-migration tools, the one-off catchment
  backfill, the Inventory app, the Sales app, the automatic-rules tool, the
  website theme, or fifteen other things this machine has and a clinic does not.
  That list is not written down by hand any more — it is **worked out** from
  what the product itself says it needs, and you can see it on the
  **In step with master** screen under "What a customer's system is made of".
  Today: 175 parts a clinic gets, 33 this machine has that they do not, each
  with a plain sentence saying why.

Rebuilding it from scratch is rarely needed — a normal deploy upgrades it like
any other database. If you must, the build command is in the H3 handover.

---

## 6. Backups

**A copy of every live clinic is taken every night, at 19:30.** Fourteen
nightly copies are kept per clinic; the ones somebody takes by hand, and the
final one before a clinic is closed, are kept for good.

**A copy is two files, and one without the other cannot be put back.**

| | |
|---|---|
| The data | `/odoo/backups/tenants/<slug>/<slug>_<kind>_<when>.dump` |
| The attachments | `…_<when>.filestore.tar.gz` beside it |

Both sizes and the number of attachment files are recorded, and **a copy whose
attachments come out suspiciously small FAILS and is thrown away** rather than
being written down as good. That is not caution for its own sake: a copy taken
from a shell with the wrong home folder reads a different, empty attachments
folder and reports success, and the day you find out is the day you need it.

| What | Where | Kept |
|---|---|---|
| Per-clinic | `/odoo/backups/tenants/<slug>/` | 14 nightly; by hand and final, for good |
| Before the platform change | `/var/backups/saas_h3/` | the master's pre-rename dump, the old nginx and certificate folders, the old application config |
| Deleted stale databases | `/var/backups/stale_dbs/` | **delete after 2026-10-04** — see the README in that folder |

### Proving a copy is good

On a clinic's **Copies** tab, **Put it back as a practice system** restores it
into `<slug>-staging`, with its scheduled jobs switched off so it sends nothing
to anybody. **Remove it when you are done** — every extra system on this
machine costs memory, and the same tab has the button.

It refuses if a practice copy already exists, because two people rehearsing on
one name destroy each other's work. And if a restore fails half-way, the
half-built copy is removed rather than left sitting on a machine with 2 GB of
memory.

By hand, if the screen is unavailable:
```bash
sudo -u postgres createdb -O odoo <slug>-staging
sudo -u postgres pg_restore --no-owner -d <slug>-staging /odoo/backups/tenants/<slug>/<file>.dump
sudo tar xzf /odoo/backups/tenants/<slug>/<file>.filestore.tar.gz -C /tmp
sudo mv /tmp/filestore /odoo/.local/share/Odoo/filestore/<slug>-staging
sudo chown -R odoo:odoo /odoo/.local/share/Odoo/filestore/<slug>-staging
sudo -u postgres psql -d <slug>-staging -c "UPDATE ir_cron SET active = false;"
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

**Since 2026-09-04 (H4b) the platform writes it.** Every five minutes, at the
end of every alert check, and after every message sent to or cleared from a
clinic. The setting that says where is `biz_tenants.status_dir`; the clock it
speaks in is `biz_tenants.status_tz` (empty means the platform company's own
zone), and **the zone is printed on the page** — a file on disk has no reader
to ask what time it is.

**It names no clinic, ever.** One function inside the application decides what
the world may read, and it copies only kinds, levels and durations across that
line; a test feeds it a state full of clinic names and asserts none come out.
A resolved urgent alert appears there as an incident **for seven days**, which
is why an alert raised while somebody is testing must be **Removed** and not
closed with "It is over".

If the page is stale or missing, press **Rewrite the public page** on the
Alerts screen. The platform also tells you itself: the Alerts screen's
"The platform itself" card has a row for it.

---

## 7a. Alerts — and the fact that nothing is emailed

**There is no outgoing mail account on this platform, so nothing is emailed to
anybody.** Everything the platform would have sent is written down on the
**Alerts** screen instead, and every alert says so on its own card ("Nobody was
emailed"). Nothing is lost; it simply has to be looked at rather than arriving.

* The platform looks at everything **every fifteen minutes**: each clinic's
  address, their copies, their certificates, the errors their system logged,
  and this machine's own memory, disk and room for another clinic.
* Every alert carries a plain sentence AND what to do next.
* **Since you were last here** at the top of the screen is how you find out
  anything happened — it counts what is new since you last opened it.
* A red line across the top of every Customers screen means something urgent is
  open.
* Three buttons on each card: **I know** (stops it reminding, leaves it open),
  **It is over** (closes it; an urgent one then shows on the public page as an
  incident for seven days), and **Remove** (takes it away altogether — this is
  the one to use for anything raised while testing).
* **Send a test email** is on the screen and answers honestly. Today it says
  there is no outgoing mail account and what to do about it. Connect one under
  Settings → Technical → Email → Outgoing Mail Servers, set a sender address,
  and press it again — from that day alerts arrive by email as well.

⚠ **Four kinds of alert are NOT found by the fifteen-minute look, and must not
be**: a trial running out, an invoice past its date, an invoice overdue enough
to consider pausing, and a clinic that has been paused. No reading of a machine
can see any of those — they are raised by the morning billing job and by the
buttons a person presses, and they are closed the same way. They are on a list
the sweep never touches; if one ever came off it, the next sweep would decide it
had cleared and close it within the quarter hour and nobody would ever see an
unpaid invoice.

---

## 7b. Sending a release out to every clinic

**Customers → Rollout.** A release reaches the fleet in rings, and the order is
the whole safety argument:

1. **Practice run** — on a throwaway copy of a real clinic's system, restored
   from their last backup. Nobody sees it and the copy is deleted afterwards
   whatever happens. **A release never reaches a real clinic without this**, and
   the screen refuses to start without a backup to practise on.
2. **The blank system** — so a clinic that signs up tomorrow starts on the new
   version.
3. **First clinic** — one, on its own, with a **24-hour watch period**
   afterwards during which its address is checked again.
4. **Early group** — 48 hours of watching.
5. **Everyone else.**

Each real clinic is updated inside **their own quiet window** (22:00 for three
hours by default, on *their* clock — the screen names the zone). Their own
people see a bar the evening before and while it is happening, and it comes
down afterwards whatever the outcome.

**It stops at the first thing that goes wrong** and says why, on the card that
stopped it. From there: **Try again**, **Leave behind** (they stay on the old
release; you have to type their short name), **Carry on**, or **Call it off**.

> ⚠ **READ THIS BEFORE YOU PRESS START, TODAY (2026-09-04).**
> "In step with master" means *every module the master has*. The master is also
> the clinic that runs today, and it has picked up **22 stock apps the product
> does not need** — Inventory (`stock`), Sales, Purchase, Timesheets, Projects,
> the Vietnamese localisation, a website theme. A rollout would install all of
> them on the blank system and on every clinic, so a nurse's system would grow
> an Inventory app and a Sales app overnight.
>
> **No rollout has been run on this platform yet, for that reason.** Somebody
> has to decide one of three things first: put those apps on the never-list, or
> take them off the master, or accept that every clinic gets them. Until then,
> use the per-clinic **Bring in step** button on "In step with master", which
> shows exactly what it would add before it adds anything.

* Only **one rollout at a time** — the practice copy has one name, and two
  rollouts destroy each other's. A stopped rollout that is not going to
  continue must be **called off**, not left lying about.
* Set which ring a clinic is in, and when their night is, on their own page:
  **Customers → the clinic → Updates**.
* Nothing installs on a schedule. A person presses Start; a background job
  then does exactly what was written down and nothing else.

---

## 7d. Switching parts of the product on and off

**Customers → What each customer has.** Every part of the product that can be
sold separately runs down the side, every clinic runs across the top, and a
**miniature of that clinic's own left menu** is drawn beside the grid. Click a
customer's name to draw theirs; click a box to move that switch, and the
miniature redraws so you can see what they will see before you tell them
anything.

The ten parts are: Care Command, Telehealth, Family access, Deterioration
watch, Health-insurance claims, Red invoice, Analytics, Assisted notes and
coding, Phone system, Training.

Three things worth knowing:

* **Switching a part off removes nothing.** The doors close — the entries leave
  their left menu, and anybody following an old link to one of those screens
  gets a page in the product's own words saying that part is not switched on
  and who to ask. Switch it back on and every screen returns with everything
  that was ever recorded behind it.
* **It reaches them in under a minute, with no page reload.** A nurse looking
  at her screen when you move a switch sees the menu redraw itself. Measured at
  21 seconds. (A tab nobody is looking at does not update until somebody looks
  at it — that is deliberate, and it means a background tab is not proof of
  anything.)
* **Nothing is decided by default.** A clinic with no answer recorded has every
  part. The little dark mark under a box means somebody actually decided that
  one.

The small buttons on a row or a column move everything at once, and ask first.
**Tell every customer again** re-sends the answers to everybody — that is the
repair button for a clinic that was unreachable when a switch moved.

---

## 7e. Going into a clinic's system to help

**Customers → open the clinic → Support access → Open as support.**

You type a **reason** and pick **15, 30 or 60 minutes**. You get one link. It
works **once**, it signs you in as the break-glass account (never as one of
their people), and it closes itself at the end — sooner if you press **End now**
or sign out.

While you are in there, **everybody in that clinic sees a rose bar across the
top of every page** saying who is in, why, and how long is left. It cannot be
closed.

Afterwards — and this is the point — **the whole thing is written on their
system, not on ours**: who came in, when, why, for how long, and which screens
they opened. Their own people read it on **About Viet Uc Care → Support
access**. So can you, on the same tab you opened the link from.

**A clinic can refuse it.** The same About screen has their own switch. When it
is off, the platform's door refuses by name, nobody here can turn it back on
for them — and the attempt is still written on their record, so they can see
that somebody tried.

Every session and every refusal also raises a line on the **Alerts** screen the
moment the button is pressed. Nothing is emailed (see §7a).

If a link does not work, the page says why in plain words — used already, ran
out, or not a link this system knows. It never shows an error page.

---

## 7c. Room for another clinic

The fleet screen carries a gauge: **how many more clinics this machine holds**.
It is `(free memory − what is kept back) ÷ what one clinic is allowed`, and
provisioning refuses at nought, by name, pointing at
`docs/SAAS_RESIZE_RUNBOOK.md`.

⚠ **The "what one clinic is allowed" figure is a POLICY, not a measurement.**
It is the setting `biz_tenants.tenant_cost_mb`, **60 MB** by default. The
MEASUREMENT is about **11 MB** — that is what this machine's memory went up by
the first time a real clinic's system was opened, across the three processes
that serve it. That is the system sitting still. Sessions, screens already
drawn and a clinic actually working are the rest, and none of them can be
measured while nobody is using it, so the setting is the measurement plus a
deliberate allowance. Re-weigh it as clinics arrive: it is on **Alerts →
Settings**, with that sentence beside it. `biz_tenants.capacity_reserve_mb`
(400 MB) is what must stay free for the database and the operating system.

---

## 7f. What a clinic pays, and what happens when they do not

Everything below lives on **Customers → Plans and invoices**, on
https://carejiox.com. Nothing here is automatic. **Nobody is ever invoiced by a
scheduled job, nothing is emailed, and no working clinic is ever locked out on
a timer.**

### The three plans, and the fact that their prices are examples

The platform ships with three shapes — one of each way of charging — and
**every figure on them was seeded as an example and has never been agreed with
anybody.** They carry an amber "Example price" badge until somebody opens the
plan, types the real price and saves it; saving is what takes the badge off.

| Plan | How it charges | The example figure |
|---|---|---|
| Starter | One price a month, whatever the clinic does | 2,000,000 ₫ a month |
| Growth | A price for each person in care, every month | 30,000 ₫ each, first 50 included |
| Clinic | One price a month, by how many people are in care | ≤100 → 5,000,000 ₫ · ≤300 → 9,000,000 ₫ · above → 15,000,000 ₫ |

A plan can charge on **any** of the four numbers the platform measures — people
in care, visits completed, staff with a login, invoices issued — because all
four are measured for every clinic every month whatever plan they are on. That
is deliberate: a plan can be changed next year without having lost the history
to bill from.

⚠ **A plan priced by size band must be created WITH its bands, in one save.**
The model refuses a banded plan with no bands (correctly), so a two-step write
fails in between. The screen and the seeder both do it in one; if you ever edit
one from a script, do the same.

### The monthly reading, and why it is never taken twice

A scheduled job at **02:30 each morning** writes down last month's four numbers
for every clinic — and, if it is missing, the month before that. **A month that
already has a reading is never given a second one**, because billing bills from
what was measured at the time; a re-run writes nothing and says so in those
words. A row taken after the month had ended is marked as such, because a count
of people taken in September is today's number wearing an August date.

"Take the reading" and "Fill in the months behind us" do the same thing by hand.

### Raising invoices

1. Pick a month. The current month is offered and marked "not over yet".
2. Read what it would cost. **Nothing on that screen has been created** —
   every clinic is listed with the numbers the platform measured, the plan
   applied to them, and one line explaining the arithmetic in words. A clinic
   that would be left out says why.
3. Press the button at the bottom. That is the only thing on the screen that
   writes anything.

Invoice numbers are sequential inside a year (`INV-2026-0001`) and are read off
the invoices that exist rather than off a counter, so a run that fails leaves no
gap. Cancelling one keeps it in the book with the reason on it.

### The document

Each invoice's PDF is rendered **once, when it is raised**, and stored — a
document that changes after it was sent is not a document. Open it, download it,
or press the envelope: the envelope is honest, says there is no outgoing mail
account, and points at the download.

⚠ **An invoice from this platform is not fit to send until four things are
filled in**: the company name it comes from, its address, its tax number, and
the bank details to pay into. Until then the document PRINTS A RED NOTE SAYING
SO on its own face, and the screen says it above every preview. Nothing was
invented for you. They are on **Plans and invoices → Billing settings**.

### Overdue, and the one switch that can lock somebody out

A job at **07:15 each morning** looks at every issued invoice. Past its date it
raises a flag on the Alerts screen naming the clinic and the number of days, and
raises a reminder once per configured step (3 and 10 days by default) — counted
rather than timed, so a machine that was switched off for a week raises each one
once rather than five.

⚠ **"Pause a clinic automatically when they do not pay" ships OFF and should
stay off.** With it on, an invoice 21 days past its date shuts every one of that
clinic's people out of their own system, in the night, with nobody pressing
anything — and the first they know of it is a locked door on a Monday morning.
With it off (the shipped setting) an overdue invoice is a flag and a person
decides. The switch is at the foot of Billing settings with that paragraph
beside it.

### Pausing a clinic, and letting them back in

**Customers → the clinic → Plan → Shut their door.** It asks for a reason —
which their own people read, word for word, on the page they meet — and for
their short name typed out. Letting them back in is **one press and no typing**:
undoing harm is never made harder than doing it.

**Nothing is deleted.** Pausing shuts a door and nothing else; every record is
where it was and comes back within a minute of resuming. Two accounts still get
in while a clinic is paused: the platform's recovery account
(`platform.recovery@carejiox.com`) and anybody in an open support session.

### Trials, and the fact that one ending does nothing

**Plan → Put them on a trial** sets a date. When it passes, **nothing happens to
their system** — it raises a note on the Alerts screen and waits for a person.
The clinic sees a calm bar for the last ten days that says so in those words.
**They are paying now** moves them across.

### Scheduling a clinic for closing down

**Plan → Shut their door** is a pause; **Closing down** is the end. Between them
sits a retention clock (60 days by default): the date their data MAY be removed.
**Nothing removes it when that date passes.** The clock raises a note and the
button on the Closing down tab is still the only thing that removes anything,
and it takes a final copy first.

### The seat limit

A plan may cap how many people can have a login. Nought — the shipped default on
all three plans — means no limit. With a limit set, a clinic trying to add one
person too many is refused **on their own system** with a sentence naming the
limit, the plan and who to ask. The recovery account and an open support session
are never refused.

### What a clinic sees of all this

One card, **Plan and usage**, on their own "About Viet Uc Care" screen: which
plan, what the platform measured for them last month, how many people have a
login, and when the next invoice is expected. Read-only, and every number on it
is the platform's own measurement rather than a second count that would disagree.


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
