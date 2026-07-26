# Phase GB — Green Build: report

**Implemented 2026-07-26 against `docs/strategy/handovers/green-build-phase.md`.**
Deployed to vietuat. Not a feature phase: it closes two conditions in which
shipped code was silently not doing its job.

---

## 0. Headline

| | before | after |
|---|---|---|
| `HttpCase` classes that had ever executed | **0 of 28** | 28 of 28 |
| tests executed across the 15 HttpCase modules | 0 (all died in `setUpClass`) | **312, 0 failed** |
| inert Vietnamese catalogues | 34 files / 1,382 entries | 0 |
| catalogues Odoo never even opens | 2 (202 entries) | 0 |
| repo-wide guard against all of it | none | 5 assertions in `health_base` |

Final verification on vietuat, two independent runs:
- combined (35 modules upgraded, tests tagged): **EXIT:0, HTTP:200,
  `0 failed, 0 error(s) of 654 tests`**;
- all 15 HttpCase modules re-run **one at a time against the committed
  state**: 15 × EXIT:0, **312 tests, 0 failed, 0 errors**, and — the check
  that matters for this phase — **zero `ERROR: setUpClass` lines** with 540
  `Starting …` lines in the log. The suites did not merely pass; they ran.

**Genuine product bugs found: zero.** Seven red tests, all traced to two
stale fixtures. That is the honest outcome and it is worth stating plainly:
the value here is the coverage, not a bug count. Twenty-eight test classes
covering public HTTP surface — portal tokens, family links, self-booking, the
PWA API, the API gateway — now actually run, and from here a regression in any
of them is visible the day it lands instead of never.

---

## 1. GB-1 — making the tests run

### 1.1 The correction

`HANDOVER-CONVENTIONS.md` §2 now drops `--no-http`, adds `--workers=0`, takes
its own `--logfile` and a spare `--http-port`, and carries a check that the
suites really ran. Both flags are load-bearing and had to be fixed together —
fixing either alone still leaves every `HttpCase` dying in `setUpClass`.

The signature of the bug was an `EXIT:1` whose `FAIL:` count was **zero**,
which reads like unrelated breakage. That is why it survived for months.

### 1.2 One handover fact corrected

The handover said "13 modules"; its own list named 15, and 15 is right. The
class count (28) was correct.

### 1.3 Results, one module at a time (handover §3.1)

Each module upgraded and tested separately so a failure has an unambiguous
owner.

| module | HttpCase classes | tests | failed | errors | outcome |
|---|---:|---:|---:|---:|---|
| biz_debranding | 1 | 7 | 0 | 0 | green |
| biz_deroute | 1 | 9 | **1** | **4** | stale fixture → fixed |
| health_api_gateway | 1 | 16 | 0 | 0 | green |
| health_family_link | 1 | 17 | 0 | 0 | green |
| health_family_messages | 1 | 25 | 0 | 0 | green |
| health_portal | 4 | 33 | 0 | 0 | green |
| health_pwa | 5 | 40 | 0 | 0 | green |
| health_pwa_daystrip | 2 | 13 | 0 | 0 | green |
| health_pwa_ergo | 1 | 3 | **2** | 0 | stale version pin → fixed |
| health_pwa_family | 3 | 21 | 0 | 0 | green |
| health_scribe | 2 | 20 | 0 | 0 | green |
| health_self_booking | 1 | 19 | 0 | 0 | green |
| health_telehealth | 2 | 16 | 0 | 0 | green |
| health_telemonitoring | 2 | 49 | 0 | 0 | green |
| health_workflow_auto | 1 | 24 | 0 | 0 | green |
| **total** | **28** | **312** | **3** | **4** | **2 root causes** |

### 1.4 Triage of all seven red tests

**`biz_deroute` — 5 tests, ONE cause. Verdict: stale test.**
Every authenticating test used the literal `admin`/`admin`. That holds on a
fresh demo database and nowhere else. Four errored in `self.authenticate`; the
fifth POSTed the same dead credentials to `/web/login`, got the login page
re-rendered at 200, and failed as `200 != 303` — reading like a routing
regression in the white-label layer when routing was never reached at all.

