# FORM STUDIO — FS-H4 report (health information reach: exports, analytics, the nurse app, encryption on the Client)

Written 2026-11-03 by the Opus implementer. Handover: `FORM_STUDIO_FS-H4_PHI_REACH.md`.

## In one paragraph (for the owner)

A field you mark as **Health information** in Studio now stays inside the system: it is no longer
offered when someone exports a list, the system refuses any export that names it (with a plain
message naming the field), it is taken out of saved export lists the moment you mark it, the
reporting screens (Analytics) neither offer it nor answer questions about it, and it never reaches
the nurse app. On the **Client** record, a text field marked Health information is also **stored
encrypted**, with the same key and the same protection the client's identity numbers already
have; the screen shows a green "Stored encrypted" badge before you switch it on. On Booking,
Contact and Incident it is hidden in all those places but not encrypted, and the screen says so.
A new switch **Nurse app** puts a field on the nurse app's client screen and booking details, in
a read-only **More details** block, once the field is on the published screen; it can never be
switched on for health information or for an Admins-only field. Fixing along the way: the nurse
app's client screen was blank for any client with bookings (an older fault) and now draws. All
of this is **live on carejiox, the golden template and hhh**; on the live systems nothing was
published, no field was created and nothing was encrypted. Two things you should know: (1) on
today's system **no clinic user can export lists at all** (only the platform's built-in accounts
hold the export right), and (2) Vietnamese-language nurses run a very old copy of the app's
offline helper (it never updates with new versions); neither was changed here — details under
"Pre-existing holes".

## Standing rules (stated back)

- **White-label:** no "Odoo" in anything a user sees. Core sources and both catalogues scanned by
  12a/16 (re-run over the FS-H4 files, test 59); the nurse-app additions scanned by test 64; every
  new sentence checked by hand.
- **Generic core:** `biz_form_studio` names no product, no `health_`, no clinic/nurse/patient. The
  cipher is a hook the overlay fills (`ir.model.fields._fs_cipher`); "nurse app" sentences come
  from the overlay (`fs.host._app_words`).
- **Plain copy;** `x_fs_` names never shown — the export refusal names labels (test 50).
- **Design:** flat `--bzk-*` tokens (badge on `--bzk-green-soft`), `ic()` icons (`lock`,
  `smartphone`, already in the registry — `kit_icons.js` not touched), no gradient/emoji/
  `font-family`. The nurse-app block follows the app's own section pattern (its `material-icons`).
- **Vietnamese** for every new string: both Studio `vi.po` regenerated from `odoo-bin i18n export`
  on the clone and filled (biz_form_studio 359 entries, health_form_studio 65, none empty), biz_bi
  one entry, nurse app "More details" → "Chi tiết thêm" in `pwa-utils.js` and the app's fallback map.
- **Chatter untouched; host models untouched.**
- **Shared-module edits:** biz_bi (own commit), health_pwa + four pin tests (own commit), the
  three guard tests (own commit). Deviations from the exact file list are D10–D13.
- **Rehearsed on `carejiox_fs4`** (slug → `nowhere_fs4_1`, 107 jobs off, mail servers off, new
  `database.uuid`, private tree `/odoo/fs4/addons` first on the path, `--db-filter=^carejiox_fs4$`,
  `systemd-run`, tests on 8189 / QA web on 8199). Never `-t` on the live box. Suites run without
  `-u` after upgrading. `validate_all` after every upgrade on every database.
- **Live:** Studio and the nurse app opened only; nothing published, no field, nothing encrypted
  (0 layouts, 0 drafts, 0 `x_fs_` fields on all three afterwards).
- **Commits** on 19.0, plain sentences, not pushed.

## Files

`addons/biz_form_studio/` (→ 19.0.1.3.0)
- `models/ir_model_fields.py` — `fs_phi`, `fs_companion`, `_fs_cipher()` hook; `_instanciate_attrs`
  sets `exportable=False` on health fields and token columns, admins-only `groups` on token
  columns, and builds an encrypted field as compute/inverse over its token column
  (`compute_sudo=True`, D5).
