# Phase W3 report — `health_web_leads` Reporting + consent bridge

**Module:** `health_web_leads` 19.0.3.0.0 → **19.0.4.0.0** · **Server:**
vietuat (care.biztinct.com) · **Date:** 2026-07-29
**Handover:** `docs/strategy/handovers/web-leads-phaseW3.md`
**Evidence pack:** `docs/strategy/reports/web-leads-phaseW3-evidence/`

Four small things that make the pipeline reportable and make the consent
checkbox mean something. A ticked marketing box on the website now becomes a
real `health.consent` record the moment ops converts the lead — identity-
matched, never superseding a staff-captured consent, and structurally unable
to break the conversion it rides on. The raw campaign strings the find-only
policy refuses to auto-create have a review queue and a find-only back-fill.
The funnel is a pivot anyone can open, and it shows the honest baseline: 292
of 295 leads carry no city and every single one says *Phone Call*. The
retention rail ships inert, because the horizon is counsel's to set.

---

## 1. What was built

| File | Change |
|------|--------|
| `models/health_consent.py` | **new**, 88 lines — `_inherit = 'health.consent'`: the `web_form` method key (`selection_add`) and the `action_grant()` evidence gate the core model does not have for it. **No file in `health_consent` was touched.** |
| `models/crm_lead.py` | `+238` — the `web_consent_bridged` marker field and the bridge: an override of `_get_or_create_patient()` plus the decision ladder, the identity matcher, the submission-time/effective-date/scope-note builders. |
| `models/lead_touchpoint.py` | `+132` — `UNMATCHED_CAMPAIGN_DOMAIN`, the group gate, and `action_link_seeded_campaigns()` (find-only, wildcard-safe, capped sweep, chatter per touched lead, `display_notification`). |
| `models/web_lead_service.py` | `+80` — `_cron_prune_raw_payloads()` and its parameter constants; plus the W2.5 review LOW (the `_heartbeat_user` comment now states the §5.89 correction instead of the premise it refutes). |
| `views/crm_lead_views.xml` | `+81` — `web_consent_bridged` on all THREE lead forms (§5.91), the Lead Funnel pivot + graph, the *Lead Analysis* action and its menuitem. |
| `views/lead_touchpoint_views.xml` | `+40` — the list `<header>` button, the *Unmatched campaign* filter, the *Campaign Review* action + menuitem. |
| `data/utm_seeds.xml` | **new** — 3 mediums + 1 source, `noupdate="1"`. See D1. |
| `data/web_leads_params.xml` | `+1` parameter: `web_leads.raw_payload_retention_days` = the string `'0'`. |
| `data/web_leads_cron.xml` | `+1` cron: the nightly prune, active and inert. |
| `data/cms_sidebar_items_web_leads.xml` | `+2` leaves — Campaign Review (22), Lead Analysis (23). |
| `i18n/vi.po` | `+29` entries (205 → 234 msgids, +165 lines). |
| `tests/test_web_leads_w3.py` | **new** — `TestWebLeadsW3`, 13 methods (T1–T12 + T12b). |
| `__manifest__.py`, `models/__init__.py`, `tests/__init__.py` | wiring, version, the `health_consent` dependency, description. |

**Nothing outside `health_web_leads` was edited** — the binding non-goal
holds. `git diff --stat`: 12 modified + 3 new files, all under
`addons/health_web_leads/`.

---

## 2. Test results

```
2026-07-29 06:20:40,107 2145511 INFO vietuat odoo.tests.result:
    0 failed, 0 error(s) of 65 tests when loading database 'vietuat'
EXIT:0            HTTP:200
```

**65 = 52 pre-existing (W1 + W2 + W2.5) + 13 new.** Counted, not assumed, and
read the §5.92 way — from `/tmp/gb/w3b.log`, **scoped to the run's own PID**,
never from stdout:

```
grep -ac "2145511.*Starting Test.*\.test_"   → 65      (expected 65)
grep -aoc "Starting TestWebLeadsW3\.test_"   → 13      (expected 13)
grep -ac "2145511.*FAIL\b"                   →  0
grep -ac "ERROR: setUpClass"                 →  0
grep -ao "Starting Test.*Http.*\.test_"      → TestWebLeadsConnectorHttp.test_w25_08…
```