Fixed by owning the user (`new_test_user` in `setUp`), which is what every
other `HttpCase` in this repo already does. The product was never involved.
Ledgered as §5.86, including the triage lesson: when several tests in one file
fail with different-looking symptoms, look for the single shared fixture
before believing you have several bugs.

**`health_pwa_ergo` — 2 tests, ONE cause. Verdict: stale test.**
Both pinned PWA version `1.9.0`; the shell has served `1.19.0` for ten bumps.
The product is fine — the same run's response body contains
`ergo.css?v=1.19.0`, `ergo.js?v=1.19.0` and the `vu_ergo_modes` boot marker.

Two things had to fail together for this to persist: `health_pwa_ergo` was
**missing from the conventions §3 pin-test list**, so nobody bumped it, and it
is an `HttpCase`, so nothing ever ran to complain. Both are now fixed — the
module is in the §3 list, and the pin stays a hard literal on purpose, since
that tripwire is the entire point.

**Product bugs: none.** Nothing was changed in any module's behaviour.

---

## 2. GB-2 — making Vietnamese load

### 2.1 The handover under-called this, and the difference matters

It described one defect (§5.67, missing `#:` occurrence lines) and a
mechanical fix. Measured, the 1,382 entries held **three** defects:

| | entries | why it is inert |
|---|---:|---|
| missing `#:` occurrence (§5.67) | 1,382 | `PoFileReader` yields one row per occurrence, no fallback |
| **also** missing the code marker (§5.58) | 1,204 | loader keeps only entries whose comments carry `odoo-python`/`odoo-javascript` |
| **and** not code strings at all | 687 | field labels/selections/view text need `model:` occurrences; a `code:` one loads and leaves the label English |

The third is the one that would have quietly wasted the work. A field label
given a `code:` occurrence produces a catalogue that passes a shape test,
reports a healthy load count, and shows the clinic English — the bug wearing
the fix, exactly as handover §3.4 warned. Only 492 of the 1,382 entries were
ever code strings. The other ~1,100 are the labels staff read all day, and
they travel a completely different road (`_load_module_terms`, at upgrade,
into a jsonb column). Recorded as §5.85.

### 2.2 How each entry was resolved

From source, per entry, never by pattern:

- a string passed through `_()` / `_lt()` / `self.env._()` → `code:addons/<mod>/<file>.py:0` + `odoo-python`
- a string passed through `_t()`, or QWeb text under `static/` → the same with `odoo-javascript`
- `fields.X(string=…)` → `model:ir.model.fields,field_description:<mod>.field_<model>__<field>`
- `selection=[…]` / `selection_add=[…]` → `model:ir.model.fields.selection,name:…`
- `_description` → `model:ir.model,name:…`; `help=` → `…,help:…`
- view arch text and `string=`/`title=`/`placeholder=` → `model_terms:ir.ui.view,arch_db:<mod>.<xmlid>`
- menus, actions, sequences, groups, data records → `model:<model>,name:<mod>.<xmlid>`
- manifest `name`/`summary` → `model:ir.module.module,shortdesc:base.module_<mod>`

**A term gets every occurrence it legitimately has, not the first one.** That
detail was found the hard way: `<field name="note_count" string="Evidence"/>`
in the *list* view stayed English because the resolver had already claimed
"Evidence" for the *form* view. Odoo's own `.pot` files list every place a
term is defined and `PoFileReader` yields a row for each. Fixing it took the
model occurrences from 1,143 to **1,333**.

Four parsing traps made real strings look dead, each fixed:
`unicode_escape` mangling every em dash and diacritic; implicit string
concatenation across source lines (solved with `ast` — Python has already
joined it); Odoo 19's `self.env._()` form; and `selection=` pairs held in a
module-level constant.

### 2.3 Every derived reference was verified — both kinds