- `models/base.py` (new) — `export_data` refuses any path reaching a Studio field that may not be
  exported, following related copies (D9).
- `models/fs_common.py` — `ENC_TYPES`, `ENC_SUFFIX`.
- `models/fs_host.py` — `pwa_ok`, `encrypt_ok`, `APP_WORDS` + `_app_words()` / `_app_text()` /
  `_pwa_reason()`.
- `models/fs_field_meta.py` — nurse-app rules forced on create/write, constraint `_check_pwa`.
- `models/fs_studio.py` — encrypted create, switch on/off conversion (`_encrypt_field`,
  `_decrypt_field`, one savepoint, count check, `_resetup` on failure), export-list sweep,
  `_value_count` for encrypted fields (references, delete sheet, option removal), delete of field
  + token column, `app_fields()` (private), `reapply_flags()`, payload keys (`pwa_reason`,
  `encrypted`, host `pwa_ok` / `encrypt_ok` / `encrypt_available` / `enc_types` / `words`).
- `models/fs_layout.py` — the writer refuses a token column.
- `migrations/19.0.1.3.0/end-migrate.py` — re-applies the flags (no-op on live: 0 fields).
- `static/src/js/studio/studio_editor.js`, `xml/studio/studio_editor.xml`, `scss/studio.scss`,
  `xml/library.xml` — badge, help, disabled switches with reasons, publish-sheet lines, chip lock.
- `i18n/vi.po`, `tests/test_fs_core.py` (49–54, 56–59).

`addons/health_form_studio/` (→ 19.0.1.3.0, depends now also on `health_phi_encryption` —
installed on all three databases, checked) — `models/ir_model_fields.py` (new: the cipher =
`phi_crypto.encrypt/decrypt/DECRYPT_ERROR_MARKER`), `models/fs_host.py` (`APP_WORDS` in the
clinic's words), `data/fs_hosts.xml` (Client: app + encrypted; Booking: app; Contact, Incident:
neither), `hooks.py`, `i18n/vi.po`, `tests/test_fs_health.py` (60–64).

`addons/biz_bi/` (→ 19.0.1.7.2) — `models/bi_source.py`, `bi_dataset.py`, `bi_query_engine.py`,
`bi_field.py` (D10), `i18n/vi_VN.po`, `tests/test_non_exportable.py` (55, 55b).

`addons/health_pwa/` (→ 19.0.1.1.0, app 1.21.0) — `controllers/sync.py`, `controllers/api.py`,
`static/src/js/app.js`, `static/src/js/utils/pwa-utils.js` (dictionary), `views/pwa_templates.xml`
(five pins). Pin tests: `health_pwa_daystrip`, `health_scribe`, `health_pwa_ergo`, `health_pwa_family`.

`addons/health_crm/` (→ 19.0.1.12.5), `addons/health_fieldservice/` (→ 19.0.2.12.5) — tests only.

## Tests (§5)

Final run on the clone after the last upgrade, no `-u`: **648 tests, 2 failed, 32 errors — all 34
pre-existing** (below); 0 `setUpClass` errors; the HttpCases started (63 ran in full; 44's tour is
skipped by the framework, §5.284). Per module: biz_access 312, biz_bi 155, biz_form_studio 76,
biz_kit 18, health_base i18n 9, health_compliance 23, health_crm 17, health_fieldservice 42,
health_form_studio 39, health_incident 22, health_phi_encryption 8, health_pwa 86,
health_pwa_daystrip 25, health_pwa_ergo 5, health_pwa_family 29, health_scribe 34,
health_telehealth 38. Every suite FS-H4 touched is green: Studio + biz_bi + i18n alone
`0 failed, 0 error(s) of 201`.

