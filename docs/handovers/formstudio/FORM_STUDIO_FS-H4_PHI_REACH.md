# FORM STUDIO — FS-H4: health information reach (exports, reports, nurse app, encryption on Client)

Handover from Fable (design) to Opus (implementation). Written 2026-11-03 after the FS-H3 report.
Read in this order before touching code:

1. `docs/strategy/HANDOVER-CONVENTIONS.md` — §2 deploy, §5 ledger incl. §5.265–§5.284, and the PWA
   entries (§5.178 jobs, the PWA version-bump rule).
2. `FORM_STUDIO_FS-H1_CORE.md` §0 (standing rules), `FS-H2_CLIENT_CONTACT.md` §0, `FS-H3_BOOKING_LISTS.md` §0.
3. The three phase reports (deviations are binding facts).
4. The engine as shipped: `biz_form_studio/models/ir_model_fields.py` (`fs_vis` column :45, `_instanciate_attrs`,
   `_fs_options`), `fs_common.py` (`param_sql`, `vis_group_xmlid` :89-110), `fs_field_meta.py` (`phi` :19, `pwa`,
   `list_ok` :25), `fs_studio.py` (`create_field`, `update_field`, `_apply_*`, `field_references` :925-931,
   `reapply_visibility`, `library`), `fs_host.py`, the editor's settings panel (`studio_editor.js:641`, :786,
   `studio_editor.xml` switches).
5. `health_phi_encryption/models/phi_crypto.py` (whole file, 120 lines) and `models/res_partner.py:15-146`.
6. `health_pwa/controllers/sync.py:329-432` (`_patient_record`, `_fso_record`), `controllers/api.py:437-585`
   (`api_fso_detail`), `static/src/js/app.js` :5025-5218 (client screen), :3629-3715 (booking modal),
   :36-64 (`_t`), `views/pwa_templates.xml` :9, :246, :365, :862, :865 (version pins).
7. `biz_bi/models/bi_source.py:172-206` (`_fetch_schema_odoo`), `bi_dataset.py:123-167` (`action_scan_fields`),
   `:616` (`get_builder_metadata`), `bi_query_engine.py:275-291` (`browse_field`).
8. `web/controllers/export.py` (REPO copy, patched; `exportable` check :396) and core `orm/models.py:880-892`.

## 0. Standing rules (FS-H1_CORE §0 binds in full; the short form)

- White-label: "Odoo" never user-visible. Generic core names no product. Plain copy, `x_fs_` never shown.
- Flat tokens, `ic()` icons, no gradients/emoji/`font-family`. Vietnamese for every new string in both `vi.po`
  **and** in the PWA dictionary (`pwa-utils.js` `vi:` map, :7+) for every new nurse-app string.
- Chatter untouched. Host models get no business-logic change.
- **Shared-module edits sanctioned for this phase, and ONLY these** (each in its own commit, each with its
  version bumped):
  - `biz_bi/models/bi_source.py`, `bi_dataset.py`, `bi_query_engine.py` — the generic "non-exportable fields are
    not BI material" rule (§3.3). The biz_bi suite is a GATE: it must be as green after as before (record the
    before/after counts; 6 historical fails are known — name them if still there).
  - `health_pwa/controllers/sync.py`, `controllers/api.py`, `static/src/js/app.js`, `static/src/js/utils/pwa-utils.js`
    (dictionary only), `views/pwa_templates.xml` (the five version pins only), `__manifest__.py` — the read-only
    "More details" block (§3.4).
  - PWA test pins (tests only): `health_pwa_daystrip/tests/test_daystrip.py:304-308`,
    `health_scribe/tests/test_scribe.py:424-428`, `health_pwa_ergo/tests/test_pwa_ergo.py:20`,
    `health_pwa_family/tests/test_pwa_family.py:420-424` → the new version.
  - Guard tests (tests only, §3.6): `health_crm/tests/test_ws_contact_form.py:284-293`,
    `health_fieldservice/tests/test_ws_client_form.py:287` and `:413-428`.
  - `biz_kit/static/src/js/kit_icons.js` — glyphs only.
  - **Not** `health_phi_encryption` (import its helpers; change nothing there). **Not** `web/controllers/export.py`.
- Rehearse on a clone `carejiox_fs4` (FS-H1 recipe). Never `-t` on the live box. `fs.studio.validate_all`
  after every upgrade on every DB. Suites WITHOUT `-u` after upgrading (§5.275). Template jobs come back ON
  after every upgrade (7, phone module) → switch off and say so.
