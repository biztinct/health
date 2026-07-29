# Phase W2 report — `health_web_leads` ops loop, triage surfaces, hardening

**Handover:** `docs/strategy/handovers/web-leads-phaseW2.md`
**Design:** `docs/strategy/website-crm-integration.md` (§5.2, §8, §11, §15)
**Module:** `health_web_leads` 19.0.1.0.1 → **19.0.2.0.0** · **Database:** vietuat
**Implementer:** Opus 5 · **Date:** 2026-07-29
**Result:** `0 failed, 0 error(s) of 38 tests`, EXIT:0, `/web/login` HTTP 200.
No PWA-facing change → no version bump (conventions §3 not applicable).

---

## 1. What was built

Everything is inside `addons/health_web_leads`. **No file in any other module
was edited** — the three foreign surfaces this phase touches are reached
through `ir.ui.view` inheritance records and one `cms.sidebar.item` seed, all
living in our own module, exactly as the handover requires.

```
addons/health_web_leads/
  __manifest__.py                          19.0.2.0.0; +health_landing,
                                           +health_cms_sidebar
  models/web_lead_service.py               + reconcile() / _reconcile_counts()
                                           + _cron_heartbeat() / _heartbeat_user()
                                             / _heartbeat_alert()
                                           + `_lead_id` seam on _result()
  models/crm_lead.py                       + message_new() marker guard
                                           + _web_lead_marker()
  models/lead_touchpoint.py                + _compute_display_name()
  controllers/web_leads.py                 + POST /api/v1/web/leads/reconcile
                                           + record_ids on the capture audit row
  views/lead_touchpoint_views.xml    NEW    list + form + search + action + menu
  views/crm_lead_views.xml           NEW    5 inheritance records (see §5 D1)
  data/web_leads_cron.xml            NEW    daily heartbeat cron (active, gated)
  data/cms_sidebar_items_web_leads.xml NEW  CMS sidebar entry (see §5 D2)
  data/web_leads_params.xml                + heartbeat_enabled / heartbeat_user_id
  security/web_leads_security.xml           implied_ids CLEARED (M3)
  security/ir.model.access.csv             + 6 rows for group_web_leads_service
  i18n/vi.po                               64 → 123 entries, 0 inert
  tests/test_web_leads_w2.py         NEW    W2-T1,2,4,5,6,8,10,11,12 (+5 extra)
  tests/test_web_leads_endpoint.py         + W2-T3, T7, T9
```

---

## 2. Test transcript (verbatim)

```
sudo su - odoo -s /bin/bash -c "/odoo/odoo-server/odoo-bin \
  -c /etc/odoo-server.conf -d vietuat -u health_web_leads \
  --test-enable --test-tags /health_web_leads \
  --stop-after-init --workers=0 --http-port=8169 \
  --logfile=/tmp/gb/web_leads_w2d.log"
```

```
EXIT:0
HTTP:200
odoo.tests.stats:  health_web_leads: 44 tests 6.15s 4857 queries
odoo.tests.result: 0 failed, 0 error(s) of 38 tests when loading database 'vietuat'
```

**38 methods proven EXECUTED**, not merely un-failed (§5.83):

```
sudo grep -ac "Starting Test.*\.test_" /tmp/gb/web_leads_w2d.log   ->  38
```