**Model occurrences:** 845 distinct xmlids, checked against `ir_model_data` on
vietuat before being written: **845 of 845 present**. A guessed reference
passes a shape test and still translates nothing, so none was guessed.

**Code occurrences:** re-checked afterwards by parsing each referenced file
with `ast` and confirming the msgid really is an argument to `_()` / `_lt()`
there (a substring grep is not enough — implicit concatenation across source
lines makes a correct reference look wrong, and that produced 23 false alarms
on the first attempt). Of 693 code occurrences in this phase's files,
**6 are inaccurate, and none of them was derived by this phase** — all six sit
in `health_base/i18n/vi_VN.po` and came in verbatim with the
`SAMPLE_TRANSLATION.po` merge, carrying references Odoo's own export wrote
against code that has since changed (`Patient Activated`,
`Please enter a valid phone number.`, …). Stale references are inert for code
translations — the loader keys on the msgid, not the path — so this is
inaccurate documentation rather than a defect, but it is not nothing and it is
listed in §5.

Every one of the occurrences this phase actually derived checks out.

### 2.4 Totals written

| | count |
|---|---:|
| `code:` occurrences | 492 |
| `model:` / `model_terms:` occurrences | 1,333 |
| distinct xmlids, all DB-verified | 845 |
| entries marked obsolete (`#~`, reach nothing) | 28 |
| catalogues repaired | 33 (+1 empty file untouched) |

### 2.5 §5.84 — two catalogues Odoo never opens at all

A third way to be inert, not in the handover and not previously known:
`get_po_paths()` builds exactly `i18n/<base_lang>.po` and `i18n/<lang>.po`.
Anything else is never opened — no scan, no warning, no log line.

| file | entries | unique | still emitted by the module | action |
|---|---:|---:|---:|---|
| `health_pwa/i18n/viVNpo.po` | 223 | 146 | **122** | 145 merged into `vi_VN.po`, file removed |
| `health_base/i18n/SAMPLE_TRANSLATION.po` | 56 | 14 | 10 | 14 merged into `vi_VN.po`, file removed |

The PWA one is the sharper find: a correctly-formed catalogue dated
2025-10-29, flawless in every respect except its name, holding 122 live
strings for the field nurses' primary surface. Ledgered as §5.84 and asserted
by `test_g1c_filename_is_a_language_odoo_reads`.

**Exactly what was not carried over.** A self-check after committing showed
**7** entries dropped from `viVNpo.po`, not the 1 first reported. All 7 were
correctly dropped, and each for a reason:

| dropped | why |
|---|---|
| 2 | msgid is a Python f-string *expression* captured as a literal (`Service completed - {payment_method.replace("_", " ").title()} payment …`). Worse, the Vietnamese translated the identifier inside the braces (`{thanh toán_phương thức.replace(…)}`) — merging them would have been actively harmful had they ever matched. |
| 2 | msgid carries literal backslashes (`Find and tap \"Add to Home screen\" …`); the real source string has none, so it can never match. |
| 3 | multi-line view text that no longer exists in any current health_pwa view. |

Nothing live was lost: an independent pass over all 37 modified catalogues
comparing (msgid, msgstr) pairs before and after — obsolete entries included —
found **0 pairs lost**, and all 56 entries of `SAMPLE_TRANSLATION.po` are
present in `health_base/i18n/vi_VN.po`.

One residue worth naming: **6 of the merged 145 carry that same
literal-backslash corruption** and will therefore never match a runtime
string. They are inert rather than harmful, and they inflate the apparent
translation count by six. Not repaired here — flagged in §5 below.

### 2.6 Live load counts (handover §1.6 — loading, not shape)

`code_translations.get_python_translations(mod, 'vi_VN')` in a shell on
vietuat. Every repaired module was 0 before, by construction.

