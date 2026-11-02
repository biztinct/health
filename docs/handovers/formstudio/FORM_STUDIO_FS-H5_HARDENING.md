# FORM STUDIO — FS-H5: hardening (deploy check, dropdown write check, template rule, the standard encrypted columns, BI SQL layer, the frozen Vietnamese worker)

Handover from Fable (design) to Opus (implementation). Written 2026-11-03 after the FS-H4 report. This is the
LAST phase of the Form Studio programme. Read in this order before touching code:

1. `docs/strategy/HANDOVER-CONVENTIONS.md` — §2 deploy, §3 PWA bump rule (:116-136), §5 ledger incl.
   §5.265–§5.295 (every Form Studio entry), §5.172 (each database encrypts with its own `database.secret`),
   §5.178 (template jobs), §5.204 / §5.220 (wrapper).
2. `FORM_STUDIO_FS-H1_CORE.md` §0 (standing rules) and the four phase reports (deviations are binding facts);
   above all `FS-H4_REPORT.md` "What FS-H5 needs" and "Pre-existing holes".
3. The engine as shipped: `biz_form_studio/models/base.py` (whole file, 59 lines), `ir_model_fields.py`
   (`_fs_options` :53-60, `_instanciate_attrs` :111-134), `fs_common.py` (`FS_PREFIX` :18, `ENC_TYPES` :52,
   `ENC_SUFFIX` :56), `fs_studio.py` (`can_use` :335-342, `_is_gate_user` :77-84, `validate_all` :1402-1435,
   `_encrypt_field` :1110-1148).
4. `.agent/workflows/carejiox-deploy.sh` (whole file, 217 lines) — the only accepted deploy procedure, and the
   file this phase changes.
5. `biz_tenants/models/service.py:229-249` (`_tenant_env`), :631-692 (`_step_clone`), :695-772
   (`_step_configure`), :1896-1923 (`_resolve_target`), :2148 (`_quiet_template`), :2168 (`template_quiet_now`);
   `biz_tenants/models/rollout_service.py:638-663`; `biz_tenants/models/tenants_common.py:37` (`template_db`),
   :47 (`template_active_crons`); `biz_tenancy/models/tenancy.py:55-57`, :326.
6. `health_phi_encryption/models/phi_crypto.py:37-70`, `res_partner.py:15-48`, `health_clinical_note.py:7-30`.
7. `biz_bi/models/bi_pipeline.py:73-112`, :251-277, :327-328; `bi_dataset.py:123-190`, :439-510, :532-542;
   `bi_source.py:155-238`; `bi_field.py:157-169`; `bi_gold.py:62-69`.
8. `health_pwa/controllers/pwa.py:392-402`, `views/pwa_templates.xml:9`, :246, :365, :379-380, :860-1241,
   `i18n/vi_VN.po:26-432`; core `/Users/adity/odoo19/odoo/odoo/orm/fields_textual.py:372`.
9. Core `/Users/adity/odoo19/odoo/odoo/orm/fields_selection.py:66-71`, :113-116, :177, :223-235;
   `odoo/service/db.py:185-213`; `odoo/addons/base/models/ir_config_parameter.py:18-57`.

## 0. Standing rules (FS-H1_CORE §0 binds in full; the short form)

- White-label: "Odoo" never user-visible. Generic core names no product. Plain copy, `x_fs_` never shown.
  Wrapper output is read by engineers only and may name modules and models.
- Flat tokens, `ic()` icons, no gradients/emoji/`font-family`. Vietnamese for every new user-visible string in
  the relevant `vi.po` / `vi_VN.po`.
