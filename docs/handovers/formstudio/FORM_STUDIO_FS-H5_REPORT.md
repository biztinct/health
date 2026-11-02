# FORM STUDIO — FS-H5 report (hardening: deploy check, dropdown check, template rule, standard encrypted columns, analytics SQL layer, the Vietnamese offline helper)

Written 2026-11-03 by the Opus implementer. Handover: `FORM_STUDIO_FS-H5_HARDENING.md` (commit b4c471f5).

## Things to know before reading

1. **Tests:** final full run on the clone, no `-u`: 659 tests; the only failures are the **same 34
   pre-existing** ones as the baseline run on the same clone with the live code (648 tests, 2 failed,
   32 errors, §5.294). Three of my new tests failed on the first full run (test-writing faults, not
   product faults); they were fixed and both affected suites re-run in full: **biz_bi 159 green**
   (gate ≥ 155) and **biz_form_studio 86 green**. Every new test 67–80 passes.
2. **Live post-check output** (verbatim, the first live runs of the new wrapper):
   ```
   carejiox:           ==> studio: checked 0 layouts, broken 0, host problems 0, encrypted values 0
                       ==> jobs: 96 active                                   (WRAPPER EXIT=0)
   carejiox_template:  ==> carejiox_template is the golden template
                       ==> studio: checked 0 layouts, broken 0, host problems 0, encrypted values 0
                       ==> jobs: 0 active (template: switched off 0 → 0)    (WRAPPER EXIT=0)
   hhh:                ==> studio: checked 0 layouts, broken 0, host problems 0, encrypted values 0
                       ==> jobs: 77 active                                   (WRAPPER EXIT=0)
   ```
   No job came back on the template this time (FS-H4 saw 7), so the live template run shows `0 → 0`;
   the real switching-off was proven on a copy of the template (`5 → 0`) and on the clone through the
   wrapper (`7 → 0`).
3. **Beyond the sanctioned file list** (all logged below): `biz_bi/models/bi_gold.py` (one line —
   without it a gold copy could not be rebuilt), a `health_pwa` migration (asked for in §3.6 text,
   not in the §0 list), test 70 in `health_phi_encryption/tests/`, and a rehearsal-only setting in the
   wrapper (`CAREJIOX_DEPLOY_CONF`) so the rehearsed binary is byte-identical to the live one.
4. **Found and fixed on the way:** the analytics **gold copies physically held the 13 encrypted
   columns** (tokens and search indexes) on all three databases — now 0 everywhere. The client table
   still has its **old plain health columns, empty**, on all three databases (§5.302) — kept out of
   analytics now; dropping them is a separate decision.
5. **Not finished / not done:** nothing in scope is left open. Not done by design: no refusal on the
   server for a hand-written export of the standard encrypted columns (residual, §"Holes").
6. **Owner decisions** (all in `docs/strategy/access-cleanup-proposal.md`): who may export lists
   (recommended: Owner only); switch off the `demo` login (active, never signed in, can export);
   fix or rename the Admin role (cannot open a Client, Contact or Booking on its own); the template
   rule (no client information on the blank system — today it holds none); and whether to delete the
   7 macOS `._*` files on the live code folder.

## In one paragraph (for the owner)

Form Studio is now finished and can be left alone. Every update of the system now ends with an
automatic check, before the system comes back up, that every Studio screen still fits, that the blank
system new clinics are made from holds no encrypted information, and that its scheduled jobs are
switched off — it switches them off by itself. A Studio dropdown now refuses anything that is not one
of its options, in plain words and in Vietnamese. The client's encrypted identity numbers and health
notes no longer appear in the export list or in Analytics, and the Analytics storage no longer keeps
copies of them (it did, on all three systems). A user's export list no longer offers a client's health
fields through the user's own contact. Vietnamese-language nurses now get the current offline helper
of the nurse app (they were stuck on a two-year-old one); the app is version 1.21.1. All of this is
live on carejiox.com, the blank system and hhh; nothing was published, no field was created, nothing
was encrypted or exported, and no one's access was changed. A plain-English proposal for who should
be able to do what is ready for you to decide.

## Standing rules (stated back)

