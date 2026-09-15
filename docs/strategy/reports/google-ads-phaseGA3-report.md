# GA3 report — Google Ads: campaign cache, daily metrics sync, reporting table

**Handover:** `docs/strategy/handovers/google-ads-phaseGA3.md`
**Module:** `health_google_ads` **19.0.2.0.0 → 19.0.3.0.0**
**Evidence:** `docs/strategy/reports/google-ads-phaseGA3-evidence/`
**Date:** 2026-09-15 · **Server:** VietUcUAT (54.206.18.111)

---

## 0. Outcome in one line

The reporting the card promised is real: a scheduled job reads the last 30
account-local days of campaign names, spend, clicks and Google conversions
into a local cache, puts this system's own new-enquiry and submission counts
beside them through one SQL view, and records every attempt — including the
ones that read nothing and the ones that failed — in a sync history an
operator can open. Deployed to all three databases, 428 tests green, template
silent.

**This phase resumed an earlier implementer run that a session limit cut off.**
The uncommitted draft in the working tree was reviewed against the handover
rather than rewritten: the four models, the sync engine, the client reads and
`test_sync.py` were kept essentially as drafted; three defects in the draft
test file were fixed, the two missing test files were written, and seven
screen-level fixes came out of driving the product (§3).

---

## 1. Deployment

