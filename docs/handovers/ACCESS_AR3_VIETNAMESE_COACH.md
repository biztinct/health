# ACCESS REVAMP — AR-3: Vietnamese and the Care Coach

Status: HANDOVER to Opus (written 2026-09-28, launches after AR-2 reports). Designed by
Fable. Read first: `ACCESS_REVAMP_GAP_ANALYSIS.md`, the AR-1 and AR-2 reports (their strings
are in scope here), `docs/strategy/HANDOVER-CONVENTIONS.md` §4 (the `i18n/vi.po` rules:
filename must be `vi.po` or `vi_VN.po`; every entry needs `#. module:`, the right marker
kind and a `#:` occurrence; **a field label is not a code translation** — it needs a
`model:ir.model.fields,field_description:` occurrence; ledger §5.58/§5.67/entry 29) and the
ledger tail (continue numbering).

Owner decisions: **the whole Access screen and the role list read in Vietnamese**; **a
short Care Coach walkthrough on Access**. Everything shows for a user whose language is
Vietnamese — today all 74 live users are `en_US`, so nothing changes on screen until a
person's language is switched; say so in the report.

## 0. Standing rules
As AR-1 §0. Versions: `biz_access` → **19.0.1.5.0**, `health_access` → **19.0.1.5.0**,
`health_learn` bump per its own convention. `biz_access` stays product-agnostic — its
`vi.po` translates generic strings only; role/ability names and sentences are DATA and are
translated in `health_access` (they are `translate=True` fields → written per-language,
not `.po`).

## 1. Scope