- Chatter untouched. Host models get no business-logic change.
- **Shared-module edits sanctioned for this phase, and ONLY these** (each module in its own commit, version
  bumped):
  - `.agent/workflows/carejiox-deploy.sh` and a new `.agent/workflows/carejiox-postcheck.py` (§3.1).
  - `biz_form_studio/models/base.py`, `fs_studio.py`, `ir_model_fields.py`, `fs_common.py`, `i18n/vi.po`,
    tests (§3.2, §3.3, §3.7).
  - `health_phi_encryption/models/res_partner.py:36-48` and `health_clinical_note.py:24-30` — **field keyword
    arguments only** (`exportable=False`), nothing else in that module changes; `__manifest__.py` version bump;
    its 8 tests stay green (§3.4). `phi_crypto.py` is NOT touched.
  - `biz_bi/models/bi_pipeline.py`, `bi_dataset.py`, `bi_source.py`, `bi_field.py`, tests, `i18n/vi_VN.po`
    (§3.5). The biz_bi suite is a GATE: 155 green before (FS-H4 report), at least 155 green after.
  - `health_pwa/views/pwa_templates.xml` (the service-worker template node and the five pins), `i18n/vi_VN.po`
    (remove the stale worker term), `__manifest__.py` (§3.6). The co-resident pin tests
    (`health_pwa_daystrip/tests/test_daystrip.py:304-308`, `health_scribe/tests/test_scribe.py:424-430`,
    `health_pwa_ergo/tests/test_pwa_ergo.py:20`, `health_pwa_family/tests/test_pwa_family.py:420-424`,
    `health_form_studio/tests/test_fs_health.py:1147-1150`).
  - Docs: `docs/strategy/HANDOVER-CONVENTIONS.md` (§2 wrapper text + new §5 entries), `docs/strategy/SAAS_RUNBOOK.md`
    (:424 template-jobs line, :316-352 wrapper usage), `docs/handovers/formstudio/FORM_STUDIO_PROGRAM.md`
    (:215-218, :282 — `fs.layout.validate_all()` → `fs.studio.validate_all()`), and a NEW plain-English
    `docs/strategy/access-cleanup-proposal.md` (§3.8).
  - **Not** `biz_tenants`, **not** `biz_tenancy`, **not** `web/`, **not** `health_phi_encryption/models/phi_crypto.py`,
    **not** `health_pwa/static/**` (no app code change this phase).
- Rehearse on a clone `carejiox_fs5` (FS-H1 recipe: slug → nowhere, jobs off, mail off, new `database.uuid`,
  private addons tree first on the path, `--db-filter=^carejiox_fs5$`, `systemd-run`). Never `-t` on the live
  box. Suites WITHOUT `-u` after upgrading (§5.275). Template jobs come back ON after every upgrade — this phase
  makes the wrapper switch them off itself; until the new wrapper is installed, switch them off by hand and say so.
- Live has 0 layouts and 0 `x_fs_` fields. On live: open Studio, the export dialog, the Analytics builder and the
  nurse app only; publish nothing, create no field, encrypt nothing, export nothing.
- Commits on 19.0, plain sentences, each ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  **Do not push.**

## 1. Scope

**Goal.** Close the known gaps so Form Studio can be left alone: the deploy wrapper checks every Studio
screen after every upgrade and quiets the template's jobs itself; a Studio dropdown refuses a value that is not
one of its options; the engine reports encrypted values on the golden template (clinics made from it could never
read them); the standard encrypted columns leave the export dialog and the analytics catalogue; the analytics
SQL layer stops carrying hidden columns; Vietnamese nurses stop receiving a two-year-old offline helper; a
user's export dialog stops listing a health field through the user's contact; a plain-English access proposal
is written for the owner. Nothing new is added to Studio's screens.

**In scope**
1. Deploy wrapper: a post-upgrade check (Studio validator + encrypted-values count + template jobs), installed on
   the box (§3.1).
2. Engine: dropdown write check (§3.2); `validate_all` reports `encrypted_values` (§3.3); `fields_get` marks a
   related copy of a non-exportable Studio field non-exportable (§3.7).
3. `health_phi_encryption`: the standard `_enc` / `_bidx` columns become `exportable=False` (§3.4).
4. biz_bi: silver view and pipeline clean view carry only analytics material (§3.5).
5. health_pwa: the service-worker script is no longer a translatable term; stale Vietnamese copy removed;
   app 1.21.0 → 1.21.1 with every pin (§3.6).
6. Access proposal document + a facts table from the live databases (§3.8). Server housekeeping (§3.9).
7. Tests 67–80, browser QA 41–48, clone rehearsal, live upgrade on the three DBs, report §8.

**Binding non-goals**
- No key rotation, no change to `phi_crypto.py`, no re-encryption on tenant creation, no change to `biz_tenants`.
- No server-side refusal of exporting the STANDARD `_enc`/`_bidx` columns (dialog + analytics hiding only; a
  hand-made request can still fetch tokens and blind indexes — state this in the report as a residual).
