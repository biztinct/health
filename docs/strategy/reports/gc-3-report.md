# Phase GC-3 — continuous conformance machinery

**Implementer:** Opus 5 · **Date:** 2026-08-03 · **Branch:** 19.0
**Handover:** `docs/strategy/handovers/hl7-gap-closure.md` §4
**Register items:** G4 (engineering closed — owner naming remains OPS), G10 (closed)
**Carry-ins:** GC-2 review R1 (consent-log durability), R2 (emit-only bindings), R3 (audit attribution proven live)

**Result: 0 failed, 0 error(s) of 154 tests on vietuat.** Server healthy
(HTTP 200). Five conformance controls now run without anyone remembering to:
CI on every push, a baseline diff in the suite, a smoke after every deploy,
sampled validation on live traffic, and a weekly cron with an assignee.

---

## 1. Headline: the new machinery found three live defects on its first runs

None of the three was in the handover, and none would have been found by the
tests that already existed — two of them are only visible to a
minimally-scoped token over real HTTP, which is precisely what the new
controls introduce.

### 1.1 Every FHIR data route was declared read-only — and writes

Odoo 19 defaults an `auth='none'` route to `readonly=True` (`http.py:924`).
All three FHIR data routes are `auth='none'` GETs, so all three ran on a
read-only cursor — while every one of them **writes an `api.audit.log` row**.
The framework normally recovers (a `ReadOnlySqlTransaction` escaping a
read-only route makes it retry on a read/write cursor), but `_audit`
deliberately swallows every exception so that auditing can never break a
read — and that swallows the signal the retry depends on. The transaction is
then poisoned and the next query fails, so the caller gets a **500**.

This was invisible on vietuat because the deployment has no read replica:
`registry.cursor(readonly=True)` hands back an ordinary read/write cursor, so
the writes simply worked. It became visible the moment GC-3 put an `HttpCase`
on the route — the test framework issues a genuinely read-only cursor.

Fixed by declaring `readonly=False` on the three data routes, which is what
they have always been. Same mechanism, same fix, and the same reasoning
already written down in `health_telemonitoring/controllers/ingest.py`.
**A read replica in front of this deployment would have 500'd every FHIR read.**

### 1.2 A missing ACL returned an HTML page from a FHIR endpoint

Found by the deploy smoke on its first authenticated run:

```
FHIR-SMOKE FAIL: /fhir/r4/DocumentReference?_count=1 returned HTTP 403 (<!doctype html>
<html lang=en>
<title>403 Forbidden</title>
<h1>Forbidden</h1>
<p>Uh-oh! Looks like you have stumbled upon some top-secret records.<br><br>Sorry, GC3 Smoke Probe (id=6453) doesn&#39;t )
```

`_authenticate` translates the gateway's `AccessError` into a FHIR 403, but
an `AccessError` raised by the **query itself** escaped every handler. A
partner integration whose service user is missing one model's
`ir.model.access` row therefore received `<!doctype html>` from a FHIR
endpoint — unparseable by any FHIR client — with the Odoo user's name and id
in the body. Same class of integration-breaking defect as G14 and G15.

Fixed: `_access_denied_response` converts it to a 403 `OperationOutcome`
whose diagnostic names the **FHIR resource type** and nothing else — enough
for an integrator to know which scope to request, nothing about the internal
model or the ACL rule. Regression test `test_92` asserts both halves,
including that `health.clinical.note` and `ir.model.access` do not appear in
the response body.

### 1.3 G14 again, on `hr.employee` — and the smoke found it too

With the 403 now legible, the next authenticated run named the next problem:

```
FHIR-SMOKE type Practitioner: HTTP 403
… AccessError: The fields "message_main_attachment_id,legal_name,private_phone,
private_email,lang,place_of_birth,country_of_birth,birthday,…,salary_distribution,
permit_no,visa_no,…,emergency_contact,emergency_phone,barcode,pin,
private_car_plate,employee_properties,…,hourly_cost", which you are trying to
read, are not available for employee public profiles.
```