| Case | Test | What it proves |
|---|---|---|
| W2-T1 | `test_w2_01_reconcile_splits_known_and_missing` | lead-matched + touchpoint-matched (merged) → `known`; absent → `missing`; request duplicates collapse, order preserved; a `call_cdr` touchpoint carrying the same id is **not** an answer for a form submission |
| W2-T2 | `test_w2_02_reconcile_counts_and_input_gates` | 2 created + 1 merged on one UTC day → `{created:2, merged:1}`; the neighbouring day sees none of it; >1000 ids → 422, missing/empty/non-list `submission_ids` → 422, unparsable `date` → 422; exactly 1000 is accepted |
| W2-T3 | `test_w2_03_reconcile_auth_and_scope` (Http) | `web_lead.write`-only token → **403**; no token → 401; garbage token → 401; the `web_lead.read` token → 200 with no `counts` key; the 422 gates answer over HTTP too |
| W2-T4 | `test_w2_04_heartbeat` | disabled → nothing; enabled + 48 h stale → exactly one activity; run again → still one; a fresh touchpoint → none |
| — | `test_w2_04b_heartbeat_user_resolution` | the configured watcher wins; `'not-an-id'` / `'0'` / a dangling id fall through without raising; the fallback chain always resolves somebody |
| W2-T5 | `test_w2_05_message_new_with_known_marker_returns_the_lead` | header **and** body **and** subject marker variants each return the existing lead, lead count unchanged, log note posted naming the submission id |
| W2-T6 | `test_w2_06_message_new_without_a_known_marker_creates` | no marker / unknown marker / malformed marker / junk header → normal create path, count +1 |
| — | `test_w2_06b_marker_parser_never_raises` | 8 hostile `msg_dict` shapes (None, str, int, bytes, an un-str-able object) → `False`, never an exception |
| W2-T7 | `test_w2_07_capture_as_the_narrowed_service_user` (Http) | full OAuth round trip as the M3-narrowed account: create **and merge**, 2 touchpoints, 1 lead, `create_uid` = the service user |
| W2-T8 | `test_w2_08_acl_negative` | the group's implied closure is now **itself alone**; its reachable ACL set is exactly the 8 expected models; `res.partner.create` and `account.move.search` raise `AccessError`; `crm.lead` / `health.lead.touchpoint` still work |
| — | `test_w2_08b_ews_read_survives_and_it_is_not_ours_to_close` | the honest negative — see §3 |
| W2-T9 | `test_w2_09_audit_rows_carry_record_ids` (Http) | created / duplicate / merged audit rows all carry `resource_ids = <lead id>`; `rejected_spam` carries none; `_lead_id` never appears in the envelope |
| W2-T10 | `test_w2_10_create_race_answers_duplicate` + `…10b_merge_race…` | both `psycopg2.IntegrityError` branches, mocked narrowly on one model's `create` with the savepoint untouched → both answer `duplicate`, the merge case with the candidate's `lead_ref` |
| W2-T11 | `test_w2_11_views_and_menu` | 9 xmlids load; `get_combined_arch` (§5.42) proves the tab merged into **both** the opportunity form and the CMS contact form, the 4 modal fields, the filters on both search views; `get_view` proves they render; the sidebar item is a childless leaf; the touchpoint display name is not `health.lead.touchpoint,N` |
| W2-T12 | `test_w2_12_po_every_entry_is_readable` + `…12b…` | every entry has `#. module:` (§29), a `#:` occurrence (§5.67) and a matching marker (§5.58) — **0 inert**; 9 required W2 msgids present; and the runtime half proven live: a `_()` string, the `res.groups` name, the `api.key.scope` name and a field `help` all read Vietnamese under `lang='vi_VN'` |

No test went red on any run of this phase.

The `ERROR: cannot execute INSERT in a read-only transaction` lines in the log
are the framework's **readonly-cursor retry on `/oauth/token`** — the gateway's
own undecorated route, exactly as W1 documented. Neither of our two routes
produces one: both declare `readonly=False` from the first statement (§5.38).

---

## 3. M3 — the ACL closure, before and after

The W1 review's recursive closure query, re-run on vietuat **after** the
narrowing:

```sql
WITH RECURSIVE cl AS (
  SELECT g.id FROM res_groups g
  JOIN ir_model_data d ON d.model='res.groups' AND d.res_id=g.id
  WHERE d.module='health_web_leads' AND d.name='group_web_leads_service'
  UNION SELECT r.hid FROM res_groups_implied_rel r JOIN cl ON r.gid = cl.id)
SELECT g.id, g.name->>'en_US' FROM res_groups g JOIN cl ON cl.id=g.id;
```

```
 id  | group_in_closure          BEFORE: 16 groups, including
-----+-------------------        User: All Documents, User: Own Documents Only,
 656 | Web Leads Service         Role / User, Healthcare: Base Access, …
(1 row)
```

```sql
… SELECT m.model, bool_or(a.perm_read) r, bool_or(a.perm_write) w,
         bool_or(a.perm_create) c, bool_or(a.perm_unlink) u
  FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id
  WHERE a.group_id IN (SELECT id FROM cl) AND a.active GROUP BY m.model;
```

```
           model           | r | w | c | u        BEFORE: 319 models, including
---------------------------+---+---+---+---       res.partner  (r/w/c),
 crm.lead                  | t | t | t | f        account.move + .line (r),
 crm.stage                 | t | f | f | f        sale.order (r/w/c),
 crm.team                  | t | f | f | f        crm.tag (r/w/c),
 health.catchment.province | t | f | f | f        health.ews.score (r),
 health.lead.touchpoint    | t | f | t | f        and ~300 more
 utm.campaign              | t | f | f | f
 utm.medium                | t | f | t | f
 utm.source                | t | f | t | f
(8 rows)
```