The `HttpCase` really ran (`--workers=0`, no `--no-http` — §2/§5.75/§5.83).
The 11 `ERROR:` strings in the log are PostgreSQL messages *inside expected
exceptions* (the W2.5 singleton-index test, and the readonly-cursor retry
Odoo performs on every HttpCase POST) — read, not assumed (§5.92).

| Handover test | Method | What it proves |
|---|---|---|
| T1 | `test_w3_01_bridge_creates_a_real_consent` | web lead + claim + version → converted **as a CRM manager** → exactly ONE consent: marketing / `web_form` / active / self-granted; mutation key `web-lead-<id>-<sub>`; scope_note carries the submission id AND the text version; `effective_date` = the SUBMISSION date, not the conversion date; `patient.can_send_marketing()` is **True**; marker `created`; chatter on both records. |
| T2 | `test_w3_02_refire_never_creates_a_second_consent` | the chokepoint driven three more ways — the button again, a `write()` that re-triggers `_process_contact_relationship`, and a direct call — still ONE consent, marker unchanged. |
| T3 | `test_w3_03_declined_claim_creates_nothing` | claim False → no record, marker `skipped_declined`, `can_send_marketing()` False, and **no note with a body** was posted (tracking flushed first, §5.56, so this holds in production too). |
| T4 | `test_w3_04_existing_active_consent_is_never_superseded` | a staff-captured active marketing consent stays THE active one, un-withdrawn; marker `skipped_existing`; exactly one note. |
| T5 | `test_w3_05_identity_mismatch_records_the_reason_once` | the representative case (same client, different phone AND email) → no record, marker `skipped_identity`, the claim still visible on the lead, and exactly ONE note even after two more re-fires. |
| T6 | `test_w3_06_a_broken_bridge_does_not_break_conversion` | `health.consent.create` patched to raise → the conversion still returns the patient and sets `patient_id`, a warning is logged, the transaction stays usable, the lead is left UNMARKED, and the next conversion succeeds for real. |
| T7 | `test_w3_07_evidence_lock_and_the_web_form_grant_gate` | rewriting the granted `scope_note` raises `UserError` (no su escape); and a `web_form` draft is refused a grant with no scope_note, refused again with no mutation key, and granted once it has both. |
| T8 | `test_w3_08_campaign_review_and_backfill` | the unmatched queue finds the row; the button links nothing while the campaign is unseeded and creates none; after seeding `RAW.upper()` it links via `=ilike`, the row leaves the queue, `utm.campaign` grew by exactly the one row MARKETING created; and a raw value of `%` links nothing (the `=ilike`-is-a-pattern trap). |
| T9 | `test_w3_09_catalogue_sidebar_and_acl` | 10 xmlids load; pivot/graph/list render through `get_view`; `web_consent_bridged` reaches all THREE primary lead forms (§5.91, asserted with `get_combined_arch` per §5.42); both sidebar leaves are childless with distinct sequences and no `match_models`; and the back-fill refuses a receptionist — after a **live `res_groups_implied_rel` closure precheck** (§5.88) that would fail first, readably, if an inverted edge granted access. |
| T10 | `test_w3_10_retention_prunes_only_the_payload` | `'0'` → no-op and the parameter ROW survives (§5.36); `''`/`false`/`off`/`none`/`not-a-number`/`-5` → no-op; `'30'` → the 31-day-old payload is cleared, the 5-day-old one is not, and the row plus `lead_id`, `touchpoint_type`, `utm_campaign`, `external_event_id`, `occurred_at` are all intact; a second run is idempotent. |
| T11 | `test_w3_11_utm_seeds_are_matched_not_duplicated` | the 4 seeds exist, are `noupdate`, and carry the exact lowercase names; `_utm_ids({'medium': 'Organic'})` resolves to the SEEDED row and creates nothing; `'TikTok'` → the seeded source; after `'CPC'` the vocabulary still holds exactly ONE `cpc`; and this module owns no `utm.campaign` xmlid. |
| T12 | `test_w3_12_po_covers_the_new_surfaces` + `_12b` | 15 named msgids present, every block well-formed (§29/§5.67), and a runtime code translation + the `web_consent_bridged` field label both proven non-English under `vi_VN`. |