| # | Item | Module |
|---|---|---|
| A | `biz_access/i18n/vi.po` — every user-visible string in models, views, JS (`_t`), XML templates, the two mail templates' subjects/bodies, the group name "Access team" | biz_access |
| B | `health_access/i18n/vi.po` — its own strings (wizards, person actions, views, palette) | health_access |
| C | Role + ability names/sentences in Vietnamese as translated field values (9 roles, 30 + AR-2's 5 abilities), applied by a migration and on fresh install | health_access |
| D | Concatenated strings that cannot be translated are refactored into `_t()` sentences with `%s` (Payobook's known list: "Give a role to X", "Looking at this as X", "The menu, as X sees it", "and N more …", "From … to …", "Inside X", "everyone who sees X" — find Carejiox's equivalents by grepping the QW for `' + ` and `+ '`) | biz_access |
| E | Care Coach: `data-a` anchors on the Access home (header, See-it-as, Hand-over button, New-role button, tabs, a role card, the builder, the passport, the Screens block row), registered in `health_learn/static/src/anchors.json`; a `learn.screen` row for the Access home; a "what does this screen do" blurb; one lesson **"Give somebody access"** (5-6 steps: find the person → give a role → what the menu now shows → hand-over for leave → take back → history) added at the GENERATED source and regenerated; 4-6 intents/phrases (EN + VI) such as "how do I give Lan the nurse role", "ai đang giữ vai trò", "hand over my access" pointing at the anchors | health_learn (+ anchors in biz_access XML) |
| E2 | **The menu (added 2026-09-29 after M1/M2):** `health_cms_sidebar/i18n/vi.po` for the shell strings M1 added (Home, the « tooltip, "Menu", breadcrumb separators, the phone ☰ label, area picker) and `health_cms_ia/i18n/vi.po`; PLUS the Vietnamese NAMES of every `cms.sidebar.section` and `cms.sidebar.item` (translatable fields; occurrence rule `model:cms.sidebar.item,name:` per ledger §5.129 — the seeds live in ~12 modules, so ship the section/item Vietnamese as DATA written by a `health_cms_ia` helper (`with_context(lang='vi_VN').write`) from one table keyed by xmlid, run from its migration + post_init, rather than 12 separate .po files). Rail labels, tab labels (measure they fit the 60px box in Vietnamese — abbreviate in the table, not in code) and segment pills must all read Vietnamese for a `vi_VN` user; add test: a `vi_VN` Doctor's `get_sidebar_data` returns no English label except proper nouns (Zalo, VoIP, BHYT, NEWS2, EMR, EVV, VAT, Google Ads) | health_cms_sidebar + health_cms_ia |
| G | **M2 follow-ups (owner rulings 2026-09-29, do these FIRST, they are small):** (1) give the Doctor role the ability "See the clinic's patients and visits" (the one that reads bookings — find it by the key `health_cms_ia`/M2 used in its can-open check) through the role-bundle seam AR-2/M2 used (create-only, audit line), then the Bookings tab appears for the 9 doctors — assert in a test and in the per-user diff; (2) hide "Google Ads application" (Settings › Connections) from everyone but `base.group_system` (gate it to no role and keep it active — the admin short-circuit still shows it to the platform administrator; assert Owner/Admin do not see it); (3) sign-in lands on **Home**: point `health_cms_sidebar.menu_cms_root`'s action (and any `home_action_id`/`action_id` default the tenancy provisioning sets — check `biz_tenants/models/service.py` and `health_access/hooks.py ensure_topbar_settings`) at the `cms_home` client action so the first screen after login is the role's own; assert for Nurse (Bookings) and Accountant (Finance); (4) the browser tab reads "Odoo" for a second while the web client loads — find where the initial `<title>` comes from (`web.layout`/`web.webclient_bootstrap` in the vendored web module vs `biz_debranding`), override it with the brand name setting (`biz_debranding.brand_name`, default "Viet Uc Care") so the tab never shows the framework name (white-label rule); add a source test | health_access + health_cms_sidebar + biz_debranding |
| F | Tests: G1/G2 catalogue tests green (`health_base/tests/test_i18n_catalogues.py`), `health_learn/tests/test_anchor_registry.py` green, a test that a `vi_VN` user's `get_board` headline and area labels are Vietnamese, a test that the role names read Vietnamese for that user | — |

Non-goals: translating other modules, changing any behaviour, changing live users' language.

## 2. Verified plumbing (2026-09-28 — do not re-derive)

- Vietnamese seed source: `/Users/adity/Documents/GitHub/gitlocal/biz_access/i18n/vi_VN.po`
  (448 msgids, complete). Most Carejiox strings are identical (the port renamed code, not
  copy) — **reuse the msgstr where the msgid matches exactly**, translate the rest in the same
  register. Payobook's known gaps there (group name, mail templates, concatenations) must NOT
  be copied — fix them here. Role/ability Vietnamese precedent:
  `gitlocal/pb_vendor_access/catalogue_vi.py` + `migrations/19.0.1.9.1` (payroll words, use
  only as a shape).
- Carejiox has NO `i18n/` in `biz_access`, `health_access`, `biz_kit`, `biz_tenancy`,
  `health_tenancy`. `biz_kit` owns `ic()` and shared primitives — if any user-visible string
  lives there (check `kit_*.js`), add `biz_kit/i18n/vi.po` too.
- Area labels go through `env._` in `access_common.py` (~:77-87); state labels `_state_label`
  in F; JS uses `_t` from `@web/core/l10n/translation`; templates use plain text (translated
  by the OWL template loader when the module's `.po` carries the `model_terms`/`code`
  occurrence for that XML file — mirror how `health_care_command/i18n/vi.po` marks XML
  strings, it was repaired to the loader's real requirements).
- Role/ability `name` and `description` are `translate=True`
  (`BA/models/access_role.py`, `access_ability.py`) → write the Vietnamese value with
  `record.with_context(lang='vi_VN').write({...})` in a `health_access` helper called from the
  seed (fresh) and from `migrations/19.0.1.5.0` (live). `vi_VN` is active on live and on the
  template (`res_lang`).
- Care Coach: anchors are `data-a="key"` attributes; registry `health_learn/static/src/anchors.json`
  (`product` kind: `{screen, file, desc}`; the test checks the key exists verbatim in that
  file and that every `data-a` in scanned files is declared). Screens are `learn.screen`
  rows in `health_learn/data/learn_screens.xml` (`key`, `name`, matching fields — read the
  model `learn.screen` in `models/learn_intent.py` ~:94 for how a screen is matched to a URL/
  action). Intents `learn.intent` + `learn.intent.phrase` in `data/learn_intents.xml`
  (`key`, `label`, `screens`, `dynamic`, `show_me` = anchor keys, `simpler`, `offer`);
  `{{accessRequestPath}}` tenant slot already exists (`learn_tenant_slots.xml:9`, resolves to
  "your Operations Manager") — reuse it in the "ask for access" phrasing.
  **Lessons/steps are GENERATED**: `data/learn_lessons.xml` header says "Source:
  docs/tutorial_crm/ · Regenerate: python3 docs/tutorial_crm/tools/gen_learn_data.py — hand
  edits are erased and fail the CI check". Add the lesson at the source, regenerate, commit
  both. Station: pick the ADMIN/people station if one exists (`learn_stations.xml`), else add
  one following the file's shape. `health_learn` uses `can_manage()` for the owner capability
  (`models/learn_intent.py` ~:279-281).
- The i18n test walks every module's `i18n/` dir (`test_i18n_catalogues.py` ~:41-46) —
  a badly formed entry fails the whole repo's gate.

## 3. Design notes
- Write Vietnamese in the product's register (the screen's words, no technical terms; "vai
  trò" for role, "bàn giao quyền" for hand-over, "menu bên trái" for the left menu, "Chủ sở
  hữu" for Owner — check `health_base/i18n/vi_VN.po` for terms already fixed there and stay
  consistent with them).
- Never translate xmlids, keys, `technical_key`, or the Learn anchor keys.
- The coach lesson runs on the practice fixture (`engine/fixture.js`) — check whether the
  Access home needs a practice replica; if it does, scope the lesson to the live screen only
  (anchors of kind `product`) and say so.

## 4. Tests (numbered)
1. `health_base` G1/G1b/G1c/G2/G2b green with the three new catalogues.
2. `get_board()` for a `vi_VN` test user: headline, area labels, state labels Vietnamese;
   for `en_US` unchanged.
3. Role and ability names/descriptions read Vietnamese for that user after the migration on a
   clone of live; English values untouched.
4. No user-visible concatenation remains in QW (grep test in the source-gate style of
   `TestSourceGates`).
5. `test_anchor_registry` green with the new anchors; every anchor present in the Access QW.
6. The lesson regenerates byte-identically from the source (run the generator twice).
7. Full `biz_access`, `health_access`, `health_learn`, `health_base` suites green.

## 5. Browser QA
Switch a test user on the clone to Tiếng Việt: Access home, a role card, the passport, the
hand-over dialog, the Screens lens — all Vietnamese, no English fragments. Coach: open the
Access home as an Owner, ask "how do I give someone access", follow the lesson.
Screenshots → `docs/handovers/access_ar3_shots/`.

## 6. Deploy + report
As AR-1 §5. Report: tests 1-7, counts, the number of msgids per catalogue and how many were
reused from Payobook, deviations, ledger entries, commits, live evidence, and the sentence
"nothing changes on screen for the 74 English users until their language is switched".