**No salesman group, no `res.partner`, no accounting rows.**

### The honest version — what the service USER can still reach

The query above is about the GROUP. The account also carries
`base.group_user`, which the handover keeps deliberately (`mail.message` for
`message_post`, `ir.sequence` read for the contact code, `res.partner` read).
Measured on user 6103 after the change:

```
models_user_can_touch_now | models_the_salesman_arm_added | models_fully_removed
                      294 |                            43 |                   25
```

```
       model       | r | w | c | u      (the rows the W1 review named)
-------------------+---+---+---+---
 account.move      | f | f | f | f      gone
 account.move.line | f | f | f | f      gone
 sale.order        | f | f | f | f      gone
 crm.tag           | f | f | f | f      gone
 res.partner       | t | f | f | f      create/write REMOVED, read remains
 crm.lead          | t | t | t | f      preserved, now via our own row
 health.ews.score  | t | f | f | f      STILL READABLE — see below
```

**`health.ews.score` is not ours to close, and the handover's fact #9 was half
right.** Read on that model comes from `health_base.group_healthcare_base`, as
the review said — but on this database `base.group_user` **implies**
`group_healthcare_base` (`res_groups_implied_rel` row `gid=1 → hid=346`), which
is the *reverse* of what `health_base/security/health_security.xml:23`
declares. It is live data, not module data. Consequence: **every internal user
on vietuat can read EWS scores**, and removing our salesman implication cannot
change that without stripping `base.group_user` from the service account, which
would break `message_post` and the contact-code sequence.

I did not "fix" it — inverting a group implication that every internal user
depends on is far outside this phase, and it is not a web-leads problem.
`test_w2_08b` asserts the *mechanism* (and `skipTest`s itself if somebody ever
corrects the edge), so the day it is fixed the test says so instead of quietly
passing. **Recommend a separate look at that edge**; it is the kind of thing
that makes every future privilege audit read better than it is.

### Extra ACL rows I had to add

Exactly the six the handover specified — `crm.lead` (r/w/c, no unlink),
`crm.team` (r), `crm.stage` (r), `utm.source` (r/c), `utm.medium` (r/c),
`utm.campaign` (r). **Nothing beyond the handover's list was needed**, and
W2-T7 proves it by driving the whole create-and-merge path over HTTP as the
narrowed user. Three things I expected to bite and did not, each because the
code already sudo's or the framework already does:

- `care.conversation` create (the `health_care_command` lead hook) — its
  `_find_or_create_for` opens with `Conv = self.sudo()`, so the hook works for
  any user. Without that it would have failed *silently*, inside the hook's own
  `except Exception`, and the merged-lead triage row would have gone missing.
- `ir.sequence` write for the contact code — `_generate_unique_contact_code`
  sudo's the search/create and calls `next_by_id()` on the sudo'd record.
- `mail.followers` create (auto-subscribe) — core sudo's it; group 1 has read
  only, which would otherwise have broken every `message_post`.

---

## 4. Reconcile + heartbeat smoke transcripts

### 4.1 Reconcile, live over TLS on `care.biztinct.com`

Two temporary OAuth clients were provisioned for the smoke (both scopes /
write-only) and **deleted afterwards** — the W1 client's secret is not stored
anywhere and was not touched.

```
--- (a) token ---
{"access_token": "hg_fd23ddda4…redacted", "token_type": "Bearer",
 "expires_in": 3600, "scope": "web_lead.read web_lead.write"}

--- (b) capture one real submission ---
{"success": true, "data": {"status": "created", "lead_ref": "01 032422026",
                           "submission_id": "w2-smoke-real-0001"}}

--- (c) reconcile: one known + one fabricated, with today's date ---
{"success": true, "data": {
   "known":   ["w2-smoke-real-0001"],
   "missing": ["w2-smoke-never-sent-0002"],
   "counts":  {"created": 1, "merged": 0}}}

--- (d) reconcile without date: no counts key at all ---
{"success": true, "data": {"known": [], "missing": ["w2-smoke-never-sent-0002"]}}

--- (h) second submission, same person -> merged ---
{"success": true, "data": {"status": "merged", "lead_ref": "01 032422026",
                           "submission_id": "w2-smoke-real-0003"}}

--- (i) spam submission -> 200, no row ---
{"success": true, "data": {"status": "rejected_spam",
                           "submission_id": "w2-smoke-spam-0004"}}

--- (j) reconcile again: the counts move ---
{"success": true, "data": {
   "known":   ["w2-smoke-real-0001", "w2-smoke-real-0003"],
   "missing": ["w2-smoke-spam-0004"],          <-- the spam id, forever
   "counts":  {"created": 1, "merged": 1}}}

--- (e) write-only token -> 403 ---
HTTP:403  {"success": false, "error": "Token is missing a required scope (web_lead.read)"}
--- (f) no token -> 401 ---
HTTP:401
--- (g) input gates ---
no-ids     HTTP:422
1001-ids   HTTP:422
bad-date   HTTP:422
```