| module | py in file | py loaded | web loaded | model occ |
|---|---:|---:|---:|---:|
| biz_bi_margin | 0 | 0 | 0 | 10 |
| health_ai_coding | 5 | 4* | 0 | 64 |
| health_base | 33 | 33 | 51 | 1347 |
| health_bhyt | 1 | 1 | 0 | 40 |
| health_care_command | 42 | 41* | 112 | 18 |
| health_care_command_ai | 4 | 4 | 8 | 8 |
| health_careplan | 35 | 35 | 3 | 106 |
| health_cms_clinical | 0 | 0 | 0 | 8 |
| health_condition | 6 | 6 | 0 | 34 |
| health_consent | 25 | 25 | 6 | 52 |
| health_emr | 8 | 8 | 0 | 17 |
| health_evv | 14 | 14 | 5 | 34 |
| health_family_link | 4 | 4 | 0 | 22 |
| health_family_messages | 7 | 7 | 0 | 36 |
| health_fhir_adapter_base | 1 | 1 | 0 | 26 |
| health_fhir_adapter_vn | 2 | 2 | 0 | 13 |
| health_fhir_terminology | 7 | 7 | 0 | 28 |
| health_incident | 27 | 27 | 2 | 84 |
| health_messaging | 2 | 2 | 0 | 35 |
| health_portal | 2 | 2 | 0 | 5 |
| health_pwa | 52 | 52 | 67 | 103 |
| health_pwa_daystrip | 0 | 0 | 0 | 4 |
| health_pwa_ergo | 0 | 0 | 0 | 2 |
| health_pwa_family | 8 | 8 | 0 | 1 |
| health_routes | 4 | 4 | 0 | 28 |
| health_schedule_canvas | 3 | 3 | 24 | 0 |
| health_schedule_drag | 12 | 12 | 9 | 4 |
| health_scribe | 5 | 5 | 0 | 44 |
| health_self_booking | 11 | 11 | 0 | 27 |
| health_telehealth | 2 | 2 | 0 | 22 |
| health_telemonitoring | 15 | 15 | 0 | 120 |
| health_twin | 8 | 8 | 5 | 77 |
| health_vitals | 20 | 20 | 1 | 71 |
| health_voip24h | 20 | 20 | 12 | 70 |
| health_workflow_auto | 5 | 5 | 0 | 33 |

\* The two shortfalls are **duplicate msgids inside one file**
(`'AI Code Suggestions'`, `'Open'`); the loader keys on msgid, so two entries
collapse to one. Benign, and confirmed rather than assumed.

### 2.7 Browser proof

`crm` switched to `vi_VN`, Diagnoses list (`/bizapp/action-1679`,
health_condition — a repaired catalogue). Screenshot:
`green-build-evidence/vi-diagnoses-list.png`.

Renders Vietnamese: **Chẩn đoán** (action), **BỆNH NHÂN**, **MÃ ICD-10**,
**TRẠNG THÁI LÂM SÀNG**, **TRẠNG THÁI XÁC MINH**, **NGÀY GHI NHẬN**,
**KHẲNG ĐỊNH G…**, **BẢNG CHỨNG**, **Xuất tất cả**, **CMS Việt Úc**,
**Thanh bên CMS**, **Tìm kiếm…**, dates as `8 thg 7`. Every column header on
the surface is translated.

`BẢNG CHỨNG` is the one that had to be earned twice: it was English in the
first browser pass, which is what exposed the first-occurrence-wins bug in
§2.2 above. Worth noting that the fix was found by *looking at the screen*,
not by any assertion — G1, G2 and G2b were all green while that column was
still English, because a term with one correct occurrence satisfies every
file-shape and load-count check ever written. The browser step in the
handover's evidence list is not ceremony.

Two lessons from getting this evidence, both recorded:
- **Changing `res_partner.lang` by SQL does not take effect.**
  `res.users.context_get()` is ormcached; the UI kept serving English while
  the database plainly held the Vietnamese values. Change it through the ORM
  or restart. This wasted three round trips and is exactly the kind of thing
  that reads as "the translations didn't work".
- **`service odoo-server restart` races on this box.** The init script's stop
  killed the newly-started process, leaving `systemctl` reporting
  `active (exited)` with nothing listening. Stop, confirm drained, then start.

`crm` has been returned to `en_US`.

---