- No change to which roles hold the export right, the Studio gate or the analytics-modeler right: the proposal
  document is for the owner; **do not grant or revoke anything on live**.
- No deactivation of the `demo` login or deletion of the macOS `._*` files on the live tree: report both with
  exact facts (§3.8, §3.9); the owner decides.
- No nurse-app JavaScript change; no new Studio screen or switch; no change to `web/controllers/export.py`.

## 2. Verified plumbing (research 2026-11-03 — re-check lines; do not re-derive)

| # | Fact | Where |
|---|---|---|
| 1 | The wrapper is tracked in the repo and installed at `/usr/local/bin/carejiox-deploy`; the server copy can drift (runbook tells people to `sed -i` it). It builds odoo-bin args at :154-156, runs at :174 with output to `/dev/null`, keeps `rc` at :175; the `-x` block :184-193 runs `odoo-bin shell … --no-http --logfile=/var/log/odoo/odoo-shell.log < $SHELLFILE` with the service DOWN and only when `rc` is 0; the service starts at :195. `run()` only sees variables passed in the `flock bash -c` string :212-214. Default `DB=carejiox` :72. No post-upgrade check exists today | `carejiox-deploy.sh`, `SAAS_RUNBOOK.md:934`, `HANDOVER-CONVENTIONS.md:39-51` |
| 2 | Only the MASTER knows which database is the template: `ir.config_parameter` key `biz_tenants.template_db` (registered as `carejiox_template` by `health_tenancy/models/registrations.py:350-354`). The template itself carries no marker; `biz_tenancy.slug` is empty on BOTH the master and the template | `tenants_common.py:37`, :168-169, :114-125; `tenancy.py:55-57`, :326 |
| 3 | Quieting the template's jobs has existing code: `_template_cron_state` (`SELECT count(*) FROM ir_cron WHERE active`), `_quiet_template`, `template_quiet_now`; the rollout marks health failed when jobs are still on. `biz_tenants.template_active_crons` (:47) records what to re-enable in a tenant (`_step_configure` :760-766) | `rollout_service.py:638-663`, `service.py:2148`, :2168 |
| 4 | Tenant creation from the screen clones with `exp_duplicate_database` → core runs `ir.config_parameter.init(force=True)` → NEW `database.secret` and `database.uuid`. `HEALTH_PHI_KEY` is not set on the box, so every database encrypts with its own secret: a token made on the template is unreadable on every tenant made from it (same for encrypted attachments; the manual `createdb -T` recipe keeps the secret) | `service.py:677`, core `db.py:205-208`, `ir_config_parameter.py:18-57`, §5.172, `SAAS_RUNBOOK.md:195` |
| 5 | `phi_crypto._get_keys` :45-63: `HEALTH_PHI_KEY` env (base64 ≥ 32 bytes) else `database.secret`; HKDF-SHA256; per-process cache by database name. No rotation code anywhere | `phi_crypto.py` |
| 6 | Standard encrypted columns are declared one by one with NO `exportable`/`groups`/`copy`: res.partner :36-48 (`allergies_enc`, `medical_history_enc`, `intake_diagnosis_enc`, `intake_notes_enc`, `healthcare_notes_enc`, `emergency_contact_name_enc`, `emergency_contact_phone_enc`, `emergency_contact_relation_enc`, `emergency_contact_relationship_enc`, `national_id_enc`, `national_id_bidx` Char index, `cccd_number_enc`, `cccd_number_bidx` Char index); health.clinical.note :24-30 (seven `_enc`). The visible fields are compute/inverse pairs (partner :51-101, note :33-65) — **do not add `groups` to the columns** (the computes are not `compute_sudo`; a group would blank the visible fields for non-admins) | `res_partner.py`, `health_clinical_note.py` |
| 7 | biz_bi silver view: `_compile_silver_sql` :439-510 builds an explicit column list (`_bi_row_key` :449-451 + every stored, non-stale `field_ids` row :463-470) and never checks `_not_analytics_material`. Pipeline clean view: `compile_sql` :78-112 starts from `SELECT * FROM <raw table>` (:87, :88-89 returns it as is with no steps; final select :111); `_base_schema` :73-76 drops non-exportable fields from the schema DICT only. `_fetch_schema_pg` :223-238 (used when a pipeline is active, :163-164) has no exportable filter. `_not_analytics_material` :157-169 (sensitive OR source `not exportable`), looked up by `technical_name` | `bi_dataset.py`, `bi_pipeline.py`, `bi_source.py`, `bi_field.py` |
| 8 | Service worker: route `/health_pwa/service-worker.js` `auth='user'` renders `health_pwa.service_worker_js` in the SESSION USER'S language (:396). The template :860-1241 is ONE CDATA text node = one translatable term; `vi_VN.po:26` carries it (msgid = the 1.19.0 script, msgstr = the 1.0.95 script); core carries old translations to a changed term when ≥ 90 % similar (`fields_textual.py:372` `get_close_matches(…, 0.9)`), which is why bumps never cleared it. Registration `?v=${PWA_SW_VERSION}` :379-380. Pins :9, :246, :365, :862, :865 | `pwa.py:392-402`, `pwa_templates.xml`, §5.288 |
| 9 | Core Selection: callable/string selection → `_selection = None` (:113-116, :177); `convert_to_cache` :228-235 returns the value unchecked when `_selection is None`. Every Studio dropdown is callable (`_fs_options`, `ir_model_fields.py:120-121`), so ANY value is accepted on create/write/import today | `fields_selection.py` |
| 10 | `fs.studio.validate_all` :1402-1435 runs for superuser / gate user / system user, re-checks every layout with a `view_id`, switches broken ones off, collects `host._problems()`; returns `{'checked', 'broken': [{layout_id, model, reason}], 'hosts': [{host_id, model, name, problems}]}`. Nothing calls it from data, cron or hook | `fs_studio.py` |
| 11 | `base.group_allow_export` is enforced in core `export_data` (`orm/models.py:889`) and `web/controllers/json.py:69`; defined in `base_groups.xml:61-66`, implied by `group_system`; granted to demo by `res_users_demo.xml:41`. No role in biz_access / health_access grants it; it is NOT on biz_access's forbidden list (`access_common.py:303-306`), so a role MAY grant it. On carejiox only `__system__` and `demo` hold it (§5.295) | core, repo |
| 12 | Studio Base override today: `export_data` + `_fs_unexportable` (:23-59); no `create`/`write`/`fields_get` override yet. `_inherits` related copies drop `exportable` (§5.286) | `base.py` |
| 13 | Pre-existing fails on the full run: 34 (consent-dependent `health_pwa_family` 19, `health_scribe` 15, `health_telehealth` 1), §5.294. Every suite Studio touched is green: Studio + biz_bi + i18n = 201/201 | FS-H4 report |
| 14 | Stale sleeper loops from an FS-H2 session on the box: `bash -c 'while pgrep -f "odoo-bin.*carejiox_fs2…"'` — the pattern matches the loop itself so they never end | FS-H4 report hole 8 |