Line (j) is the `rejected_spam` contract made visible: the spam id is reported
`missing` and always will be, because no row exists for it by design. The
endpoint docstring says this in as many words, and it belongs in the Proima
spec: **the relay marks a spam submission done from the CAPTURE reply and must
never re-post it**, or it loops forever.

### 4.2 The audit rows (review L2), read from psql

```
 id | route                       | status | resource_type          | resource_ids
----+-----------------------------+--------+------------------------+--------------
 91 | /api/v1/web/leads           |    200 | crm.lead               | 1342     <- duplicate
 90 | /api/v1/web/leads/reconcile |    200 | health.lead.touchpoint |
 89 | /api/v1/web/leads           |    200 | crm.lead               |          <- rejected_spam
 88 | /api/v1/web/leads           |    200 | crm.lead               | 1342     <- merged
 87 | /api/v1/web/leads/reconcile |    422 |                        |
 84 | /api/v1/web/leads/reconcile |    401 |                        |
 83 | /api/v1/web/leads/reconcile |    403 |                        |
 80 | /api/v1/web/leads           |    200 | crm.lead               | 1342     <- created
```

All four capture outcomes, exactly as §4.6 specifies. The reconcile route
records `health.lead.touchpoint` as its resource type and no ids — it answers
about a set of submission ids, not about records.

### 4.3 Heartbeat dry run

The shipped state first, straight from the database:

```
 id  | cron_name                                    | active | interval | nextcall
-----+----------------------------------------------+--------+----------+---------------------
 139 | Web Leads: heartbeat (relay delivery canary) | t      | 1 days   | 2026-07-30 01:57:26

 web_leads.heartbeat_enabled | False
 web_leads.heartbeat_user_id | (empty)
```

Then the four arms, run in ONE `odoo-bin shell` transaction that was **rolled
back** — so the staleness was staged without touching a single live row, and
nothing below persisted:

```
SHIPPED PARAM       : 'False'
A) gate off, run    : False | activities: 0
B) gate on + stale  : True  | activities: 1
C) run again        : False | activities: 1
   activity user    : ash@biztinct.com | type: To-Do | deadline: 2026-07-29
   activity note    : <p>The last website submission was received on
                      2026-07-27 02:00:55 (over 24 hours ago). Check the
                      WordPress relay and the gateway audit log before ass…
D) pipe recovers    : False | activities: 0
ROLLED BACK - nothing above persists
```

Fresh-cursor verification afterwards: `heartbeat_enabled` still `False`,
`heartbeat_user_id` still empty, 0 heartbeat activities. `ash@biztinct.com` is
the fallback (first gateway administrator) because no watcher is configured —
**ops should set `web_leads.heartbeat_user_id` and flip
`web_leads.heartbeat_enabled` to `True` the day the relay goes live**, and not
before: until then every night is legitimately quiet.

### 4.4 Browser evidence

`docs/strategy/reports/web-leads-phaseW2-evidence/` — 9 screenshots with the
click-by-click path, the persona's groups, the console log and the server-side
rows, in that directory's `README.md`. The drive starts from the CMS landing
page, never from a deep link; that is how D1 below was found.

---

## 5. Deviations

The handover expected none. There are two, both **additions**, both forced by
driving the real UI, and both implemented with the mechanism the handover
already sanctions (view-inheritance / data records inside our own module).

### D1 (material) — the Web Attribution tab and the filters also had to reach a THIRD lead surface

Handover fact #5 names two lead surfaces: the Lead Hub Source spoke modal and
`health_crm.view_healthcare_opportunity_form`. I built both. Then I logged in
as a real ops persona and clicked **CRM › Contacts › a lead** — and landed on
neither.

`crm.lead` has **three** standalone primary form views on this database:

| view | priority | inherit_id | reached by |
|---|---|---|---|
| `health_crm.view_healthcare_opportunity_form` | 1 | — | `/odoo` Sales & CRM lists; hub centre click |
| `health_landing.view_lead_source_modal` | 16 | — | Lead Hub → Source spoke |
| **`health_crm.view_crm_contact_form_crm_center`** | **50** | — | **the CMS sidebar's `Contacts`** (`action_crm_contact_list_native`, `crm_center_views.xml:53`) |

The third is what the CMS-shell persona actually opens, and it is where a
receptionist working a lead lives. The same is true of the search view: the
CMS Contacts list binds `health_crm.view_crm_contact_search_crm_center`, a
separate primary search view, so an inherit of `crm.view_crm_case_opportunities_filter`
never reaches it and "Needs review (web)" would have existed only on a list
this persona does not open.

This is ledger §5.41 with a different model — "which view renders" is a
question you answer in the browser, not in a handover. Shipped two more
inheritance records (`view_crm_contact_form_crm_center_web_attribution`,
`view_crm_contact_search_crm_center_web_leads`) carrying the same fields,
the same filters and deliberately the same strings, so both tabs share one set
of vi.po entries. Screens 03/04/05 are the proof. `test_w2_11` asserts the
merge on all four views, so a future edit cannot quietly drop one.

I judged the phase's own §1 ("the Web-Attribution triage surfaces **on the
forms ops actually use**") to outrank the enumeration in §4.3, and the §2
non-goals do not forbid it. If you disagree, the two records are self-contained
and removing them is a two-line revert.

### D2 (minor) — a `cms.sidebar.item` for the touchpoint list

§4.3 asks for "a menu entry under the CRM menu ops actually uses (match where
health_crm hangs its config menus)". I shipped exactly that —
`Sales & CRM › Configuration › Web Touchpoints`. Ledger §5.69 then applies in
full: a backend menuitem **is not a reachable surface** for the CMS persona,
who never leaves `/bizapp`. Without a sidebar seed the entire touchpoint
deliverable would have been deep-link-only, which the DoD rejects as evidence.

Added `data/cms_sidebar_items_web_leads.xml`, seeded into
`health_cms_sidebar.section_crm` at sequence 21 as a **childless sibling** —
§5.69(a): an item with children stops navigating and breaks its parent, so
Contacts was re-clicked after the deploy to confirm it still opens (it does).
`test_w2_11` asserts both the leafness and the absence of children. New
manifest dependency `health_cms_sidebar` (already installed; no loop — nothing
depends on `health_web_leads`, §5.71 walked).

### Not deviations, but worth stating

- **`health_landing` is now a manifest dependency.** Unavoidable: an
  inheritance record cannot `ref` a view from a module that is not a
  dependency. Transitive additions over what `health_api_gateway` already
  pulled: `health_user_admin`, `advanced_pricing`, `health_field_requirements`
  — all installed. No dependency loop (§5.71 checked transitively).
- **`implied_ids` had to be cleared with `eval="[(5, 0, 0)]"`, not by deleting
  the field.** §5.69(b): a data update writes only the fields it names, so
  simply removing the line would have left the salesman implication in place
  through the whole upgrade. The closure query in §3 is what proves it landed.
- **`HEARTBEAT_SUMMARY` is deliberately NOT translated.** It is the dedupe key
  the cron searches on; a summary that varies with the reader's language is not
  a key. The note body beside it is translated, and that is the sentence a
  human reads. `test_w2_12` asserts the *absence* of that msgid so nobody
  "helpfully" adds it later.
- **`health.lead.touchpoint` gained a `_compute_display_name`.** Without it
  every breadcrumb and m2o label read `health.lead.touchpoint,97`. The label
  comes from `fields_get`, which returns the translated selection, so it
  follows the reader's language and costs the catalogue no new msgid.
- **Extra tests.** `test_w2_04b`, `06b`, `08b`, `10b`, `12b` are additions, not
  replacements; W2-T1–T12 are exactly the numbered cases in the handover.
- **No §5.38-family cursor issue** bit the reconcile route. Fact #1 was right:
  the hand-rolled `readonly=False` route works, and the log shows the retry
  firing only on the gateway's own `/oauth/token`.

---

## 6. The marker format, verbatim for the Proima spec

```
Body — the FINAL line of the CF7 notification email:

    [web-lead:<submission_id>]

Header — where the transport allows it:

    X-Web-Lead-Submission: <submission_id>

<submission_id> is the SAME uuid the webhook payload carries. The plugin
generates it once at `wpcf7_before_send_mail` so both the email and the
webhook see it. Accepted shape: 8–64 characters from [A-Za-z0-9-].
```