All new model xmlids were verified against `ir_model_data` on the server
(§5.85) rather than trusted — including
`selection__health_consent__method__web_form`, which a `selection_add` owns
under the EXTENDING module. All five new selection labels, both action names,
both menu names, both sidebar names and both new view archs carry `vi_VN` in
the database.

---

## 3. The six report-back items

### (1) Test transcript + §5.90/§5.92-proven executed count
Above. **`0 failed, 0 error(s) of 65 tests`, 65 methods executed (13 of them
W3), EXIT:0, HTTP:200**, all read from the run's own logfile scoped to
PID 2145511.

### (2) The live free-sequence check, and the sequences chosen
Run BEFORE choosing (handover fact #9):

```sql
SELECT s.sequence, s.name FROM cms_sidebar_item s
 JOIN cms_sidebar_section sec ON sec.id = s.section_id
 WHERE sec.id = (SELECT res_id FROM ir_model_data
                 WHERE module='health_cms_sidebar' AND name='section_crm')
 ORDER BY s.sequence;
--  10 Dashboard | 11 Care Command | 12 Channel Center | 13 Website Connector
--  20 Contacts  | 21 Web Touchpoints | 50 Activities            (7 rows)
```

14, 15, 22, 23 were free. **Chosen: 22 = Campaign Review, 23 = Lead
Analysis** — adjacent to *Web Touchpoints* (21), the list they both read
from. (The handover suggested 15 and 22; 15 would have split the connector
group from Contacts for no reason.) Verified after the deploy:

```
10 Dashboard · 11 Care Command · 12 Channel Center · 13 Website Connector
20 Contacts · 21 Web Touchpoints · 22 Campaign Review · 23 Lead Analysis
50 Activities                                                   (9 rows)
```

### (3) Pivot + Campaign Review screenshots
`evidence/04-lead-funnel-pivot.png` (rows city → contact status, columns
mode of contact, total 295 — **Hà Nội 2, TPHCM 1, None 292**, and the only
channel column is *Phone Call*), `evidence/07-lead-funnel-graph.png`,
`evidence/02-campaign-review-list.png`, plus the sidebar, the *Unmatched
campaign* filter and the Consent Bridge field on the Lead Hub Source modal.
Zero console errors and zero warnings on every screen. Full click-by-click
path in `evidence/README.md`.

### (4) Proof the retention cron is inert
```
ir_cron 140  active=t  1 days  "Web Leads: prune touchpoint raw payloads"
ir_config_parameter  web_leads.raw_payload_retention_days = 0
```
and the method run by hand on the server:
```
RESULT: 0
2026-07-29 06:12:31,686 INFO vietuat …web_lead_service: web_leads:
raw-payload retention is off (web_leads.raw_payload_retention_days='0')
— nothing pruned
```
The disabled path logs deliberately: an operator must be able to tell "ran
and did nothing on purpose" from "never fired" (§5.83's lesson, applied to a
cron). No compliance claim is made anywhere in code or docs and no retention
number is hard-coded — the horizon is counsel's (design §10, a W0 item).

### (5) Zero consent / patient / lead rows created in live data by QA
Confirmed, measured after the drive:

| | consents | `web_form` consents | leads | web leads | bridged markers | touchpoints | patients | campaigns | `wl_w3%` users |
|---|---|---|---|---|---|---|---|---|---|
| after QA | 8 | **0** | 476 | **0** | **0** | **0** | 305 | 11 | **0** |

and nothing at all was created in the surrounding window:
`res_partner`, `crm_lead`, `health_consent` and consent-mentioning
`mail_message` rows with `create_date > now() - interval '3 hours'` are all
**0**. No conversion was driven in the browser; the one form modal opened
(Lead Hub → Source) was closed with **Discard**. **The bridge is proven by
the test transcript only** — as the handover requires.

