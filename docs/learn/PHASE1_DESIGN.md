# Phase 1 — Content spine, anchor registry, Journey

Module: **`health_learn`** · target version `19.0.1.0.0` · branch `19.0`

Phase 0 (the prototype at [docs/tutorial_crm/](../tutorial_crm/)) proved the interaction
quality, the bilingual parity, the arithmetic and the content schema. Phase 1 turns that
schema into product: real records, real security, real delivery, real tests — and the
foundation that makes Phases 2 and 3 cheap.

---

## 1. Scope

**In:**

1. `health_learn` addon: 9 models, security, ORM bundle delivery.
2. **Anchor registry** — `anchors.json` in the module, `data-a="…"` added to the real
   product templates, and a **test** that fails when the two disagree.
3. **Journey map** — an OWL client action, reachable from a sidebar leaf, showing the CRM
   line with 8 stations, progress and resume.
4. **Two flagship lessons** (L1 Care Command, 10 steps + quiz; L2 Channel Center, 9 steps +
   quiz) with the full visual engine ported: spotlight, trace, morph toggle, calc
   breakdown, pipeline stepper.
5. **Six outlines** — the remaining CRM stations, labelled as outlines, content written.
6. **Tenant overrides** — 38 named slots, `{{token}}` resolution, tenant-admin editable.
7. **The event log** — ships now, not in Phase 4. Without it the pre-tutorial reference
   period is lost permanently (analysis §6).
8. **Content pipeline** — generator from the prototype's `data.js` to module data + `.po`,
   with a no-diff check.

**Binding non-goals for Phase 1** (each has its own phase):

- **No Coach.** No launcher, no drawer, no retrieval, no `WebClient` patch. Phase 2.
- **No missions.** No practice screens driven by anchors, no recovery dialogs. Phase 3.
- **No OPS/CLINICAL/FINANCE content.** The models are line-agnostic from day one so
  Phase 4 adds rows, not columns — but no content is written for them now.
- **No LLM.** The resolver seam arrives with the Coach in Phase 2.
- **No writes to product data.** `health_learn` reads `cms.sidebar.item` and
  `access.role`; it writes only its own tables.

---

## 2. Verified plumbing facts — do not re-derive