This is **G14's exact defect on a second model**. `hr.employee` treats every
field outside its public-profile whitelist as private, and the Practitioner
serializer still used the blanket "every stored field" prefetch — so ~30
HR-private fields were dragged into the read and *any* Practitioner
serialization raised AccessError for a service user without an HR group.
GC-1's own remedy anticipated it in as many words ("serializers over models
with group-gated fields MUST declare `prefetch_fields`"); Patient was
declared, Practitioner was not.

Fixed with the same one-line pattern: `prefetch_fields` on
`PractitionerSerializer`, listing only the eight fields `to_fhir` and
`_identifiers` actually read. `test_93` asserts the declaration is minimal
and that the prefetch itself now succeeds for a non-HR user.

**Not fixed, and reported instead (F2):** `to_fhir` also reads
`healthcare_skill_ids` for `Practitioner.qualification`, and that field is
private on the public profile as well. Exposing it means adding it to
health_base's public-employee whitelist, and `health_base` is not a module
GC-3 sanctions. Until that decision is made, a Practitioner-reading token
still needs an HR-privileged service user. The prefetch fix is still worth
having on its own: it removes ~30 unnecessary gated fields from every read.

---

## 2. What was built

### R1 — the consent check log outlives its subject (§4.0)

`health_consent/models/health_consent_check_log.py`:

- `client_id` is now `ondelete='set null'` (was `cascade`) and no longer
  `required` — a required column cannot accept the SET NULL, and a row whose
  subject is gone is still evidence.
- New stored `client_ref` Char, frozen at create time as `Name [patient_code]`
  (bare name when there is no code), so a surviving row still names its
  subject. Filled in an `@api.model_create_multi` `create` override, so it is
  captured whatever path wrote the row.
- The append-only `write`/`unlink` guard is untouched.
- **No backfill.** Rows predating the field have an empty `client_ref`, said
  so in the field help: a fabricated label is worse evidence than an honest
  blank.
- Exposed as an optional column on the check-log list view (the only thing
  that names the subject of an orphaned row), with `vi.po` entries for the
  label and the help.

Odoo applies both DDL changes on upgrade — the FK is dropped and recreated
with the new `ondelete` (`registry.check_foreign_keys`) and the NOT NULL is
dropped (`fields.py:1179`) — so no migration script is needed.

Tests: `test_13` (two real deny rows written by `check_consent`, patient
hard-deleted, rows survive with `client_id` empty and `client_ref` intact),
`test_13b` (an orphan is still append-only), `test_13c` (the bare-name branch
and the empty-recordset branch of the label).

### R2 — the two emit-only status bindings (§4.0)

`test_fhir_bindings.py` gained `test_67` (DocumentReference.status ⊆
`{current, superseded, entered-in-error}`) and `test_68` (Location.status ⊆
`{active, suspended, inactive}`, both branches exercised on real fixtures).
Both assert values read out of **serializer output**, never retyped from the
serializer source.

Worth recording, because it changes what the binding tier is for:
**`fhir.resources` does not validate required-binding membership at all.**
Measured on the server —

```
Location {"status": "not-a-status"}          → VALID
Location {"meta": {"lastUpdated": "not-a-date"}} → ValidationError
```

— so a resource can pass `validate_resource` and still carry a code that is
not in its required ValueSet. The binding tests are the only thing standing
between the facade and that defect, and the C4/C5 validation controls cannot
substitute for them.

### C1 — the CI conformance gate (§4.1)

`.github/workflows/fhir-conformance.yml`: `container: odoo:19` +
`postgres:15`, triggered by push/PR on `addons/health_fhir_*`,
`addons/health_condition`, `addons/health_base` or the workflow itself, plus
`workflow_dispatch`. Installs the three FHIR modules (the chain pulls the
~50-module spine automatically), runs their test tags, uploads the odoo log
as an artifact on every run.

**Four gates, not one** — the last is the one that matters:

0. a log file was produced at all;
1. the run exited zero (§5.75: an `EXIT:1` with `FAIL: 0` is an ERROR-line
   problem, not a pass);
