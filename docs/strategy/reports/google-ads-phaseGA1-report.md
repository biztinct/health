# GA1 — Google Ads: acquisition card + website-lead attribution — implementation report

Handover: `docs/strategy/handovers/google-ads-phaseGA1.md`
Design: `docs/strategy/google-ads-channel-design.md`
Conventions: `docs/strategy/HANDOVER-CONVENTIONS.md`

---

## 1. Deployment

| Item | Value |
|---|---|
| Start commit | `551c9c22` (docs: design Google Ads acquisition and reporting integration) |
| Final commit | the ONE commit this phase produced: `feat(google-ads): GA1 — acquisition card + website-lead attribution`, the tip of branch `19.0`. Its hash is deliberately not written here — a commit cannot contain its own hash, and two attempts to amend one in simply moved it. `git log --oneline -1` on `19.0` is the authority. |
| Branch | `19.0` (not pushed — the orchestrator pushes at the end of the programme) |

Module versions after the three-database ritual (`carejiox-deploy -d -i health_google_ads
-m health_care_command_channels,health_web_leads`, then `-D carejiox_template`, then `-D hhh`):

| Database | health_google_ads | health_care_command_channels | health_web_leads |
|---|---|---|---|
| carejiox | 19.0.1.0.0 installed | 19.0.12.2.0 installed | 19.0.5.0.0 installed |
| carejiox_template | 19.0.1.0.0 installed | 19.0.12.2.0 installed | 19.0.5.0.0 installed |
| hhh | 19.0.1.0.0 installed | 19.0.12.2.0 installed | 19.0.5.0.0 installed |

- `carejiox_template` active cron count after the ritual: **0**.
- `"some depends are not loaded" / "Some modules are not loaded"` grep: **no entry dated
  2026-09-15**. The only hit in the whole log is a historical 2026-09-06 line for a database
  called `carejiox_r1` (`biz_platform_channel_relay`, `health_channel_relay`) which predates
  this phase and belongs to the relay work stream.
- The practice clones `vietuat` and `codex_fb_center_reply` were **not** touched, upgraded or
  tested against.

_(Test results, HTTP checks and QA-residue counts: §4, §6.)_

---

## 2. Files

### New module `addons/health_google_ads` (19.0.1.0.0)

```
__init__.py, __manifest__.py
services/__init__.py, services/attribution.py          pure helpers, no ORM (kernel, verbatim)
models/__init__.py
models/google_ads_account.py                           google.ads.account
models/google_ads_campaign.py                          google.ads.campaign
models/crm_lead.py                                     _inherit crm.lead — first-touch snapshot
models/lead_touchpoint.py                              _inherit health.lead.touchpoint
models/web_lead_service.py                             _inherit web.lead.service — the two seams
models/channel_center.py                               _inherit care.channel.connection
security/ir.model.access.csv, security/google_ads_security.xml
data/cms_sidebar_items_google_ads.xml
views/google_ads_account_views.xml, views/crm_lead_views.xml, views/lead_touchpoint_views.xml
static/src/center/google_ads_center.scss
i18n/vi.po                                             100 entries, 0 duplicates,
                                                       every python msgid matched to source
tests/__init__.py, tests/common.py, tests/test_attribution.py, tests/test_center.py,
tests/test_security.py, tests/test_website_test.py
```

### `addons/health_care_command_channels` (19.0.12.1.16 → 19.0.12.2.0)

- `models/channel_center.py` — `_center_extra_cards()` (default `[]`) + the insertion loop
  before `return cards` in `center_overview()`. Nothing else.
- `static/src/center/channel_center.js` — the `external_action` branch at the top of
  `onPrimary`; the `google_ads` entry in `CHANNEL_STYLE`.
- `static/src/center/channel_center.xml` — the tagline / capabilities / lines block after
  `card.notice`, and the "View leads" ghost button in the actions block.
- `tests/test_center.py`, `tests/test_call_center.py`, `tests/test_platform_go_live.py`,
  `tests/test_meta_center.py` — the FORCED edits (see §3, D1 and D5).
- `__manifest__.py` version + a 19.0.12.2.0 changelog paragraph; `i18n/vi.po` + "View leads".