| Fact | Evidence |
|---|---|
| Client actions register as `registry.category("actions").add(tag, Component)` | [channel_center.js:1183](../../addons/health_care_command_channels/static/src/center/channel_center.js#L1183), [crm_dashboard.js:518](../../addons/health_crm/static/src/js/crm_dashboard.js#L518) |
| …paired with an `ir.actions.client` record carrying the same `tag` | [channel_center_views.xml](../../addons/health_care_command_channels/views/channel_center_views.xml) |
| Sidebar leaves are `cms.sidebar.item` with `action_xmlid` + `action_tag` + `match_action_tags` | [cms_sidebar_items_crm.xml](../../addons/health_cms_sidebar/data/cms_sidebar_items_crm.xml), [cms_sidebar_item.py:17-45](../../addons/health_cms_sidebar/models/cms_sidebar_item.py#L17-L45) |
| Sections are `cms.sidebar.section`; CRM is `section_crm`, seq 10 | [cms_sidebar_sections.xml:4](../../addons/health_cms_sidebar/data/cms_sidebar_sections.xml#L4) |
| The repo's data-fetch idiom is an **ORM method**, not a controller: `orm.call("cms.sidebar.item", "get_sidebar_data", [])` | [cms_sidebar.js:54](../../addons/health_cms_sidebar/static/src/js/cms_sidebar.js#L54) → [cms_sidebar_item.py:134](../../addons/health_cms_sidebar/models/cms_sidebar_item.py#L134) |
| An always-mounted component reaches every screen by patching `web.WebClient` and injecting a sibling of `<ActionContainer/>` | [ops_webclient_patch.js](../../addons/health_fieldservice/static/src/js/ops_webclient_patch.js), [ops_webclient_patch.xml:7](../../addons/health_fieldservice/static/src/xml/ops_webclient_patch.xml#L7) — **Phase 2 uses this; Phase 1 does not touch it** |
| Design tokens are `--vuf-*`, derived from `--vu-*`, themeable at runtime | [vu_tokens.scss:16-69](../../addons/health_theme/static/src/scss/vu_tokens.scss#L16-L69) |
| Tests in this repo are `@tagged('post_install', '-at_install')` | [test_channel_wiring.py:20](../../addons/health_care_command_channels/tests/test_channel_wiring.py#L20) |
| Manifest version format is `19.0.X.Y.Z` | any `__manifest__.py` |

**Repo gotchas that bind this design** (from the memory ledger, already paid for once):

- Content data files must be **`noupdate="0"`**, or an upgrade silently does not apply
  edited records.
- `Selection` fields only translate through the **callable `env._()`** form. Static lists
  and jsonb writes do not. Every selection on these models uses the callable form.
- `access.role` rows carry **no xml-id**; role gating lives in the DB. The Training leaf is
  therefore **ungated** (`role_ids` empty = visible to all), which is what we want anyway.
- Neither `cms.sidebar.item` nor `access.role` has `company_id` — navigation and roles are
  database-global. Content follows the same rule; only progress/events/overrides are
  company-scoped.

---

## 3. Model schema

Nine models, all prefixed `learn.`. Translatable fields marked **T**.

### Content (shipped as module data, `noupdate="0"`)

**`learn.station`** — one node on the journey map.
```
key            Char, required, unique      # "crm_care_command"
name           Char T                      # "Care Command"
line           Selection (callable _())    # crm | ops | clinical | finance
sequence       Integer
summary        Text T                      # one line on the map card
icon           Char                        # sprite symbol id
kind           Selection (callable _())    # lesson | outline | mission
sidebar_key    Char                        # xml-id of the cms.sidebar.item it teaches
duration_min   Integer
prereq_ids     Many2many self
active         Boolean
```
`sidebar_key` is the join back to the product. A station whose sidebar item no longer
exists is a broken station, and §7's test catches it.

**`learn.lesson`** — `station_id`, `name` T, `goal` T, `step_ids`, `quiz_ids`.

**`learn.step`**
```
lesson_id      Many2one, ondelete cascade
sequence       Integer
title          Char T
body           Text T
visual         Selection (callable _())    # none|spot|trace|morph|calc|pipeline|list
screen         Char                        # fixture screen key this step renders
anchor         Char                        # anchor key, must exist in anchors.json
note           Text T
line_ids       One2many learn.step.line
```

**`learn.step.line`** — one child model serving every visual, so the model count stays flat.
```
step_id, sequence
role     Selection  # calc_row | calc_total | pipe_stage | morph_before |
                    # morph_after | bullet | warn | ok
label    Char T
value    Char       # NOT translatable — numbers, ids, anchor keys
note     Text T
```
The **T / non-T split is the whole point**: prose translates through `.po`, arithmetic does
not. A translator cannot accidentally change `224` to `225`.

**`learn.quiz`** — `lesson_id`, `sequence`, `kind` (choice|order|match), `prompt` T,
`explain_right` T, `explain_wrong` T, `option_ids`.

**`learn.quiz.option`** — `quiz_id`, `sequence`, `label` T, `is_correct`, `feedback` T.

### Tenant data (per-company, not shipped)

**`learn.tenant.override`** — `company_id`, `key`, `value_en`, `value_vi`.

Not `.po`-translated, deliberately: these are *per-tenant facts*, and `.po` translates
per-module strings. Explicit `value_en`/`value_vi` is the only correct shape.
`key` is constrained against `TENANT_SLOTS` in `models/learn_tenant_override.py` — the one
declaration, which the token lint also reads. Unknown key → `ValidationError`.

### Learner data (per-user, per-company)

**`learn.progress`** — `user_id`, `station_id`, `company_id`, `state`
(not_started|in_progress|done), `step_index`, `attempts`, `first_try_correct`,
`completed_at`, `lang`. Unique on (user, station).

**`learn.event`** — the metrics backbone.
```
user_id, company_id, station_id, lang, occurred_at
kind     Selection  # journey_open | station_open | lesson_start | step_view |
                    # quiz_answer | lesson_complete | lesson_abandon
                    # (Phase 2 adds coach_*, Phase 3 adds mission_*)
screen   Char
detail   Char       # small, bounded: option index, step key, ms bucket
```
Append-only for users: create + read-own, no write, no unlink. Kept deliberately thin —
no free text, so it can never become a shadow PHI store.

**Why nine and not four:** every field above is either queried, translated, or gated
differently from its neighbours. The one place I collapsed is `learn.step.line`, which
serves six visual roles through one table because they share exactly the same shape.

---

## 4. Delivery

**One ORM method**, not a controller:

```python
learn.station.get_bundle(lang=None) -> {version, lang, stations, lessons, tokens, progress}
```

Deviation from the roadmap's "controller + ETag", on purpose:

- It is the repo's own idiom ([cms_sidebar.js:54](../../addons/health_cms_sidebar/static/src/js/cms_sidebar.js#L54)).
- It adds **no new HTTP surface**. A controller would be a new public route to secure for
  content that is already session-scoped.
- Caching is not lost: `version` is a hash of (module version, lang, override write_date),
  the server memoises per (lang, company) with `ormcache`, and the browser stores the
  bundle in `sessionStorage` keyed on `version`.

`tokens` is the resolved 38-slot map for **this** company, already merged
default → override, so the frontend never implements the fallback chain twice.

`progress` is the calling user's rows only, so the Journey paints on first frame without a
second round-trip.

---

## 5. The anchor registry — the piece that must land first

`health_learn/static/src/anchors.json`:

```json
{
  "care_command.wall_row":     {"screen": "care_command", "desc": "A conversation row on the wall"},
  "care_command.claim_banner": {"screen": "care_command", "desc": "The claim/ownership banner"},
  ...
}
```

Three artefacts, one truth, enforced by **`tests/test_anchor_registry.py`**:

1. **Every key in `anchors.json` exists as `data-a="key"` in some product template.**
   Fails when someone deletes or renames a control the tutorial points at.
2. **Every anchor referenced by content (`learn.step.anchor`) is in `anchors.json`.**
   Fails when content points at something never registered.
3. **Every `data-a` in a scanned template is in `anchors.json`.** Fails on a stray anchor —
   which is usually a typo of a real one.

Running this as an **Odoo test** rather than a bespoke CI script is the change I made to
the roadmap: it executes in the harness the repo already runs, so it cannot quietly stop
running.

Templates edited in Phase 1 (attribute-only, no logic):
`health_care_command` (wall rows, claim banner, action strip, composer),
`health_care_command_channels` (connection cards, readiness panel),
`health_crm` (dashboard KPI tiles, contact list, activity list).

---

## 6. Content pipeline

The prototype's `data.js` stays the **authoring surface** — it has a sub-second preview
loop and the contract checker already guards it against product drift. The module is the
**delivery surface**.

```
docs/tutorial_crm/data.js  ──┐
docs/tutorial_crm/practice-data.js ─┤─► tools/gen_learn_data.py ─► addons/health_learn/data/*.xml
                                    │                            ► addons/health_learn/i18n/vi_VN.po
                                    └───────────────────────────► addons/health_learn/static/src/engine/fixture.js
```

Generated files carry a `GENERATED — edit docs/tutorial_crm/data.js and re-run` header, and
`tools/gen_learn_data.py --check` fails if regenerating would produce a diff. Hand-editing
the XML is therefore a build failure, not a silent fork.

The `.po` gets my Vietnamese as the `msgstr` for each English `msgid`. Both languages exist
from day one; the standard `.po` workflow takes over from there.

---

## 7. Security

| Group | Who | Content | Own progress/events | All progress/events | Overrides |
|---|---|---|---|---|---|
| `base.group_user` | everyone | read | create/read/write | — | read |
| `group_learn_author` | Product | full | — | read | full |
| `health_user_admin.group_health_user_admin` | tenant admin | read | — | read (own company) | full (own company) |

Record rules:

- `learn.progress` / `learn.event`: `[('user_id','=',user.id)]` for `base.group_user`;
  company-scoped read for admins; unrestricted read for `group_learn_author`.
- `learn.event`: **no write, no unlink for anyone below author** — append-only.
- `learn.tenant.override`: `[('company_id','in',company_ids)]`.

---

## 8. Tests (numbered, all `post_install`)

1. `test_anchor_registry` — the three directions in §5.
2. `test_bundle_completeness` — every station resolves to a lesson or an outline; every
   lesson has ≥1 step; every quiz has exactly one correct option.
3. `test_bundle_bilingual` — `get_bundle('vi_VN')` returns no string identical to its
   `en_US` counterpart for translatable prose fields (with a whitelist for proper nouns
   like "CareJioX"). This is the check that catches an untranslated string shipping.
4. `test_no_unresolved_tokens` — no `{{…}}` survives resolution in either language, for a
   company with overrides and one without.
5. `test_tenant_override` — unknown key raises; override wins over default; blank falls
   back; a second company's override is invisible to the first.
6. `test_progress_isolation` — user A cannot read user B's `learn.progress`; a
   non-author cannot `write` a `learn.event`.
7. `test_station_sidebar_link` — every `station.sidebar_key` resolves to a live
   `cms.sidebar.item`.
8. `test_selection_translation` — every `Selection` on these models uses the callable
   form (guards the repo's known trap by reflection, not by eyeball).
9. `tools/gen_learn_data.py --check` — regeneration is a no-op.
10. `tools/check_contract.py` — the 22 existing prototype checks still pass.

---

## 9. Frontend port

`static/src/engine/` — plain ES modules, DOM-driven, no OWL reactivity needed:
`i18n.js` (`tx()` + token resolution), `fixture.js` (generated), `screens.js`,
`spot.js`, `trace.js`, `visuals.js` (morph/calc/pipeline), `player.js`.

`static/src/journey/` — `journey.js` (OWL client action `learn_journey`),
`journey.xml`, `journey.scss`.

The SCSS consumes `var(--vuf-*)` **directly** rather than copying the hex values as the
prototype did, so the Journey re-themes with the Theme Engine for free.

Accessibility carried over intact: `prefers-reduced-motion` **and** the manual toggle,
keyboard path through player and quiz, `aria-live` narration, visible focus, no gradients,
no emoji, SVG sprite only.

---

## 10. Mount point

New leaf **Training / Đào tạo** in `section_crm`, sequence last, `role_ids` empty
(visible to everyone — a learning system nobody can open is not a learning system).
`action_xmlid` = `health_learn.action_learn_journey`, `action_tag` = `learn_journey`.

Phase 4 promotes it to its own section when OPS/CLINICAL/FINANCE lines exist. Moving a leaf
between sections is a one-line data change, so this costs nothing to defer.

---

## 11. Deploy + verify

1. `scp` to `/tmp`, `sudo cp` with odoo ownership, `-u health_learn`, restart `odoo-server`
   (the standing UAT workflow).
2. Browser QA on care.biztinct.com — desktop, one mobile width, reduced motion, EN and VI,
   as owner and as a non-CRM user.
3. Report back: bundle size + first-paint, the anchor test output, the bilingual test
   output, and screenshots of the Journey and both lessons in both languages.

---

## 12. Report-back items

- Anchor count registered vs. templates touched.
- Any product template where a control genuinely has no stable place for an anchor.
- Bundle payload size per language.
- Whether any of the 8 stations turned out to have no honest content to teach.

---

## 13. As built — what changed against this design, and why

Recorded here rather than silently: the design was right about the shape and
wrong about three details, each of which the build found empirically.

| Planned | Built | Why |
|---|---|---|
| `learn.step.line` carries calc rows, pipeline stages and morph captions | **morph only** | The calc breakdown and the lifecycle stepper are also drawn by the practice screens straight from the fixture. Emitting them as lesson rows too would put one product fact under two owners, and the one that drifted would be the one nobody watched. |
| Content authored as data files | **Generated** from `docs/tutorial_crm/` by `tools/gen_learn_data.py`, with `--check` | The prototype is the authoring surface with a sub-second preview loop, and `check_contract.py` already guards every product fact it asserts. Hand-editing the generated XML is now a build failure rather than a silent fork. |
| Nine models | **Ten** (`learn.string` added) | Chrome had to be readable twice from the server, because the brief's "switchable live" rules out `_t()` — which binds to the session language and would need a reload. |

**Bugs the build found, all now covered by a test:**

1. **The asset minifier eats a space after `}`** — 59 sites. Ledger §5.144.
2. **`res.groups.category_id` / `res.users.groups_id` / `<group expand>`** are all
   Odoo-19 renames that fail at install or invalidate a view. Ledger §5.145.
3. **The bilingual zipper skipped three chrome labels** whose content names
   collide with structural keys, and turned empty optional fields into truthy
   `{en:"", vi:""}` pairs that drew empty cards. Ledger §5.146.
4. **The token lint over-counted** — `region()` had no JS-aware stop, so it ran
   past `TENANT_DEFAULTS` to end-of-file. 38 "slots" were really 25, and an
   undeclared token could have been masked by a same-named fixture key.
5. **The verdict was printed twice** on a check — every explanation is authored
   to open with its own ("Yes.", "Let's rethink that."), so the heading above it
   was the app repeating itself.

**Verified on UAT** (`vietuat`, as a CRM-role user): 36/36 tests pass; install
clean; 8 stations / 2 lessons / 19 steps / 10 morph rows / 2 checks / 6 options /
167 chrome strings / 13 glossary terms / 25 tenant slots loaded; Journey, outline,
lesson player, spotlight, calc, morph toggle, check, recovery and completion all
work in EN and VI; progress and all six event kinds persist; no console errors;
no horizontal scroll at 390 px; reduced motion honoured from both the OS
preference and the in-app toggle.

**Left open on purpose:** the practice replica still renders eight screens of its
own rather than the real ones — Phase 3 is what drives real screens through the
anchors. The anchors and the lint landed now precisely so that Phase 3 does not
have to discover them.