2. an `odoo.tests.result` line exists **and** says `0 failed, 0 error(s)`
   (no line = no suite ran = failure);
3. **at least 50 test methods actually executed** (§5.83). Phase GB found 28
   `HttpCase` classes that had never once run; a gate that can go green while
   running nothing is not a gate. A floor, not a pin: it fails on collapse,
   not on growth.

Each gate is its own named step, and so is each attempt at installing
`fhir.resources`. That shape is a direct response to a constraint discovered
while getting the first runs green: **downloading an Actions log requires
repo-admin rights, which the implementing session did not have** — but every
step's name and conclusion are public. Splitting the work into named steps
makes a red build diagnosable from the run summary alone, by anyone, without
a token. It also documents itself: the step list *is* the checklist.

`addons` is listed **first** in the addons-path. This repo tracks the
deployment's copies of several core Odoo modules (`account`, `crm`, `mail`,
`sale`, `hr`, `web`, `product`, `calendar`), because on the server
`/odoo/odoo-server/addons` is one directory holding both. Listing the image's
packaged addons first would silently test different code from the one that is
deployed.

Also delivered: `tools/ci_fhir_local.sh` — the same suite, the same gates,
the same messages, against a local Odoo checkout — and
`docs/conformance/ci-runbook.md` covering both. See §5 D3 for why the
fallback ships unconditionally rather than only on a blocked run.

### C3 — the post-deploy conformance smoke (§4.2)

`tools/fhir_deploy_smoke.sh` + `docs/conformance/deploy-smoke.md`. Runs on
the server after the restart step; six checks (metadata 200, `fhirVersion`,
the `software` element, `software.version == $1`, resource count ≥ 22, and in
token mode a 200 searchset `Bundle` for every interaction-bearing type plus
one psql check that the newest `/fhir/r4/` audit row carries a non-empty
`key_or_client` **and** `auth_kind`). The type list is read out of the
capability response, so a new resource type is probed the first release it
exists with no edit to the script.

The version comparison is a hard FAIL, because "copied the files, forgot the
upgrade" is the most common silent deploy failure and nothing else catches
it. Verified both ways before use (§4 below).

The audit check is R3: it is the GC-2 review's M2 fix, asserted live rather
than assumed.

### C4 — sampled runtime validation (§4.3), register item G10

`serializers/base.py`: `validation_sample_pct(env)` and
`validation_sample_hit(env, client_label)` beside the existing
`validation_enabled(env)`. Two independent triggers:

- `health_fhir_core.validate_canary_client` — one client label, matched
  against `request.gateway_auth['key_ref']`, i.e. **the same identifier the
  audit row carries**, so "which client drifted" and "which client was
  sampled" are the same question. Every response to that client is validated.
- `health_fhir_core.validate_sample_pct` — an int 0–100, parsed defensively
  and clamped. Unset, blank, `banana`, `True` and `-5` all mean 0; `900`
  means 100. A typo in a config parameter must not become an outage, and must
  not silently mean "validate everything" either.

The controller decides at the three existing seams via `_should_validate`.
`_runtime_validate` logs `FHIR-CONFORMANCE-DRIFT rtype=%s id=%s: %s` at ERROR
and **swallows** the finding: a facade that 500s because its own validator
disagrees with it has converted a monitoring control into an outage.

Both parameters are left **unset** by this phase — the mechanism is delivered
and tested; choosing a rate is a deployment decision. `deploy-smoke.md` and
`ci-runbook.md` say where it lives.

### C5 — the weekly conformance cron (§4.4)

New `health_fhir_core/models/fhir_conformance.py`, AbstractModel
`fhir.conformance`, method `run_weekly_check()`:

1. rebuild the capability from a cleared cache and compare it to the
   committed baseline, using a normalization **byte-identical** to the test's
   — the CI control and the production control must not be able to disagree
   about what "unchanged" means;