| # | Test | Result | What it proves |
|---|---|---|---|
| 49 | `test_49_health_information_is_not_export_material` | PASS | `fs_phi` follows the setting on create and update; `fields_get` → `exportable: False`, back to `True` when switched off |
| 50 | `test_50_the_server_refuses_to_export_health_information` | PASS | `export_data` with `x_fs_a`, with `partner_id/x_fs_a` from Users, and with the user's own related copy → "Health information cannot be exported: Allergy flag", no `x_fs_` in the text; a non-health Studio field exports |
| 51 | `test_51_saved_export_lists_lose_the_field` | PASS | lines on the own record type and on Users (path and related copy) removed; other lines/lists kept; chatter "Removed from 2 saved export lists: …"; the delete blocker is gone |
| 52 | `test_52_the_mobile_app_rules_and_values` | PASS | screen not in app / health / Admins-only → switch off with the host's reason; Staff on an app screen → on; direct write refused; `app_fields` gives the option name, the link's name, the date and the time in the reader's zone (02:30 UTC → 9:30), "Yes", "1,200", no file, nothing unplaced; a field made Admins-only behind the switch is dropped at call time; a screen leaving the app sends nothing; the method is not callable over RPC |
| 53 | `test_53_the_encrypted_shape` | PASS | two field rows (field without column, text token column); column `_enc` only; write → token, reads "Hello" in any language, also `read()` as a non-administrator after cache clear; dropdown stores its code encrypted and keeps its label; damaged token → marker; a date marked health information stays stored; a non-admin `fields_get` has no token column |
| 54 | `test_54_switching_an_existing_field_converts_its_values` | PASS | 7 of 10 values → 7 tokens, plain column dropped, reads unchanged, "7 values converted"; off again restores column and values and removes the token column; a lossy conversion (one token lost) raises "… nothing was changed" and leaves field, column, setting and values as they were |
| 55 | `test_55_non_exportable_fields_are_not_analytics_material` (+55b) | PASS | discovery skips a non-exportable field; rescan marks it sensitive, keeps it, adds no duplicate; builder leaves it out; the engine refuses it (dimension and filter) for the superuser — even with a cached result, and even put back to "visible"; a sensitive field is refused |
| 56 | `test_56_deleting_an_encrypted_field` | PASS | delete sheet counts 3 (token column); both rows and the token column gone; the layout republished without it |
| 57 | `test_57_without_a_cipher` | PASS | no cipher → "Encryption is not available on this system." on create and on switching; date marked health information still allowed; payload says `encrypt_available: False`; a screen that does not encrypt hides only |
| 58 | `test_58_the_hidden_column_is_never_shown` | PASS | no form arch, list arch, Studio payload, library or app payload names a token column; non-admin `fields_get` has none; the writer refuses to place one; it is "not made in Studio" |
| 59 | `test_59_the_gates_cover_the_fs_h4_files` + 12a–12f | PASS | gates run over every FS-H4 core file incl. `models/base.py` and the migration; the core ships `_fs_cipher` and imports no cipher |
| 60 | `test_60_hosts_flags_and_words` | PASS | Client (encrypt, app), Booking (app), Contact/Incident (neither); `health_phi_encryption` installed; real cipher round-trips an `enc$1$` token; every app sentence says "nurse app" and has its Vietnamese |
| 61 | `test_61_end_to_end_on_the_client` | PASS | as the Owner: "Allergy notes" (long text, health) encrypted (`enc$1$` at rest, no plain column), read by a nurse; "Preferred language" in the app's client record ("English"; "Tiếng Anh" / "Ngôn ngữ ưu tiên" for a Vietnamese reader); the health field absent; export refused; analytics discovery skips the field and its token column, keeps the dropdown |
| 62 | `test_62_end_to_end_on_the_booking` | PASS | "Key safe code" hidden only (stored, not exportable, its column exists), never in the app; "Parking instructions" (Staff, app) in the app's booking record and `app_fields` with its newlines; "Internal code" (Admins) cannot be switched on, reasons in the clinic's words |
| 63 | `test_63_the_nurse_app_over_http` (HttpCase) | PASS | a minimal nurse over `/health_pwa/sync/changes` and `/health_pwa/api/fso/<id>`: client carries only "Preferred language", booking only "Parking instructions"; "Penicillin", "4455" and both health field names absent from both bodies |
| 64 | `test_64_the_nurse_app_version_and_strings` + co-resident pin tests | PASS | five pins read 1.21.0; "More details" has Vietnamese in both dictionaries; the two blocks name no product; daystrip/scribe/ergo/family shell tests pass at 1.21.0, telehealth's version test passes |
| 65 | guard tests (3.6) | PASS | `health_crm…test_05`, `health_fieldservice…test_05_workspace_skeleton` and `…test_07` |
| 66 | `health_phi_encryption` (8) and `health_compliance` (23) | PASS | unchanged and green before and after |

