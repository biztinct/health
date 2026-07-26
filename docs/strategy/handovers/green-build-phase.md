# Phase GB — Green Build: make the tests actually run, make Vietnamese actually load

**Handover, 2026-07-26.** Read `HANDOVER-CONVENTIONS.md` §2 (the deploy
procedure this phase CHANGES), §5.32, §5.58, §5.67, §5.72, §5.75 first.

This is not a feature phase. It closes two conditions in which **shipped code
is silently not doing its job**, both found by the Channel Center stream and
both already measured. Neither is speculative: the numbers below came from
grepping the repo and querying vietuat on 2026-07-26.

## 0. Why this, and why now

The channel arc CC-A…CC-F is complete and every remaining step in it is
blocked on a human (a platform app, Google's CASA assessment, VoIP24h's
documentation). Building further channel features would be stacking work on
ground we cannot prove. Meanwhile:

- **28 `HttpCase` classes across 13 of our own modules have never executed.**
  Under §2's documented command (`--no-http`) and under a manual run against
  the deployment conf (`workers = 2`, §5.75) they die identically in
  `setUpClass`. The runner counts them as errors and the process exits 1 with
  a `FAIL:` count of zero — which reads like unrelated breakage, so it has
  been ignored. These are precisely the tests that cover **public HTTP
  endpoints**: portal tokens, family links, self-booking, the PWA API surface,
  the API gateway. This is an unverified security surface, not untidiness.
  CC-D already pulled one months-old real failure out of it by accident
  (health_telehealth pinned `telehealth.css?v=1.9.0` against a 1.19.0 shell).
- **34 hand-written Vietnamese catalogues are inert** — roughly 1,700 msgids
  that translate nothing, including `health_care_command` (158),
  `health_careplan` (118), `health_telemonitoring` (106), `health_incident`
  (106), `health_vitals` (87), `health_voip24h` (86), `health_twin` (79),
  `health_consent` (67). Odoo's `PoFileReader` yields one row per entry
  *occurrence* and has no fallback, so an entry with no `#: ` reference is
  read by nothing (§5.67). Clinic staff are the primary users and the product
  is showing them English.

## 1. Scope

**GB-1 — make every test run, then fix what that reveals.**
1. Correct the §2 procedure: **drop `--no-http`, add `--workers=0`**, and say
   why in the doc itself so nobody reintroduces either.
2. Run the full suite module by module across all 13 modules that ship an
   `HttpCase`. Capture the real result for each.
3. Triage every failure into: (a) a genuine product bug — fix it; (b) a stale
   test asserting behaviour that has legitimately changed — fix the test and
   say so with a `FORCED EDIT` comment and a reason; (c) an environment
   artefact — document it in the ledger.
4. Expect real bugs. A suite that has never run is not a suite that passes.

**GB-2 — make the Vietnamese catalogues load.**
5. Add the missing `#: ` occurrence lines to all 34 inert catalogues.
6. Verify LOADING, not file shape: for each module,
   `code_translations.get_python_translations(mod, 'vi_VN')` must return a
   non-zero count in a shell on vietuat. A green file that loads nothing is
   the exact failure being fixed.
7. Add ONE shared shape assertion so this cannot regress.

**GB-3 — codify both** in `HANDOVER-CONVENTIONS.md` so every later phase
inherits the corrected procedure rather than rediscovering it.

**Binding non-goals:** no new features; no refactoring beyond what a fix
requires; no channel work; no touching a module's behaviour to make a test
pass (fix the test or fix the bug — never bend the product to the assertion);
no mass reformatting of `.po` files beyond adding occurrence lines and
translations that are genuinely missing.

## 2. Verified facts — do NOT re-derive

### 2.1 The 13 modules shipping a real `HttpCase` (grep `^class .*HttpCase`)

```
biz_debranding          biz_deroute             health_api_gateway
health_family_link      health_family_messages  health_portal (4 classes)
health_pwa (5 classes)  health_pwa_daystrip     health_pwa_ergo
health_pwa_family       health_scribe           health_self_booking
health_telehealth       health_telemonitoring   health_workflow_auto
```

Beware the grep trap (§5.72): `grep -rl HttpCase addons/*/tests/*.py` also
matches the **prose** in modules that say "TransactionCase ONLY — this module
ships no HttpCase on purpose" (`health_care_command_channels` is one). Match
the class statement, not the word.

### 2.2 Why they never ran — two independent causes

- `--no-http` (in the §2 command) leaves no HTTP server for `HttpCase` to
  reach. Already ledgered narrowly in the memory note "HttpCase needs http".
- `workers = 2` in `/etc/odoo-server.conf` starts a **PreforkServer**, and
  `HttpCase.setUpClass` reaches for `server.httpd.server_port`, which only the
  threaded server has → `AttributeError: 'PreforkServer' object has no
  attribute 'httpd'` (§5.75).

Both must be corrected together. Fixing one still leaves the other.

### 2.3 The `.po` shape that actually loads (§5.67)