### `addons/health_web_leads` (19.0.4.2.0 → 19.0.5.0.0)

- `models/web_lead_service.py` — `wbraid`/`gbraid` in `_create_lead` AND `_touchpoint_vals`;
  `_lead_extra_vals` / `_touchpoint_extra_vals` and their call sites; the stale
  "170 touchpoints" comment replaced with a dated measurement.
- `models/lead_touchpoint.py` — stored computed `company_id` + the `_check_attached`
  company-mismatch refusal.
- `models/care_conversation_attribution.py` — `_LEAD_ATTRIBUTION_FIELDS` extended with the
  eight Google copy fields (not `google_ads_influenced`).
- `security/catchment_rules.xml` — the GLOBAL company rule on the touchpoint.
- `security/ir.model.access.csv` — ONE read-only row (see §3, D4).
- `i18n/vi.po` — obsolete `#~` blocks and dead `touchpoint_type` xmlids repaired (§3, D5).
- `tests/test_web_leads_ga1.py` (new) + `tests/__init__.py`.
- `tests/test_web_lead_service.py`, `tests/test_web_leads_w2.py`,
  `tests/test_web_leads_w3.py` — FORCED edits (§3, D4 and D5).
- `__manifest__.py` version + description paragraph.

Nothing outside these three modules was edited.

---

## 3. Deviations

### D1 — the card-count pins (FORCED, pre-approved in §6.4 — plus a FOURTH the handover did not enumerate)

`center_overview()` now returns a ninth, acquisition card, so every test that
asserted the exact eight-key list had to say which list it means. The handover
named three; a fourth exists and was found only by running the suite:

| File | Change |
|---|---|
| `tests/test_center.py` T97 | filter on `kind`, plus a new assertion that the acquisition card is present and sits after `fb` when `health_google_ads` is installed |
| `tests/test_call_center.py` T155 | filter on `kind` |
| `tests/test_platform_go_live.py` `_cards()` helper | filter on `kind` (one place instead of every call site) |
| **`tests/test_meta_center.py` T139 `test_139_catalogue_shape`** | **not named in the handover** — same class, same fix |

### D2 — `native_eligibility` is guarded in `write()`, not by a field-level `groups=`

The handover asked for `groups="base.group_system"` on the field. A field-level
`groups=` hides the value from READS too, so the "Google lead forms" page would
have been blank for exactly the tenant it exists to inform — and a `required`
Selection behind a group is a create-path hazard for a non-member. The field is
therefore readable by anyone who can open the account and `readonly` in the
view, while `write()` raises `AccessError` on any attempt to change it by a
non-platform-admin (loudly, not by silent stripping). The contract the handover
states — "cannot leave `healthcare_blocked` except by a `base.group_system`
user, and no UI offers it to tenants" — is unchanged and tested (GA1-T13d).

### D3 — the touchpoint form gets a PAGE, not a group after "Click Identifiers"

`//group[@string='Click Identifiers']` is not a legal inheritance selector on
Odoo 19 (conventions §5.21 — `string` is translatable). The first deploy died
on it. The nine Google fields are a notebook page anchored on
`//page[@name='raw_payload']` instead, which is both legal and a better home.

### D4 — two READ-ONLY ACL rows outside the handover's sanctioned list

Both were forced by failures this phase's own test run surfaced, and the second
of them is a **live product defect that predates this phase**:

1. `health_web_leads/security/ir.model.access.csv` —
   `health.lookup.value` read for `group_web_leads_service`. Since the
   dropdown-vocabulary conversion, `_create_lead` and `_touchpoint_vals`
   resolve `mode_of_contact` and `touchpoint_type` through
   `health.lookup.value`, which the relay's service user has no ACL for. **The
   live `POST /api/v1/web/leads` endpoint answered HTTP 403 to every website
   submission**, and `action_test_pipeline` on the website connector failed the
   same way. Five pre-existing tests were red on it
   (`test_w25_05`, `test_w25_05b`, `test_15_full_round_trip`, `test_w2_07`,
   `test_w2_09`) and so were four of this phase's own.