**Pre-existing failures (identical on a fresh clone with the live code, run `fs4b`, 2026-11-03):**
`health_pwa_family` 19 errors (consent grant now needs a recorded notice), `health_scribe` 2
failures + 13 errors (upload refused / no audio-recording consent), `health_telehealth` 1 error
(`health.consent.check.log.consent_type_code` missing). The same baseline also failed the four
stale version pins and the three guard tests, which pass now. Ledger §5.294.

### biz_bi suite, before and after (the gate)

| Run | biz_bi tests | Failed | Errors |
|---|---|---|---|
| Before (clone, live code) | 151 | 0 | 0 |
| After (clone, FS-H4 code) | 155 | 0 | 0 |

The six historical failures the handover mentions are gone on today's tree. FS-H4 adds the test
file `test_non_exportable.py` (55, 55b); the framework's stats line counts 155.

## Browser QA (§6) — evidence in `fs_h4_shots/`

Personas on the clone: **Owner** `fs4.qa.owner` (Owner role; given the export right for QA 33,
D20), **VI Owner** `fs4.qa.owner.vi`, **Nurse** `fs4.qa.nurse` (Nurse role + employee, lead on
BK3852 and BK3848). Backend at 1440 and 820 px, the nurse app at 390 px phone emulation.

| Step | Result | Evidence |
|---|---|---|
| 31 | Client → Studio: new Long text "Allergy notes" with Health information on: green "Stored encrypted" badge and "Stored encrypted, like the client's identity numbers. Hidden from lists, exports, reports and the nurse app."; Nurse app switch disabled "Health information never reaches the nurse app."; column switch disabled. Dropdown "Preferred language" (Everyone): Nurse app switch on. A Text field set to Admins: switch disabled "Admins-only fields cannot show in the nurse app." Booking "Key safe code": "Hidden from lists, exports, reports and the nurse app. Not encrypted on this screen." VI Owner: all of it in Vietnamese | `31a`–`31e` |
| 32 | Publish sheet lists "Now stored encrypted: Allergy notes" and "Now in the nurse app: Preferred language". After publish the value "Penicillin / Latex gloves" saves and comes back after reload. psql: `x_fs_allergy_notes_enc = enc$1$OaMQ…`, no `x_fs_allergy_notes` column. Clients list column chooser has no health field. Saved export list "FS4 QA client list" naming "Door code": switching Door code to health information converted 1 value, removed it from the list, and wrote "Removed from 1 saved export lists: FS4 QA client list." (wording made singular afterwards, D15) | `32a`–`32c` |
| 33 | Export dialog on Clients: "Allergy notes" absent (searching "Allergy" shows only the standard "Known Allergies (encrypted)" — pre-existing hole), "Door code" listed and chosen; xlsx export answered 200 and the same `export_data` returned `[["Nguyễn Văn An", "1234#"]]`. Hand-made `export_data` with the health path → "Health information cannot be exported: Allergy notes"; also through Users `partner_id/…` | `33a` |
| 34 | Clients dataset "Bookings & Service Orders" rescanned: only "Preferred language" among the Studio fields; neither the health fields nor any token column; the builder lists "Preferred language" and finds nothing for "Allergy" | `34a`, `34b` |
| 35 | Nurse app, client Nguyễn Văn An: "More details" with PREFERRED LANGUAGE / English; Hồ Thị Xuân (no value): no block, no "undefined"; a Vietnamese nurse account: "Chi tiết thêm", "NGÔN NGỮ ƯU TIÊN", "Tiếng Anh". Found and fixed on the way: the client screen drew nothing for a client with orders (D12) | `35a`–`35c` |
| 36 | Booking BK3852 details: "Chi tiết thêm / Hướng dẫn đỗ xe / Use the side gate. / Blue door, ring twice."; Key safe code "4455" absent. A booking with no Studio values (BK3848) before vs after the Booking fields were published: **0 differing pixels from the first section down**; the only differences are above it (the page behind the sheet's backdrop and the client banner) | `36a`–`36c` |
| 37 | English session: app config 1.21.0, worker `service-worker.js?v=1.21.0`, `CACHE_VERSION 1.21.0`, only cache `health-pwa-v1.21.0`. A Vietnamese session is served the frozen v1.0.95 worker (pre-existing, §5.288) | `37a` |
| 38 | Nurse in the backend: `fields_get` lists Allergy notes, Preferred language, Door code — not the Admins-only "Specialist referral code" and no token column; `read` of Allergy notes returns the text, of the Admins field and of the token column is refused. The client form shows "Ghi chú dị ứng: Penicillin / Latex gloves" and no Admins field. (This step found D5: before it the nurse's `read` was refused.) | `38a` |
| 39 | 820 px: the settings panel with the reasons — page width 820 = 820, every row inside the panel, no overflow | `39a` |
| 40 | Live carejiox.com, temporary Owner: Client → Studio, new Long text, Health information on (not saved): badge and help as on the clone; cancelled ("No changes yet"). Nurse app at 390 px: 1.21.0 config, worker and cache; client screen draws; no console message. hhh not opened in the browser (no clients there) | `L40a`–`L40c` |

Console: no errors from this work. Pre-existing: "The widget: date don't support the type
datetime" on client screens (backend). Live clean-up: user `fs4.qa.live.20261103` (id 10115 /
partner 38000) and its sign-in traces (1 login log, 14 live-update rows, the welcome chat: 1
channel, 2 members, 1 message) deleted; fresh queries show 0 of each.

## Deploy (§7)

1. Clone built, upgraded (`-u biz_form_studio,health_form_studio,biz_bi,health_pwa,health_crm,
   health_fieldservice`, exit 0), jobs off after each upgrade (7 came back each time), suites,
   QA, `validate_all` → `{'checked': 0, 'broken': [], 'hosts': []}`. A second helper clone
   `carejiox_fs4b` was used once for the co-resident baseline and dropped.
2. Live tree compared file by file with the pre-phase commit: identical. Backups
   `/var/backups/fs4/{carejiox,carejiox_template,hhh}.dump` (19 / 13 / 14 MB, readable by
   `pg_restore -l`).
3. Staged from the commits with `git archive` (0 `._` files) →
   `carejiox-deploy -d -m biz_form_studio,health_form_studio,biz_bi,health_pwa,health_crm,
   health_fieldservice -i health_pwa_daystrip,health_scribe,health_pwa_ergo,health_pwa_family`
   (odoo-bin exit 0, http 200; the `-i` list only copies the four pin-test modules, D19), then
   `-D carejiox_template -m …` (exit 0, 200), `-D hhh -m …` (exit 0, 200).
4. All three: biz_form_studio 19.0.1.3.0, health_form_studio 19.0.1.3.0, biz_bi 19.0.1.7.2,
   health_pwa 19.0.1.1.0, health_crm 19.0.1.12.5, health_fieldservice 19.0.2.12.5 installed;
   `validate_all` → `{'checked': 0, 'broken': [], 'hosts': []}`; hosts Client (app, encrypted),
   Booking (app), Contact, Incident; cipher present; service worker (English) 1.21.0; 0 layouts,
   0 drafts, 0 `x_fs_` fields. `synconics_bi_dashboard` **uninstalled on all three**.
   **Template jobs: 7 came back on → `UPDATE ir_cron SET active=false` → 0.**
5. `/web/login` 200 on carejiox.com and hhh.carejiox.com; live QA 40.
6. Clone, filestore, private tree, units, staging folders, scratch files and the tunnel removed;
   only the three backups remain in `/var/backups/fs4/`.

## Deviations

- **D1 — the cipher is a hook, filled by the overlay.** `biz_form_studio` may not name
  `health_phi_encryption` (gate 12a), so the core asks `ir.model.fields._fs_cipher()` (None in the
  core) and `health_form_studio` returns `phi_crypto`'s functions; the overlay now depends on
  `health_phi_encryption`. Test 57 patches the hook.
- **D2 — without a cipher an encrypted field is built empty and read-only, not "stored and
  plain".** While modules load one by one the overlay's cipher is not loaded yet; a stored plain
  build there would make the framework add a plaintext column. Logged as a warning only once the
  registry is complete.
- **D3 — the cipher is three things:** encrypt, decrypt, and its failure marker, so switching back
  from encrypted refuses a value that cannot be decrypted instead of writing the marker as text.
- **D4 — tokens are written with SQL in batches of 500, not an ORM loop.** No record is "edited":
  no last-changed date moves (the nurse app would otherwise re-send every client), no business
  write hook or per-record audit line fires. The whole switch (export clean-up, conversion,
  settings) is one savepoint inside `update_field`; the conversion has its own with the count
  check; on any failure the record type is rebuilt from the database.
- **D5 — `compute_sudo=True` on encrypted fields** (found in QA 38): a non-stored computed field
  is computed as the reader by default, and only administrators may read the token column.
  Ledger §5.285; tests 53/61 now `read()` as a non-administrator.
- **D6 — the app shows a field only once it is placed on a published screen** (plus the rules),
  in screen order — what the switch's help and the publish-sheet lines say.
- **D7 — app sentences:** the core says "mobile app"; the overlay supplies all eight sentences in
  its words (`_app_words`). The reason order is: screen not in the app, then health information,
  then Admins-only.
- **D8 — values:** Yes/No and numbers always have a value (as on the form); empty text, dates,
  dropdowns and links are left out; files never sent.
- **D9 — related copies:** a user carries its contact's fields as related copies that do not keep
  "not exportable" (§5.286). The server refusal and the export-list clean-up judge the source
  field; the Users export DIALOG still lists the field (the server refuses it).
- **D10 — biz_bi beyond the three named files:** `bi_field.py` (`_not_analytics_material`, used by
  scan, engine and the pre-cache check), `i18n/vi_VN.po`, the new test file, and the refusal moved
  ahead of the result cache (§5.287) — without that, any request run before would still be answered.
- **D11 — tests 61–64 live in `health_form_studio/tests/`:** `health_pwa/tests` is not a sanctioned
  file and `health_pwa` cannot depend on Studio.
- **D12 — one name added to the nurse app's client screen** (`displayDbValue` in
  `patient-detail-view`'s return): without it the screen drew nothing for any client with orders,
  so the new block could never be seen (§5.291). Outside "the block only"; flagged here.
- **D13 — line breaks in the block use an inline style** (`white-space: pre-line`): the app's
  stylesheets are not sanctioned files.
- **D14 — the "do not put health information here" note no longer appears for a field that is
  marked health information.**
- **D15 — "1 value converted" / "the saved export list X"** instead of "1 values" / "1 saved export
  lists".
- **D16 — the core tests switch off the product's own screens on `res.partner`** inside their
  class, so encryption and the app (decided per record type) are tested on the neutral screen only.
- **D17 — `health_phi_encryption` has 8 tests,** not 6.
- **D18 — scribe pins at lines 424–430** (the same test also pins `telehealth.js` and `ergo.css`).
- **D19 — the four pin-test modules were not version-bumped** (tests only); they were copied with
  `-i` (a plain load for an installed module, FS-H1 D23).
- **D20 — QA personas:** the Owner was given the export right on the clone (no clinic role has it,
  §5.295); the QA nurse's account language was set to Vietnamese for the Vietnamese check (the
  app's VI switch does not change what the server writes, §5.289); the analytics rescan was run as
  the superuser (the Owner is not an analytics modeler); fields for QA 33/36/38 were made over the
  editor's own RPC as the Owner.
- **D21 — the money check in test 52 runs only where the neutral screen can hold money.**
- **D22 — export-list clean-up chatter and conversions are written on the screen's layout**
  (as every field event since FS-H1).

## Verified plumbing — drift found

All §2 facts held at the cited lines except: fact 20 — 8 tests in `health_phi_encryption`;
fact 14 — scribe pins run to :430. New facts: `compute_sudo` defaults to `store`
(`fields.py:443-449`, §5.285); related copies don't copy `exportable` (`fields.py:774-778`,
§5.286); biz_bi caches before resolving (`bi_query_engine.py:160-171`, §5.287);
`ir.model.fields._prepare_update` refuses to drop a column another manual field depends on
(`ir_model.py:899-985`, §5.292); `odoo-bin i18n export` without `-o` writes into the module
(§5.293); manual binary fields are attachments by default (`fields_binary.py:39`) and
`health_phi_encryption/models/ir_attachment.py` encrypts attachments of `res.partner`, `health.*`
and `account.move` — so Studio files on Client, Booking and Incident are already encrypted at
rest; on Contact (`crm.lead`) they are not.

