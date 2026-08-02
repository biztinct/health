# Phase GC-1 — capability truth + integration-breaking defects — implementation report

**Handover:** `docs/strategy/handovers/hl7-gap-closure.md` §2 (ONLY §2).
**Branch:** `19.0`. **Database:** `vietuat`. **Date:** 2026-08-02.
**Register items closed:** G14, G15, G2, G12, G3, G11 (+ the C2 baseline).

---

## 1. What was built

### 1.1 D1 — Patient prefetch fix (G14)

| File | Change |
|---|---|
| `addons/health_fhir_core/serializers/base.py` | `FHIRSerializer.prefetch_fields = None` declaration + the `serialize_batch` kernel from handover §2.1, verbatim. `None` keeps the legacy "every stored non-binary field" behaviour, so no other serializer changes. |
| `addons/health_fhir_core/serializers/patient.py` | `prefetch_fields = [...]` — the 21-field list from handover §2.1, verbatim. |

The defect and the fix were both verified **on the live server**, against the
pre-D1 code, before anything was deployed (transcript in §4.1): a user holding
only `health_base.group_healthcare_receptionist` could not serialize a Patient
at all.

One mechanism worth recording (it is the reason this defect existed and the
reason the fix is safe) — see the new-gotcha candidate in §7:

- Odoo's **implicit** prefetch (`_fetch_field`, `odoo/orm/models.py:3751-3769`)
  builds its field list with `if self._has_field_access(f, 'read')`, i.e. it
  silently drops fields the caller's groups exclude.
- An **explicit** `records.fetch([...])` does not filter: it checks access on
  the whole list you passed and raises.

So the old "warm the cache with one explicit fetch of every stored field" line
converted a benign, self-filtering prefetch into a hard `AccessError` for any
user missing any group-gated field on the model.

### 1.2 D2 — Flag ACL (G15)

`addons/health_base/security/ir.model.access.csv` — six rows appended for
`model_health_fall_risk`, mirroring the `health.observation` matrix (handover
F10) exactly:

| xmlid | group | R/W/C/U |
|---|---|---|
| `access_health_fall_risk_receptionist` | receptionist | 1,0,0,0 |
| `access_health_fall_risk_nurse` | nurse | 1,1,1,0 |
| `access_health_fall_risk_head_nurse` | head_nurse | 1,1,1,0 |
| `access_health_fall_risk_doctor` | doctor | 1,1,1,0 |
| `access_health_fall_risk_operations_manager` | operations_manager | 1,0,0,0 |
| `access_health_fall_risk_manager` | manager | 1,1,1,0 |

`everything.py` was **not** touched — the §5.47 suppress-and-declare net stays,
and its test (which mocks the `AccessError` rather than depending on the missing
ACL — handover F7) is still green.

### 1.3 A1 — operations registry + ValueSet + nits (G2, G12)

| File | Change |
|---|---|
| `addons/health_fhir_core/serializers/__init__.py` | New module-level `OPERATIONS` (`{'Patient': [everything]}`) and `OPERATION_ONLY_RESOURCES` (`{}`). |
| `addons/health_fhir_core/capability.py` | Hard-coded Patient block **deleted**; operations now attach from `OPERATIONS.get(rtype)`; one entry per `OPERATION_ONLY_RESOURCES` item emitted after the registry loop with `type` + `operation` and **no** `interaction` / `searchParam`; `_count` append removed (`_lastUpdated` kept); new `SEARCH_PARAM_DEFINITIONS` table attaches canonical `definition` URLs. |
| `addons/health_fhir_terminology/serializers/__init__.py` | Alongside the CodeSystem registration: `OPERATIONS['CodeSystem'] = [lookup]`, `OPERATION_ONLY_RESOURCES['ValueSet'] = [expand]`, then `clear_capability_cache()` (same pattern the module already used). |

The `definition` canonicals follow handover §2.3 step 4 **exactly**. Params not
in that rule set carry no `definition` key (legal; never guessed):
`AdverseEvent.severity`, `MedicationAdministration.date` and `_lastUpdated`.