- Live has 0 layouts and 0 `x_fs_` fields. On live: open Studio and the nurse app only; publish nothing,
  create no field, encrypt nothing.
- Commits on 19.0, plain sentences, each ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  **Do not push.**

## 1. Scope

**Goal.** A Studio field marked **health information** is kept out of exports, out of the analytics
datasets and out of the nurse app on every screen, and on the **Client** record its value is stored
encrypted with the same key and token format the system already uses for the client's identity numbers. A
Studio field with **Show in the nurse app** on appears as a read-only "More details" block on the nurse
app's client screen and booking details. Three stale tests are repaired.

**In scope**
1. Engine: `fs_phi` registry column + `exportable=False`; server-side export refusal; saved-export sweep;
   PWA switch rules; `fs.host.pwa_ok` / `encrypt_ok`; encryption wiring for PHI text fields on encrypt hosts
   (companion column, compute/inverse callables, migrate on switch); honest copy.
2. biz_bi: the generic non-exportable rule (scan, builder metadata, engine).
3. health_pwa: `custom_fields` in the client record, the booking detail API, and the two read-only blocks;
   version bump; stale test pins.
4. Overlay: `pwa_ok` / `encrypt_ok` on the four hosts, vi.po, `HOST_TEXT` additions.
5. Guard tests repaired (own commit).
6. Tests 49–66, browser QA 31–40 (backend + nurse app), clone rehearsal, live upgrade on the three DBs.

**Binding non-goals**
- No encryption on Booking, Contact or Incident custom fields (owner decision: Client only, release 1).
- No encryption of non-text types (date, numbers, money, yes/no, links, files) — they are hidden only;
  the copy says so. Files: state in the report whether manual binary fields are attachments and therefore
  already covered by `health_phi_encryption/models/ir_attachment.py`; do not build anything for it.
- No blind index / no search on encrypted Studio fields (they are never list columns or filters).
- No change to `health_phi_encryption`, no key rotation, no audit model. The `_enc`/`_bidx` columns of the
  standard PHI fields being exportable and BI-visible is a pre-existing hole — **report it, do not fix it**.
- No nurse-app WRITE of custom fields; no offline replay change; no family portal / client portal reach.
- No closing of the biz_bi "silver SQL view includes hidden columns" gap (§2 fact 12) beyond what §3.3
  says; report it for BI hardening.
- No `export_data` filtering of standard fields; only Studio PHI paths.

## 2. Verified plumbing (research 2026-11-03 — re-check lines; do not re-derive)