## 3. GB-3 — codified

`HANDOVER-CONVENTIONS.md`:
- **§2** rewritten: no `--no-http`, mandatory `--workers=0`, own logfile and
  port, plus a check that the HttpCases actually ran and a warning that
  `--logfile` **appends** (a stale `FAIL:` from an earlier run stays in the
  file and a naive grep will report it — this nearly produced a false
  regression in this very phase).
- **§3** pin-test list gains `health_pwa_ergo`, with the rule that a new
  version pin joins the list in the same commit.
- **§4** catalogue rule now states the filename constraint, the three-part
  entry shape, and that a field label is not a code translation.
- **§5.83–§5.86** added: never-executed suites; the filename trap; code vs
  model occurrences; `admin/admin` fixtures.

### Tests added (`health_base/tests/test_i18n_catalogues.py`)

| id | assertion |
|---|---|
| G1 | every non-obsolete entry in every repo catalogue carries `#. module:` and `#: ` |
| G1b | a code marker implies a `#: code:addons/<mod>/` occurrence |
| G1c | every catalogue filename is one `get_po_paths()` will open |
| G2 | every module claiming python translations actually serves them |
| G2b | a translated field label reaches the **database** in Vietnamese, per installed module |

G2b deliberately asserts the label is *translated*, not that it equals the
`.po`: `_load_module_terms` runs with `overwrite=False`, so a value already
refined in the database legitimately wins over the file
(`res_partner.is_patient` holds `Là bệnh nhân` where the file says
`Là Bệnh nhân`). Demanding equality would fail on correct data and push the
next person to "fix" the database to match a file.

**Three of these five failed on their first run**, which is the point of
writing them:
1. G1c caught `health_base/i18n/SAMPLE_TRANSLATION.po` — a real second
   instance of §5.84 that I had not found by grepping.
2. G2 and G2b failures were **my own test's `.po` parser**: it read escaped
   quotes literally and read multi-line msgids as empty, so well-formed
   entries looked unloaded. Fixed in the test, then re-verified by simulating
   the loader locally before re-deploying.

---

## 4. Deviations

- **D1 — GB-2 was three defects, not one.** The handover scoped "add the
  missing `#:` lines". Doing only that would have produced 34 green-looking
  files with ~1,100 labels still English. Did the whole job; §2.1 above.
- **D2 — G2 is two repo-walking tests, not 34 per-module ones.** The handover
  asked for one runtime check per repaired module. A data-driven pair that
  discovers catalogues on disk covers the same ground, cannot go stale as
  modules are added, and does not put 34 near-identical files in the tree.
- **D3 — 28 unreachable entries marked obsolete (`#~`) rather than left or
  deleted.** That is the po standard for "kept, attached to nothing";
  `PoFileReader` skips them explicitly, so behaviour is unchanged and the file
  now states what was already true. It also keeps G1 a clean invariant.
- **D4 — two modules touched beyond the 34** (`health_base`, `health_pwa`).
  They are the §5.84 instances; leaving them would have meant closing a phase
  about inert catalogues while knowingly leaving 132 live dead strings.
- **D5 — no PWA version bump** despite editing `health_pwa/i18n/`. No asset
  content changed; §3's rule is about cache-busting shipped JS/CSS.

---

## 5. Found and NOT fixed

Per handover §6 — a phase about honesty in testing cannot end with a quiet
omission.

1. **28 entries translate nothing and cannot** (now marked obsolete):
   - `health_incident` (8) — `Location`, `Witnesses`, `Root Cause`,
     `Contributing Factors`, `Outcome`, `Notified Authority`, `Notified Date`,
     `Due Date`: appear nowhere in the module. Dead, probably renamed fields.
   - `health_voip24h` (7) — `Sync Started`, `Sync failed: %s`, `Group By`, …:
     leftovers from before the Odoo 19 migration.
   - `health_twin` (7) — `Blood Pressure`, `Heart Rate`, `Temperature`,
     `Weight`, `Blood Glucose`, …: **a real product gap.** They are hardcoded
     in a Python tuple (`health_twin_risk.py:259`) and never passed through
     `_()`, so the chart series can never be translated. Fixing it is a
     product change and out of scope here; it is a small, well-defined job.
   - `health_vitals` (6) — three are `_sql_constraints` messages, which by
     ledger §5.1 are never materialised in this repo, so no
     `ir.model.constraint` record exists to attach them to. Confirmed against
     the DB: zero rows. Untranslatable by construction.