### (6) Deviations
D1–D4 below.

---

## 4. Deviations, each with the premise that forced it

### D1 — 4 of the 9 named UTM seeds were NOT created, because a
### case-insensitive twin already exists
`data/utm_seeds.xml` ships `organic`, `social`, `messaging` (mediums) and
`tiktok` (source) — not `cpc`, `referral`, `google`, `facebook`, `zalo`.

**Premise:** §4.4 says "Seed ONLY names absent from core utm data (check
`addons/utm/data/utm_data.xml` and live rows first)". Measured on vietuat
(17 mediums, 24 sources) and against
`addons/utm/data/utm_{medium,source}_data.xml`:

| candidate | already present as | id |
|---|---|---|
| medium `cpc` | `cpc` | 105 |
| medium `referral` | `Referral` | 87 |
| source `google` | `google` | 186 |
| source `facebook` | `Facebook` (core) | 4 |
| source `zalo` | `Zalo` | 158 |

`_utm_ids` matches with **`=ilike`**, which is case-insensitive — so an
incoming `referral` already finds `Referral` and creates nothing. Seeding a
lowercase twin would not fix a spelling; it would put TWO rows for one
channel into the vocabulary, and split that channel across two columns in
the very funnel this phase is building. T11 asserts the invariant that
actually matters (`search_count([('name','=ilike','cpc')]) == 1`) rather than
the presence of a row we deliberately did not create.

### D2 — the funnel action carries NO `search_default_` group-by; the
### outcome dimension is the pivot's second ROW instead
§4.3 asked for rows `catchment_province_id`, cols `mode_of_contact`, plus
"context group-bys `contact_status`". Those two instructions fight.

**Premise, measured in the browser** (the first drive, before the fix): with
`{'search_default_groupby_contact_status': 1}` the pivot rendered
**contact-status rows and no city axis at all** — a search-panel group-by
REPLACES a pivot's arch row groupbys. The city dimension is the one this
phase is named for, so it cannot be the one that loses. The pivot now
declares `catchment_province_id` **and** `contact_status` as rows (nesting
outcome under city, which no search default can clobber) and the action's
context is `{}`. `groupby_contact_status` is still one click away in the
search panel. T9 asserts both halves so a future edit cannot quietly restore
the clobber. Evidence: `evidence/04-lead-funnel-pivot.png`.

### D3 — neither new sidebar leaf declares `match_models`
§4.2/§4.3 said to clone the existing leaves, which carry it.

**Premise:** `health_cms_sidebar/static/src/js/cms_sidebar.js:50-100`.
`_buildMatchIndex` stores `match_models` in a **last-wins** map keyed by
model name, and `_resolveActiveItem` falls back to it whenever the current
action has no `xml_id`. `crm.lead` already belongs to *Contacts* (seq 20) and
`health.lead.touchpoint` to *Web Touchpoints* (21); a higher-sequence leaf
declaring the same model would have silently STOLEN their highlight. Both new
leaves declare their action xml-id (checked first, and exact) and nothing
else. T9 asserts `match_models` is empty on both.

### D4 — the back-fill button is gated to the operator trio **plus**
### `sales_team.group_sale_manager`, and its body runs `sudo()`
§4.2 allowed this ("+ `sales_team.group_sale_manager` if it exists — check").
It exists (`sales_team/security/sales_team_security.xml:25`) and it is the
group the live ops persona actually carries — uid 40 holds group 51
"Administrator" under Sales, which is where its `crm.lead` write ACL comes
from. `health_crm.group_health_crm_manager` alone has **no `crm.lead` ACL at
all** on this database (the only ACL rows are healthcare-owner, the web-leads
service group, `sales_team.group_sale_manager` and
`sales_team.group_sale_salesman`), and `health_user_admin.group_health_user_
admin` has none either — so the body reads and writes through `sudo()` AFTER
the group gate (the §5.24 pattern). The rows being acted on are the user's own
selection, which already passed their record rules.

---

## 5. Design notes worth carrying