Per entry: `#. module: <mod>` + the code marker (`#. odoo-python` /
`#. odoo-javascript`) + **`#: code:addons/<mod>/<file>.py:0`** — Odoo's own
`.pot` files use a literal `:0`; the line number is unused for code
translations. Model/field/selection/menu labels need a *model* occurrence
instead (`#: model:ir.model.fields.selection,name:<mod>.selection__…`), and
the xmlid must exist in `ir_model_data` — verify before writing one.

`health_care_command_channels/i18n/vi.po` is the worked example: it was the
first catalogue repaired (CC-C), and CC-F extended it correctly. Clone its
shape. Its `test_105` is the shape assertion to generalise.

### 2.4 Ops facts

Service `odoo-server`; conf `/etc/odoo-server.conf`; addons
`/odoo/odoo-server/addons/`; DB `vietuat`; ssh alias `VietUcUAT`. Stop the
service **and drain workers** (`until` loop on the process count) before
`odoo-bin`, use a spare `--http-port` and an isolated `--logfile`, and restart
afterwards. An `EXIT:1` with a `FAIL:` count of zero means **read the
`ERROR:` lines** — it is never by itself either a pass or a failure.

## 3. Design decisions (binding)

### 3.1 One module at a time, and record every result
Run each module's suite separately and write the real numbers into the report
table — including the ones that were already green. A single combined run
hides which module owns a failure, and this phase's whole value is knowing.

### 3.2 A test that has never run is evidence, not authority
When a never-executed test fails, the default assumption is **the test is
stale**, not that the product is broken — but that assumption must be
*checked* against the code each time, never applied as a rule. The
health_telehealth case went the other way: the test was right and the product
had drifted. Decide per failure, in writing.

### 3.3 Never bend the product to a stale assertion
If a test asserts a behaviour the product deliberately changed, the test moves
and the comment explains why (§5.62's `FORCED EDIT` convention). If a test
asserts a behaviour the product should still have, the product is fixed. What
must never happen is a product change made only to satisfy an assertion nobody
has thought about since it was written.

### 3.4 The `.po` fix is mechanical, its verification is not
Adding occurrence lines can be scripted; proving the catalogue loads cannot.
Every module must be verified with a live
`get_python_translations(mod, 'vi_VN')` count in a shell. A file that passes a
shape test and still loads zero entries is the same bug wearing the fix.

### 3.5 Scope control
If GB-1 unmasks more than a handful of genuine product bugs, **stop, report
the list, and let the user decide** what gets fixed in this phase. Do not
silently expand into a multi-day repair. Finishing GB-2 and reporting an
honest GB-1 triage is a complete phase; half-fixing twenty bugs is not.

## 4. Tests
This phase's deliverable IS test execution, so the additions are small:

- **G1** — a shared assertion (generalise
  `health_care_command_channels/tests/test_center.py::test_105`) that every
  non-header block in a repo `.po` carries `#. module:` and `\n#: `, and that
  a block with a code marker carries `#: code:addons/<mod>/`. Place it where
  every module can reach it.
- **G2** — one per repaired module: under `lang='vi_VN'`, a known `_()` string
  from that module actually returns Vietnamese. This is the assertion that
  caught §5.67 in the first place; a shape test alone would not have.
- **G3** — for each genuine product bug fixed in GB-1, a regression test that
  fails without the fix.

## 5. Deploy + evidence
Per §2 **as corrected by this phase**. Green = EXIT:0 + `0 failed, 0 error(s)`
+ zero `FAIL:` / `ERROR: setUpClass` lines, per module.

Evidence required:
- a table of all 13 HttpCase modules: tests run, passed, failed, and what each
  failure turned out to be;
- for each fixed bug: what was broken, since when (git blame the introducing
  commit), and what the regression test asserts;
- a table of all 34 repaired catalogues with the live
  `get_python_translations` count before (0) and after;
- a browser check that one repaired surface really renders Vietnamese for a
  `vi_VN` user — file shape and load count are both necessary and neither is
  sufficient.

## 6. Report back
Deviations (D-numbered); the two evidence tables; every bug found with its
age; ledger entries added; and — most importantly — **an explicit list of
anything found and NOT fixed**, with why. A phase about honesty in testing
cannot end with a quiet omission.

---
**Kickoff line:** Implement `docs/strategy/handovers/green-build-phase.md`
(Phase GB — Green Build: correct the §2 test procedure so `HttpCase` suites
actually execute, run all 13 modules that ship one, triage and fix what that
unmasks, then repair the 34 inert Vietnamese catalogues and prove each one
LOADS; G1–G3). Read HANDOVER-CONVENTIONS.md §2, §5.32, §5.58, §5.67, §5.72 and
§5.75 first. Drop `--no-http` and add `--workers=0`. A never-executed test is
evidence, not authority — decide per failure whether the test is stale or the
product drifted, and never change the product just to satisfy an assertion. If
more than a handful of genuine bugs surface, stop and report the list rather
than expanding the phase. Report every finding, including what you did not fix.