## Pre-existing holes found (reported, not fixed)

1. **The standard encrypted columns are exportable and visible to analytics.** The export dialog
   of Clients lists "Known Allergies (encrypted)", "National ID (encrypted)", "CCCD Number
   (encrypted)" and eight more `_enc` columns, plus the `_bidx` search columns; an export of them
   hands out tokens (and the blind index). Same for analytics discovery.
2. **`synconics_bi_dashboard`** has its own CSV/Excel export from field rows an admin picks —
   uninstalled on all three databases today, so no open door now.
3. **biz_bi's silver SQL view and pipeline `SELECT *`** still carry hidden/sensitive columns
   (BI-hardening follow-up); a calculated field can still reference a sensitive stored field.
4. **Nurse-app language:** the server's Vietnamese preload table does not exist in this version
   (fact 13); the app's VI/EN switch is client-only — server-written text follows the account
   language (§5.289).
5. **Vietnamese nurses run the v1.0.95 service worker** on all databases (§5.288).
6. **Nobody in the clinic can export:** only `__system__` and `demo` hold the export right on
   carejiox (§5.295).
7. **Consent-related nurse-app suites red** (§5.294).
8. **Stale shell loops on the server** from an FS-H2 session (`while pgrep -f "odoo-bin.*carejiox_fs2…"`
   — the pattern matches the loop itself, so they never end). Harmless sleepers; left alone (not
   this phase's processes).
9. `hr_skill` / `hr_job_skill` / `hr_skill_level` NOT NULL warnings on every upgrade (null data).

## New ledger entries (HANDOVER-CONVENTIONS §5)

§5.285 non-stored computes run as the reader · §5.286 `_inherits` copies drop `exportable` ·
§5.287 biz_bi answers from cache before resolving · §5.288 the Vietnamese service worker is frozen
at v1.0.95 · §5.289 the nurse app's language switch is client-only · §5.290 a changed PWA file
under the same version is invisible · §5.291 the client screen's missing `displayDbValue` ·
§5.292 delete the dependent custom field first · §5.293 `i18n export` needs `-o` · §5.294 the
red consent-related suites · §5.295 no clinic role can export.

## What FS-H5 (hardening) needs

1. **Validator in the deploy wrapper:** `fs.studio.validate_all()` after every `-m`/`-i` on every
   database, failing loudly on `broken` or `hosts`; plus the template-jobs check (7 jobs came back
   on the template again this time).
2. **Callable-selection write check** (FS-H3 known limit): a write of a value not in the options
   is not refused; with encrypted dropdowns the stored code is also invisible to SQL, so the check
   must be in Python (`_fs_options` + `write`/`create` override for `x_fs_` selections).
3. **Tenant/template behaviour:** decide whether template databases may hold Studio fields;
   encrypted fields on the template would carry tokens made with the template's own key
   (`database.secret`) into tenants that never share it — a cloned tenant could not read them.
   Either forbid encrypted Studio fields on the template or re-encrypt on tenant creation.
4. **Access clean-up proposal:** the Admin role cannot open clients/bookings (§5.277/§5.283), no
   clinic role can export (§5.295); propose who exports, who holds Studio, who is an analytics
   modeler.
5. **The standard `_enc` / `_bidx` columns** (hole 1): mark them `exportable=False` in
   `health_phi_encryption` (needs that module sanctioned); biz_bi then hides them by the generic
   rule already shipped.
6. **The Vietnamese service-worker copy** (hole 5): drop the `vi_VN` term of
   `health_pwa.service_worker_js` (one write per database) or move the script out of a translatable
   node; then bump.
7. **Users export dialog** still lists a health field through the user's related copy (D9):
   a small `res.users` `fields_get` override, or accept the server refusal.
8. **Key rotation** for Studio tokens rides on `phi_crypto` — when that module grows rotation,
   include `x_fs_%_enc` columns (`ir_model_fields.fs_companion`).

## Commits

- `957b8018` — Form Studio (health19): FS-H4 keeps health information out of exports, reports and the nurse app, and stores it encrypted on the Client record
- `65b71578` — Analytics: fields a product marks as not exportable are not offered or answered
- `b3e537ad` — Nurse app 1.21.0: a read-only More details block on the client screen and in booking details
- `cd70787e` — Client and Contact screen guard tests: allow the Form Studio top-bar button and the rail fold
- (this report, the ledger entries and the evidence) — the commit after it.

## Evidence folder `docs/handovers/formstudio/fs_h4_shots/`

31a_clone_client_new_long_text_phi_stored_encrypted_badge · 31b_clone_client_dropdown_nurse_app_switch_enabled ·
31c_clone_client_admins_only_nurse_app_switch_disabled · 31d_clone_booking_health_field_hidden_not_encrypted ·
31e_clone_vi_owner_health_field_encrypted_badge_and_reasons_in_vietnamese ·
32a_clone_client_publish_sheet_encrypted_and_nurse_app_lines · 32b_clone_client_encrypted_field_value_after_reload ·
32c_clone_clients_list_column_chooser_no_health_fields ·
33a_clone_export_dialog_allergy_search_studio_field_absent_door_code_chosen ·
34a_clone_analytics_builder_preferred_language_listed_health_fields_absent ·
34b_clone_analytics_builder_search_allergy_no_studio_field ·
35a_clone_nurse_app_client_more_details_preferred_language · 35b_clone_nurse_app_client_without_values_no_block ·
35c_clone_nurse_app_vietnamese_more_details_label_and_option ·
36a_clone_nurse_app_booking_no_custom_values_before · 36b_clone_nurse_app_booking_no_custom_values_after ·
36c_clone_nurse_app_booking_more_details_parking_no_key_code · 37a_clone_nurse_app_loads_at_1_21_0_owner_session ·
38a_clone_nurse_backend_client_staff_health_field_shown_admin_field_absent ·
39a_clone_820px_settings_panel_reasons_no_overflow ·
L40a_live_carejiox_studio_client_health_switch_stored_encrypted_unsaved · L40b_live_carejiox_nurse_app_loads_1_21_0 ·
L40c_live_carejiox_nurse_app_client_screen_draws_no_studio_block (all `.png`).