| # | Fact | Where |
|---|---|---|
| 1 | Only `fs_vis` reaches `_instanciate_attrs` (it is a column on `ir_model_fields`, core does `SELECT *`). `phi`/`pwa`/`list_ok` live on `fs_field_meta` only | `ir_model_fields.py:45`, core `base/models/ir_model.py:1276-1287`, `fs_field_meta.py:18-29` |
| 2 | `exportable` is a Field class attribute (core `orm/fields.py:309`), exposed to `fields_get` via `_description_exportable` (:900); any kwarg passes `Field.__init__` → `_setup_attrs__` (:314-317, :491-499) → `attrs['exportable']=False` from our override is legal and warning-free. Manual fields are built `Field._by_type__[ttype](**attrs)` (core `orm/model_classes.py:580-592`) | core |
| 3 | The export DIALOG drops `exportable=False` fields (REPO `web/controllers/export.py:396-397`; the repo copy is patched vs core — do not edit). Saved lists (`namelist` :437 → `fields_info` :441) do NOT filter. Server `export_data` (core `orm/models.py:880-892`) checks only `group_allow_export`; `_export_rows` never reads `exportable` | export.py, core |
| 4 | `ir.exports.line.name` holds slash paths (`x_fs_foo`, `partner_id/x_fs_foo`); the FS-H1 sweep precedent (`fs_studio.py:925-931`) matches only lists whose `resource` is the field's own model | core `base/models/ir_exports.py` |
| 5 | Other record exports: biz_bi xlsx (`biz_bi/controllers/main.py:24-80`) and the emailed snapshot (`bi_dashboard.py:146-200`) both go through `bi.query.engine.run`; `synconics_bi_dashboard` has its own CSV/Excel (:934, :1040) from `ir.model.fields` rows — check whether it is installed on any of the three DBs; no spreadsheet module in the repo | research A4-A5 |
| 6 | biz_bi discovery `_fetch_schema_odoo` (`bi_source.py:172-206`) keeps `store=True` fields with a real column, skips binary/reference/m2m/o2m/json/properties; checks NO `groups`/`exportable`/PHI. `action_scan_fields` (`bi_dataset.py:123-167`) excludes only `SKIP_FIELDS` (:14-28); default visibility 'visible' except id-like (:157) | biz_bi |
| 7 | Governance that exists: `bi.field.visibility` visible/hidden/sensitive (`bi_field.py:82-88`) honoured by `get_builder_metadata` (:616), modeler (:650), AI card (:734), publish (:529-531); access-rule masks (`bi_access_rule.py:84-98`) | biz_bi |
| 8 | Engine gap: `browse_field` (`bi_query_engine.py:284-291`) checks only existence/dataset/mask → a hidden field is queryable by id. Engine runs raw SQL (`_execute` :860-876) → field `groups` never protect BI readers | biz_bi |
| 9 | PWA sync: `_patient_record(self, patient)` :329-358 and `_fso_record(self, order)` :395-432 run on `.sudo()` after `_sync_scope` (:108-178); keys listed in research C9; delta = `write_date >= since` or `create_date >= since` (:375-377, :452-456); no version field; a new key reaches cached records only when they change, are in the 30-day fallback window, or re-pulled via a changed in-scope order (:383) | `health_pwa/controllers/sync.py` |
| 10 | PWA client store = PouchDB (`app.js:206-213`), schemaless; `updateLocalData` stores `{...record}` (`sync-manager.js:383-423`) → new keys need no schema change. One-time purge precedent `health_pwa_scope_v` (`sync-manager.js:240-277`) | health_pwa |
| 11 | The booking modal does NOT read `_fso_record`; it GETs `/health_pwa/api/fso/<id>` (`fetchBookingDetail` `app.js:1770-1799`; server `api_fso_detail` `api.py:437-585`, sudo after `_can_access_order_detail` :65-92). Only the client screen (`patient-detail-view` `app.js:5025`, loads PouchDB :5040-5041) reads `_patient_record` | health_pwa |
| 12 | Read-only blocks to clone: client screen `div.info-section` "Medical Information" `app.js:5204-5218` (h3 + `.info-grid` + `.info-item` label/span); booking modal `.detail-section`/`.detail-row` :3674-3715 ("Scheduled Visit", "Contact Information") | app.js |
| 13 | PWA `_t` (`app.js:36-64`, exposed :888) → `PWAUtils.i18n.t` (`pwa-utils.js:6`, dictionary `vi:` :7+, `t()` :958-964) → `APP_VI_FALLBACK_TRANSLATIONS` (`app.js:3-32`) → `odoo._t`. The server l10n preload (`controllers/pwa.py:34-48`, :247-263) searches a table that does not exist in Odoo 19 and always falls to its `fallback_map` | health_pwa |
| 14 | PWA version pins: `pwa_templates.xml` :9 `pwa_asset_version` 1.20.2; :246 `version: '1.20.2'`; :365 `PWA_SW_VERSION`; :862 comment; :865 `CACHE_VERSION`. `__manifest__.py:4` 19.0.1.0.41. `static/manifest.json` has NO version. Test pins at **1.20.0 (already stale)** in the four files named in §0; `health_telehealth/tests/test_telehealth.py:443+` reads the current version | health_pwa + co-residents |
| 15 | PWA write-back is whitelisted (`sync.py:995-1001` orders; :1064-1068 patients); replay types `KNOWN_ACTION_TYPES = ('start_service','save_clinical_notes')` (:15) — a read-only block touches none of it | sync.py |
| 16 | Sync access = any internal user with partner read (`_check_sync_access` :51-60); no PWA group. Studio "Staff" = `health_base.group_healthcare_base`; "Admins" = `health_access.group_clinic_admin` (`health_form_studio/data/fs_parameters.xml`) | — |
| 17 | Crypto helpers are MODULE-LEVEL and reusable: `phi_crypto.encrypt(env, plaintext)` :77 (idempotent, falsy passthrough), `decrypt(env, token)` :88 (non-token passthrough, `DECRYPT_ERROR_MARKER` :34 on failure), `is_encrypted` :73, `blind_index` :110, `_get_keys` :45-63 (env `HEALTH_PHI_KEY` or `database.secret`, HKDF). Token `enc$1$` + base64(nonce‖ct‖tag). Imported elsewhere as `from odoo.addons.health_phi_encryption.models import phi_crypto` (`health_compliance/models/protections.py:7`) | `health_phi_encryption/models/phi_crypto.py` |
| 18 | The partner pattern: exposed field = non-stored `compute='_compute_phi_fields', inverse='_inverse_phi_fields'` (:51-86), `_enc` = `fields.Text` (:36-47), compute decrypts `self[enc]` (:89-93), inverse encrypts (:95-101). Same pattern copy-pasted in `health_clinical_note.py:7-65`. No mixin, no Field subclass | `health_phi_encryption/models/res_partner.py` |
| 19 | Manual fields: core `_instanciate_attrs` sets `store`, `readonly` from the row (:1295-1306) and `compute` only from the row's text (:1360-1361); never `inverse`. BUT `compute`/`inverse` are typed `str | Callable` (core `orm/fields.py:285`, :288); `determine()` (:66-86) runs callables; `_compute_field_value` → `determine(field.compute, self)` (core `orm/models.py:4960-4961`); inverse via `determine_inverse` (fields.py :1923-1925) from write (models.py :4405-4425, :4496-4507). Depends for a callable compute come from `func._depends` (fields.py :584-596) or `attrs['depends']` (:463-464, :563-565). A failing manual field is SKIPPED with a log, never raises (`model_classes.py:519-526`, :585-592). `setup_regular_full` does not exist in 19 (`Field.setup` → `setup_nonrelated`, :526-557) | core |
| 20 | `health_phi_encryption` tests: `tests/test_phi_encryption.py` (6 tests) — must stay green. Compliance audit of partner read/write lives in `health_compliance/models/protections.py:28-58` (untouched) | — |
| 21 | Guard tests: `health_crm/tests/test_ws_contact_form.py:293` `assertNotIn('t-inherit="health_crm.CrmContactFormView"', …)` inside a walk :284-292 (tripped by `health_form_studio/static/src/xml/ws_header_contact.xml:18`); `health_fieldservice/tests/test_ws_client_form.py:428` `assertEqual(hooked, 0)` with `hooked` counted :413-418 (tripped by `ws_header_client.xml:18`; class check :419-421 passes); `test_05_workspace_skeleton` :287 expects the rail's first widget `ws_client_shortcuts` but the arch now starts with `ws_rail_fold` (`ops_client_profile_form_views.xml:601`, shortcuts :604) | tests |