**The bridge is an override of the chokepoint, not of a button.** All seven
lead→client call sites funnel through `CrmLead._get_or_create_patient`
(`health_crm/models/crm_lead.py:1343`), which also returns PRE-EXISTING
patients and re-fires from both `create()` and `write()`. So the hook is
idempotent by construction: `web_consent_bridged` is the re-fire guard AND
the reporting answer, written exactly once per lead.

**Three independent things keep it safe.** (a) The whole ladder is inside
`try/except Exception` — a marketing consent must never cost an ops user
their booking flow (T6). (b) Only the create+grant is inside
`cr.savepoint()` — ledger §5.55: catching an `IntegrityError` without one
leaves PostgreSQL aborted and the conversion dies on its own next statement.
(c) Every value comes from the LEAD record; nothing from the context, nothing
from `request`.

**Skip, never supersede.** `action_grant()` withdraws any other active
consent of the same (client, type). An automated checkbox claim must never do
that to a record a human captured, so rail B4 checks and skips BEFORE
granting rather than relying on the supersede branch being harmless.

**The `web_form` grant gate exists because core's gates are per-method `if`
branches, not a whitelist** (`health_consent.py:389-400`). A key added by
`selection_add` falls through all three and would grant with no evidence at
all. The extending module owns its own discipline: `scope_note` (which
consent wording, which submission, when) and `client_mutation_id`.

**`effective_date` is clamped to today.** `submitted_at` is sender-
controlled; a relay that FORWARD-dates would otherwise write a consent
`check_consent` refuses to see until that day arrives — a silently inert
record.

**Verified, not assumed:** `ondelete={'web_form': 'set default'}` cannot make
this module un-uninstallable despite `health.consent.write()` refusing to
touch evidence fields out of draft. Core's `_process_ondelete` wraps the
write in `safe_write` (`odoo/addons/base/models/ir_model.py:1722-1745`),
catches the `UserError` and falls back to a raw `UPDATE`. Read on the server;
ledger §5.17's trap is about `cascade` on an unconditional `unlink()` guard
and does not reach this field.

---

## 6. Data honesty

- **0 touchpoints and 0 web leads on vietuat.** The WordPress relay has never
  delivered. Campaign Review is therefore honestly empty, and the Web
  Touchpoints list says *"No web touchpoints yet"*. (The "170" in the W2.5
  report was not a touchpoint count.)
- **The funnel's baseline is the deliverable, not a defect.** 295 leads for
  this persona; 292 of them carry no `catchment_province_id`; the only value
  `mode_of_contact` takes is `phone`. The web column starts at zero and is
  supposed to.
- **`can_send_marketing()` still has zero production callers.** W3 creates
  the data those checks read; adopting the check in outbound sends is
  `health_messaging`'s change, later (binding non-goal).
- **0 `web_form` consents exist in live data**, and will until the relay
  delivers a submission that converts.

---

## 7. Non-goals honoured