The capability's `documentation` line about string modifiers was **not** added —
that is GC-2's, and pre-declaring GC-2 behaviour is exactly what the handover
forbids.

### 1.4 A2 — software element (G3)

`build_capability` now emits
`'software': {'name': 'health19 / CarejioX', 'version': module_version}`, with
`module_version` read once from `ir.module.module.latest_version` for
`health_fhir_core` before the cache store.

### 1.5 A3 — version pinning + equivalence (G11)

| File | Content |
|---|---|
| `requirements-fhir.txt` (repo root) | `fhir.resources==8.3.0` + the conventions §1 pip-chain warning (cryptography / pyOpenSSL — do not "check" this by running pip on the server). |
| `docs/conformance/r4-r4b-equivalence.md` | The committed claim: R4B's substantive changes are confined to the Subscription, Evidence-Based-Medicine and medication-definition families; none of the 21 served types (all listed) is in any of them, so validating with R4B classes while declaring `fhirVersion 4.0.1` is sound. Includes the two scoping consequences (adding a resource from those families, or changing the pin, invalidates the claim). |
| `tests/test_fhir_conformance.py::test_24` | Asserts `fhir.resources.R4B.patient` imports **and** `importlib.metadata.version('fhir.resources')` starts with `8.`. |

### 1.6 C2 seed — capability baseline + route diff

| File | Content |
|---|---|
| `addons/health_fhir_core/conformance/capability_baseline.json` | The full statement, `date` removed, generated on `vietuat` from the deployed code (22 resource entries, 19 075 bytes). Read via `odoo.tools.misc.file_open`; **not** a manifest `data` entry. |
| `addons/health_fhir_core/conformance/README.md` | The regeneration procedure — i.e. the operating instruction for control C2, including the note that a manifest version bump is itself a capability change. |
| `tests/test_fhir_conformance.py::test_22` | `build_capability(env)` minus `date`, `json.dumps(sort_keys=True)` on both sides, byte-exact. |
| `tests/test_fhir_conformance.py::test_23` | The route-vs-capability diff, both directions (see §3). |

### 1.7 Tests

New file `addons/health_fhir_core/tests/test_fhir_conformance.py` (registered in
`tests/__init__.py`), 14 methods, `@tagged('post_install', '-at_install')`:

| Test | Handover ref | What it proves |
|---|---|---|
| `test_11_minimal_privilege_patient_serializes` | T1.1 | receptionist-only user serializes a Patient and it validates |
| `test_12_minimal_privilege_patient_search_bundle` | T1.2 | same user, `name` search → searchset Bundle, no AccessError |
| `test_13_prefetch_declaration_covers_every_mapped_field` | (added) | the declared list covers every mapped field and re-admits neither `credit_limit` nor `signup_type` |
| `test_14_nurse_can_read_fall_risk` | T1.3a | `health.fall.risk.search_count([])` as a nurse does not raise |
| `test_15_everything_contains_flag_and_declares_nothing_suppressed` | T1.3b | `$everything` carries the `Flag` entry and no `suppressed` OperationOutcome naming Flag |
| `test_16_capability_declares_every_operation` | T1.5a | Patient.everything, CodeSystem.lookup, ValueSet.expand all declared with canonical `OperationDefinition` URLs |
| `test_17_valueset_is_operation_only` | T1.5b | the ValueSet entry has no `interaction` and no `searchParam` |
| `test_18_count_is_not_a_search_param` | T1.5c | no resource lists `_count`; every REGISTRY type still lists `_lastUpdated` |
| `test_19_search_param_definitions_are_canonical` | T1.5d | every `definition` starts with `http://hl7.org/fhir/SearchParameter/`, plus spot-checks |
| `test_20_statement_validates` | T1.9 | the whole statement validates as an R4B `CapabilityStatement` |
| `test_21_software_element_carries_the_deployed_version` | T1.6 | `software.version == ir.module.module.latest_version` |
| `test_22_capability_matches_the_committed_baseline` | T1.7 | byte-equality against the committed baseline |
| `test_23_routes_and_capability_agree` | T1.8 | the route/capability diff, both directions |
| `test_24_fhir_resources_pin_resolves` | A3 | the pinned library resolves as documented |

