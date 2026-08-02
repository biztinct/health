# Post-deploy FHIR conformance smoke (control C3)

`tools/fhir_deploy_smoke.sh` — the check that runs **on the server, after the
restart**, in the deploy procedure of `docs/strategy/HANDOVER-CONVENTIONS.md`
§2. It exists because a green test run and a healthy `/web/login` together
still cannot answer the question that matters after a release:

> Is the process now serving traffic the build we just deployed, and does it
> still declare what we say it declares?

Registered against the gap register as control **C3** (item **G4**).

---

## When to run it

Immediately after step 2 of the deploy workflow — after
`sudo service odoo-server start`, in the same shell, before you call the
deploy done. It is read-only and takes under a second in metadata mode.

```bash
# from the repo root, once per deploy
scp tools/fhir_deploy_smoke.sh VietUcUAT:/tmp/
ssh VietUcUAT 'chmod +x /tmp/fhir_deploy_smoke.sh && \
  /tmp/fhir_deploy_smoke.sh 19.0.1.5.0'   # <- health_fhir_core's version
```

The argument is **the version you believe you just deployed**, read from
`addons/health_fhir_core/__manifest__.py`. The script compares it to
`software.version` in the live CapabilityStatement (which Odoo derives from
`ir.module.module.latest_version`, i.e. what the database actually upgraded
to). A mismatch is the single most common silent deploy failure — the files
were copied but the upgrade did not run, or ran against the wrong database —
and it is a hard FAIL here, not a warning.

---

## What it checks

| # | Check | Fails when |
|---|---|---|
| 1 | `GET /fhir/r4/metadata` returns 200 | the facade is down or the route regressed |
| 2 | `fhirVersion == 4.0.1` | the declared version drifted |
| 3 | `software` element present, `software.version == $1` | the deployed build is not the one you think (G3) |
| 4 | capability declares ≥ 22 resources (`FHIR_MIN_RESOURCES`) | a serializer or a whole downstream module failed to load |
| 5 | *(token mode)* every interaction-bearing type answers `?_count=1` with a 200 searchset `Bundle` | auth, scope, ACL or serialization broke for that type |
| 6 | *(token mode)* the newest `api.audit.log` row for `/fhir/r4/` has a non-empty `key_or_client` **and** `auth_kind` | reads are not attributable to the calling integration |

Check 6 is deliberate scar tissue. Until the GC-2 review, the controller read
a request attribute that was never assigned, so **every** FHIR audit row had
empty attribution: each read was traceable to a service *user* but not to the
partner *integration* that made it — which is exactly the attribution a breach
investigation needs. The fix is one line, and one line is exactly what a
future refactor deletes without noticing. This check is how it stays fixed.

The type list in check 5 is read out of the capability response itself, so it
follows the registry automatically — a new resource type is probed the first
release it exists, with no edit here.

---

## Token mode — and why this script never creates the token

Without `FHIR_SMOKE_TOKEN` the script runs the public half and says so
explicitly:

```
FHIR-SMOKE note: FHIR_SMOKE_TOKEN is unset — metadata-only run. The
authenticated half (search + audit attribution) was NOT executed.
```

That line is the point: a metadata-only pass must never read as a full pass.

The token is an ordinary gateway bearer token (`hg_…`) belonging to a
smoke-test OAuth client with `system/*.read`. **This client is created and
activated by OPS, never by an engineering phase and never by this script.** A
deploy script that can mint itself a credential with read access to every
resource type is a standing privilege-escalation path, and one that would
exist on the server rather than in anyone's threat model. The engineering
position is: the check is written and ready; whether a long-lived read-all
token exists on this deployment is an operational decision with an owner.

When OPS has provisioned one:

```bash
ssh VietUcUAT 'FHIR_SMOKE_TOKEN=hg_… /tmp/fhir_deploy_smoke.sh 19.0.1.5.0'
```

### What the smoke token's service user actually needs

Learned the hard way on this control's first authenticated run, and worth
stating before someone provisions the client and finds out one deploy at a
time: **the smoke reads one record of every interaction-bearing type, so its
service user needs read access to every model behind the facade — through
both `ir.model.access` AND the record rules.**

A user holding nurse + operations-manager groups still failed on
`DocumentReference`, because the note it found dereferences a
`health.fieldservice.order` in another catchment and the *record rule* denied
it (see the phase report's findings). Catchment-scoped groups are the wrong
shape for this user: a smoke token that can only see one province cannot
answer "did every type come up serializable".

Provision it with a group whose record rules are unscoped
(`health_base.group_healthcare_owner` is `[(1,'=',1)]` on the field-service
models) or with a purpose-built group, and give it `system/*.read`. Treat the
credential accordingly: it reads PHI across the whole database, so it belongs
in the same custody as any other read-all credential — which is the reason
this is an OPS decision and not something a deploy script mints for itself.

A per-type failure does **not** stop the run: every type is probed, the audit
check still executes, and the final `FAIL` line names all the failing types
at once. Stopping at the first one would report a single problem and hide the
rest, and "which types are broken" is the diagnostic value of this step.

Reads made in token mode **are audited** — that is the audit trail working,
and check 6 depends on it. They are also subject to the consent gate, which
has been enforced since GC-2: on a database with no `data_sharing` consents
recorded, PHI-bearing types correctly return an empty Bundle. An empty
`entry` is a pass here; the check is on the Bundle, not on its contents.

### Environment

| Variable | Default | Purpose |
|---|---|---|
| `FHIR_SMOKE_TOKEN` | *(unset)* | enables the authenticated half |
| `FHIR_SMOKE_BASE` | `http://localhost:8069` | base URL |
| `FHIR_SMOKE_DB` | `vietuat` | database for the audit query |
| `FHIR_MIN_RESOURCES` | `22` | minimum declared resource count |

The audit query runs through `sudo su - postgres -c psql`, so the operator
needs the same sudo rights the deploy procedure already assumes.

---

## Reading a failure

Every failure is one line on stderr beginning `FHIR-SMOKE FAIL:` and a
non-zero exit — the script is meant to be chained onto the deploy command
with `&&`. The three you will actually meet:

- **`software.version is 'X' but this deploy was 'Y'`** — the upgrade did not
  take. Re-run the `-u health_fhir_core` step and read the log; do not
  re-run the smoke until it does.
- **`capability declares N resources, expected at least 22`** — a module
  failed to load, so its serializers never registered. The count is a proxy
  for "everything that should be here is here"; the server log names the
  module that raised.
- **`newest /fhir/r4 audit row has an empty key_or_client`** — attribution
  regressed. Treat as a release blocker: reads are being served that cannot
  be attributed to a client.

---

## Relationship to the other conformance controls

| Control | Runs | Asks |
|---|---|---|
| C1 — `.github/workflows/fhir-conformance.yml` | on every push/PR touching the FHIR modules | does the **repo** still conform? |
| C2 — `capability_baseline.json` + route diff | inside the test suite | did anyone change the capability without regenerating the baseline? |
| **C3 — this script** | after every deploy | did **this release** come up conformant, and is it the right one? |
| C4 — sampled runtime validation | continuously, on live traffic | is what we actually serve valid? (`FHIR-CONFORMANCE-DRIFT` in the log) |
| C5 — weekly cron (`fhir.conformance`) | weekly | has anything drifted **between** releases? |

C3 is the only one that can catch "deployed the files, forgot the upgrade",
and C5 is the only one that catches drift with no release to blame.