## 3. Architecture

### 3.1 Registry flags (core)
`ir.model.fields` gains `fs_phi = fields.Boolean()` and `fs_companion = fields.Boolean()` beside `fs_vis`.
`create_field` / `update_field` keep `fs_phi` equal to `meta.phi` (one write, as `fs_vis` is handled; writing the
row triggers the registry rebuild FS-H1 already pays). `_instanciate_attrs`:
- `fs_phi` or `fs_companion` → `attrs['exportable'] = False`.
- `fs_companion` → `attrs['groups'] = <admin gate xmlid>` (via `vis_group_xmlid(cr, 'admin')`) so no form,
  list or `fields_get` of a non-admin ever carries the ciphertext column; it is never placed in a layout
  (the writer refuses names ending `_enc`; the schematic, library and `_field_info` skip `fs_companion` rows).
`reapply_visibility` becomes `reapply_flags` (keeps the old name as an alias) and re-syncs `fs_vis` and
`fs_phi` from meta for every Studio field.

### 3.2 Export reach (core)
- Dialog: automatic via `exportable=False` (fact 3).
- Server: `biz_form_studio/models/base.py` — `_inherit = 'base'`, override `export_data(fields_to_export, …)`:
  resolve each path segment by segment through `_fields`/`comodel_name`; if any segment is a Studio field
  whose `ir.model.fields` row has `fs_phi` or `fs_companion`, raise `UserError(_("Health information cannot be
  exported: %s", ", ".join(labels)))`. Labels are the fields' `string`s, never `x_fs_` names. Cost: one dict walk
  per export call.
- Sweep on PHI switch-on (`update_field` when `phi` goes False→True): find `ir.exports.line` rows on ANY
  resource whose path's last segment is the field name AND whose path resolves to this model (walk as above);
  unlink them; chatter line on the layout "Removed from N saved export lists: <list names>". The FS-H1 blocker
  (`field_references` kind `export`) stays for deletion.
- `synconics_bi_dashboard`: if installed on a DB, report it as an unguarded export path (its columns are
  `ir.model.fields` rows chosen by an admin); do not change it.