T1.4 (the existing §5.47 suppression test) was **run, not skipped** — see §4.2.

---

## 2. §5.49 sweep (T1.10)

```
$ grep -rn "len(listed)" addons/*/tests/
addons/health_fhir_core/tests/test_fhir_phase2.py:77:        self.assertGreaterEqual(len(listed), 19)
addons/health_fhir_terminology/tests/test_terminology.py:174:        self.assertGreaterEqual(len(listed), 20)
```

Both are already `>=` (relaxed in the condition-spine phase). The count moved
**21 → 22** with the ValueSet entry, which satisfies both. **No relaxation was
required and none was made.**

One other capability assertion did have to change, and it is a forced deviation
— see D1 in §5.

---

## 3. Route-vs-capability diff (the C2 teeth)

`test_23` reads `self.env['ir.http'].routing_map()`, keeps the rules whose path
starts `/fhir/r4`, and extracts every literal `$op` segment:

| Route | Extracted |
|---|---|
| `/fhir/r4/Patient/<int:rid>/$everything` | `(Patient, everything)` |
| `/fhir/r4/CodeSystem/$lookup` | `(CodeSystem, lookup)` |
| `/fhir/r4/ValueSet/$expand` | `(ValueSet, expand)` |

Assertions, all of which must hold in **both** directions:

1. routed operations `==` declared operations (the diff is empty either way);
2. `{types with an interaction}` `==` `set(REGISTRY)` — no phantom resource, no
   registry type missing from the statement;
3. every entry without `interaction` is absent from `REGISTRY` and carries at
   least one `operation` (i.e. ValueSet is operation-only, and nothing else can
   quietly become a contentless entry);
4. an operation route that does not name its resource type literally fails the
   test rather than being skipped.

---

## 4. Verification

### 4.1 T1.1 failed BEFORE D1 (verified live, pre-deploy)

Run in `odoo-bin shell` against `vietuat` with the **then-deployed** code, in a
transaction that was rolled back:

```
BEFORE-D1 record found: True
BEFORE-D1 RESULT: AccessError as expected -> You do not have enough rights to
access the field "signup_type" on Contact (res.partner). Please contact your
system administrator. |  | Operation: read | User: 6376 |
Groups: allowed for groups 'Access Rights'
BEFORE-D1 rolled back
```

That is G14 reproduced exactly as the register describes it: the record was
found (record rules were fine), and serialization died on a group-gated field
the serializer never reads. After D1 the same call is `test_11`, green.

### 4.2 Test run (verbatim)

Deploy per conventions §2 — `--workers=0`, no `--no-http`, own logfile and
spare HTTP port:

```
$ ssh VietUcUAT 'sudo service odoo-server stop && sleep 6 && \
  sudo su - odoo -s /bin/bash -c "/odoo/odoo-server/odoo-bin \
    -c /etc/odoo-server.conf -d vietuat \
    -u health_base,health_fhir_core,health_fhir_terminology,health_condition \
    --test-enable --test-tags /health_fhir_core,/health_fhir_terminology,/health_condition \
    --stop-after-init --workers=0 --http-port=8169 \
    --logfile=/tmp/gb/gc1_b.log"; echo EXIT:$?; \
  sudo service odoo-server start; sleep 12; \
  curl -s -o /dev/null -w "HTTP:%{http_code}\n" localhost:8069/web/login'
EXIT:0
HTTP:200

$ ssh VietUcUAT 'sudo grep -a "odoo.tests.result" /tmp/gb/gc1_b.log | tail -3'
2026-08-02 09:47:07,115 2224543 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 83 tests when loading database 'vietuat'
```

Executed-method count (§5.83 / §5.90 — a failure count is not evidence that
anything ran; 83 methods executed, 83 counted in the result line):

```
$ ssh VietUcUAT 'sudo grep -ac "Starting Test.*\.test_" /tmp/gb/gc1_b.log'
83
$ ssh VietUcUAT 'sudo grep -ac "FAIL:\|ERROR:" /tmp/gb/gc1_b.log'
0
```