2. serialize and validate one record of every registered type
   (`search(limit=1)` as superuser, no record rules and no consent gate: this
   is an in-process self-check, and a narrowed sample would hide exactly the
   drift it exists to find). A type with no records is skipped and **not
   counted** — an empty table is not a conformance failure;
3. on any failure, `_logger.error('FHIR-CONFORMANCE-FAIL …')` **and** a
   `mail.activity` on the partner of `health_fhir_core.conformance_owner_login`
   (admin fallback, with a WARNING when the named login does not exist). One
   open activity at a time (§5.89: the dedupe key is whatever you search on),
   because a weekly cron that stacks a new to-do every run turns a finding
   into noise. On success, one line: `FHIR-CONFORMANCE-OK <n> types`.

Cron record in a **new** `data/fhir_conformance_cron.xml`, never in
`data/fhir_data.xml` — that file is a `noupdate="1"` configuration seed whose
values are owned by the deployment (GC-2 flipped `consent_enforced` in the
database), and re-writing it is how a seed cutover gets silently reverted.

Live on vietuat: `ir_cron` id **141**, active, every 7 days, next call
`2026-08-09 03:00:00`, model `fhir.conformance`, code
`model.run_weekly_check()`.

---

## 3. Test results (verbatim)

```
# shipping run — the exact committed code, health_consent + health_fhir_core
# upgraded together, four test tags
2026-08-02 20:51:49 INFO odoo.tests.result: 0 failed, 0 error(s) of 154 tests
                          when loading database 'vietuat'
EXIT:0   HTTP:200

grep -ac "Starting Test.*\.test_"   → 154   (every test the result line counted)
grep -ac "FAIL:\|ERROR:"            → 0
grep -ac "ERROR: setUpClass"        → 0     (§5.75 — no HttpCase died in setUpClass)
```

New tests, all confirmed executed by name (§5.83/§5.90 — a count of failures
is not evidence):

```
TestHealthConsent.test_13, test_13b, test_13c                 (3)  R1
TestFHIRBindings.test_67, test_68                             (2)  R2
TestFHIRSamplingGC3.test_80…test_83                           (4)  C4 sampling
TestFHIRRuntimeValidationGC3.test_84…test_86, test_92, test_93 (5)  C4 over HTTP + both defect fixes
TestFHIRConformanceCronGC3.test_87…test_91                    (5)  C5
```

`TestFHIRRuntimeValidationGC3` is an `HttpCase` and really executed —
`grep -ac "ERROR: setUpClass"` is 0 and its five methods appear by name
(§5.75/§5.83). No test was skipped.

### The gate proving itself

The first run of this phase's suite, before the defects of §1 were fixed, is
the failing half of C1's acceptance criterion ("a deliberately-broken
serializer is rejected") — the same code, the same command, the same three
gates, red then green:

```
20:23:22 ERROR odoo.tests.result: 5 failed, 1 error(s) of 151 tests   EXIT:1
20:31:33 INFO  odoo.tests.result: 0 failed, 0 error(s) of 152 tests   EXIT:0
20:44:50 ERROR odoo.tests.result: 0 failed, 1 error(s) of 154 tests   EXIT:1   ← §1.3, mid-fix
20:51:49 INFO  odoo.tests.result: 0 failed, 0 error(s) of 154 tests   EXIT:0   ← shipped
```

Note the third line: `EXIT:1` with `FAIL: 0`. That is the §5.75 shape the
gate's first check exists for — a run that reads like success to anything
counting only failures.

---

## 4. Live verification on vietuat

### Deploy smoke, both outcomes

```
# wrong version (server was 19.0.1.4.0)
$ /tmp/fhir_deploy_smoke.sh 19.0.1.5.0
FHIR-SMOKE FAIL: metadata: software.version is '19.0.1.4.0' but this deploy was
'19.0.1.5.0' — the server is NOT running the release you think it is
EXIT:1

# no argument
FHIR-SMOKE FAIL: no expected software version given (usage: … <version>)   EXIT:1

# after the upgrade, metadata mode
$ /tmp/fhir_deploy_smoke.sh 19.0.1.5.0
FHIR-SMOKE ok:   metadata: fhirVersion 4.0.1, software.version 19.0.1.5.0, 22 resources (21 interaction-bearing)
FHIR-SMOKE note: FHIR_SMOKE_TOKEN is unset — metadata-only run. The authenticated half
(search + audit attribution) was NOT executed.
FHIR-SMOKE ok:   smoke passed (metadata only)   EXIT:0
```