| Database | `health_google_ads` | Upgraded | Google Ads crons (`id`/`active`) |
|---|---|---|---|
| `carejiox` (master) | 19.0.3.0.0 installed | yes | `159`/**true** (purge sign-in sessions, GA2) · `160`/**true** (read campaign figures, GA3) |
| `carejiox_template` (golden template) | 19.0.3.0.0 installed | yes | `79`/**false** · `80`/**false** |
| `hhh` (tenant) | 19.0.3.0.0 installed | yes | `79`/**true** · `80`/**true** |

`health_care_command_channels` was copied and upgraded on all three databases
in the same sitting (no version bump, no edit) so that commit `ce224fb7`'s two
corrected test literals reached the server. Its suite is now fully green.

**Template cron re-activation: OBSERVED, and re-disabled (H78 / ledger §5.178).**
Straight after the first `-D carejiox_template -m health_google_ads` the
template reported **1** active `ir_cron` — id 80, *"Google Ads: read campaign
figures"*, this phase's own new job, switched on by its `forcecreate` data
load. Ran the runbook's remedy:

```bash
sudo -u postgres psql -d carejiox_template -c "UPDATE ir_cron SET active = false"   # UPDATE 80
sudo -u postgres psql -d carejiox_template -Atc "select count(*) from ir_cron where active"  # 0
```

The three LATER template upgrades in this pass each left the count at **0** —
the record carries `noupdate="1"`, so only the upgrade that CREATED it turned
it on. That is a useful refinement of §5.178: the risk window is the release
that introduces a cron, not every release afterwards.

Final state, all three databases, on a fresh `psql` cursor:

```
carejiox           platform_config=0 account=0 campaign=0 campaign_day=0 sync_run=0
carejiox_template  platform_config=0 account=0 campaign=0 campaign_day=0 sync_run=0
hhh                platform_config=0 account=0 campaign=0 campaign_day=0 sync_run=0
carejiox_template  ir_cron where active = 0
```

`/web/login` after the final restart: **`Host: carejiox.com` → HTTP 200**,
**`Host: hhh.carejiox.com` → HTTP 200**.
"Not loaded" grep for today: **clean** (the only hit in the whole log is
2026-09-06, on the practice clone `carejiox_r1`, and names two relay modules
this phase does not touch).

---

## 2. Files

### New in `addons/health_google_ads`

| File | What it is |
|---|---|
| `models/google_ads_campaign_day.py` | the daily cache; `cost_micros` as text, `spend` derived through `Decimal`, int4 clamp with an `overflow` flag (§5.80), the unique index in `init()` (§5.1) |
| `models/google_ads_sync_run.py` | the honesty log; created **before** the fetch so a crash still leaves an attempt |
| `models/google_ads_campaign_stat.py` | the SQL view — the one place the §8 reporting definitions live |
| `models/google_ads_sync.py` | the sync engine and the buttons, on `google.ads.account` |
| `models/google_ads_backfill_wizard.py` | "fetch older days", clamped to 365 |
| `views/google_ads_reporting_views.xml` | pivot / list / graph / search + 3 actions, the run list and form, the day list, the wizard form |
| `tests/test_sync.py` | GA3-T01 … T07, T09, T10, T12, T13, T16 |
| `tests/test_stat_view.py` | GA3-T08, T11, T15 |
| `tests/test_reporting.py` | GA3-T14, T17 |

### Edited in `addons/health_google_ads`

`__manifest__.py` (version + the GA3 paragraph), `models/__init__.py` (load
order — the day TABLE must exist before the view's `init()` runs),
`models/google_ads_account.py` (three fields into `EVIDENCE_FIELDS`, the
`syncing` card label, the zero-vs-unknown reporting line),
`models/google_ads_campaign.py` (`status_label` + the ten rollups),
`services/google_ads_client.py` (`Q_CAMPAIGNS`, `Q_DAYS`, `list_campaigns`,
`fetch_campaign_days`), `views/google_ads_account_views.xml`,
`data/ir_cron.xml`, `data/cms_sidebar_items_google_ads.xml`,
`security/ir.model.access.csv` (20 rows), `security/google_ads_security.xml`
(3 global company rules), `i18n/vi.po` (+89 entries), `tests/common.py`,
`tests/__init__.py`, and — see D2 — `tests/test_client.py` and
`tests/test_discovery.py`.

**`models/channel_center.py` needed no change** — GA2's D5 holds: the card
label map lives in `google_ads_account.py`.

---

## 3. Deviations

### D0 — the SQL view kernel is UNCHANGED

PostgreSQL accepted handover §4.4 verbatim, first try, including
`AT TIME ZONE` against a **column** zone. Quoted in full as shipped
(`models/google_ads_campaign_stat.py`, `VIEW_SQL`):

```sql
CREATE OR REPLACE VIEW google_ads_campaign_stat AS (
  WITH tz AS (
    SELECT a.id AS account_id, COALESCE(NULLIF(a.account_timezone, ''), 'UTC') AS zone
    FROM google_ads_account a
  ),
  touches AS (
    SELECT t.google_ads_account_id AS account_id,
           c.id AS campaign_id,
           ((t.occurred_at AT TIME ZONE 'UTC') AT TIME ZONE tz.zone)::date AS day,
           COUNT(*) AS submissions,
           COUNT(*) FILTER (WHERE l.id IS NOT NULL
                              AND l.external_submission_id = t.external_event_id
                              AND l.google_ads_origin IS NOT NULL) AS new_enquiries
    FROM health_lead_touchpoint t
    JOIN tz ON tz.account_id = t.google_ads_account_id
    JOIN google_ads_campaign c
      ON c.account_id = t.google_ads_account_id
     AND c.external_campaign_id = t.google_ads_campaign_id
    LEFT JOIN crm_lead l ON l.id = t.lead_id
    WHERE t.google_ads_origin IS NOT NULL
    GROUP BY 1, 2, 3
  ),
  keys AS (
    SELECT account_id, campaign_id, date AS day FROM google_ads_campaign_day
    UNION
    SELECT account_id, campaign_id, day FROM touches
  )
  SELECT row_number() OVER (ORDER BY k.account_id, k.campaign_id, k.day) AS id,
         k.account_id,
         a.company_id,
         k.campaign_id,
         k.day AS date,
         COALESCE(d.currency_id, a.currency_id) AS currency_id,
         COALESCE(d.impressions, 0) AS impressions,
         COALESCE(d.clicks, 0) AS clicks,
         COALESCE(d.spend, 0.0) AS spend,
         COALESCE(d.google_conversions, 0.0) AS google_conversions,
         COALESCE(t.new_enquiries, 0) AS new_enquiries,
         COALESCE(t.submissions, 0) AS submissions,
         (d.id IS NOT NULL) AS has_metrics
  FROM keys k
  JOIN google_ads_account a ON a.id = k.account_id
  LEFT JOIN google_ads_campaign_day d
    ON d.account_id = k.account_id AND d.campaign_id = k.campaign_id AND d.date = k.day
  LEFT JOIN touches t
    ON t.account_id = k.account_id AND t.campaign_id = k.campaign_id AND t.day = k.day
)
```

### D1 — a hand-built act_window opens OUTSIDE the CMS shell (found in the browser)

`action_open_sync_runs` and `action_open_campaign_days` were drafted as literal
dicts (`{'type': 'ir.actions.act_window', 'res_model': …}`). Driven live, the
sync history opened with **no sidebar at all**: the CMS shell resolves an
opened action against the leaf's `match_action_xmlids`, and an action with no
xmlid matches nothing (ledger §5.69/§5.93). Both now go through a shared
`_scoped_action(xmlid, context)` helper built on
`ir.actions.act_window._for_xml_id`, a new act_window
`action_google_ads_campaign_days` was added for the day list, and the sidebar
leaf's `match_models` gained `google.ads.sync.run` and
`google.ads.campaign.day`. Re-driven: evidence step 09 is now inside the
chrome with the leaf highlighted. **No interface changed** — the method names
and their return type are what the handover specified.

### D2 — two GA2 tests had to be updated, both inside this module

Neither is optional; both assert a premise GA3 deliberately retires.

* `test_client.py::test_ga2_t13f_the_reporting_surface_is_read_only` asserted
  that `list_campaigns` / `fetch_campaign_days` raise `NotImplementedError`.
  They are implemented now. The test was rewritten to assert the property that
  actually matters and must keep holding: both reads work, a caller **string**
  date is refused with `bad_window` (so no caller text can reach GAQL), and
  every `Q_*` constant starts with `SELECT` and names no mutating verb.
* `test_discovery.py::test_ga2_t08b_a_child_binds_with_its_manager_context`
  asserted `reporting_state == 'connected'` after account selection. Handover
  §5 requires that step to enqueue the first read, so the record now lands on
  `syncing`. Updated to assert `syncing` + `sync_requested_at` set, and it
  still asserts **no figures were fetched in the request**.

### D3 — "exact micros" is exact in the TEXT column, not in the money column

Handover T07 asks that `spend` equal `Decimal('12345678901234.567890')` within
float tolerance. It cannot: `spend` is a `fields.Monetary`, and Odoo rounds a
Monetary to its currency's precision on write. The account currency is **VND,
which has no sub-units at all**, so the stored spend is a whole đồng. The test
therefore asserts the property in the places where it is actually true:

* `cost_micros` is byte-for-byte the nineteen-digit string Google sent;
* `micros_to_amount('12345678901234567890')` equals
  `float(Decimal('12345678901234567890') / Decimal(10)**6)` exactly — the
  derivation loses nothing;
* `spend` equals `currency.round(...)` of that figure.

The field help already said "exact for any spend below about 9 thousand
million in the account currency"; this deviation makes the currency-precision
half of that explicit. **`cost_micros` remains the record of truth**, which is
the whole reason it is a `Char`.

### D4 — the report action carries a third search default

Handover §5 gives `action_open_report` the context
`{'search_default_last_30': 1, 'search_default_group_campaign': 1}`. Shipped
with `'search_default_group_currency': 2` as well, and the standalone action
`action_google_ads_campaign_stat` carries the same three. Reason: §5.93 — a
`search_default_` group-by REPLACES the pivot arch's row groupbys, so an
action carrying only `group_campaign` would erase `currency_id` from the pivot
the moment a user switched to it, and rail R5 (never sum two currencies) would
hold in the arch and not on the screen. With both defaults the pivot shows
*Campaign > Currency* in every view mode — proved in the browser, evidence
step 11.

### D5 — two `display_name` computes, because a model with no `name` prints its table name

Driven live, the sync-run form's title read **`google.ads.sync.run,473`** —
Odoo's fallback for a model with no `name` field, in the breadcrumb, the
window title and every link. A table name is a word from the code, not a word
a clinic should ever read. `google.ads.sync.run` now renders
*"First read — 2026-09-15 19:17:00"* (the kind label, translated, plus the
start time **in the reader's own time zone**, so the title cannot disagree
with the *Started* field under it) and `google.ads.campaign.day` renders
*"<campaign> — <day>"*.

### D6 — the queued-sync notification title is the bare channel name

The drafted title *"Google Ads: sync queued"* over the handover's body
*"Sync queued — the numbers refresh within a minute."* read as a stutter on
the screen. The handover's body string is kept verbatim; the title is now
*"Google Ads"*.

### D7 — the account form's button row is a plain div

The draft used `class="oe_button_box"`, which is styled for the stat buttons
at the top of a form and renders ordinary buttons as bare text. Changed to
`class="mb-3 d-flex flex-wrap gap-2"`; evidence step 05.

### D8 — a requested run is `initial` the first time and `manual` afterwards

Handover §5 says the cron picks `'scheduled'` or `'manual' if
sync_requested_at`, and separately gives account selection *"kind='initial'
semantics"*. Those two only reconcile if `initial` means *a requested read on
an account that has never been read*. That is the rule shipped:
`manual if account.last_sync_success_at else 'initial'`. It gives `initial`
its only possible meaning and is what evidence step 09 shows (*First read*).

---

## 4. Tests

### 4.1 The master run, verbatim

```bash
ssh VietUcUAT 'carejiox-deploy -m health_google_ads,health_care_command_channels,health_web_leads \
  -t /health_google_ads,/health_web_leads,/health_care_command_channels'
```

```
2026-09-15 09:32:25,245 3484175 INFO carejiox odoo.tests.stats: health_care_command_channels: 264 tests 54.52s 40461 queries
2026-09-15 09:32:25,245 3484175 INFO carejiox odoo.tests.stats: health_google_ads: 156 tests 40.11s 25486 queries
2026-09-15 09:32:25,245 3484175 INFO carejiox odoo.tests.stats: health_web_leads: 88 tests 19.13s 13622 queries
2026-09-15 09:32:25,245 3484175 INFO carejiox odoo.tests.result: 0 failed, 0 error(s) of 428 tests when loading database 'carejiox'
```

**0 failed, 0 error(s).** Nothing was skipped and nothing silently failed to
run (§5.83/§5.90, scoped to the run's PID per §5.92):

| Count | Value |
|---|---|
| executed test METHODS in the run | **428** (= 428 reported tests) |
| `health_google_ads` | **134** |
| `health_care_command_channels` | **220** |
| `health_web_leads` | **74** |
| this phase's own `test_ga3*` methods | **33** |
| `HttpCase` classes that actually started | **7** |

```bash
sudo grep -a " 3484175 " /var/log/odoo/odoo-server.log | grep -ac "Starting Test.*\.test_"          # 428
sudo grep -a " 3484175 " /var/log/odoo/odoo-server.log | grep -ac "Starting Test[A-Za-z0-9]*\.test_ga3"  # 33
sudo grep -a " 3484175 " /var/log/odoo/odoo-server.log | grep -aE "FAIL:|ERROR: Test|ERROR: setUpClass"  # (nothing)
```

**The two failures GA2 reported are gone.** `TestCallCenter.test_153` and
`TestChannelCenter.test_97` belonged to commit `03103e07`'s wording change and
were fixed by the orchestrator in `ce224fb7`; deploying
`health_care_command_channels` in this sitting is what made those fixes
reachable by the server. No file in that module was edited by this phase.

### 4.2 The vi.po gate

```bash
ssh VietUcUAT 'carejiox-deploy -m health_base -t /health_base:TestI18nCatalogueShape,/health_base:TestI18nCatalogueLoads'
2026-09-15 09:34:21,358 3484533 INFO carejiox odoo.tests.result: 0 failed, 0 error(s) of 5 tests when loading database 'carejiox'
```

**89 entries added** to `health_google_ads/i18n/vi.po` (197 → 286 msgids,
**0 duplicates**): 4 model names, 45 field labels, 8 selection values, 22
python strings (each with `#. odoo-python` **and** a
`#: code:addons/health_google_ads/…:0` occurrence, §5.58/§5.67), 3 action
names and 7 view-arch terms. Entries whose msgid already existed (`Paused`,
`Currency`, `Not synced`, …) were deliberately **not** re-added.

### 4.3 The GA3 test table

| ID | File | Covered by |
|---|---|---|
| T01 | `test_sync.py` | `t01a` campaign metadata in Google's camelCase, id kept `str` · `t01b` int64-as-string metrics, fractional conversions · `t01c` a 3-page `nextPageToken` fixture yields all rows · `t01d` inverted / over-long / **string** windows all refused `bad_window` · `t01e` `Q_DAYS` is not segmented by conversion action |
| T02 | `test_sync.py` | `t02` — `Asia/Ho_Chi_Minh` at 2026-09-14T17:30Z → `(2026-08-17, 2026-09-15)`; `UTC` → ends 2026-09-14; `Mars/Olympus` → UTC + a logged warning |
| T03 | `test_sync.py` | `t03` — 2 campaigns × 3 days → 2 provider rows, 6 day rows, `success` with counters, rollups filled, and a hand-typed row flipped to `provider` and renamed |
| T04 | `test_sync.py` | `t04` — revised row updated in place, omitted (campaign, day) deleted (`rows_removed=1`), a row OUTSIDE the window untouched, a campaign Google stopped listing kept |
| T05 | `test_sync.py` | `t05` — page 2 refuses on all 3 attempts → `failed`, `attempts=3`, `request_id` kept, sleeps `[2, 8]`, cache byte-identical, `last_sync_success_at` unchanged, state still `connected` |
| T06 | `test_sync.py` | `t06` — `needs_reconnect` → `skipped_reconnect`, account `action_required`, **no retry at all**, cache untouched, website status unchanged |
| T07 | `test_sync.py` | `t07` — 19-digit `cost_micros` byte-for-byte, exact `Decimal` derivation, currency-rounded storage (D3), `'abc'`/`'-1'` skipped and counted as *"2 malformed rows"* with the run still `success`, `2**31` impressions stored at the ceiling with `overflow` |
| T08 | `test_stat_view.py` | `t08` new=1 / submissions=2 on the **account-local** day, unmatched touch in `unresolved_campaign_count` and in no row · `t08b` metrics-without-touches vs touches-without-metrics (`has_metrics`) · `t08c` the same campaign number on another account borrows nothing |
| T09 | `test_sync.py` | `t09` — a REAL second connection holds `pg_try_advisory_xact_lock` → `skipped_locked`, **zero** calls to Google; after release a normal run succeeds |
| T10 | `test_sync.py` | `t10` — `action_sync_now` sets the flag, one `_trigger`, **zero HTTP**; second press warns and does not trigger again; a plain CRM user gets `AccessError`; the job then runs it as `manual` and the state returns to `connected` · `t10b` an unconnected account refuses |
| T11 | `test_stat_view.py` | `t11` pivot arch has `currency_id` **and** `campaign_id` as rows, `has_metrics` is no measure, the view carries no `search_default_`, the ACTION carries them · `t11b` the account button scopes to its own account |
| T12 | `test_sync.py` | `t12` — empty success → `rows_written=0` and a card line with no "failed"; then a failed run keeps the earlier stamp and appends *"last attempt failed (http_503)"* · `t12b` the card says **"Syncing…"**, tone `info` |
| T13 | `test_sync.py` | `t13` — 400 days clamped to 365, 3 windows per run, cursor advanced, `kind='backfill'`, windows never overlap the rolling one, both fields cleared when the cursor passes |
| T14 | `test_reporting.py` | `t14` a CRM user reads none of the three models (`AccessError`) · `t14b` a company-2 operator reads **0 rows, no error** · `t14c` an operator cannot create or write a day, a run, or the report · `t14d` the backfill wizard is operator-only |
| T15 | `test_stat_view.py` | `t15` every rollup equals the view's sum over the window; cost per new enquiry is spend ÷ our enquiries · `t15b` a zero denominator shows **"—"**, never `0` |
| T16 | `test_sync.py` | `t16` — account 1 fails non-retryably and account 2 still succeeds in the same `_cron_sync_reporting()`; the run log prunes to 200 per account |
| T17 | `test_reporting.py` | `t17` no vendor name in any label, help or selection of the four new models · `t17b` Running / Paused / Removed / Unknown and the run labels are sentences · `t17c` the action help explains zero-versus-unknown · `t17d` the sidebar leaf matches the new actions and models |

---

## 5. Security surface added

| Model | Read | Create / write / unlink | Record rule |
|---|---|---|---|
| `google.ads.campaign.day` | CRM manager, clinic admin, healthcare admin, owner, system | **`base.group_system` only** (the job runs elevated) | global `[('company_id','in',company_ids)]`, all four perms |
| `google.ads.sync.run` | same five | **`base.group_system` only** | same |
| `google.ads.campaign.stat` | same five | **nobody** (a SQL view) | global, read only |
| `google.ads.backfill.wizard` | the four operator groups + system | the same (it is a transient request form) | — |

`sync_requested_at`, `backfill_until` and `backfill_cursor` joined
`EVIDENCE_FIELDS`: a form that could set them is a form that can make this
system ask Google for anything it likes. Deliberately **not** granted:
`health_crm.group_health_crm_user` — spend is commercially sensitive, and
design §8's "area-mapped campaigns visible to area staff" stays deferred.

---

## 6. Self-review against handover §7 rails

| Rail | Proved by | Verdict |
|---|---|---|
| R1 atomic window replacement | T04, T05 (cache byte-identical after 3 failed attempts) | ✅ |
| R2 never delete a campaign row; never a day outside the window | T04 | ✅ |
| R3 exact micros | T07 — with D3's honest split: exact in `cost_micros` and in the derivation, currency-rounded in the money column | ✅ (qualified) |
| R4 account-local days | T02, T08 (17:30 UTC on the 14th → the 15th) | ✅ |
| R5 no mixed-currency sums | T11 arch + browser step 11 (grouping survives the view switch, D4) | ✅ |
| R6 one run per account | T09, a REAL second connection | ✅ |
| R7 no HTTP in a browser request | T10 (zero client calls, one `_trigger`) + browser step 06 | ✅ |
| R8 zero vs unknown | T12 + browser step 13 | ✅ |
| R9 operators only, company rule on all three | T14 | ✅ |
| R10 template stays silent | 0 active crons, 0 rows in all four tables; re-activation observed once and reported (§1) | ✅ |
| R11 provider text through `redact()`, `request_id` the only raw string | GA2's `_error_from_response`/`redact` reused unchanged; T05 asserts `request_id` survives; browser step 12 shows the redacted detail | ✅ |

**Rails I could not prove:** none. **What the browser pass could NOT prove**
is a different thing and is stated in the evidence README §4 — no real
advertising account was read, so no screenshot shows a real campaign, a real
spend figure or a real cost per enquiry. Those are proved by T03–T08 and T15
against fixtures, and will not be proved live until real credentials exist.

---

## 7. What is live, and what is not

| Capability | State | Detail |
|---|---|---|
| Website leads → CRM (GA1) | **live** | unchanged by this phase |
| Reporting sign-in (GA2) | **live** | unchanged kernel; the selection step now also queues the first read |
| **Campaign + daily cache** | **live** | `google.ads.campaign.day`, rolling 30 account-local days, `cost_micros` exact as text |
| **Scheduled daily read** | **live, and harmless by default** | 03:30 UTC; selects `reporting_state in ('connected','syncing')`; **zero such accounts on every database today**, so it logs one line and makes no provider call |
| **Sync now** | **live** | enqueues only; says so, and says when scheduled jobs are off |
| **Fetch older days** | **live** | clamped to 365, 3 windows of 30 per run |
| **The report** (list / pivot / graph) | **live** | one SQL view; `Last 30 days` + `Campaign > Currency` by default |
| **Sync history** | **live** | every attempt, capped at 200 per account |
| **Per-campaign 30-day rollups** | **live** | spend, clicks, impressions, Google conversions, new enquiries, submissions, cost per new enquiry (**"—"** when nothing to divide by) |
| Conversion upload to Google | **not built** | out of scope (non-goal) |
| Per-area spend for area-restricted staff | **not built** | deferred, recorded in the handover's non-goals |
| A real sync against a real advertising account | **NEVER RUN** | the only provider call made in this phase used a fake token and Google refused it — by design |

**The exact date window the cache holds:** the last **30 account-local
calendar days including today**, in the advertising account's own IANA zone.
In the evidence pass that was **2026-08-17 → 2026-09-15**
(`Asia/Ho_Chi_Minh`). **Today, every database holds zero days of figures**,
because no account is connected.

---

## 8. Gotchas — candidates for conventions §5

### §5.189 — an act_window returned as a hand-built DICT opens outside the CMS shell
`match_action_xmlids` can only match an action that HAS an xmlid. A button
that returns `{'type': 'ir.actions.act_window', 'res_model': …}` therefore
opens with no sidebar, no breadcrumb root and no highlighted leaf — the user
loses the whole navigation chrome and the only way back is the browser's back
button. Rule: any button that opens a list or a form **must** go through
`ir.actions.act_window._for_xml_id(<xmlid>)` and then narrow `domain`/
`context`; ship an act_window record even for a screen nothing else links to.
Sharpens §5.69 and §5.93 (which describe the leaf and the group-by, not this
failure). Found by driving the screen, not by reading the code. (Google Ads
GA3, D1.)

### §5.190 — a model with no `name` field prints `<model>,<id>` on the user's screen
`google.ads.sync.run` has no `name`, so Odoo's display-name fallback put
**`google.ads.sync.run,473`** in the breadcrumb, the window title and every
link to the row. It breaks no test and is invisible in code review. Rule: a
model a user can ever open needs `_rec_name` pointing at a real field, or a
`_compute_display_name` — and when that name carries a timestamp, build it
with `fields.Datetime.context_timestamp`, or the title disagrees with the
datetime field underneath it by the user's UTC offset. (Google Ads GA3, D5.)

### §5.191 — a `fields.Monetary` silently rounds to its currency's precision, and VND has none
An amount derived exactly through `Decimal` is rounded on write by
`Monetary.convert_to_cache`, to `currency.round(value)`. With VND
(`decimal_places = 0`) a figure of 12 345 678 901 234.567890 stores as a whole
đồng, and a test asserting the exact value fails against perfectly correct
code. Rule: when exactness matters, keep the exact figure in its own
non-Monetary column (here `cost_micros`, a `Char` holding Google's int64) and
assert exactness THERE; assert the money column against
`currency.round(...)`. (Google Ads GA3, D3.)

### §5.192 — the template's crons come back on the release that CREATES them, and only that one
§5.178 says a template upgrade switches jobs back on. Measured here across
four consecutive template upgrades in one sitting: the count went 0 → **1**
on the upgrade that first loaded the new `ir.cron` record, and stayed **0** on
the three after it, because the record ships `noupdate="1"`. The check is
still mandatory after every upgrade (§5.178's attribution surprise is real),
but the release that introduces a cron is the one to watch. (Google Ads GA3.)

### §5.193 — `AT TIME ZONE` with a COLUMN zone works per row, and is the right way to do local days
`((t.occurred_at AT TIME ZONE 'UTC') AT TIME ZONE tz.zone)::date` with `zone`
coming from a joined column converts each row in its OWN account's time zone,
inside one view, with no per-account query and no Python loop. Accepted by
PostgreSQL first try. It is the pattern for any "count this in the customer's
calendar, not the server's" report. (Google Ads GA3.)

### §5.194 — `ir.cron._trigger()` on an INACTIVE cron is a silent no-op
On the golden template (and anywhere jobs are off) a button that "queues" work
by calling `_trigger()` queues nothing at all, and the screen shows a state
that will never advance. Rule: check `cron.active` after triggering and say so
in the same notification — *"Scheduled jobs are off on this system, so this
will not run until they are on."* (Google Ads GA3.)

---

## 9. Owner inputs still needed, in plain words

1. **Real Google credentials.** Nothing in this phase has ever read a real
   advertising account. The list is unchanged from the GA2 report: a Google
   Cloud project with the Ads API turned on, its sign-in ID and secret, an
   approved developer token, and the return address
   `https://carejiox.com/channel_hub/oauth/callback/google_ads` registered
   against that project. Until those exist, every screen honestly says
   "not connected" and the daily job does nothing.
2. **Which Google campaign belongs to which area.** Each campaign row has an
   **Area** field (`catchment_id`) and a **Campaign** link to this system's own
   campaign list (`utm_campaign_id`). Both are empty until somebody fills them
   in, and until then a campaign's spend shows under no area. Nothing is
   guessed from the campaign's name.
3. **Whether to ask for 12 months of history once connected.** The system
   holds 30 days by default. "Fetch older days" will walk back up to a year,
   30 days at a time over successive nightly runs. Say the word and it is one
   click; leaving it alone costs nothing.
4. **Who should see spend.** Today the figures are visible to CRM managers,
   clinic administrators, healthcare administrators and owners. Ordinary CRM
   staff see none of it. If area nurses or area managers should see their own
   area's cost per enquiry, that is a follow-up phase, not a setting.
