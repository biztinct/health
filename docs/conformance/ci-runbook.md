# FHIR conformance CI gate (control C1)

Gap register item **G4** — *"No CI; conformance tests run only when someone
remembers"* — was described in the compliance response as the single biggest
process gap, and the one the client asked about directly. This document
describes the gate that closes the engineering half of it.

Two implementations of the same gate ship, deliberately:

| | Where | When it runs |
|---|---|---|
| **Primary** | `.github/workflows/fhir-conformance.yml` | GitHub Actions, on every push/PR touching the FHIR modules |
| **Fallback** | `tools/ci_fhir_local.sh` | on a developer machine or a self-hosted runner, on demand |

They install the same modules, run the same test tags, and apply the same
three gates. The fallback exists because the hosted runner is the one part of
this control that engineering does not own: if Actions is disabled for the
repository, if the organisation's runner minutes are exhausted, or if the
`odoo:19` image drifts from the deployment, the *control* must survive the
*hosting*.

---

## The three gates

Both implementations fail the change unless **all three** hold. The third one
is the interesting one.

1. **The run exited zero.** An Odoo test run that exits non-zero is a
   failure even if it reports `FAIL: 0` — conventions §5.75: when every
   `HttpCase` dies in `setUpClass`, the runner counts errors, exits 1, and the
   failure count stays at zero.
2. **There is an `odoo.tests.result` line, and it says `0 failed, 0 error(s)`.**
   Absence of the line is a failure, not a pass: no line means no suite ran.
3. **At least 50 test methods actually executed** (`Starting Test….test_`).
   Conventions §5.83: *"0 failed" over a suite that never executed is
   indistinguishable from "0 failed" over a suite that passed.* Phase GB found
   28 `HttpCase` classes across 15 modules that had never once run, precisely
   because nobody compared the count to an expectation. A CI gate that can go
   green while running nothing is not a gate.

The threshold is a floor, not a pin — it fails on collapse (a module that
silently failed to install, a `--test-tags` typo), not on ordinary growth.
Raise it if the suite ever shrinks past it for a legitimate reason, and say so
in the commit.

---

## Primary: GitHub Actions

```
.github/workflows/fhir-conformance.yml
```

- **Triggers:** push and PR on `addons/health_fhir_*`,
  `addons/health_condition`, `addons/health_base`, or the workflow file
  itself; plus `workflow_dispatch` for a manual run.
- **Environment:** `container: odoo:19` with a `postgres:15` service
  (`odoo`/`odoo`). The image tag is pinned to the deployment's major version
  on purpose — floating it to `latest` would mean testing something the
  server does not run.
- **Dependency:** `pip install fhir.resources==8.3.0`, the version the
  R4/R4B equivalence argument is scoped to (`r4-r4b-equivalence.md`, item
  G11). `--break-system-packages` is needed because the image is Debian and
  PEP 668 applies.
- **Command:** installs `health_fhir_core,health_fhir_terminology,
  health_condition` — the dependency chain pulls the ~50-module spine in
  automatically — with `--test-tags` limited to those three, `--workers=0`,
  `--without-demo=all`, and a `--logfile` that is uploaded as an artifact on
  every run, pass or fail.

### addons-path order is load-bearing

```yaml
CI_ADDONS_PATH: addons,/usr/lib/python3/dist-packages/odoo/addons
```

The repo's `addons/` is **not** only our modules: it also tracks the
deployment's copies of several core Odoo modules (`account`, `crm`, `mail`,
`sale`, `hr`, `web`, `product`, `calendar`, …), because on the server
`/odoo/odoo-server/addons` is one directory holding both. Odoo resolves a
module name against the first path that contains it, so listing the image's
packaged addons first would silently test *different code from the one that is
deployed*. Repo first, image second.

### Reading a red run

Download the `odoo-conformance-log` artifact. Then, in order:

- `grep -a 'odoo.tests.result' odoo.log | tail -1` — the headline.
- If the exit was non-zero but failures are 0, read the `ERROR` lines
  (§5.75). It is usually an install-time problem, not a test.
- `grep -ao 'Starting Test[A-Za-z0-9]*\.test_[a-z0-9_]*' odoo.log | sort` —
  what actually ran (§5.90). Compare against what you expected to run; a
  missing class is a finding in itself.

---

## Fallback: `tools/ci_fhir_local.sh`

```bash
ODOO_BIN=~/odoo/odoo-bin \
ODOO_ADDONS=~/odoo/addons \
  tools/ci_fhir_local.sh
```

Requires a local Odoo 19 checkout, a PostgreSQL reachable as `odoo`/`odoo`,
and `fhir.resources` 8.x importable. It **drops and recreates** its database
(default `fhir_ci_local`) and refuses outright to run against `vietuat` or any
name containing `prod`.

Everything is overridable: `CI_DB_HOST`, `CI_DB_USER`, `CI_DB_PASSWORD`,
`CI_MODULES`, `CI_TEST_TAGS`, `CI_MIN_EXECUTED`, `CI_LOG`.

Same three gates, same messages, same log format — a red locally and a red in
Actions read identically.

---

## What this gate does **not** cover

Stating the boundary is part of the control:

- It runs the **repo's** tests against a **fresh** database. It says nothing
  about the deployed release or about production data — that is control C3
  (`deploy-smoke.md`) and control C5 (the weekly cron).
- It does not validate against an external conformance service. Touchstone
  is item **G1**, an operational action prepared in GC-4.
- It does not assert the capability against an implementation guide. VN Core
  conformance is item **G9**.
- Naming the human who owns a red build is item **G4**'s residual half, and
  it is an OPS action (§10.11 of the compliance response): the machinery runs
  either way, but a gate whose failures nobody is accountable for is only
  half a control.

---

## Related controls

| Control | Artefact | Question |
|---|---|---|
| **C1** | this document | does the repo still conform? |
| C2 | `health_fhir_core/conformance/capability_baseline.json` | did anyone change the capability without regenerating the baseline? |
| C3 | `tools/fhir_deploy_smoke.sh`, `deploy-smoke.md` | did this release come up conformant? |
| C4 | `health_fhir_core.validate_sample_pct` / `…canary_client` | is what we actually serve valid? |
| C5 | `fhir.conformance.run_weekly_check()` | has anything drifted between releases? |