### Token mode + the R3 audit-attribution proof

Run with a **throwaway** probe client, created and destroyed inside this
phase (`smoke_test_client`, the OPS-owned one, was not touched — it is still
inactive, verified below). 20 of the 21 interaction-bearing types answered
with a 200 searchset Bundle; `Practitioner` is finding F2:

```
FHIR-SMOKE ok:   metadata: fhirVersion 4.0.1, software.version 19.0.1.5.0, 22 resources (21 interaction-bearing)
FHIR-SMOKE type Practitioner: HTTP 403 {"resourceType": "OperationOutcome", "issue":
  [{"severity": "error", "code": "forbidden",
    "diagnostics": "Access to Practitioner is not permitted for this token"}]}
FHIR-SMOKE: 21 types probed, failures: Practitioner(HTTP403)
FHIR-SMOKE ok:   audit attribution: key_or_client=3166aa393eef4927872ffd38d66ed695 auth_kind=oauth
FHIR-SMOKE FAIL: these types did not return a searchset Bundle: Practitioner(HTTP403)
EXIT:1
```

Three things are proven by that transcript:

- **R3 is satisfied.** `key_or_client=3166aa393eef4927872ffd38d66ed695
  auth_kind=oauth` — the GC-2 review's M2 fix, asserted live against the
  newest `/fhir/r4/` audit row rather than assumed.
- The 403 is now a parseable `OperationOutcome` (§1.2) instead of an HTML
  page, and it names the FHIR type without leaking the Odoo model.
- The script enumerates **every** failing type and still runs the audit check
  before exiting non-zero — stopping at the first failure would have reported
  `Practitioner` and hidden whether the other 20 worked.

The consent gate is enforced on this deployment and no `data_sharing`
consents are recorded, so PHI-bearing types correctly returned empty Bundles.
An empty `entry` is a pass here: the check is on the Bundle, not its contents.

**Fixture cleanup + fresh-cursor verification** (psql, new connection):

```
oauth_client_182              → 0 rows      (credential destroyed)
tokens_for_182                → 0 rows
probe_user_active             → false       (ARCHIVED, not deleted: the 48
                                             audit rows it created are
                                             append-only evidence and must
                                             stay attributable to a real row)
fhir_audit_rows_from_probe    → 48
newest_fhir_audit             → 3166aa39…|oauth|127.0.0.1|/fhir/r4/Task
smoke_test_client_untouched   → smoke_test_client | active=f
```

### The weekly check against live data

Called directly:

```
$ env['fhir.conformance'].run_weekly_check()
RESULT: []
CHECKED: 12   FAILURES: []
FHIR-CONFORMANCE-OK 12 types
```

…and fired through the **cron record itself**, so the XML → `ir.actions.server`
→ model path is proven rather than assumed (a green unit test says nothing
about whether the cron is wired up):

```
$ env['ir.cron'].browse(141).method_direct_trigger()
GC3CRON before: name=FHIR: weekly conformance check active=True nextcall=2026-08-09 03:00:00
GC3CRON triggered ok

/var/log/odoo/odoo-server.log:
2026-08-02 20:53:35 INFO vietuat odoo.addons.health_fhir_core.models.fhir_conformance:
  FHIR-CONFORMANCE-OK 12 types
```

Twelve of the 21 registered types have at least one record on vietuat; the
other nine are empty tables and are honestly not counted.

---

## 5. Deviations from the handover, with reasoning

**D1 — `readonly=False` on the three FHIR data routes.** §4.3 sanctions
controller edits "at the existing `_runtime_validate` seams"; this is a
different line in the same file. Forced: without it every `HttpCase` on a
FHIR route 500s, so C4 could not be tested over HTTP at all — and, more
importantly, it is a live defect that a read replica would have turned into
a total outage of the facade (§1.1).