### 3.3 Analytics reach (biz_bi, sanctioned, own commit) — one generic rule
"A field the product marked non-exportable is not analytics material."
- `_fetch_schema_odoo`: skip fields with `exportable is False` (beside the existing type/store checks).
- `action_scan_fields`: on rescan, an existing `bi.field` whose model field is now non-exportable is set
  `visibility='sensitive'` (never deleted; saved charts keep their references).
- `get_builder_metadata`, the modeler and the AI card: already hide 'sensitive'.
- `browse_field` (`_resolve_request`): refuse a field whose live model field is non-exportable, or whose
  `visibility == 'sensitive'`, with `UserError(_("This field is not available to analytics."))` — for admins too.
- Leave the silver SQL view and pipeline `SELECT *` as they are (report as BI-hardening follow-up).
- Because Studio PHI fields on encrypt hosts are NON-STORED (3.5), they never reach discovery anyway; on the
  other three hosts they are stored and rely on this rule. Companion columns are stored text → excluded by
  this rule. Test 55 covers both.
- Run the whole biz_bi suite before and after; counts in the report.

### 3.4 Nurse app (health_pwa, sanctioned, own commit)
**Rules (core, `fs.field.meta`):** `pwa` may be True only when `phi` is False AND `vis != 'admin'` AND the host
has `pwa_ok`. Forced off otherwise, with reasons: "Health information never reaches the nurse app." /
"Admins-only fields cannot show in the nurse app." / "This screen is not in the nurse app." (Switch disabled in
the editor with the reason, as `list_ok` is.)

**Payload (core helper, product-agnostic):** `fs.studio.app_fields(model, records)` → `{record_id: [{name, label,
value, type}]}` for fields with `pwa=True` (re-checked against the rules at call time), values FORMATTED for
display in the caller's language: selection → option label; many2one → display_name; date/datetime → the
user's format (tz applied for datetime); monetary → amount formatted with the record's currency symbol;
boolean → "Yes"/"No" translated; char/text as is; binary → skipped. `label` = the field's translated `string`.
Runs with the caller's env (sync is sudo — the rules above are what gate it, not groups).

**health_pwa:**
- `_patient_record` adds `custom_fields: [...]` (via `app_fields` if `'fs.studio' in request.env` else `[]`);
  `_fso_record` adds the same; `api_fso_detail` adds `custom_fields` to its response.
