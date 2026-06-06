# Migration ROLLBACK & RE-RUN guide

Everything the migration does is **reversible** and **idempotent**. Migrated
business records carry a legacy key; auto-created dimension records are logged in
`migration.xref`; archived pre-existing records are logged in `migration.baseline`.

How to open a shell on UAT:
```bash
ssh VietUcUAT
sudo su - odoo -s /bin/bash -c \
  "/odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d vietuat --no-http"
```
Each snippet below ends by committing — call `env.cr.commit()` after it.

---

## What the migration created (all findable)
| Records | How to find them |
|---|---|
| Clients (patients) | `res.partner` where `legacy_client_code != False` |
| Bookings | `health.fieldservice.order` where `legacy_booking_ref != False` |
| Leads | `crm.lead` where `legacy_contact_guid != False` |
| Sale orders | `sale.order` where `origin like 'BKG-%'` |
| Payments | `health.payment.transaction` linked to a booking with a legacy ref |
| Staff stubs / services / facilities | `migration.xref` where `auto_created = True` |
| Pre-existing data we archived | `migration.baseline` |

---

## Level 1 — Restore the pre-existing (demo/test) data that was archived
Un-hides everything the archive step set to `active=False`:
```python
env['migration.runner'].restore_baseline(run_tag='legacy_mig')
env.cr.commit()
```

## Level 2 — Hide the migrated data (reversible, keeps it in the DB)
Archives every migrated client/booking/lead/payment/sale order (sets `active=False`),
leaving reference dimensions in place:
```python
env['migration.runner'].purge_migrated(delete=False)
env.cr.commit()
```
To bring it back: `res.partner` etc. with the legacy key, set `active=True` — or just
re-run the import (idempotent, restores active records).

## Level 3 — Full purge (DELETE migrated data + auto-created dimensions)
Hard-removes migrated business records AND the staff stubs / services / facilities
the migration fabricated, and clears the xref + baseline logs:
```python
env['migration.runner'].purge_migrated(delete=True)
env.cr.commit()
```
> Use Level 3 only to start completely clean (e.g. before importing the real,
> unredacted export). Records that can't be deleted (referenced elsewhere) are
> archived instead and reported.

## Full reset to pre-migration state
```python
r = env['migration.runner']
r.purge_migrated(delete=True)   # remove everything migration added
r.restore_baseline()            # un-archive the original demo/test data
env.cr.commit()
```

---

## Re-running the import (idempotent)
Re-running **updates in place** (keyed on legacy fields) and never duplicates —
this is exactly how the **real unredacted export** will be loaded later:
```python
r = env['migration.runner']
rep = r.run_migration(booking_path='/tmp/Booking_mig.json',
                      contact_path='/tmp/Contact_mig.json')
env.cr.commit()
print(rep)
```
Dry-run instead: end with `env.cr.rollback()` (nothing persists).

Archive the pre-existing data so only migrated rows show:
```python
rep = {}
env['migration.runner'].archive_baseline(rep)   # logs to migration.baseline
env.cr.commit()
```

---

## Emergency DB-level rollback (last resort, psql)
Only if the ORM path is unavailable. Archives (does not delete):
```sql
-- as: sudo -u odoo psql -d vietuat
UPDATE res_partner SET active=false WHERE legacy_client_code IS NOT NULL;
UPDATE crm_lead   SET active=false WHERE legacy_contact_guid IS NOT NULL;
UPDATE health_fieldservice_order SET active=false WHERE legacy_booking_ref IS NOT NULL;
-- restore archived baseline:
UPDATE res_partner p SET active=true
  FROM migration_baseline b
  WHERE b.target_model='res.partner' AND b.res_id=p.id;
```
(Repeat the restore for each `target_model` in `migration_baseline`.)
Prefer the ORM snippets above — they keep computed fields and stage/state consistent.