## 3. Design

### 3.1 Deploy wrapper: post-upgrade check (new) — `.agent/workflows/carejiox-deploy.sh` + `carejiox-postcheck.py`

After a successful `-m`/`-i` upgrade (`rc` = 0) and after any `-x` script, WHILE THE SERVICE IS STILL DOWN, the
wrapper runs `.agent/workflows/carejiox-postcheck.py` through `odoo-bin shell` exactly as the `-x` block does
(same `--no-http`, same `--logfile`). The check file is installed next to the wrapper
(`/usr/local/lib/carejiox/postcheck.py`; the wrapper refers to it by an absolute path and refuses to run with a
clear line if the file is missing). Its stdout is NOT swallowed. It prints, in this order:

```
==> studio: checked <n> layouts, broken <m>, host problems <k>, encrypted values <v>
    broken: <model> layout <id> — <reason>            (one line each, only when m > 0)
    host: <name> — <problem>                          (one line each, only when k > 0)
==> jobs: <a> active (template: switched off <a> → 0)   | ==> jobs: <a> active
```

Rules:
- Studio line: only when `fs.studio` is in the registry; otherwise `==> studio: not installed`. `validate_all()`
  is called as the superuser (`env(user=SUPERUSER_ID)`); the new `encrypted_values` key (§3.3) is printed.
