# Making the platform machine bigger — one page

Written 2026-09-04 (SAAS H3). Read this the day the platform runs out of room
for another clinic, or the day somebody sells one more clinic than it holds.

**This is the only part of the capacity story that is not automatic, on
purpose.** Growing the machine costs money and costs everybody a morning, so it
stays a decision a person makes.

---

## What you are changing

| | Today (measured 2026-09-04) | After |
|---|---|---|
| Memory | 1.9 GB (`MemTotal` 1910 MB) + a 2 GB swap file | 4 GB (`t3.medium`) or 8 GB (`t3.large`) |
| Processor | 2 cores | 2 cores (`t3.medium`) |
| Disk | 58 GB, 24 % used | unchanged — the disk is separate from the size |
| Cost | the `t3.small` rate | about twice (`t3.medium`) / four times (`t3.large`) |

**Memory is the thing that runs out, not disk.** This server runs `workers = 2`,
which means it is a *prefork* server: **every database that gets a visitor loads
a full copy of the product into every worker process that serves it**, and there
are three of those (two web workers plus the background one). A clinic that
nobody has opened today costs nothing; a clinic in use costs its share three
times over. That is why the number of clinics this box holds is smaller than the
disk or the processor would suggest.

**Expected downtime: 10 to 20 minutes**, nearly all of it the stop and the first
boot. Every clinic is signed out and every address is unreachable for the whole
of it. Do it early on a Sunday, and put a notice up the day before.

---

## Before you start

1. **Tell everybody**, with the window written out in local time.
2. **Take a backup of every clinic** (`/odoo/backups/tenants/<slug>/`). The
   snapshot in step 2 covers the whole machine, but a whole-machine snapshot is
   not something you can restore *one clinic* from.
3. **Write down the current address: `54.206.18.111`.** It is an AWS **Elastic
   IP**, so it survives a resize: you stop the instance, change its type and
   start it again, and the address comes back with it. **Nothing at the domain
   registrar changes.** Nothing on the box names the address either — nginx
   routes by `server_name`, so there is nothing to edit afterwards.
4. **Know the instance**: `i-0fb43cd9281f12945`, `t3.small`, zone
   `ap-southeast-2a`, region `ap-southeast-2` (Sydney).

---

## The move

EC2 **can** change an instance type in place — unlike Lightsail, there is no
snapshot-and-rebuild. That is why this is twenty minutes and not an hour.

1. **Stop the application cleanly** (so nothing is half-written):
   ```bash
   ssh VietUcUAT
   sudo service odoo-server stop
   sudo systemctl stop nginx
   sudo systemctl stop postgresql
   sync
   ```
2. **Take a snapshot anyway, as the way back.** EC2 console → the instance →
   Storage → the root volume → *Actions* → *Create snapshot*. Name it
   `carejiox-before-resize-YYYY-MM-DD`. Wait for *Completed* (10–20 min for this
   disk). You can do this while the machine is stopping.
3. **Stop the instance.** EC2 console → the instance → *Instance state* →
   *Stop instance*. Wait for **Stopped** (not "stopping").
4. **Change the type.** *Actions* → *Instance settings* → *Change instance
   type* → pick **`t3.medium`** (4 GB, 2 cores) — the next size up, and roughly
   double the clinics this platform holds. `t3.large` (8 GB) if you are buying a
   year of room. Apply.
5. **Start the instance.** *Instance state* → *Start instance*.
6. **Check the address came back.** The Elastic IP re-associates by itself:
   ```bash
   dig +short @8.8.8.8 carejiox.com     # 54.206.18.111
   ssh VietUcUAT 'curl -4 -s ifconfig.me'   # 54.206.18.111
   ```
   If it did **not**, EC2 console → Elastic IPs → the address → *Associate* →
   this instance. Nothing at the registrar changes either way.
7. **Check it came up:**
   ```bash
   ssh VietUcUAT
   free -m                                    # MemTotal ~3900 or ~7900
   sudo systemctl is-active postgresql nginx
   sudo service odoo-server status
   pgrep -cf '^python3 /odoo/odoo-server/odoo-bin'   # 4
   ```
   If the application did not start on its own: `carejiox-deploy -s`.
8. **Let the database server use the new memory.** PostgreSQL was tuned for a
   2 GB box and will not use more on its own. In
   `/etc/postgresql/16/main/postgresql.conf`:
   | setting | now | on 4 GB | on 8 GB |
   |---|---|---|---|
   | `shared_buffers` | 128MB | **1GB** | **2GB** |
   | `effective_cache_size` | (default) | **2GB** | **5GB** |
   then `sudo systemctl restart postgresql` and `carejiox-deploy -s`.
   Skipping this is not dangerous — it just leaves some of the new machine
   unused.
9. **Keep the 2 GB swap file** (`/swapfile`). It is not a substitute for memory
   and it is not there to be used; it is there so that a bad afternoon ends in
   something slow rather than in something killed. Leave it exactly as it is.

---

## Verify before you tell anybody it is done

Work down this list. Every row is something a person would notice.

| # | Check | How |
|---|---|---|
| 1 | The application is running | `pgrep -cf '^python3 /odoo/odoo-server/odoo-bin'` → 4 |
| 2 | It finished loading | `sudo grep -a "Modules loaded" /var/log/odoo/odoo-server.log \| tail -1` |
| 3 | The platform answers | open `https://carejiox.com` and sign in |
| 4 | Every clinic answers | open each clinic's own address (`<slug>.carejiox.com`) and check the sign-in page appears |
| 5 | Certificates are still trusted | no browser warning on the platform address and on one clinic address; `sudo certbot certificates` lists them all unexpired |
| 6 | Certificates still renew | `sudo certbot renew --dry-run` → all simulated renewals succeeded |
| 7 | The old address still forwards | `curl -sI https://care.biztinct.com/` → `301` to `https://carejiox.com/` |
| 8 | The status page is served | `curl -sI https://carejiox.com/status` → `200` **with a `Last-Modified` header** (that header is the proof it came off disk and not out of the application) |
| 9 | No database manager anywhere | `curl -sI https://carejiox.com/web/database/manager` → `404`, and the same on a clinic address |
| 10 | Scheduled jobs are running | `sudo grep -a "odoo.addons.base.models.ir_cron" /var/log/odoo/odoo-server.log \| tail` — activity, no repeated errors |
| 11 | The template's jobs are still OFF | `sudo -u postgres psql -d carejiox_template -Atc "select count(*) from ir_cron where active"` → **0** |
| 12 | Backups still work | run one by hand into `/odoo/backups/tenants/` |

Then take the notice down.

---

## Afterwards

* **Keep the snapshot for 48 hours**, then delete it (AWS charges for it).
* **Write down what the new machine measured** — `free -m`, and the memory one
  clinic costs — in the SAAS ledger, so the next person knows what changed.
* The per-clinic memory cost does **not** change when you resize. The same
  clinic costs the same memory on a bigger machine; what changes is how much
  free memory there is to spend.

## If it goes wrong

Stop the instance, change the type back to `t3.small`, start it. That is the
whole rollback and it takes about ten minutes — which is why changing the type
in place is preferred over rebuilding from the snapshot. Use the snapshot only
if the disk itself is damaged.