**D2 — `AccessError` → FHIR 403 `OperationOutcome`.** Not in the handover.
Found by this phase's own deploy smoke on its first authenticated run (§1.2).
Shipped because an HTML page from a FHIR endpoint is a conformance defect of
exactly the class GC-1 was chartered to close, the fix is contained to the
sanctioned file, and leaving it would have meant shipping a smoke script whose
first real use fails.

**D3 — `tools/ci_fhir_local.sh` + `ci-runbook.md` ship unconditionally.**
§4.1 makes them the fallback for a blocked Actions run. They are delivered
either way: the Actions result cannot be known until after the push, the
runbook is the C1 artefact the register asks for regardless, and the
fallback is what keeps the *control* alive if the *hosting* goes away. If the
Actions run is green they are a convenience; if it is not, they are the
sanctioned exit. Actions outcome: PLACEHOLDER_ACTIONS

**D4 — `--test-tags` and `--without-demo=all` added to the CI command.**
§4.1's command has neither. Without `--test-tags` the run executes the test
suites of every installed dependency (account, sale, crm, mail…), which is
neither this gate's business nor green; `--without-demo=all` matches
production. The gate's own §5.83 floor is what keeps the tag filter honest.

**D5 — the C5 green-path test does not use `assertLogs`.** Measured on
vietuat: `assertLogs(<cron logger>, level='INFO')` reported "no logs of level
INFO or higher triggered" around a `run_weekly_check()` that demonstrably
ran, returned `[]`, and whose `FHIR-CONFORMANCE-OK` line appears in the log
file as soon as the same call is made with an ordinary handler attached. I
could not establish the cause and am not going to claim one. The test now
attaches its own handler, which works — and is better anyway: `assertLogs`
raises *on the missing log line*, which masks the failure list, the one thing
worth reading when a conformance check goes red.

**D6 — the R1 survival test uses deny rows only.** The handover's fixture is
"probe patient + consent check row". A patient with a *granted* consent
cannot be hard-deleted at all: `health.consent.client_id` is
`ondelete='restrict'` and granted consents are un-unlinkable. The rows
actually at risk are therefore the deny rows of a patient nobody consented —
which is exactly what GC-2 lost (rows 5203/5204). `test_13c` covers the label
branches separately.

**D7 — `client_id` lost `required=True`.** Unavoidable: a NOT NULL column
cannot receive the SET NULL. Every writer passes `client_id`; nothing creates
rows without one.

**D8 — `docs/conformance/clinical-status-mappings.md` was NOT extended with
the two R2 tables.** That document is a signable instrument awaiting the
clinical lead (§10.11, G17) and these two statuses need no clinical judgment:
`DocumentReference.status` is a constant and `Location.status` is derived
from the archive flag. Adding rows would have re-opened a document that is
waiting for a signature, to say nothing a clinician decides.

**D9 — `prefetch_fields` declared on the Practitioner serializer.** Not in
the handover; it is G14's remedy applied to the second model that needed it
(§1.3), found by this phase's own smoke, using a mechanism GC-1 already
built and a precedent GC-1 already set on Patient. Contained to one
serializer, strictly narrowing what is read. The residual
`healthcare_skill_ids` problem is reported (F2), not worked around.

No other deviations. In particular: the facade is still **read-only** (no
create/update/delete/vread/history/transaction route), no new resource
serializer, `health_fhir_adapter_vn`/`_base` untouched, no `meta.profile`,
nothing pip-installed on the server, no test relaxed to pass, the sampling
parameters left unset, and the only HTML edits are the two §10.5 status cells
plus one appended §10.10 row.

---

## 6. Findings for the reviewer (not fixed — out of GC-3 scope)