All 14 GC-1 methods are in that list by name:

```
$ ssh VietUcUAT 'sudo grep -ao "Starting Test[A-Za-z0-9]*\.test_[a-z0-9_]*" \
    /tmp/gb/gc1_b.log | sed "s/Starting //" | grep ConformanceGC1 | sort'
TestFHIRConformanceGC1.test_11_minimal_privilege_patient_serializes
TestFHIRConformanceGC1.test_12_minimal_privilege_patient_search_bundle
TestFHIRConformanceGC1.test_13_prefetch_declaration_covers_every_mapped_field
TestFHIRConformanceGC1.test_14_nurse_can_read_fall_risk
TestFHIRConformanceGC1.test_15_everything_contains_flag_and_declares_nothing_suppressed
TestFHIRConformanceGC1.test_16_capability_declares_every_operation
TestFHIRConformanceGC1.test_17_valueset_is_operation_only
TestFHIRConformanceGC1.test_18_count_is_not_a_search_param
TestFHIRConformanceGC1.test_19_search_param_definitions_are_canonical
TestFHIRConformanceGC1.test_20_statement_validates
TestFHIRConformanceGC1.test_21_software_element_carries_the_deployed_version
TestFHIRConformanceGC1.test_22_capability_matches_the_committed_baseline
TestFHIRConformanceGC1.test_23_routes_and_capability_agree
TestFHIRConformanceGC1.test_24_fhir_resources_pin_resolves
```