- Template detection is the WRAPPER's job, not the check's: before stopping the service it reads
  `biz_tenants.template_db` from the MASTER (`sudo -u postgres psql -d carejiox -Atc "SELECT value FROM
  ir_config_parameter WHERE key='biz_tenants.template_db'"`); when `$DB` equals that value it passes
  `CAREJIOX_IS_TEMPLATE=1` into the shell's environment. On the template the check quiets the jobs through the
  EXISTING routine (`_quiet_template` / `template_quiet_now`, fact 3 — read their signatures and what they write
  to `template_active_crons`; reuse, do not re-implement; fall back to `UPDATE ir_cron SET active=false` ONLY if
  neither fits a shell context, and say so in the report). On any other database it only prints the count.
- Exit code: the check returns 0 when healthy; **3** when `broken` or `hosts` is non-empty, or when the template
  holds `encrypted_values > 0` (clinics made from it could never read them, fact 4), or when the template still has
  active jobs after quieting. The wrapper prints `==> POSTCHECK FAILED (exit=3) — read the lines above` and
  carries 3 as its own exit code, **but still starts the service** (a switched-off layout is a safe state; a
  stopped clinic is not).
- The check never writes anything except the job quieting; `validate_all` itself already switches a broken layout
  off (fact 10) and that is the intended behaviour.
- Variables: `POSTCHECK` path and `IS_TEMPLATE` must be added to the `flock bash -c` string (fact 1).
- Header comment of the wrapper documents the new lines; `HANDOVER-CONVENTIONS.md` §2 and `SAAS_RUNBOOK.md`
  :316-352 / :424 get three sentences each (what is printed, the exit code 3 meaning, that template jobs are now
  quieted by the wrapper). `FORM_STUDIO_PROGRAM.md` :215-218 and :282 name the real method.
- Install on the box as part of the deploy (§7): `sudo install -m 755 … /usr/local/bin/carejiox-deploy` and the
  check file; keep a copy of the previous wrapper at `/usr/local/bin/carejiox-deploy.pre-fs5` (restored if the
  new one misbehaves). The first live run of the new wrapper IS the deploy of this phase.

### 3.2 Engine: a dropdown refuses a value that is not an option — `biz_form_studio/models/base.py`

Add to the existing Base override:

```python
def _fs_check_selections(self, vals_list):
    """A Studio dropdown reads its options when asked (callable selection), and the
    framework does not check values against a callable list (fact 9). Check them here."""
    for vals in vals_list:
        for name, value in vals.items():
            if not value or not name.startswith(FS_PREFIX):
                continue
            field = self._fields.get(name)
            if field is None or field.type != 'selection' or not field.manual:
                continue
            if value not in [v for v, _label in field.get_values(self.env)]:  # verify the API: get_values / _description_selection
                label = self.env['ir.model.fields'].get_field_string(self._name).get(name) or field.string
                raise UserError(_("\"%(value)s\" is not one of the options of %(field)s.", value=value, field=label))

@api.model_create_multi
def create(self, vals_list):
    self._fs_check_selections(vals_list)
    return super().create(vals_list)

def write(self, vals):
    self._fs_check_selections([vals])
    return super().write(vals)
```

- Cost rule: the loop touches only keys that start with `x_fs_`; on a model without Studio fields it is a
  prefix test per key and nothing else. Measure once on `res.partner` create (report: before/after µs).
- Encrypted dropdowns (the exposed field is the selection; the token is written by the inverse AFTER this check)
  are covered by the same code — test it.
- Imports go through `create` → covered. `load()` surfaces the message in the import screen.
- Vietnamese for the sentence in `biz_form_studio/i18n/vi.po`.
- Ledger entry: callable selections skip validation; Studio checks in Base.

### 3.3 Engine: `validate_all` reports encrypted values — `fs_studio.py`

Add `encrypted_values` to the returned dict: the sum over every `ir.model.fields` row with `fs_companion=True`
of `SELECT count(*) FROM <table> WHERE <enc> IS NOT NULL AND <enc> <> ''` (reuse `_non_empty`, :1193). 0 when
there are no companions. Also add `hosts`-style detail: `encrypted_fields: [{model, name, values}]` so the
wrapper can name them on the template. No UI change; the Studio library already shows "Stored encrypted".

### 3.4 `health_phi_encryption`: the standard encrypted columns leave the export dialog — fields only

Add `exportable=False` to each `_enc` and `_bidx` field declaration in `res_partner.py:36-48` and
`health_clinical_note.py:24-30` (fact 6). Nothing else: no `groups`, no `copy` change, no map change, no hook
change. Version bump; the module's 8 tests and `health_compliance`'s 23 stay green.