**F1 — `health.clinical.note` has no ACL row for `group_healthcare_manager`
or `group_healthcare_doctor`.** Read is granted to nurse,
operations_manager, `base.group_public` and owner only
(`health_fieldservice/security/ir.model.access.csv:73-76`). That a *doctor*
cannot read a clinical note through the ORM looks wrong, and
`base.group_public` having read on a PHI-bearing model looks worse — a public
row is the widest grant in the system. Neither is a GC-3 change; both deserve
a decision. The facade now fails safely (403 `OperationOutcome`) either way.

**F2 — `Practitioner.qualification` needs an HR-privileged service user.**
`hr.employee` treats every field outside its public-profile whitelist as
private, and `healthcare_skill_ids` — a health_base addition — is not on it.
The GC-3 prefetch fix removed ~30 other private fields from the read, but
this one is read by `to_fhir` itself. The remedy is one entry in health_base's
public-employee whitelist; `health_base` is not sanctioned by GC-3, and the
decision is "should a read-all FHIR token see staff skills" rather than a
mechanical fix. Until then, `/fhir/r4/Practitioner` answers 403 (a proper
`OperationOutcome`, since §1.2) for a token whose user has no HR group.

**F3 — record-rule scoping is inconsistent between a resource and the records
it dereferences.** `/fhir/r4/DocumentReference` 403s for a catchment-scoped
user because the note passes its own record rules while the
`health.fieldservice.order` it points at does not
(`ir.rule: Access Denied … model: health.fieldservice.order`). A legitimately
scoped integration therefore loses an entire search rather than receiving a
filtered Bundle. Two possible answers — narrow the serializer's `base_domain`
to notes whose order is readable, or apply §5.47's omit-and-declare per
record — and both change what the facade returns, which makes it a design
decision rather than a GC-3 fix.

**F4 — the C5 cron's resource sample is `search(limit=1)`, i.e. the
lowest-id record of each type.** Stable and cheap, but it means drift that
only affects newer records is invisible until the oldest record happens to
change. A random or newest-first sample would trade determinism for coverage.
Deliberate for now, worth a decision if the weekly log ever reads as
uninformative.

**F5 — `smoke_test_client` (gateway.oauth.client id 10) exists and is
inactive.** Activating it is the OPS half of C3, exactly as §4.2 says; this
phase did not touch it. The token half of the smoke was proven with a
throwaway probe client that was destroyed afterwards (§4 above).

---

## 7. Deferred / not in this phase

- **G4's residual half:** naming the Interoperability Owner and recording it
  in the facility's IT-application file. All five automated controls now run;
  the person does not exist yet. §10.11, owner = client leadership. The
  `health_fhir_core.conformance_owner_login` parameter is the seam that turns
  the name into an assignee the moment it is given.
- **Sampling rate and canary client:** both parameters ship unset. Turning
  them on is a deployment decision with a latency budget attached; C4's
  register acceptance also asks for a p95 latency measurement, which needs
  production traffic this deployment does not yet have.
- Everything in GC-4.

---

## 8. New gotchas (candidates for conventions §5)

**§5.100 — an Odoo 19 route with `auth='none'` defaults to `readonly=True`,
and a broad `except` around a write inside it converts the framework's
retry into a 500.** `http.py:924`: `default_mode = routing.get('readonly',
default_auth == 'none')`. The recovery path (`http.py:2246-2255`) depends on
the `ReadOnlySqlTransaction` *escaping* the endpoint — so any `try/except
Exception` around the write (an audit row, a counter, a log) eats the signal,
leaves the transaction poisoned, and the next query dies with "current
transaction is aborted". All three FHIR data routes had this. **It is
invisible on a deployment with no read replica**, because
`registry.cursor(readonly=True)` then returns an ordinary read/write cursor —
so the bug ships, passes every `TransactionCase`, works in production, and
detonates the day someone puts a replica in front of it. An `HttpCase` is
what exposes it, because the test framework hands out a genuinely read-only
cursor. Rule: any route that writes declares `readonly=False`, and "it is a
GET" is not evidence that it doesn't write — auditing is a write. (Precedent
already in the repo: `health_telemonitoring/controllers/ingest.py`,
`health_web_leads/controllers/web_leads.py`.)