Server side: header first (case-insensitive), else
`re.compile(r'\[web-lead:([A-Za-z0-9-]{8,64})\]')` over `body` then `subject`.
A known id returns the existing lead and posts a log note on it; anything else
falls through to `super()`. The parser cannot raise.

**One caveat the spec must carry.** Odoo's stock `message_parse`
(`mail_thread.py:1765-1874`) builds a **fixed key set** and does not copy
custom headers into `msg_dict` — so on an unmodified deployment the header
branch never fires and the **body line is the load-bearing path**. It is
implemented anyway (it costs nothing and works the moment a parser hook keeps
headers), but the WordPress plugin must treat the body line as mandatory, not
as the fallback. `test_w2_05` exercises header, body and subject variants, so
whichever path a future Odoo makes real is already covered.

Nothing about this is live yet: vietuat still has **no `mail.alias.domain` and
zero fetchmail servers**, so nothing reaches the five `crm.lead` aliases. That
is the point — the door is now safe to open.

---

## 7. New gotchas for §5 (please add)

**A. `base.group_user` implies `health_base.group_healthcare_base` on vietuat —
the reverse of what the module declares — so every internal user carries the
healthcare base ACLs.** `health_security.xml:23` says
`group_healthcare_base → base.group_user`; `res_groups_implied_rel` also holds
`gid=1 → hid=346`, a live-data edge nobody's XML asks for. Any privilege audit
that reasons from the addon source will overstate what a narrowing achieves —
`health.ews.score` read is reachable by every logged-in user and no module
change can take it away. Rule: **compute a privilege closure from
`res_groups_implied_rel`, never from the security XML**, and re-run it on the
target database after the change (§3 has the query).

**B. `mail.activity` supports MODEL-LESS activities, and they are the honest
shape for an alert about an absence.** `res_model_id` is `required=False`; the
`_check_res_id_is_set_if_model` CHECK explicitly allows an empty `res_model`
when `user_id` is set, `action_notify()` skips them (`self.filtered('res_model')`)
and `_compute_res_name` handles them. The heartbeat has no record to point at —
the alert is that nothing arrived — and hanging it on the `ir.cron` row would
have made "mark as done" an `AccessError` for the ops user who receives it
(activity write access is checked against the *related document*). Free
activities still appear in the systray and in My Activities.

**C. the §2 executed-methods grep is fragile to a digit in a class name.** The
W1 report already showed that `grep -ac "Starting .*Http"` returns 0 for a
correctly-run `HttpCase` whose class is not named `…Http…`. The obvious
replacement, `Starting Test[A-Za-z]*\.test_`, has the same failure mode one
level down: it silently drops `TestWebLeadsW2` because of the `2`. Use
`grep -ac "Starting Test.*\.test_"` for the count and
`grep -ao "Starting Test[A-Za-z0-9]*\.test_[a-z0-9_]*"` for the list, and
**compare the count to the number you expect** — that comparison, not the
regex, is what §5.83 actually asks for.

**D. `crm.lead` has THREE standalone primary form views and TWO primary search
views on this database.** §5.41 is stated for `res.partner`; it is worse for
`crm.lead`, and the one with the highest priority (50,
`view_crm_contact_form_crm_center`) is the one the CMS sidebar opens. Before
adding a tab or a filter to "the lead form", enumerate
`SELECT id, priority, inherit_id FROM ir_ui_view WHERE model='crm.lead' AND
mode='primary'` and then **click the surface** to see which one renders.

---

## 8. Deferred / not built (binding non-goals, unchanged)

- No connector UI / credential self-service (W2.5). No Lead Ads endpoints.
  No email-ingestion Mode B activation — this phase only makes it SAFE.
- No reporting pivots, no consent bridge (W3).
- `health_care_command`'s hook is untouched; the spam-conversation noise is
  accepted, as decided at design time.
- No Python edits outside `health_web_leads`; no W1 field renamed; the capture
  endpoint's contract is byte-identical for Proima.
- The `base.group_user → group_healthcare_base` edge (§7 A) is reported, not
  touched.

## 9. One thing the next phase should know

The reconcile endpoint is live and the relay can drive it today, but
**`web_leads.heartbeat_enabled` is `False` and should stay that way until the
WordPress relay actually starts delivering** — otherwise the canary fires every
night before there is anything to watch. When it is switched on, set
`web_leads.heartbeat_user_id` to a named owner first; the fallback currently
resolves to the first gateway administrator, which is a person who has not
agreed to own this.
