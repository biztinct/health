# Consent enforcement on the FHIR facade — operations runbook

**Applies to:** `health_fhir_core.consent_enforced` on `vietuat`.
**State as of 2026-08-02 (Phase GC-2, register item G5):** **ENFORCED
(deny-by-default).** Flipped in the GC-2 deploy, verified live — see
"Evidence" below.

---

## ⚠️ Read this first

With the gate enforced, **the facade serves a patient's data to an external
system only if that patient has an active `data_sharing` consent on file.**

There are, today, almost no such consents in the database. That is not a
defect — it is the correct and intended state: **with zero consents recorded,
the facade correctly serves zero PHI.** A partner who connects tomorrow will
get empty Bundles until consent capture happens, and that is the safe failure
direction. Turning the gate back off to "make the integration work" would
release patient data without a lawful basis.

**Capturing `data_sharing` consent for real patients is an operational task
with an operational owner** (§10.11 of the compliance tracker). Engineering
has provided the gate, the audit trail and this runbook; it cannot provide
the consents.

---

## 1. What the gate does

| | Log-only (`False`) | Enforced (`True`) — current |
|---|---|---|
| Consent check runs | yes, every request | yes, every request |
| Written to `health.consent.check.log` | yes | yes |
| Un-consented patient in a search Bundle | **included** | **excluded**, and `total` is reduced |
| Un-consented patient read by id | 200 with data | **404 OperationOutcome** |
| `Patient/$everything` for an un-consented patient | full bundle | denied |

The check is per patient and deny-by-default: a resource carrying more than
one patient is served only if **every** patient on it is consented
(`serializers/base.py`, `consent_allowed_records`).

A denial is deliberately **indistinguishable from "no such record"**. The
404 body for an un-consented patient is byte-identical in shape to the 404
for an id that never existed — only the id in `diagnostics` differs. This is
intentional: a distinguishable "denied" answer would confirm to an
unauthorised caller that a given person is a patient here.

## 2. How ops records a `data_sharing` consent

The consent must exist **before** an external system asks for that patient.

1. Obtain the patient's (or their legal representative's) informed agreement
   to share their record with the named external system, by the facility's
   normal consent procedure.
2. In Odoo: **Consents → New**, then
   - **Client** = the patient,
   - **Consent Type** = `Data Sharing`,
   - **Method** = how it was obtained (`verbal` with a witness,
     `digital_signature`, `paper`…),
   - **Effective / Expiry date** — an expiry makes the consent lapse
     automatically; leave empty for open-ended.
3. Press **Grant**. The consent moves to `active`; only an `active` consent
   (within its date window) satisfies the gate. `draft` does not.
4. Withdrawal: press **Withdraw** — never delete. Withdrawn and expired
   consents are immutable audit records (`health.consent.unlink` refuses
   anything but a draft), and both read as `inactive` on the FHIR facade.

Bulk capture for an existing patient population is a project, not a data
migration: each row must be traceable to a real act of consent.

## 3. Where the evidence lives

| Evidence | Model / table | Notes |
|---|---|---|
| The consent itself | `health.consent` | append-only once granted |
| Every check, allowed **and denied** | `health.consent.check.log` | one row per patient per request; `source = 'fhir_facade'` for the facade. Append-only: `write`/`unlink` raise. |
| Every request that returned data | `api.audit.log` | route, user, status, record ids, patient ids |

Two things to know before an audit:

- **A denial writes a consent-check row but no `api.audit.log` row.** The
  request never reached the audit call — it raised not-found first. To show
  "we refused to release X", read the check log (`result = false`), not the
  audit log.
- **Deleting a patient deletes their check-log rows.** `client_id` is
  `ondelete='cascade'`, so the database removes the evidence without the
  model's append-only guard ever running. Archive patients (`active = False`);
  do not delete them.

Useful query — every refusal in the last week:

```sql
SELECT l.create_date, l.client_id, p.name, l.source
FROM health_consent_check_log l JOIN res_partner p ON p.id = l.client_id
WHERE l.result = false AND l.consent_type = 'data_sharing'
  AND l.create_date > now() - interval '7 days'
ORDER BY l.create_date DESC;
```

## 4. Changing the setting (both directions)

The parameter is seeded `noupdate="1"`, so **editing the XML does nothing on
upgrade** — the value must be written to the database. And it is read through
a per-worker `ormcache`, so **a write is not seen until a full restart**
(conventions §5.48): a reload is not enough, and the workers will keep serving
the old behaviour, silently, for as long as they live.

```bash
# enforce (current state)
ssh VietUcUAT 'sudo su - postgres -c "psql -d vietuat -c \
  \"UPDATE ir_config_parameter SET value='"'"'True'"'"' \
    WHERE key='"'"'health_fhir_core.consent_enforced'"'"'\""'
ssh VietUcUAT 'sudo service odoo-server stop && sleep 6 && \
  sudo service odoo-server start && sleep 12 && \
  curl -s -o /dev/null -w "HTTP:%{http_code}\n" localhost:8069/web/login'

# confirm what the SERVER now believes (not just what the table says)
ssh VietUcUAT 'sudo su - postgres -c "psql -d vietuat -tAc \
  \"SELECT value FROM ir_config_parameter \
    WHERE key='"'"'health_fhir_core.consent_enforced'"'"'\""'
```

Turning it back to `False` is a **decision with a compliance consequence**,
not a troubleshooting step. If an integration returns empty Bundles, the
answer is almost always a missing consent (§2), and the check log will say so
in one query.

## 5. Verifying the gate after any change

Deploy-time (automatic): the consent suites run in both modes and set the
parameter themselves —
`health_fhir_core/tests/test_fhir_consent.py` (5 tests) and
`test_fhir_everything.py`. Green in both modes is the acceptance criterion.

Live (manual, ~2 minutes) — the shape of the GC-2 probe:

1. Create two synthetic patients, one with a granted `data_sharing` consent.
2. Issue a token for a test OAuth client with `system/Patient.read`.
3. `GET /fhir/r4/Patient?name=<prefix>` → the Bundle must contain **only**
   the consented patient, and `total` must be **1**, not 2.
4. `GET /fhir/r4/Patient/<unconsented id>` → **404**.
5. `SELECT … FROM health_consent_check_log WHERE source='fhir_facade'` →
   one row per patient, `result` true and false respectively.
6. Delete the un-consented fixture; **archive** the consented one (its
   granted consent is an un-deletable audit record and FK-restricts the
   patient). Re-verify in a **fresh** cursor — a `psql` session, not the shell
   that made the change (conventions §5.34).

## 6. Evidence — GC-2, 2026-08-02, vietuat

Parameter flipped to `True`, full restart, then, with a live gateway token:

```
GET /fhir/r4/Patient?name=GC2PROBE          → 200, Bundle total = 1
                                              (only the consented patient)
GET /fhir/r4/Patient/<unconsented>          → 404 OperationOutcome not-found
GET /fhir/r4/Patient/<consented>            → 200
GET /fhir/r4/Patient/99999999               → 404, same shape as the deny

health_consent_check_log (source = fhir_facade):
  consented   → result = true   (search + read)
  unconsented → result = false  (search + read)
```

Full transcript, fixture ids and the fresh-cursor cleanup verification:
`docs/strategy/reports/gc-2-report.md` §4.

---

*Owner of the operational half (consent capture): facility operations. See
§10.11 of `docs/strategy/hl7-fhir-compliance-response.html`.*