2. `health_google_ads/security/ir.model.access.csv` —
   `google.ads.account` read for the same group. `crm.lead.google_ads_account_id`
   is `check_company=True`, and `_check_company` reads the account's company as
   the writing user.

`health_web_leads/tests/test_web_leads_w2.py::test_w2_08_acl_negative` pins the
exact reachable-model set for that group and went red, which is the tripwire
working. Its expected set was extended (FORCED) with a comment explaining both
rows. Neither model carries patient data and both are read-only.

### D5 — pre-existing test rot repaired (FORCED, three files + one catalogue)

Red before this phase, all traceable to the dropdown-vocabulary conversion that
replaced two Selections with `health.lookup.value` many2ones:

| File | Was | Now |
|---|---|---|
| `health_web_leads/tests/test_web_lead_service.py` T01 | `lead.mode_of_contact` (AttributeError) | `lead.mode_of_contact_code` |
| `health_web_leads/tests/test_web_lead_service.py` T20 | `env.ref(...field_health_lead_touchpoint__touchpoint_type)` (ValueError) | `...__touchpoint_type_id` |
| `health_web_leads/tests/test_web_leads_w3.py` T09 | `name="mode_of_contact"` in the funnel arch | `name="mode_of_contact_id"` |
| `health_care_command_channels/tests/test_meta_center.py` T133c3 | created a second province called "Hà Nội" while the deployment already has one (id 2) — the name matcher picks the live row (ledger §5.50) | search-or-create |
| `health_web_leads/i18n/vi.po` | 10 obsolete `#~` blocks + 7 occurrences pointing at `touchpoint_type` xmlids that no longer exist | obsolete blocks removed, the field occurrence repointed to `touchpoint_type_id`, the five dead selection entries removed |

### D6 — "Partially connected" after a server-only test, per §4.2 not §9

The handover's §9 browser script says the chip should still read "Setup needed"
after a server test; its own §4.2 defines `overall_status` as `partial` when
`website_status` is in `(test_passed, receiving)` **or** reporting is connected.
The two contradict. The normative data-model definition (§4.2) is implemented,
so the chip reads **"Partially connected"** after a passing server test, and the
capability row underneath still reads the honest "Test passed; awaiting live
lead" rather than "Receiving". GA1-T12g asserts exactly that, including that it
is never "Connected".

### D7 — `_search_google_ads_influenced` resolves ids itself

See §7 gotcha G1. The `web_touchpoint_ids.google_ads_origin` traversal the
handover suggests is replaced by an explicit, sudo'd id lookup; the filter
semantics are identical and the outer search still applies the reader's rules.

---

## 4. Tests

Run on the **master** through the wrapper, all four tags in one run:

```bash
ssh VietUcUAT 'carejiox-deploy -d -m health_google_ads,health_care_command_channels,health_web_leads \
  -t /health_google_ads,/health_web_leads,/health_care_command_channels,/health_care_command'
```

Result lines, verbatim (PID 3404613):

```
2026-09-15 02:50:10,024 3404613 INFO carejiox odoo.tests.stats: health_care_command_channels: 264 tests 56.46s 40458 queries
2026-09-15 02:50:10,024 3404613 INFO carejiox odoo.tests.stats: health_google_ads: 57 tests 19.66s 12627 queries
2026-09-15 02:50:10,024 3404613 INFO carejiox odoo.tests.stats: health_web_leads: 88 tests 19.33s 13622 queries
2026-09-15 02:50:10,025 3404613 INFO carejiox odoo.tests.result: 0 failed, 0 error(s) of 343 tests when loading database 'carejiox'
```