2. **Selection *values* still render English** in the Diagnoses list
   (`Active`, `Confirmed`) even though the data is plainly correct:
   ```
   29452|active  |{"en_US": "Active",   "vi_VN": "Đang hoạt động"}
   29453|inactive|{"en_US": "Inactive", "vi_VN": "Không hoạt động"}
   29454|resolved|{"en_US": "Resolved", "vi_VN": "Đã khỏi"}
   ```
   No duplicate rows, no missing key. The column *header* for that very field
   (`TRẠNG THÁI LÂM SÀNG`) translates, so the language context is right and
   the model-term import worked. So this is somewhere on the display path
   between `ir.model.fields.selection` and the rendered cell, not in the
   catalogue. I checked the data, ruled out duplicates and a stale registry,
   and stopped there rather than guess. Small, well-scoped follow-up; it
   affects every module's status columns, so it is worth doing.
3. **Nobody is reading Vietnamese today.** All **78 active users** are on
   `en_US`. The catalogues are now correct and loading, and the browser proof
   is real, but no clinic user currently consumes them. The work is a
   precondition for Vietnamese rollout, not a change anyone will notice
   tomorrow. Said plainly so the number is not mistaken for impact.
4. **`health_pwa/i18n/pwa.po.backup` and `health_base/i18n/base.po.backup`**
   exist on the server but not in the repo. Not `.po`, so never loaded and not
   caught by G1c. Left alone — server-side cruft, not ours to delete
   unasked.
5. **The 24 non-live orphans** among the merged PWA strings translate text the
   PWA no longer emits. Harmless (the loader keys on msgid) and cheaper to
   keep than to audit one by one.
6. **6 merged PWA entries carry literal-backslash msgids**
   (`… \"Add to Home screen\" …`) and can never match the real string, which
   has no backslashes. They came in that way from the dead catalogue. Inert,
   not harmful; repairing them means re-deriving each msgid from source, which
   is a small separate job. Reported rather than silently left: the
   translation count for health_pwa is six higher than the number of strings
   that can actually resolve.
7. **6 merged `health_base` entries carry stale `code:` references** pointing
   at `models/res_partner.py` / `models/health_facility.py` for strings that
   are no longer `_()` arguments there (§2.3). They arrived with the
   `SAMPLE_TRANSLATION.po` merge, written by an Odoo export against older
   code. Inert — code translations key on the msgid, not the path — so this is
   wrong documentation, not a broken translation. Re-deriving them is a small
   job and worth doing next time `health_base`'s catalogue is touched.
8. **`addons/biz_deroute/biz_deroute_stage/` is a full module copy nested one
   level too deep.** Odoo discovers modules as direct children of the addons
   path, so it is invisible — `ir_module_module` holds `biz_deroute` and
   nothing else. Its `tests/test_deroute.py` is a stale copy still carrying
   the `admin/admin` fixture this phase fixed, and it can never run to say so.
   Dead weight, and a trap for the next person who greps: fixing the copy
   would change nothing, and reading it would suggest the defect is still
   open. Left alone — deleting someone's staging copy is not this phase's
   call. (The other `admin/admin` hits in the repo are all in vendored Odoo
   core modules, which are upstream's business.)
9. **My own report was wrong once, and I found it after committing.** It said
   1 entry was skipped in the PWA merge; the real number was 7. Corrected in
   §2.5 with the reason for each. Noting it here because the check that caught
   it — comparing (msgid, msgstr) pairs across every changed file rather than
   trusting the merge script's own tally — is the check worth repeating on any
   future bulk catalogue edit, and it is cheap.