Consequences you must prove (tests 70–71): the Clients export dialog no longer lists "… (encrypted)" entries or
the blind-index columns; biz_bi discovery skips them by the FS-H4 generic rule (`_fetch_schema_odoo` :181), and a
rescan of an existing dataset marks the already-catalogued ones `sensitive` (:134-139). Saved export lists that
name them are NOT swept (that sweep is Studio's own, for Studio fields); say so.

### 3.5 biz_bi: the SQL layer carries only analytics material — `bi_dataset.py`, `bi_pipeline.py`, `bi_source.py`

- Silver view (`_compile_silver_sql` :463-470): skip a `field_ids` row when `field._not_analytics_material()`.
  Gold reuses the SQL (`bi_gold.py:62-69`) and so follows.
- Pipeline clean view (`compile_sql` :87 and :111): replace `SELECT *` with an explicit column list = the raw
  table's columns (`information_schema.columns` for the model's `_table`) MINUS every column whose
  `env[model]._fields[name]` is `not exportable`, MINUS every column whose dataset `bi_field` is `sensitive`.
  Columns with no `_fields` entry (orphans) are kept. The final select (:111) uses the same list so a step cannot
  re-add them. The editor preview (:327-328) reads the compiled SQL, so it follows.
- `_fetch_schema_pg` (:223-238): also drop names in `_non_exportable_names` (`bi_dataset.py:180-190`) — belt and
  braces for a clean view built before this change.
- `action_apply` (:251-277) re-creates the view, so an existing pipeline is fixed the next time it is applied;
  add a one-off in the module's `end-migrate` that re-applies every active pipeline and re-creates every silver
  view (count printed to the log). On live there may be zero of each — report the counts.
- One new Vietnamese string at most (if any message is added). Tests in `biz_bi/tests/test_non_exportable.py`
  (extend). Suite gate: ≥ 155 green.

### 3.6 health_pwa: the worker script stops being a translatable term; app 1.21.1

- Wrap the script text node in `views/pwa_templates.xml:860-1241` so it is not collected as a translation term:
  `<t t-translation="off">` around the CDATA (verify in core `ir_ui_view` / QWeb translation collection which
  attribute the 19.0 engine honours — `t-translation="off"` is the documented one; if the 19.0 collector ignores
  it inside `<template>`, use the equivalent the collector honours and note it in the report).
- Remove the stale worker term from `health_pwa/i18n/vi_VN.po` (:26 to about :432) so it is never re-imported.
- After the upgrade, assert on every database that rendering `health_pwa.service_worker_js` for a `vi_VN` user
  returns the same bytes as for `en_US` and contains `CACHE_VERSION = '1.21.1'`. If the stored `arch_db` JSON still
  carries a `vi_VN` copy of the old script after the upgrade (the term is no longer collected but the JSON may
  survive), remove that language key for THAT VIEW ONLY in a migration (`UPDATE ir_ui_view SET arch_db =
  arch_db - 'vi_VN' WHERE id = <view id>`, guarded by the xmlid lookup), and prove the render afterwards.
- Bump 1.21.0 → 1.21.1 in the five pins and in the five co-resident test files (§0 list, incl.
  `health_form_studio/tests/test_fs_health.py:1147-1150`). No app JavaScript changes.
- Ledger: §5.288 gets a "fixed in FS-H5 by …" line (append, do not rewrite history).

### 3.7 Engine: a related copy of a non-exportable Studio field is not offered either — `base.py`

`fields_get` override on Base: for every field in the result whose `self._fields[name].related` resolves (follow
`related_field` as `_fs_unexportable` does, :39-41) to a manual `x_fs_` field with `exportable=False`, set
`exportable: False` in the returned description. Prefix-gate the loop on `x_fs_` names. Prove it on `res.users`
(test 74). This closes FS-H4 D9 for the dialog; the server refusal already exists.

### 3.8 Access proposal (document, no code) — `docs/strategy/access-cleanup-proposal.md`