No file in `health_consent` (or any module outside `health_web_leads`) was
edited — the one model extension is `_inherit` inside this module. No
ZNS/marketing-send wiring. No auto-linking of `partner_id` or patient
identity from typed contact data. No superseding of an existing active
marketing consent. No new HTTP endpoints, no gateway edits, no GA4/Ads API,
no Lead Ads, no Mode B email. **No `utm.campaign` seed and no campaign
auto-create anywhere** — the back-fill LINKS existing campaigns and T8 proves
it creates none. Retention prunes `health.lead.touchpoint.raw_payload` only.
No BI datasets (the pivots are plain Odoo views, per fact #8). No PWA-facing
change, so no version bump was due (§3).

---

## 8. Follow-ups

1. **Pre-existing, blocks nothing here, third phase in a row:** every
   `mail.thread` chatter and the CMS Contacts list raise an `AccessError`
   dialog for uid 40 — core Odoo's
   `_message_get_suggested_recipients_batch` reads `base.partner_root`
   without sudo (`addons/mail/models/models.py:557`) and this database's
   `res.partner` rules deny uid 40 partner id 1. Reproduced again during this
   drive (evidence README, "Pre-existing, not ours"). **It needs its own
   remediation ticket** — a read rule for `base.partner_root`, or a targeted
   core patch.
2. **`web_leads.raw_payload_retention_days` is `'0'` and must stay `'0'`
   until counsel names a horizon.** The mechanism is built and tested; the
   number is a legal decision (design §10, W0).
3. **The campaign register is marketing's.** Campaign Review will stay empty
   until the relay delivers; the back-fill exists for the day a raw string
   arrives before its `utm.campaign` does.
4. **A new gotcha for §5, if the reviewer agrees it is general enough:** a
   `search_default_` group-by REPLACES a pivot/graph view's arch row
   groupbys, so an action that ships both silently loses the arch dimension —
   put the second dimension in the arch as another `type="row"`, and never
   prove a pivot by reading its arch (D2). Sibling of §5.42's "get_view lies"
   and §5.62's "a default that widens under you".
5. **A second one:** `cms.sidebar.item.match_models` is a LAST-WINS index
   (`cms_sidebar.js:65`), so a new leaf that declares a model another leaf
   already owns steals its highlight for every action without an `xml_id`.
   Declare `match_action_xmlids` on satellite leaves; leave `match_models` to
   the model's primary surface (D3).

---

## 9. Fable review addendum (2026-07-29) — PASS, no fixes shipped

**Verdict: PASS.** One review subagent completed the whole-module spec check
and the independent server verification end-to-end (no assurance gap this
cycle); Fable personally read the four risky files it ranked
(`crm_lead.py` bridge ladder, `health_consent.py` grant gate,
`lead_touchpoint.py` back-fill, T6/T9 in the test file — both judged
non-vacuous: T6 stages a real exploding `create` and proves conversion +
unmarked retry + §5.55 transaction survival; T9 pre-checks the live §5.88
closure before asserting the denial).

**Independently reproduced, none taken on trust:** module 19.0.4.0.0 in the
DB; all 27 files md5-identical repo↔`/odoo/odoo-server/addons`; fresh test
re-run `0 failed, 0 error(s) of 65 tests` (PID 2146991, §5.92 log-scoped:
65 `Starting Test`, 13 × TestWebLeadsW3 by name, 0 FAIL; the 19 PID-scoped
ERROR lines are the geocoder test-mode block + W2.5's expected
unique-index refusals); service healthy after (localhost + care.biztinct.com
both 200); live-data honesty confirmed (0 web_form consents, 0 bridge
markers, 0 touchpoints, cron 140 active + param literal `'0'`, sidebar
81/82 at seq 22/23 with empty `match_models`, utm seeds 106/107/108/201,
`utm_campaign` count unchanged at 11, no QA residue — the one 24h partner
is W2.5's relay-service partner).

**Deviations D1–D4: all four premises CONFIRMED** and adopted. One count
correction: D1 skipped **5** candidates, not 4 — the five case-insensitive
twins are `cpc`/`Referral`/`google`/`Facebook`/`Zalo` (one row each, no
case-duplicates), 4 seeds shipped. Follow-up 4 → ledger **§5.93**;
follow-up 5 → **§5.94**; follow-up 1 → **`docs/strategy/open-tickets.md`
T-002** (with §5.88 as T-001), as requested — a ticket, not a footnote.

**Findings (5, all LOW, none warranting a redeploy):**
1. "Nothing outside the module was edited" is literally false — the commit
   also updates `docs/web-leads/index.html` (a docs page; no spec breach).
2. The "4 of 9" seed count above (and in the commit message) is 5 — see D1.
3. `web_lead_service.py:94`'s "(170 touchpoints ever)" comment re-asserts
   the number §6 of this report itself refutes (live count 0). Comment-only;
   left as-is for md5 discipline, fold into the next phase touching the file.
4. Behavior note: in the `skipped_identity`/`skipped_existing` branches the
   marker is written before `message_post`, so if the note ever raises
   (T-002's chatter bug), rail B1 swallows it after the marker — "one note"
   can become zero notes with no retry. Designed priority (marker and
   conversion survive) — accepted.
5. Reviewer calibration: 295 is the uid-40 persona-visible lead count under
   catchment rules; the table holds 476.