- Client screen: a new `div.info-section` "More details" after "Medical Information", rendered only when
  `patient.custom_fields?.length`, one `.info-item` per entry (label/span), text values wrap, long text keeps
  newlines (`white-space: pre-line` via an existing utility class or one new rule in the PWA's own scss).
- Booking modal: a new `.detail-section` "More details" after "Contact Information", same shape, from the
  API response.
- Strings: "More details" / "Chi tiết thêm", "Yes"/"No" come from the server already translated; add the
  section title to `pwa-utils.js` `vi:` map and to `APP_VI_FALLBACK_TRANSLATIONS`.
- Version: 1.20.2 → **1.21.0** in all five places (fact 14); `__manifest__.py` → 19.0.1.1.0; the four stale test
  pins → 1.21.0.
- Delta honesty: existing cached clients show the block after they next change or after the app's next full
  pull; new bookings' details are fetched live so they show at once. Say this in the report and in the
  switch's help text ("Appears in the app for records synced after you publish.").

### 3.5 Encryption on Client (core + overlay data)
**Host flag:** `fs.host.encrypt_ok` (Boolean). Overlay: True for Client only. `fs.host.pwa_ok`: True for Client
and Booking; False for Contact and Incident.

**Which fields:** `phi=True` AND host `encrypt_ok` AND `ttype in ('char', 'text', 'selection')` →
**encrypted**. Everything else with `phi=True` → hidden only. The PHI switch's help text says which applies:
"Stored encrypted" badge (Client, text types) or "Hidden from lists, exports, analytics and the nurse app. Not
encrypted on this screen." The field-library row shows the badge too.

**Shape (mirrors fact 18 exactly, with manual fields):**
- Exposed field `x_fs_<name>`: `ir.model.fields` row with `store=False`, `readonly=False`, `fs_phi=True`.
- Companion `x_fs_<name>_enc`: row `ttype='text'`, `store=True`, `fs_companion=True`, `fs_phi=True`.
- `_instanciate_attrs` for the exposed field (when `fs_phi` and a companion row exists for `<model>`,
  `<name>_enc` — look it up by SQL on `ir_model_fields`):
  ```python
  enc = name + '_enc'
  def _compute(recs):
      for rec in recs:
          rec[name] = phi_crypto.decrypt(rec.env, rec[enc])
  def _inverse(recs):
      for rec in recs:
          rec[enc] = phi_crypto.encrypt(rec.env, rec[name]) if rec[name] else False
  attrs.update(compute=_compute, inverse=_inverse, store=False, readonly=False, depends=(enc,))
  ```
  Import `phi_crypto` lazily inside the branch and ONLY if `health_phi_encryption` is in the registry
  (`'health_phi_encryption' in self.env.registry._init_modules` or a module-state SQL check); otherwise leave the
  field stored and plain and log a warning — the core is generic, the overlay guarantees the module is present
  (test 57 asserts it on the three DBs' module list). For `selection`, the exposed field keeps its callable
  options (`_fs_options`) and the companion stores the encrypted CODE.
- **Why non-stored + companion, not in-place:** every ORM read path (`web_read`, `_read_format`, `read`,
  `search_read`, mail tracking, exports) goes through the compute, and the plaintext never has a column.

**Switching PHI on for an EXISTING stored text field on an encrypt host (`update_field`, in ONE transaction):**
1. Count non-empty values `n`.
2. Create the companion row (registry rebuild).
3. SQL: `UPDATE <table> SET <enc_col> = ... ` cannot encrypt in SQL → ORM loop in batches of 500:
   `rec[enc] = encrypt(rec[name_plain])` reading the plaintext column by SQL (`SELECT id, <col> FROM <table>
   WHERE <col> IS NOT NULL`), writing via `sudo()` with `tracking_disable`.
4. Flip the exposed row to `store=False` (registry rebuild).
5. **Drop the plaintext column explicitly** (`ALTER TABLE <table> DROP COLUMN IF EXISTS <col>`) — core keeps
   orphan columns; the promise "no plaintext at rest" requires this. Then assert: count of non-empty
   companions == `n`; otherwise raise and roll back everything.
6. Chatter: "Now stored encrypted (n values converted)."
Switching PHI off (decrypt back) is the mirror: create plaintext column by flipping `store=True` (registry
rebuild creates it), copy `decrypt(enc)` in batches, drop the companion row (its column goes with
`ir.model.fields.unlink` of a manual field — verify; else drop explicitly), count check, chatter.
A field CREATED with `phi=True` on an encrypt host is created directly in the encrypted shape (no migration).

**Deletion** of an encrypted field (`delete_field`): the FS-H1 flow plus the companion row; the "values" count
shown in the DELETE sheet counts non-empty companions.

**Type change** is still refused (FS-H1 7b). **Layout writer**: the exposed field is placed as any field;
`required="1"` works (non-stored compute with inverse is writable).

**Tests must prove at rest:** raw `SELECT` of the companion shows `enc$1$…` tokens and the plaintext column is
absent; ORM read returns the plaintext; a tampered token reads as the marker; `_export_rows` as an admin refuses
the path (3.2); `fields_get` of a nurse has no companion; BI discovery skips both.

### 3.6 Guard tests repaired (tests only, own commit)
- `health_crm…test_05` :284-293 and `health_fieldservice…test_07` :413-428: the walk may count files under
  `health_form_studio/static/src/xml/` as the ONE sanctioned extender each (assert exactly that file set and
  that it anchors only on classes that exist — keep :419-421), everything else still forbidden.
- `health_fieldservice…test_05_workspace_skeleton` :287: expect `ws_rail_fold` first and `ws_client_shortcuts`
  second (matches the arch since the WS-2 fold work).
Commit message: "Client and Contact screen guard tests: allow the Form Studio top-bar button and the rail fold".

### 3.7 Copy (EN → VI)
Switch help texts and badges above; publish-sheet lines: "Now stored encrypted: {field}", "Now in the nurse
app: {field}", "Removed from the nurse app: {field}"; export refusal; BI refusal. Settings tile text unchanged.

Bumps: `biz_form_studio` 19.0.1.3.0, `health_form_studio` 19.0.1.3.0, `biz_bi` patch, `health_pwa` 19.0.1.1.0,
`health_crm` / `health_fieldservice` patch (tests only — still bump).

## 4. Safety rails
- The encryption migration is ONE transaction with a count assertion at the end; any mismatch rolls back and
  the field stays as it was. Never run it on live in this phase (no fields exist there).
- Companion columns never appear in a layout, list, export, BI, PWA or the schematic; test 58 greps the
  generated arches and payloads for `_enc`.
- `export_data` refusal names labels, never `x_fs_` names.
- biz_bi: never delete a `bi.field`; the engine refusal is a `UserError` with plain text.
- PWA: the block renders nothing when `custom_fields` is missing (old cached records) — no `undefined` on
  screen; the service worker cache name changes with the version so stale JS is not served.
- Rollback of a layout never changes PHI flags (flags live on meta, not on sections).
- If `health_phi_encryption` is not installed on a DB, `encrypt_ok` hosts must refuse the PHI switch with
  "Encryption is not available on this system." (test 57).

## 5. Tests (numbered; core `test_fs_core.py`, overlay `test_fs_health.py`, biz_bi `biz_bi/tests/`, pwa `health_pwa/tests/`)

Core:
- **49** `fs_phi` mirrors `meta.phi` on create and on update; `fields_get` of the field says `exportable: False`;
  switching PHI off restores `exportable: True`.
- **50** `export_data` as an admin with a PHI path (`x_fs_a`) and a related path (`partner_id/x_fs_a` from another
  model) raises naming the label; a non-PHI Studio path exports normally.
- **51** Saved-export sweep: lines `x_fs_a` on the own model and `partner_id/x_fs_a` on another model are removed
  when PHI switches on; unrelated lines stay; the layout's chatter names the lists.
- **52** PWA switch rules: PHI → forced off (reason); `vis='admin'` → forced off (reason); host `pwa_ok=False` →
  forced off (reason); staff/all on a `pwa_ok` host → allowed. `app_fields` formats selection label, m2o name,
  date, datetime (tz), monetary, boolean, skips binary, and re-applies the rules at call time (a field whose
  `vis` became admin after the switch is dropped).
- **53** Encrypt shape on a `pwa_ok`/`encrypt_ok` test host (generic model with `health_phi_encryption` installed in
  the test DB — the clone has it): create a char field with `phi=True` → two `ir.model.fields` rows (exposed
  `store=False`, companion text `fs_companion`), the table has the `_enc` column and NO plain column; write
  "Hello" → raw SQL shows an `enc$1$` token; ORM read returns "Hello"; `with_context(lang='vi_VN')` same; a
  selection PHI field round-trips its code and its label.
- **54** Migration on: a stored char with 7 values of 10 records → switch PHI on → 7 tokens, plain column gone,
  reads unchanged, chatter "7 values converted". Migration off mirrors it. A forced mismatch (monkeypatch the
  count) rolls everything back and leaves the field stored and plain.
- **55** biz_bi (in `biz_bi/tests/`, generic): a model field with `exportable=False` is skipped by
  `_fetch_schema_odoo`; a rescan marks an existing `bi.field` for it 'sensitive'; `get_builder_metadata` hides it;
  a request naming its id is refused for an admin too; the whole biz_bi suite count before == after (minus
  nothing).
- **56** Delete an encrypted field: the DELETE sheet count equals the companion non-empty count; both rows and
  the `_enc` column are gone after deletion; history/layout republished without it.
- **57** Without `health_phi_encryption` (simulate by patching the availability check): the PHI switch on an
  `encrypt_ok` host is refused with the plain message; on a non-encrypt host PHI switches on as hidden-only.
- **58** Hygiene: no generated form arch, list arch, `get_studio` payload, `library()` row or `app_fields` output
  contains a name ending `_enc`; `fields_get` as a nurse has no companion; the writer refuses placing one.
- **59** Source gates 12a–12f over the new files; the PWA JS additions contain no product words beyond what the
  PWA already uses and no "Odoo".

Overlay / PWA:
- **60** Hosts: `encrypt_ok` True only on Client; `pwa_ok` True on Client and Booking; `health_phi_encryption`
  installed; every new `HOST_TEXT` string has VI.
- **61** End to end on Client as the Owner: "Allergy notes" (text, PHI) → encrypted shape; "Preferred language"
  (dropdown, nurse app on) → appears in `_patient_record(...)['custom_fields']` with the VI option label when the
  sync user's lang is vi_VN; the PHI field does NOT appear; `export_data` on the client with the PHI path refuses.
- **62** End to end on Booking: "Key safe code" (char, PHI) → hidden-only (stored plain, `exportable False`, no
  column, not in `_fso_record`/`api_fso_detail`); "Parking instructions" (text, nurse app on, Staff) → present in
  both payloads with the label; an Admins-only field cannot be switched on for the app.
- **63 (HttpCase)** As a nurse over `/health_pwa/sync/...` (the real routes): the client payload carries
  `custom_fields` with the allowed field only; `GET /health_pwa/api/fso/<id>` carries the booking's; the PHI
  fields are absent from both.
- **64** PWA version: the five pins equal 1.21.0; `health_telehealth`'s version test passes; the four co-resident
  pin tests pass at 1.21.0.
- **65** Guard tests (3.6) pass; `test_05_workspace_skeleton` passes.
- **66** `health_phi_encryption` suite (6 tests) and `health_compliance` suite unchanged and green.
- Full suites without `-u` after upgrade: biz_form_studio, health_form_studio, biz_bi, health_pwa, health_pwa_*
  co-residents, health_scribe, health_telehealth, health_phi_encryption, health_compliance, health_incident,
  health_fieldservice, health_crm, biz_access, biz_kit, health_base i18n. Green is the gate.

## 6. Browser QA (clone; Owner, VI Owner, Nurse; backend at 1440/820, nurse app at 390 px in a phone emulation)

- **31** Client → Studio: PHI switch on a new text field shows the "Stored encrypted" badge and help; on Booking the
  same switch shows the "hidden, not encrypted" help. Nurse-app switch disabled with its reason on a PHI field
  and on an Admins-only field; enabled on a Staff field.
- **32** Publish on Client: the encrypted field saves and re-opens with the value; psql on the clone shows the
  token and no plain column; the field is absent from the Clients list column chooser and from the export dialog;
  a saved export list that named it was cleaned (chatter line).
- **33** Export dialog on Clients: PHI field absent; a non-PHI Studio field present and exports to xlsx with its
  label. Server refusal: craft an `export_data` call with the PHI path → plain error text.
- **34** Analytics: rescan the Clients dataset → the PHI field is not listed; the companion is not listed; the
  builder cannot pick either; a Studio non-PHI stored field IS listed.
- **35** Nurse app (nurse persona, phone size): sign in, full pull, open a client that has "Preferred language"
  set → "More details" block with label and value; a client with no custom values shows no block; Vietnamese app
  language shows the VI label and VI option.
- **36** Nurse app booking details: "More details" with "Parking instructions"; PHI "Key safe code" absent; the
  booking's other sections unchanged (pixel-compare one booking before/after with no custom values: 0 px diff).
- **37** Service worker: version string 1.21.0 in the app's About/debug or the SW scope; old cache names gone after
  reload.
- **38** Nurse persona in the backend: `fields_get`/form of a client shows neither the companion nor the PHI field
  when `vis=admin`; shows the PHI field when `vis=staff` (encrypted at rest, visible to staff on screen).
- **39** 820 px backend: settings panel with the new badges and reasons does not overflow.
- **40** Live (after upgrade, open-only): Studio on a Client shows the PHI switch help with the encrypted badge
  text; the nurse app loads at 1.21.0 on carejiox.com with no console error; nothing saved.
- Console clean. PNGs to `docs/handovers/formstudio/fs_h4_shots/`.

## 7. Deploy
1. Clone `carejiox` → `carejiox_fs4`. `-u biz_form_studio,health_form_studio,biz_bi,health_pwa,health_crm,health_fieldservice`
   plus the co-resident test modules if they need a bump; suites without `-u`; QA; `validate_all`.
2. Backups `/var/backups/fs4/` for all three.
3. Live: `carejiox-deploy -d` (every changed module) then `-m` of the same list on `carejiox`, `-D carejiox_template …`,
   `-D hhh …`; exit 0 and `/web/login` 200 each; `/health_pwa` loads with the new version; `validate_all` on each;
   template jobs OFF again; bundle serves the new symbols; `synconics_bi_dashboard` installed? (report).
4. Destroy the clone and every transient.

## 8. Report back (`docs/handovers/formstudio/FORM_STUDIO_FS-H4_REPORT.md`)
Owner paragraph; rules restated; tests 49–66; QA 31–40 with PNGs; biz_bi suite counts before/after; deploy log;
deviations D1…; plumbing drift; the pre-existing holes found (standard `_enc`/`_bidx` exportable and BI-visible;
`synconics` export path; silver view hidden columns; PWA l10n preload dead); new ledger entries §5.285+; what
FS-H5 (hardening: validator in deploy, callable-selection write check, tenant/template behaviour, access
clean-up proposal) needs. Commit: engine+overlay, biz_bi, health_pwa (+pins), guard tests, report — separately.
Do not push.