- **White-label:** no "Odoo" in anything a user sees. The one new sentence ("… is not one of the
  options of …") and its Vietnamese were checked by hand and by gate 12a over the catalogue.
  Found pre-existing (not touched, not sanctioned): the Analytics pipeline editor shows source types
  as `Contact (odoo_model)` (screenshot 43a).
- **Generic core:** `biz_form_studio` names no product; the new `base.py` code names none; gate 12a
  and test 75 run over it; the core still imports no cipher.
- **Vietnamese** for every new user-visible string: one entry in `biz_form_studio/i18n/vi.po`;
  biz_bi needed none; the stale offline-helper term removed from `health_pwa/i18n/vi_VN.po`;
  `health_base` catalogue gates (9) green with the private tree.
- **Design:** no screen changed; no new icon, colour or font.
- **Chatter untouched; host models untouched.**
- **Shared-module edits:** each module in its own commit with its version bumped (biz_form_studio
  19.0.1.4.0, health_phi_encryption 19.0.1.1.1, biz_bi 19.0.1.7.3, health_pwa 19.0.1.1.1). Not
  touched: `biz_tenants`, `biz_tenancy`, `web/`, `phi_crypto.py`, `health_pwa/static/**`, nurse-app
  JavaScript.
- **Rehearsed on `carejiox_fs5`** (tenant slug → `nowhere_fs5_1`, 96 jobs off, mail servers and
  fetchmail off, new `database.uuid`, private tree `/odoo/fs5/addons` first on the path via
  `/etc/odoo-fs5.conf`, `--db-filter=^carejiox_fs5$`, `systemd-run` units; tests on 8189, QA web on
  8199/8197 through a tunnel). The new wrapper was proven on the clone as a separate binary
  (`/usr/local/bin/carejiox-deploy-fs5`) before it replaced the live one. Never `-t` on the live box.
  Suites without `-u` after upgrading.
- **Live:** only the export dialog (opened, nothing chosen, closed), the Analytics builder and the
  nurse app were opened, by a temporary Owner removed afterwards. Nothing published, no field, nothing
  encrypted, nothing exported, nothing granted or revoked to a real person, nobody deactivated, no file
  deleted on the live tree. Backups first.
- **Commits** on 19.0, plain sentences, not pushed.

## Files

- `.agent/workflows/carejiox-deploy.sh` — post-upgrade check after every successful `-m`/`-i` (and
  after any `-x`), service down; template detection from the master before the stop; refuses to
  upgrade when the check file is missing; exit 3 carried, service started anyway; header documents
  the lines. `.agent/workflows/carejiox-postcheck.py` (new) — the check (installed as
  `/usr/local/lib/carejiox/postcheck.py`).
- `addons/biz_form_studio/` (→ 19.0.1.4.0) — `models/base.py` (`_fs_check_selections`, `create`,
  `write`, `fields_get`, shared `_source_field`), `models/fs_studio.py` (`validate_all` returns
  `encrypted_values` + `encrypted_fields`; `_encrypted_value_counts`), `i18n/vi.po`,
  `tests/test_fs_core.py` (68, 68b, 69, 74, 74b, 75).
- `addons/health_phi_encryption/` (→ 19.0.1.1.1) — `exportable=False` on the 13 client and 7
  clinical-note storage columns (keyword argument only); `tests/test_phi_encryption.py` (70).
- `addons/biz_bi/` (→ 19.0.1.7.3) — `bi_pipeline.py` (explicit column lists, `_left_out_columns`,
  `_clean_base_columns`, `action_apply` refreshes `has_active_pipeline`), `bi_dataset.py` (silver skips
  fields that are not analytics material; `_withheld_stored_fields`, `_silver_left_out_fields`),
  `bi_source.py` (`_non_exportable_field_names`, `_fetch_schema_pg` filter), `bi_gold.py` (one line,
  D8), `migrations/19.0.1.7.3/end-rebuild-sql-layer.py`, `tests/test_non_exportable.py` (71, 71b).
- `addons/health_pwa/` (→ 19.0.1.1.1, app 1.21.1) — `views/pwa_templates.xml` (`<t
  t-translation="off">` around the script; five pins), `i18n/vi_VN.po` (stale term removed, 790
  lines), `migrations/19.0.1.1.1/end-drop-stale-worker-copy.py`.
- Pin tests: `health_pwa_daystrip`, `health_scribe`, `health_pwa_ergo`, `health_pwa_family`,
  `health_form_studio/tests/test_fs_health.py` (+ 72, 73).
- Docs: `HANDOVER-CONVENTIONS.md` (§2 paragraph, §5.288 fixed line, §5.296–§5.305),
  `SAAS_RUNBOOK.md` (§4 check paragraph; template section: jobs line + template rule),
  `FORM_STUDIO_PROGRAM.md` (`fs.studio.validate_all()` at :215-219 and :283),
  `docs/strategy/access-cleanup-proposal.md` (new).

## Tests (§5)

Baseline (clone, live code, no `-u`): **648 tests, 2 failed, 32 errors** — the 34 of §5.294
(`PwaFamilyBase` 17 distinct, scribe `TestAcl`/`TestIdempotency`/`TestRobustness`/`TestSweepGates`/
`TestTranscription`/`TestUpload`, telehealth `TestConsentLogged`). After (clone, FS-H5 code, no
`-u`): **659 tests**; new failures only the three FS-H5 tests fixed below; "gone" none. Per-module
stats after: biz_access 312, biz_bi 159, biz_form_studio 86, biz_kit 18, health_base 9,
health_compliance 23, health_crm 17, health_fieldservice 42, health_form_studio 45, health_incident 22,
health_phi_encryption 11, health_pwa 86, health_pwa_daystrip 25, health_pwa_ergo 5, health_pwa_family
29, health_scribe 34, health_telehealth 38. Re-runs after the fixes: biz_bi `0 failed, 0 error(s)`
(159), biz_form_studio `0 failed, 0 error(s)` (86).

| # | Test | Result | What it proves |
|---|---|---|---|
| 67 | post-check, shell level on the clone | PASS | healthy: `==> studio: checked 1 layouts, broken 0, host problems 0, encrypted values 0` / `==> jobs: 0 active`, exit 0. Broken (layout anchored on a card that does not exist, D7): `broken 1` + `broken: res.partner layout 254 — The card "nope" no longer accepts fields.`, exit 3, layout `broken`, its view switched off. The service starting in both cases is shown by 78 |
| 68 | `test_68_a_dropdown_refuses_a_value_that_is_not_an_option` | PASS | create/write refused "\"not_an_option\" is not one of the options of Blood group.", no `x_fs_`; an option and False pass; a batch with one wrong value creates nothing; encrypted dropdown refused before any token is written, good value tokenised; Vietnamese "… không phải là một lựa chọn của …"; import: a label imports, a wrong value creates nothing and the importer names the label (D3) |
| 68b | `test_68b_the_check_costs_nothing_without_studio_keys` | PASS | measured **0.35 µs per written record** with no Studio key (res.partner, 200-record batches × 2000) |
| 69 | `test_69_validate_all_counts_encrypted_values` | PASS | 0 and `[]` with no encrypted field; field with 0 values listed; 3 values → +3 and `{'model': 'res.partner', 'name': …, 'values': 3}` |
| 70 | `test_70_the_standard_encrypted_columns_are_not_export_material` | PASS | all 13 + 7 columns `exportable: False`; no `groups` added, still stored; visible fields exportable; an Owner (not administrator) reads and writes Known Allergies and National ID; token at rest; the visible field still exports |
| 71 | `test_71_the_bi_sql_layer_carries_only_analytics_material` (+71b) | PASS | silver view without the non-exportable and the sensitive field; clean view without `SELECT *`, without both, without the leftover columns of non-stored fields; `_fetch_schema` of the clean view lists neither; editor preview lists neither; filter + calc keep the list; a step naming either is refused; an old `SELECT *` clean view is never offered the column; the end-migrate rebuilds it and the silver view |
| 72 | `test_72_the_worker_script_is_the_same_in_every_language` (HttpCase) | PASS | a planted `vi_VN` copy (1.0.95) is served, then gone after the migration (other views' copies untouched); GET as a `vi_VN` nurse == as an `en_US` nurse, `CACHE_VERSION = '1.21.1'`, no `<t` in the body; the app shell still shows "Việt Úc Care v" to the Vietnamese nurse and "Viet Uc Care v" to the English one |
| 73 | `test_73_the_nurse_app_version_pins` + co-resident pin tests | PASS | five pins 1.21.1; the worker template's only child is `t-translation="off"`; five pin files at 1.21.1, none at 1.21.0; no worker term in `vi_VN.po`; daystrip/scribe/ergo/family shell tests pass (same pre-existing consent fails only) |
| 74 | `test_74_a_user_does_not_offer_its_contacts_health_field` (+74b HttpCase) | PASS | `res.users.fields_get` → the related copy of a health field `exportable: False`, a plain Studio field `True`; with an attribute list without `exportable` nothing is added; over `/web/export/get_fields` for Users and Contacts the health field is absent and the plain one present |
| 75 | `test_75_the_gates_cover_the_fs_h5_files` + 12a–12f | PASS | gates over `base.py` and `fs_studio.py`; prefix gate and `get_values` in the source; no `phi_crypto`/cryptography import; the catalogue entry exists |
| 76 | phi 11 · compliance 23 · health_form_studio 45 · biz_form_studio 86 | PASS | all green |
| 77 | full run baseline vs after | PASS | the same 34 pre-existing failures and nothing else (after the three test fixes) |
| 78 | wrapper end to end on the clone (rehearsal binary) | PASS | run A `-D carejiox_fs5 -m biz_form_studio`: studio + jobs lines, `WRAPPER EXIT=0`, http 200. Run B with `CAREJIOX_IS_TEMPLATE=1`, 7 jobs on and one encrypted value: `encrypted values 1` + the field named, `==> jobs: 7 active (template: switched off 7 → 0)`, `==> POSTCHECK FAILED (exit=3) — read the lines above`, service started (http 200), `WRAPPER EXIT=3`, 0 jobs afterwards. Also: a typo database → exit 2 before any stop; missing check file → exit 2 before the lock |
| 79 | template rule | PASS | shell level, template mode: one encrypted value → exit 3 naming `res.partner x_fs_allergy_flag — 1 values`; 0 values → exit 0. Real template path (template without the platform module → the master's routine): on a copy of the template with the clone as master, `5 active (template: switched off 5 → 0)`, the job list written into the copy's `biz_tenants.template_active_crons` |
| 80 | white-label + i18n | PASS | the dropdown sentence names no product and has Vietnamese; biz_bi added no string; `health_base` catalogue gates 9/9 |

### biz_bi suite (the gate)

| Run | biz_bi tests | Failed | Errors |
|---|---|---|---|
| Before (clone, live code) | 155 | 0 | 0 |
| After (clone, FS-H5 code, final) | 159 | 0 | 0 |

## Browser QA (§6) — evidence in `fs_h5_shots/`

Personas on the clone: Owner `fs5.qa.owner` (Owner role + export right + Analytics designer, D11),
VI Owner `fs5.qa.owner.vi`, nurses `fs5.qa.nurse.vi` / `fs5.qa.nurse.en`. Studio fields on the Client
screen for QA: "Preferred language" (dropdown, Staff), "Allergy flag" (health information → stored
encrypted), "Shoe size" (plain), published in a "FS5 QA" card.

| Step | Result | Evidence |
|---|---|---|
| 41 | Clients → Actions → Export: 411 fields listed; "encrypted" → "No match found."; "ID" → "National ID (CCCD/CMND)" listed, no "National ID Index"/"CCCD Number Index"; Studio "Allergy flag" absent, "Preferred language"/"Shoe size" present | `41a`, `41b` |
| 42 | Analytics → Explore → Visit Margin (after rescan as the superuser): no "(encrypted)" field, Studio plain fields offered, "enc" → nothing; the 11 `_enc` and 2 `_bidx` catalogue rows still exist, marked sensitive | `42a` |
| 43 | Analytics → Data → Pipelines → Contact (a filter step, applied): preview of 211 columns, none `_enc`/`_bidx`, no old plain health column, no Studio health field. Found here: the old empty plain columns (D8b, §5.302) | `43a` |
| 44 | Client "Client Mar19": Preferred language → Vietnamese, saved, read back `vietnamese`; a wrong value over RPC → dialog "\"klingon\" is not one of the options of Preferred language."; the VI Owner gets "\"klingon\" không phải là một lựa chọn của Preferred language." / "Đóng"; 820 px: card fits, `scrollWidth 820 = 820` | `44a`–`44d` |
| 45 | Nurse app at 390 px, Vietnamese nurse: config 1.21.1, worker `service-worker.js?v=1.21.1`, `CACHE_VERSION 1.21.1`, only cache `health-pwa-v1.21.1`, no console message; English nurse the same; the worker script is byte-identical for both (SHA-256 `229c2c5a49fcf4de…`, 14,089 bytes) | `45a` |
| 46 | Settings → Users → Export: "Allergy" finds only "All Emergency Contacts"; "Shoe" finds "Shoe size"; no `_enc`/`_bidx` | `46a`, `46b` |
| 47 | Live carejiox.com, temporary Owner: Clients export dialog (409 fields, "encrypted" → nothing, no `_enc`/`_bidx`, no Studio field — live has none; closed without choosing); Analytics Explore → Visit Margin, "enc" → nothing; nurse app at 390 px: 1.21.1 config, worker and cache, worker SHA identical to the clone's; no console message | `L47a`–`L47c` |
| 48 | The wrapper's own output on the three databases — see "Things to know" §2 and "Deploy" | (text) |

Live clean-up: user `fs5.qa.live.20261103` (id 10116 / contact 38001) deleted with its sign-in log
(1), live-update rows (12), device log (1), presence (1), welcome chat (channel 148 and its message),
its #general membership, its welcome task (13872) and its 7 personal task stages; a scan of every
column that points at users or contacts finds 0 rows for either id.

## Deploy (§7)

1. Clone built and neutralised; baseline run; upgrade
   `-u biz_form_studio,health_form_studio,biz_bi,health_phi_encryption,health_pwa -i <4 pin modules>`
   with the private tree (exit 0, 67 s); end-migrate on the clone: "1 gold copy re-created", worker
   view "0 stale language copies removed" (the upgrade itself had dropped it); after-run; QA 41–46;
   tests 67/79 at shell level; the rehearsal wrapper `carejiox-deploy-fs5` for 78 (two runs, ~90 s of
   live downtime each at 03:04–03:08 Vietnam time — the wrapper always stops the service).
2. Backups `/var/backups/fs5/{carejiox,carejiox_template,hhh}.dump` (19 / 13 / 14 MB; `pg_restore -l`
   reads 26,560 / 23,867 / 23,869 entries). Jobs before: 96 / 0 / 77.
3. Old wrapper kept as `/usr/local/bin/carejiox-deploy.pre-fs5` (md5 e42df2b7…); new wrapper installed
   from the commit (`cmp` identical to the rehearsed binary) and the check file at
   `/usr/local/lib/carejiox/postcheck.py`. **To restore the old wrapper:**
   `sudo cp -p /usr/local/bin/carejiox-deploy.pre-fs5 /usr/local/bin/carejiox-deploy`.
   Staged with `git archive` (0 `._` files; every module diffed identical to what was tested).
   `carejiox-deploy -d -m … -i …` (03:15 Vietnam time), then `-D carejiox_template -m … -i …`, then
   `-D hhh -m … -i …` — outputs above, all `WRAPPER EXIT=0`, http 200. Jobs after: 96 / 0 / 77.
4. All three: biz_form_studio 19.0.1.4.0, health_form_studio 19.0.1.3.0, biz_bi 19.0.1.7.3,
   health_phi_encryption 19.0.1.1.1, health_pwa 19.0.1.1.1 installed; worker view holds `en_US` only;
   rendering the worker as `vi_VN` == `en_US` with `CACHE_VERSION = '1.21.1'` on every database (same
   SHA); 0 layouts, 0 drafts, 0 `x_fs_` fields; gold copies hold 0 encrypted columns (were 13), silver
   views 0; end-migrate: carejiox 1 gold copy, template 5 silver + 1 gold, hhh 5 silver + 1 gold, 0
   failed; `/web/login` 200 on carejiox.com and hhh.carejiox.com.
5. Housekeeping (§3.9): the four FS-H2 sleeper loops (PIDs 863850, 864009, 865007, 865253 — each a
   `bash -c while pgrep -f "odoo-bin.*carejiox_fs2…"`, never an `odoo-bin`) killed by PID; list empty
   afterwards. QA 47–48. Clone, its filestore, the template copy `carejiox_fs5t`, private tree, clone
   config, rehearsal binary, units, staging folders, scratch files and the tunnel removed; only the
   backups remain in `/var/backups/fs5/`.

**macOS `._*` files on the live code folder (deleted nothing):** 7, all in `advanced_pricing`, 163
bytes each, dated 2026-11-01: `security/._ir.model.access.csv`, `views/._menu_items.xml`,
`views/._pricing_import_wizard_views.xml`, `views/._pricing_rule_bulk_wizard_views.xml`,
`views/._product_catalog_views.xml`, `wizards/.___init__.py`, `wizards/._pricing_rule_bulk_wizard.py`
(§5.271 counted twelve; the `health_pwa` ones are gone since health_pwa is staged from git).

**`hr_skill` NOT NULL warnings (fixed nothing):** carejiox — `hr_skill.category_id`,
`hr_skill_level.level_value`, `hr_job_skill.required_level_id`; carejiox_template and hhh —
`hr_skill.category_id`, `hr_skill_level.level_value`.

## Deviations

- **D1 — `Selection.get_values(env)` answers the option values, not pairs**
  (`fields_selection.py:223-227`); the handover's sketch unpacked pairs. The check uses the list as
  is.
- **D2 — the `fields_get` rule is generic, not prefix-gated:** any related field whose final source
  is not exportable is described not exportable. Reason: after §3.4 the Users export dialog would
  otherwise still list the 13 standard encrypted columns through the user's contact. It only adds a
  flag already true at the source; cost is one attribute check per related field.
- **D3 — the import path refuses first with the importer's own message** ("Value 'zzz' not found in
  selection field 'Blood group'", labels shown, `ir_fields.py:447-475`); the new message appears on
  create and write. Test 68 asserts both.
- **D4 — `CAREJIOX_DEPLOY_CONF`** in the wrapper (rehearsal only, documented in its header): the
  live config points at the live code folder, so without it a rehearsal on the clone would have
  upgraded the clone with the OLD code. With it, the rehearsed binary is byte-identical to the one now
  live. Never set on live.
- **D5 — `biz_tenants.template_db` is not stored on the master** (fact 2 drift): the wrapper falls
  back to the registered default `carejiox_template` (`DEFAULT_TEMPLATE`).
- **D6 — the template quieting reuses `biz.tenants._quiet_template`; the template has no
  `biz_tenants`,** so the check opens the master's registry in the same process and calls it there
  (on a database that has the module — a clone — it calls its own). No `UPDATE ir_cron` fallback was
  needed. `template_quiet_now` was not used: it requires a platform administrator and reads the
  template name itself.
- **D7 — test 67's broken layout** was made by pointing the layout at a card that does not exist (as
  core test 10 does) instead of renaming a field in the clone's base view: the same validator path,
  and nothing on a shared view changed.
- **D8 — biz_bi beyond the named files:** (a) `bi_gold.py` one line — gold builds indexes on
  `_silver_left_out_fields()` instead of the stale list, otherwise rebuilding a gold copy with a
  filterable withheld field fails; (b) the clean view also leaves out physical columns whose field is
  not stored (the empty old plain health columns, §5.302); (c) the end-migrate also re-publishes every
  EXISTING gold copy (they held the 13 encrypted columns) and only re-creates silver views that exist
  (a missing one is made by the engine on first use, as before); (d) `action_apply` refreshes
  `has_active_pipeline` (§5.303).
- **D9 — `health_pwa/migrations/19.0.1.1.1/end-drop-stale-worker-copy.py`** (asked for by §3.6's
  text, not in the §0 file list). It removes every language copy but the source, for that view only.
  It found 0 on all databases: the upgrade itself had already dropped the copy (§5.299).
- **D10 — test 70 lives in `health_phi_encryption/tests/`** (a new class beside the original six);
  that suite's stats line reads 11.
- **D11 — QA personas:** the clone Owner was given the export right and the Analytics designer right
  (FS-H4 D20 precedent); the temporary live Owner was given the export right to open the export
  dialog, and was deleted afterwards. No real person's access changed.
- **D12 — wrapper wording:** a forced template says "is treated as the golden template
  (CAREJIOX_IS_TEMPLATE=1)"; the real one "is the golden template". On the template the check also
  prints one `encrypted:` line per field holding values.
- **D13 — not version-bumped:** `health_form_studio` and the four pin-test modules (tests only, as
  FS-H4 D19); they were copied with `-i` (a plain load for an installed module).
- **D14 — test numbering extras:** 68b (cost), 71b (old view + end-migrate), 74b (dialog over HTTP).

## Verified plumbing — drift found

All §2 facts held at the cited lines except: fact 2 — no `biz_tenants.template_db` row on the master;
fact 3 — `biz_tenants` is not installed on the template (nor on hhh); fact 8 — the pins now sit at
:9, :246, :365, :866, :869 (four lines of comment added); fact 11 — on carejiox the export right is
held by `demo`, `ash@biztinct.com` (platform administrator) and two archived built-in accounts;
§3.2 sketch — `get_values` returns values (D1). Verified APIs: `t-translation="off"` is honoured by the
19.0 term collector (`tools/translate.py:211`) and is a QWeb special directive that renders nothing
(`ir_qweb.py:483`); a term-less translated field is stored `{'en_US': …}` only
(`fields_textual.py:343-345`); `_quiet_template(dbname, say)` writes the template's own
`biz_tenants.template_active_crons` through `_tenant_env` (`service.py:2148-2165`); `odoo-bin shell`
exits with the script's `sys.exit` code and rolls back unless the script commits (`cli/shell.py`).
New facts: the gold copies held the encrypted columns (§5.300); empty old plain health columns exist
on all three databases (§5.302).

## The access proposal's facts table (from the live databases, 2026-11-03)

People = active staff accounts holding the role on carejiox (template / hhh). "Opens" measured on the
clone (identical code and data) by a test person holding only that role, given the record's area.

| Role | People | Client | Contact | Booking | Form Studio | Export | Analytics designer |
|---|---|---|---|---|---|---|---|
| Owner | 6 (0 / 2) | Yes | Yes | Yes | Yes | No | No |
| Admin | 9 (0 / 2) | No (invoices) | No | No (invoices) | Yes | No | No |
| Operations Manager | 3 (0 / 0) | Yes | Yes | Yes | Yes (No on template) | No | No |
| Branch Manager | 3 (0 / 0) | No (invoices) | No | No | No | No | No |
| Doctor | 22 (0 / 2) | No (invoices) | No | Partly | No | No | No |
| Nurse | 57 (0 / 2) | Yes (own area) | No | Own visits | No | No | No |
| Accountant | 7 (0 / 0) | No | Yes | Yes | No | No | No |
| CRM | 8 (0 / 0) | No | Yes | Yes | No | No | No |

`demo` (carejiox only, id 5): active, never signed in, holds the export right plus contacts manager,
sales, stock, projects, timesheets, attendance officer, time-off officer, e-learning officer and
several-companies; no role. Export right holders: carejiox `demo`, `ash@biztinct.com`; template and
hhh only the platform's recovery/administrator accounts. Analytics designer: only
`ash@biztinct.com`. Studio gate on all three: `health_access.group_clinic_admin`.

## Pre-existing holes still open (residual)

1. **A hand-written export of the STANDARD encrypted columns is not refused by the server** (only the
   dialog and analytics hide them; Studio fields are refused). Someone with the export right could
   still ask for tokens and search indexes by name. Nobody in a clinic holds that right today.
2. **The visible standard health fields** ("Known Allergies", "National ID (CCCD/CMND)", …) are
   still in the export dialog and export decrypted for whoever holds the export right — they are not
   marked health information. Worth deciding together with "who exports".
3. **Encrypted files on the template:** attachments encrypted on the template would be unreadable in
   a clinic made from it; the check counts Studio values only (the template holds 0 health files
   today).
4. **`phi_crypto.clear_key_cache` is never called;** no key rotation anywhere (unchanged).
5. **Empty old plain health columns** on all three databases (§5.302).
6. **The pipeline editor shows `(odoo_model)`** after each source name (white-label, biz_bi JS).
7. **Consent-related nurse-app suites red** (§5.294); `hr_skill` null warnings; 7 `._*` files.
8. **A calculated analytics field that names a withheld field** now fails at query time (the column
   is gone from the views) instead of answering; no friendlier message.

## New ledger entries (HANDOVER-CONVENTIONS §5)

§5.288 "fixed in FS-H5" line · §5.296 the wrapper's post-check and its exit 3 · §5.297 no
`template_db` row on the master, no `biz_tenants` on the template · §5.298 callable selections accept
anything; `get_values` returns values; the importer already checks labels · §5.299 `t-translation="off"`
and the term-less write that drops language copies · §5.300 gold copies held the encrypted columns;
matviews are not in `information_schema` · §5.301 related copies in the export dialog · §5.302 empty
old plain health columns · §5.303 `has_active_pipeline` cached per request · §5.304 a failed `load()`
resets the registry in a test · §5.305 measuring "can this role open it" needs the record's area.

## Commits

- `52b149f7` — Form Studio core 19.0.1.4.0: a Studio dropdown refuses a value that is not one of its options, the validator counts encrypted values, and a related copy of a field that may not be exported is not offered in the export dialog
- `f312fd4e` — Encrypted client and clinical-note storage columns are no longer export or analytics material (field flags only)
- `1005d62a` — Analytics: the clean and silver views and the gold copy carry only analytics material, and an end-migrate rebuilds the existing ones
- `2ce9a9a9` — Nurse app 1.21.1: the offline helper script is no longer a translatable term, so Vietnamese users get the current one
- `7544b163` — Form Studio product tests: the nurse app version pins and the offline helper is the same in every language
- `b11f8d99` — Deploy wrapper: a post-upgrade check of Form Studio, encrypted values and the template's scheduled jobs after every upgrade
- `84f06f30` — Access clean-up proposal for the owner: who exports, the demo login, the Admin role and the template rule
- (this report, the ledger entries and the evidence) — the commit after it.

## Evidence folder `docs/handovers/formstudio/fs_h5_shots/`

41a_clone_clients_export_dialog_search_encrypted_nothing · 41b_clone_clients_export_dialog_search_id_no_index_columns ·
42a_clone_analytics_builder_visit_margin_search_enc_nothing · 43a_clone_pipeline_editor_contact_preview_no_hidden_columns ·
44a_clone_client_dropdown_option_saved · 44b_clone_client_dropdown_wrong_value_refused_owner ·
44c_clone_vi_owner_dropdown_wrong_value_refused_in_vietnamese · 44d_clone_820px_client_studio_card_no_overflow ·
45a_clone_nurse_app_vietnamese_nurse_1_21_1 · 46a_clone_users_export_dialog_search_allergy_studio_health_field_absent ·
46b_clone_users_export_dialog_plain_studio_field_present · L47a_live_carejiox_clients_export_dialog_search_encrypted_nothing ·
L47b_live_carejiox_analytics_builder_search_enc_nothing · L47c_live_carejiox_nurse_app_1_21_1 (all `.png`).

## Form Studio: what is left

The programme's five phases are delivered and live. Not done, by decision or out of scope:
- **Key rotation** for encrypted values (Studio's ride on `phi_crypto`; include `x_fs_%_enc` columns,
  `ir_model_fields.fs_companion`, when rotation exists) and **re-encryption on tenant creation**
  (instead, the template must hold none — now checked at every deploy).
- **Server refusal of a hand-written export of the standard encrypted columns** (residual 1).
- **A nightly validator job** (the program's "nightly" idea): the deploy check covers every upgrade;
  layouts can only break when code changes, so no job was added.
- **Bus-pushed reload of open forms after publish** (FS-H1 left it optional; the next page load shows
  the change, §5.269).
- **Studio on more screens** than Client, Contact, Booking and Incident — each needs a host record
  in the product overlay.
- **The owner's decisions** in the access proposal (export right, `demo`, Admin role) and the
  clean-ups listed under holes 5–7.