The pre-baseline run (`/tmp/gb/gc1_b.log`'s predecessor `gc1_a.log`) is worth
one line for the reviewer: it was the same 83 tests with `1 failed` — only
`test_22`, against the placeholder baseline, exactly as the two-run bootstrap in
§7 predicts. No other test was ever red in this phase.

### 4.3 Live capability after deploy

Server-local (`auth='public'`, so no token needed):

```
$ ssh VietUcUAT 'curl -s http://localhost:8069/fhir/r4/metadata'   # summarised
fhirVersion       : 4.0.1
software          : {"name": "health19 / CarejioX", "version": "19.0.1.4.0"}
implementation.url: http://localhost:8069/fhir/r4
resource entries  : 22
operations        : [('CodeSystem', ['lookup']), ('Patient', ['everything']),
                     ('ValueSet', ['expand'])]
ValueSet entry    : {"type": "ValueSet", "operation": [{"name": "expand",
                     "definition": "http://hl7.org/fhir/OperationDefinition/ValueSet-expand"}]}
_count anywhere   : False
definitions       : 55 of 78 params carry a canonical
non-hl7 definition: []
```

Public host, same statement:

```
$ curl -s https://care.biztinct.com/fhir/r4/metadata
PUBLIC fhirVersion: 4.0.1 | software: {'name': 'health19 / CarejioX',
'version': '19.0.1.4.0'} | entries: 22
```

Note what the ValueSet entry does **not** contain: no `interaction`, no
`searchParam`. The server declares the one thing it serves for that type and
claims nothing else.

### 4.4 Browser evidence pack

None, and none is due. GC-1 changes an ACL csv, a serializer prefetch list, the
generated CapabilityStatement and tests. Nothing user-facing, no PWA asset, no
new user-visible string (ACL names and capability text are machine-facing), so
conventions §3 (PWA bump), §4 (`vi.po`) and DoD item 5 (evidence pack) are all
no-ops for this phase. The equivalent evidence for a machine-facing surface is
the live `/fhir/r4/metadata` transcript above.

---

## 5. Deviations from the handover

**D1 — one more capability assertion had to be relaxed than the handover's
sweep anticipated.** `health_fhir_core/tests/test_fhir_core.py::
test_capability_statement_lists_phase1_resources` asserted
`self.assertIn('_count', names)`. §2.3 step 2 removes the `_count` append, so
that line is unsatisfiable by construction. It is now `assertNotIn`, with a
comment pointing at `test_18`, which asserts the removal across every resource.
The handover's T1.10 sweep pattern (`len(listed)`) does not find it — a
capability nit can be pinned by a test that never counts anything. **This is a
sanctioned-module edit** (health_fhir_core), declared here per the §5.49 rule
that any such change is a forced deviation.

**D2 — `health_fhir_core` manifest version bumped `19.0.1.3.0` →
`19.0.1.4.0`.** Not named in the sanction list. Required in substance: A2 makes
the module's version part of what the server publicly declares, and shipping a
materially changed facade under the version string of the pre-GC-1 build would
make the new `software` element misleading on its first day. Consequence,
documented in `conformance/README.md`: a version bump is now itself a capability
change and requires a baseline regeneration.

**D3 — the tracker HTML is a second commit, not the same commit as the code.**
The handover asks for the §10.5 status cells and the §10.10 row to carry the
code commit's short hash, in that same commit. A commit cannot contain its own
hash. Resolved by committing the code + docs + report first, then committing the
tracker update citing that hash — adjacent commits in one push, so the tracker
never reaches the remote out of step with the code, and the hash it names is a
real one. (Amending instead would have made the cited hash a commit that does
not exist.)

**D4 — added `addons/health_fhir_core/conformance/README.md`.** The handover
specifies the baseline file but not how to regenerate it, and the regeneration
procedure *is* control C2's operating instruction — GC-3's weekly cron reads the
same file and will hand its owner the same question. Documentation only; no code
or capability effect.

**D5 — three tests beyond the numbered list** (`test_13`, `test_14`,
`test_24`'s import half). `test_13` pins the prefetch declaration so a future
edit cannot quietly re-admit a group-gated field; `test_14` isolates the "ACL
exists" half of T1.3 from the "$everything is populated" half, so a failure says
which one broke. Additions, not substitutions — every numbered test is present.

No other deviations. In particular: the facade is still read-only, no new
resource serializer was added, no `sudo` was added to any serializer or to
`everything.py`, `health_fhir_adapter_vn`/`_base` were not touched, no
`meta.profile` is emitted, nothing was pip-installed, and the only HTML edits
are §10.5 status cells and one appended §10.10 row.

---

## 6. Deferred / not in this phase

- The capability `documentation` string about `:exact` / `:contains` — GC-2 §3.2
  adds it (and regenerates the baseline in the same commit).
- Everything else in GC-2/3/4.

---

## 7. New Odoo 19 gotcha (candidate for conventions §5)

**An explicit `records.fetch([...])` enforces field ACLs on the whole list;
Odoo's own implicit prefetch silently drops what the caller may not read. A
"warm the cache in one query" optimisation therefore converts a benign prefetch
into a hard `AccessError`.**

`_fetch_field` (`odoo/orm/models.py:3751-3769`, Odoo 19) builds its prefetch
list with `if self._has_field_access(f, 'read')` — group-gated fields the user
cannot read are simply not requested, so ordinary attribute access on a record
never 403s because of a *neighbouring* field. `fetch(field_names)` has no such
filter: it checks access on exactly what you passed and raises. So the idiom

```python
records.fetch([f for f, fld in records._fields.items() if fld.store and ...])
```

is not "the implicit prefetch, done eagerly" — it is strictly stronger, and on
any model carrying group-gated columns (`res.partner` drags account's
`credit_limit` and base's `signup_type`) it fails for every user outside those
groups. Symptom: a read that works for admin and 403s for a service user, naming
a field the code never touches. Fix pattern: declare the fields the consumer
actually needs (`prefetch_fields`) instead of "all stored", or filter the
explicit list through `_has_field_access` yourself. Corollary for reviewers:
`grep` for `\.fetch(` on any model with gated fields — the blast radius is every
minimally-scoped user, and admin-run tests cannot see it.

Second, smaller note (already written into `conformance/README.md` rather than
proposed for the ledger): a committed golden file whose content includes the
module's **installed** version can only be generated after the upgrade that
installs that version, so the first deploy of such a baseline is inherently two
runs — deploy, dump, commit, redeploy.