Written for the owner in plain English (screen words, no code names). From the LIVE databases (read-only
queries on carejiox, carejiox_template, hhh), a table: every role, how many active people hold it, whether it
can open a Client, a Contact, a Booking (facts §5.277/§5.283), whether it holds Form Studio, the export right,
and the Analytics modeler right. Then: the `demo` login — active or not, last login, which rights it holds
(§5.295 says it holds the export right). Then three short options for "who exports" (nobody / Owner only /
Owner + Operations Manager), one recommendation, and what changes on screen for each. Then the Admin role's two
defects as one paragraph with a recommended fix (grant the missing access, or rename the role) — fix NOTHING.
Then the template rule in one paragraph: the golden template must hold no client data at all (identity numbers,
Studio health fields, files), because a clinic made from it cannot read them; the new deploy check reports it.

### 3.9 Server housekeeping (in the deploy step, say exactly what was done)

- Kill the stale FS-H2 sleeper loops (fact 14): list with `ps -eo pid,etime,user,cmd | grep '[c]arejiox_fs2'`,
  confirm each is a `bash -c while pgrep …` loop (never an `odoo-bin` process), kill by PID, show the list is empty
  afterwards. Never `pkill -f odoo-bin`.
- Count and list the macOS `._*` files on the live addons tree (`find /odoo/odoo-server/addons -name '._*'`) in the
  report; delete nothing.
- Report the `hr_skill` NOT NULL warnings once more with the exact tables; fix nothing.

## 4. Safety rails

- The post-check runs ONLY with the service down and ONLY after a successful upgrade; it never raises past its
  own `try` (an exception prints `==> studio: check failed — <error>` and exits 3).
- `_fs_check_selections` raises only `UserError`; it never reads the database for a model without `x_fs_` keys.
- `t-translation="off"` must be proven to leave EVERY other PWA string translated (test 72 checks one existing
  Vietnamese app string still renders in Vietnamese).
- Backups of the three databases before the live upgrade (`/var/backups/fs5/`), `pg_restore -l` readable.
- On live: no field, no layout, no export, no publish, no grant, no deletion of users/files.
- The old wrapper is kept as `carejiox-deploy.pre-fs5`; the report says how to restore it in one line.

## 5. Tests (numbering continues from FS-H4; names as given)

| # | Test | Proves |
|---|---|---|
| 67 | `test_67_the_post_check_on_a_healthy_and_a_broken_system` (clone, shell-level) | healthy DB → lines printed, exit 0; a layout made broken on purpose (rename its anchor field in the base view on the clone) → `broken 1`, the layout switched off, exit 3; the service starts in both cases |
| 68 | `test_68_a_dropdown_refuses_a_value_that_is_not_an_option` | create/write/`load` with a non-option → "… is not one of the options of <label>", `x_fs_` never in the text; an option and `False` pass; the same on an encrypted dropdown (token written only for the good value); Vietnamese message for a VI user |
| 69 | `test_69_validate_all_counts_encrypted_values` | `encrypted_values` 0 with no companions; n after n values on an encrypted field; `encrypted_fields` names model/name/values |
| 70 | `test_70_the_standard_encrypted_columns_are_not_export_material` (health_phi_encryption tests) | `fields_get` → `exportable: False` for all 13 partner + 7 note columns; the visible fields still compute/inverse for a non-admin; the 8 existing tests green |
| 71 | `test_71_the_bi_sql_layer_carries_only_analytics_material` (biz_bi) | pipeline clean view and silver view omit `_enc`/`_bidx` columns and a `sensitive` field; `_fetch_schema_pg` on the clean view lists none; preview lists none; the end-migrate re-applies existing pipelines; suite ≥ 155 green |
| 72 | `test_72_the_worker_script_is_the_same_in_every_language` (health_pwa or health_form_studio HttpCase) | a planted stale `vi_VN` arch copy disappears after the migration; GET `/health_pwa/service-worker.js` as a `vi_VN` user == as `en_US`, contains `1.21.1`; one existing Vietnamese app string still renders in Vietnamese |
| 73 | `test_73_the_nurse_app_version_pins` + co-resident pin tests | five pins 1.21.1; daystrip/scribe/ergo/family/form_studio pin tests pass |
| 74 | `test_74_a_user_does_not_offer_its_contacts_health_field` | `res.users.fields_get` marks the related `x_fs_` copy `exportable: False`; the export dialog's field list for Users omits it; a non-PHI Studio field is still offered |
| 75 | `test_75_the_gates_cover_the_fs_h5_files` + 12a–12f | gates over every changed core file incl. `base.py`; the core still imports no cipher and names no product |
| 76 | `health_phi_encryption` 8 + `health_compliance` 23 + `health_form_studio` 39 + `biz_form_studio` ≥ 76 | unchanged and green |
| 77 | Full run baseline vs after on the clone (no `-u`) | the same 34 pre-existing fails (§5.294) and nothing else |
| 78 | Wrapper end-to-end on the clone | `carejiox-deploy -D carejiox_fs5 -m biz_form_studio` prints the studio and jobs lines and exits 0; `-D carejiox_fs5` with `CAREJIOX_IS_TEMPLATE` forced → jobs quieted and the count printed |
| 79 | Template rule | on a DB flagged as template with one encrypted value → exit 3 and the field named; with 0 → exit 0 |
| 80 | White-label + i18n scan over every new user-visible string (the dropdown message, any biz_bi message) | no product word; Vietnamese present |