**§5.101 — an `AccessError` from the ORM inside an API controller becomes the
framework's HTML error page, and API clients cannot parse HTML.** The FHIR
facade translated the *authentication* AccessError but not the one raised by
the query, so a token whose service user lacked one `ir.model.access` row got
`<!doctype html><title>403 Forbidden</title>` — with the Odoo user's name and
id in the body — from a `application/fhir+json` endpoint. Rule for any
machine-facing controller: catch `AccessError` at the route boundary
alongside your own error type, and answer in the protocol's error shape with
a diagnostic in the protocol's vocabulary (the FHIR resource type), never the
ORM's (the model name, the rule name, the user). Corollary: this is only
findable with a *minimally-scoped* token — an admin-grouped service user
never hits it, which is the same blind spot G14 came from.

**§5.102 — G14 is a PATTERN, not an incident: any Odoo model with a
group-gated read surface breaks a minimally-scoped serializer, and
`hr.employee` is the second one.** `res.partner` gates accounting fields
behind the accounting group; `hr.employee` goes further and treats **every**
field outside its public-profile whitelist as private
(`hr/models/hr_employee.py::_check_private_fields`), raising on `fetch()`
rather than on access. A blanket "read every stored field" prefetch therefore
403s the whole resource for exactly the users an API token maps onto. Rule:
a serializer over ANY model that another module extends with private or
group-gated fields declares `prefetch_fields`, and the check is
`fetch(<declared>)` **as a minimally-grouped user**, never as admin — an
admin-grouped fixture cannot see this bug at all. Corollary for
`hr.employee` specifically: a custom field added to it is private by default,
so adding a field to a serializer's output can 403 the resource without any
change to the serializer's own module.

**§5.103 — `fhir.resources` does not validate required-binding membership.**
Measured on vietuat 8.3.0: `Location(status='not-a-status')` validates clean;
`meta.lastUpdated='not-a-date'` does not. `validate_resource` checks types
and cardinality, not ValueSet membership, so runtime validation (C4) and the
weekly cron (C5) **cannot** catch a wrong status code. The
`test_fhir_bindings.py` tier is the only thing that does, and any new
status-bearing resource needs a table there — including emit-only statuses,
which the `test_66` search-param guard does not see (that is what GC-3 R2
fixed for DocumentReference and Location).

---

## 9. Files

**New — `health_fhir_core`:** `models/__init__.py` ·
`models/fhir_conformance.py` · `data/fhir_conformance_cron.xml` ·
`tests/test_fhir_gc3.py`

**Changed — `health_fhir_core`:** `__init__.py` (+`models`) ·
`__manifest__.py` (version 19.0.1.5.0, +cron data entry) ·
`serializers/base.py` (`validation_sample_pct`, `validation_sample_hit`,
param constants) · `controllers/fhir.py` (`_should_validate`,
`FHIR-CONFORMANCE-DRIFT` logging, `readonly=False` ×3,
`_access_denied_response`) · `conformance/capability_baseline.json`
(regenerated for the version bump) · `tests/__init__.py` ·
`tests/test_fhir_bindings.py` (+test_67, +test_68)

**Changed — `health_consent`:** `models/health_consent_check_log.py`
(`ondelete='set null'`, `client_ref`, `create` override, `_client_label`) ·
`views/health_consent_views.xml` (+`client_ref` column) · `i18n/vi.po`
(+label, +help) · `__manifest__.py` (version 19.0.1.1.0) ·
`tests/test_health_consent.py` (+test_13, +test_13b, +test_13c)

**New — repo:** `.github/workflows/fhir-conformance.yml` ·
`tools/fhir_deploy_smoke.sh` · `tools/ci_fhir_local.sh` ·
`docs/conformance/deploy-smoke.md` · `docs/conformance/ci-runbook.md` ·
`docs/strategy/reports/gc-3-report.md`

**Changed — docs:** `docs/strategy/hl7-fhir-compliance-response.html`
(§10.5 G4 + G10 status cells, one appended §10.10 row)