Executed-METHOD count (conventions §5.83/§5.90, scoped to the run's PID per §5.92):

```bash
sudo grep -a "3404613" /var/log/odoo/odoo-server.log | grep -ac "Starting Test.*\.test_"
343
sudo grep -aE "3404613.*(FAIL:|ERROR:)" /var/log/odoo/odoo-server.log
(no output)
```

**343 executed methods = 343 reported tests**, so nothing silently failed to
run. Per module: `health_care_command_channels` 264, `health_web_leads` 88,
`health_google_ads` 57 — plus `health_care_command`'s own suites, which the
tag included and which contributed the remainder of the 343 (the stats line
only names modules that were upgraded).

### How it got there — the first run, for honesty

The first full run was **16 failed, 8 error(s) of 342**. Not one of those was a
regression this phase introduced in shipped behaviour; the breakdown, because
"we fixed the tests" deserves to be shown rather than asserted:

| Cause | Count | Kind |
|---|---|---|
| `health.lookup.value` ACL missing for the website service user (§3 D4) | 9 | **pre-existing live defect** — 5 tests had been red before this phase, 4 were this phase's own |
| The card-count pins (§3 D1) | 4 | expected, pre-approved (3) + one the handover missed (1) |
| `health_web_leads/i18n/vi.po` obsolete `#~` blocks and dead `touchpoint_type` xmlids (§3 D5) | 5 | pre-existing rot |
| `mode_of_contact` → `mode_of_contact_id` in two assertions (§3 D5) | 2 | pre-existing rot |
| A fixture creating a second province named "Hà Nội" (§3 D5) | 1 | pre-existing, ledger §5.50 |
| `_search_google_ads_influenced` and the `OrderedSet` (§7 G1) | 1 | **a real bug in this phase's code** |
| Unique-index pre-check ordering, ledger §5.3 | 2 | this phase's code |
| `care.conversation.channel` — the field is `channel_declared` | 2 | this phase's test fixtures |
| A `crm.lead` company write tripping `_check_company` on `team_id` | 1 | this phase's test fixture |
| `@string` as an inheritance selector (§3 D3, §7 G3) | — | killed the first INSTALL outright, before any test ran |

---

## 5. Live capability table

What the Google Ads card says on the master **right now**, read from the DOM
during the browser pass, and why each line is the honest one:

| Capability | Live status | Why it says that |
|---|---|---|
| **Website leads** | *Setup needed* with no account; *Ready for test* once a website connector is linked; *Test passed; awaiting live lead* after the server test | Evidence-driven, never a checkbox. The synthetic test proves this system handles a Google ad click; it cannot prove the WEBSITE sends one, because the relay does not exist yet, and the screen says so in those words. Only a real enquiry moves it to *Receiving*. |
| **Campaign reporting** | *Not connected* | GA1 makes **no Google API call of any kind** — no OAuth, no developer token, no `requests` import. `reporting_state` is a field a later phase drives and nothing in this one can move it. |
| **Google lead forms** | *Unavailable for healthcare ads* | Google's published policy, checked 2026-09-15: *"Advertisements for healthcare-related content are not allowed for lead forms."* Recorded as `native_eligibility = healthcare_blocked`, readable by the tenant, writable only by a platform administrator against a written finding — and there is **no bypass switch anywhere in the UI**. |
| **Card chip (aggregate)** | *Setup needed* → *Partially connected* after a passing server test | Never *Connected*: that needs a real website lead **and** connected reporting, and neither exists. |

With the QA account removed, the live card is back to **Setup needed** on all
three databases, with all three capability rows at their unconfigured values.

---

## 6. QA residue — nothing left behind

Fresh-cursor counts, taken in a separate `psql` session after the shell that
made the changes had exited (ledger §5.34):

| Database | `google_ads_account` | `google_ads_campaign` | `crm_lead` | `health_lead_touchpoint` | QA user | account chatter |
|---|---|---|---|---|---|---|
| carejiox | **0** | **0** | 481 (= the pre-QA count) | **0** | 0 | 0 |
| carejiox_template | **0** | **0** | 0 | **0** | 0 | 0 |
| hhh | **0** | **0** | 0 | **0** | 0 | 0 |

The QA account (id 92) and QA user (uid 9142) were **unlinked, not archived** —
the customer-id unique index is database-wide and ignores `active`, so an
archived row would have reserved `1234567890` for good. The 481 leads on the
master is the number measured **before** the test button was pressed: the
synthetic run created nothing, which is rail R6.

Also verified live, outside the test suite (conventions §5.68 — nothing in the
test suite compiles the asset bundle):

```
sass.compile(google_ads_center.scss)      →  OK, 293 chars
web.assets_backend                        →  2,390,689 chars
  --ch-google-ads                         →  PRESENT
  .cc-card .cc-caps / .cc-cap             →  PRESENT
  .cc-card  (known-good sibling selector) →  PRESENT
```

---

## 7. Gotchas (ledger candidates)

### G1 — a custom `search=` on a Boolean receives an `OrderedSet`, and a naive truthiness test returns the EXACT COMPLEMENT

Ledger §5.13 already says a custom field search method "may receive
`OrderedSet` (not list/set builtins) and the domain optimizer rewrites `=` to
`in`". What §5.13 does not say is **how the failure presents**, and it is the
worst possible shape: not an error, not an empty result, but the complement.

Measured on the master:

```
[('google_ads_influenced', '=', True)]  →  the method is called with
                                            operator='in', value=OrderedSet([True])
```

`value == [True]` is False for an `OrderedSet`. `value in (True, 1, '1')` is
False. So a perfectly reasonable-looking truthiness test reads "the user asked
for NOT influenced", the method returns `('id', 'not in', ids)` — and the
filter lists **298 unrelated enquiries and hides the one it is named for**. It
looks like a working filter with wrong data behind it, which is exactly the
kind of thing a human calls "the report is wrong" and nobody traces to a
domain.

Rule: in a `search=` method, never compare the value to a literal. Branch on
the operator first, and for `in`/`not in` derive truthiness by ITERATING
(`any(bool(v) for v in value)`); then XOR with the negation. Assert every
spelling in a test — `= True`, `!= False`, `in [True]` and all three negatives
— and assert the negative one returns the COMPLEMENT, not merely "something".
(`health_google_ads/tests/test_attribution.py::test_ga1_t06b`.)

### G2 — a satellite ACL is not optional when the base model gained a `check_company` many2one or a lookup-backed field

Two of this phase's red tests were the same shape one layer apart: a
**service** user that can create `crm.lead` cannot necessarily WRITE a field on
it, because `check_company=True` makes the ORM read the *target's* company as
that user, and a `health.lookup.value`-backed default makes it read the
vocabulary table. Both are invisible in the model definition and both surface
only as an `AccessError` from deep inside `create()`.

The live consequence here predated this phase by the whole
dropdown-vocabulary conversion: **`POST /api/v1/web/leads` was answering 403 to
every real website submission** because nobody granted the relay's service
account read on `health.lookup.value`. Five pre-existing tests said so and had
been red long enough to be treated as scenery.

Rule: when a converted field (Selection → `health.lookup.value` m2o) lands on a
model any SERVICE user writes, grant that group read on `health.lookup.value`
in the same change; and a group whose reachable-model set is pinned by a test
(§5.88 family) is the right place to discover it.

### G3 — `@string` is still the first thing to break on a view inherit

Conventions §5.21, paid for again: `//group[@string='Click Identifiers']`
killed the first install of this phase with a bare `ParseError` naming the
file and the record's line, not the selector. Anchor on `@name`, and if the
base node has none, add a page rather than inventing one.

### G4 — the CMS shell and `doAction` from the Center

Observed in the browser evidence pack: the Center's "Set up Google Ads" button
calls `this.action.doAction('health_google_ads.action_google_ads_accounts')`
and the account list opens **inside** the CMS chrome, with the "Google Ads"
sidebar leaf highlighted. The sidebar seed is what does that (§5.69/§5.93) —
the action xmlid is matched against `match_action_xmlids`. See §5 of the
evidence pack for the screenshot and the observation.

---

## 8. Open question for the owner

**Which website forms, and which Google Ads account number, belong to Viet UC?**

Two specific things are needed before a real Google Ads account can be set up
on the live system, and neither can be guessed:

1. **The advertising account number.** Google Ads shows a ten-digit customer ID
   at the top right of the account (it looks like `123-456-7890`). If more than
   one is in use — for example one for Hanoi and one for Ho Chi Minh City —
   each needs its own entry here, and each needs its own number. Today nothing
   is set up, so every Google-looking enquiry would be filed as
   *"came from a Google ad, but we do not know which account"*.
2. **Which contact form on the website serves which city.** The system already
   maps form `15838` to Hanoi and `15670` to Ho Chi Minh City. If the website
   has other contact forms, or if those two have moved, the enquiries will
   arrive with no city and be flagged for review.

Also worth knowing, because it decides what is worth building next: **is the
website able to send the extra information at all?** The piece that carries an
ad's details from the website into this system has never been installed.
Everything in this phase works the moment it is; until then, an ad click that
becomes a website enquiry arrives with only whatever the web address itself
carried.

Nothing above blocks the phase. It blocks the first real Google Ads account.

---

## 9. Self-review against the handover

### §7 safety rails

| Rail | Implemented | Proven by |
|---|---|---|
| R1 — company never comes from the payload | yes | `_google_ads_resolve_account` domains every lookup on `self.env.company`; GA1-T08 sends another company's customer id and gets `unmatched` with no account |
| R2 — first touch is immutable | yes | `_lead_extra_vals` is called ONLY from `_create_lead`; GA1-T06 merges a Google follow-up onto an organic lead and the lead's fields stay empty; `test_ga1_wl_06` patches the seam and asserts a merge never reaches it |
| R3 — ids are strings | yes | no `int()` anywhere in the chain; GA1-T04/T11 assert byte equality on a 19-digit campaign id and `isinstance(..., str)` |
| R4 — never the first of several accounts | yes | GA1-T09: the same campaign id mapped on two accounts resolves `unmatched`; mapped on one resolves to that one |
| R5 — evidence is internal-write-only | yes | GA1-T13 a–d: stripped without the context, lands with context+su, the context alone is not enough, and `native_eligibility` raises `AccessError` for a non-platform-admin |
| R6 — the synthetic test creates nothing | yes | GA1-T12 fresh `search_count` after `invalidate_all`; **and** the browser pass's before/after DB counts (481 / 0, unchanged) |
| R7 — no secret material in the card payload | yes | GA1-T02 dumps the card to JSON and asserts none of `token`, `secret`, `chs$1$`, `refresh`, `client_secret`; a second test asserts no "Sent"/"Reply"/"Compose" |
| R8 — classification never rewrites UTM | yes | GA1-T10: `utm_source` on the touchpoint is still `'facebook'` while the match status is `conflict` and review is raised |
| R9 — `sudo()` only where named | yes | three places, each commented: the account/campaign lookup in the service hook, the card payload's company-pinned read, the influenced-search id lookup. Every action method gates BEFORE it elevates |
| R10 — all existing suites stay green | yes | 0 failed, 0 error(s) of 343 — **including** repairing five pre-existing reds that were not this phase's doing |

**Rails I could not prove:** none. R6 is the only one where a test alone would
have been weak evidence, and it is backed by live before/after counts as well.

### §8 test table

GA1-T01 … GA1-T20 are all implemented. Mapping to files:

- `test_attribution.py` — T04, T05, T06 (+T06b, the §7 G1 regression pin), T07,
  T08, T09 (+T09b), T10 (+T10b, T10c), T11 (+T11b, T11c), T16 (+T16b, T16c), T20
- `test_center.py` — T01, T02 (+T02b), T03 (+T03b), T18 (+T18b, T18c), T19
- `test_security.py` — T13 (a–d), T14 (+T14b, T14c), T15, T17 (a–g)
- `test_website_test.py` — T12 (a–g)
- `health_web_leads/tests/test_web_leads_ga1.py` — braid persistence on both
  rows and both paths, the seams' defaults and call signatures, the merge
  exclusion, touchpoint `company_id` and its recompute, the anchorless branch

Two scope notes on the table as written:

- **T20 was not skipped.** `care.conversation` fixtures turned out to be
  practical; the only correction needed was that the model has no `channel`
  field (it carries `channel_primary` / `channel_declared` / the computed
  `channel_effective`).
- **T12's "second press updates the timestamp"** is asserted by forcing a
  distinguishable prior value first — Odoo truncates datetimes to the second
  (ledger §5.35), so two presses inside one second are otherwise
  indistinguishable and the assertion would pass for the wrong reason.