## 6. Browser QA (41–48; personas as in FS-H4: Owner, VI Owner, Nurse; backend 1440 + 820 px, app at 390 px)

| # | Step | Expect |
|---|---|---|
| 41 | Clone, Clients → Export dialog, search "encrypted" and "ID" | no "(encrypted)" entries, no blind-index columns; the plain standard fields still listed |
| 42 | Clone, Analytics → a Clients dataset → rescan, builder search "enc" | none of the columns offered; previously catalogued ones shown as sensitive, not deleted |
| 43 | Clone, Analytics → a pipeline on Clients → preview | no `_enc`/`_bidx` columns in the preview table |
| 44 | Clone, Studio dropdown on Client: via the form, pick an option, save (works); via RPC write a wrong value | plain refusal naming the field's label; VI Owner sees Vietnamese |
| 45 | Clone, nurse app as the VI nurse at 390 px | config 1.21.1, worker `?v=1.21.1`, `CACHE_VERSION 1.21.1`, cache `health-pwa-v1.21.1`; EN nurse the same |
| 46 | Clone, Settings → Users → Export dialog | no Studio health field through the contact; a non-PHI Studio field present |
| 47 | Live carejiox.com, temporary Owner: Clients export dialog (open, choose nothing, close); Analytics builder search "enc"; nurse app at 390 px | as 41/42/45 with 1.21.1; no console errors; temp user and traces deleted afterwards as in FS-H4 |
| 48 | Live: the wrapper's own output on the three databases (copy the lines into the report) | studio line with `checked 0 … encrypted values 0`, jobs line `0 active` on the template |

## 7. Deploy and verify (in this order)

1. Clone `carejiox_fs5`; upgrade `biz_form_studio,health_form_studio,biz_bi,health_phi_encryption,health_pwa`
   plus `-i` the five pin-test modules; tests; QA 41–46; test 78/79 against the clone with the NEW wrapper
   installed as a SEPARATE binary first (`/usr/local/bin/carejiox-deploy-fs5`) so the live wrapper is untouched
   until the clone proves it.
2. Backups of the three live databases to `/var/backups/fs5/`.
3. Install the new wrapper + check file (keep `carejiox-deploy.pre-fs5`). Stage modules with `git archive` (0 `._`
   files). `carejiox-deploy -d -m biz_form_studio,health_form_studio,biz_bi,health_phi_encryption,health_pwa -i
   <pin-test modules>` on carejiox → read the post-check lines; then `-D carejiox_template -m …` → the jobs line
   must show the template quieted by the wrapper itself; then `-D hhh -m …`.
4. On all three: versions, `validate_all` (via the wrapper lines), the service-worker render in `vi_VN` ==
   `en_US` with 1.21.1, `/web/login` 200 on carejiox.com and hhh.carejiox.com, 0 layouts / 0 `x_fs_` fields.
5. Housekeeping §3.9. QA 47–48. Remove the clone, tree, units, staging, tunnel; keep the backups.

## 8. Report back (`FORM_STUDIO_FS-H5_REPORT.md`, same shape as FS-H4's)

Owner paragraph in plain words; standing rules stated back; files; tests 67–80 table; biz_bi before/after counts;
QA 41–48 with screenshots in `fs_h5_shots/`; the wrapper's live output verbatim; deviations D1…; drift found;
the access proposal's facts table repeated; pre-existing holes still open (residual: hand-made export of the
standard tokens; attachments on the template; `clear_key_cache` never called); new ledger entries §5.296+;
commits; and a closing section "Form Studio: what is left" listing anything the programme did not do.
