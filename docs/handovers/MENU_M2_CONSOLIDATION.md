# MENU IA — M2: the consolidated catalogue

Status: HANDOVER to Opus (written 2026-09-29; launches after M1 reports). Designed by
Fable. Read first: `MENU_IA_PROGRAM.md` (§1 facts, §2.2 the approved table, §4 rulings incl.
**Q6: the Clinical area opens for Doctor + Owner + Admin, not Nurse**), `MENU_M1_SHELL.md` +
the M1 report (the shell you are filling: rail = sections, tab column = root items, segment
strip = children; the list of tab labels that needed an ellipsis), and the conventions ledger
tail (continue numbering after M1's last entry).

**This phase changes WHAT is in the menu, not how it is drawn.** Every existing action keeps
an entry. Every person keeps every screen they can reach today (reachability diff = 0 lost),
except where the owner ruled otherwise (Q6 widens Clinical to Doctor/Owner; nothing narrows).

## 0. Standing rules
As M1 §0. Plus: this is a DATA re-home over noupdate=1 seeds → the work is (a) an idempotent
hook + migration in a NEW glue module `health_cms_ia` (depends on every module that seeds
rows — cms_sidebar, cms_coverage, cms_clinical, access, tenancy, biz_bi_cms, care_command,
care_command_channels, care_command_voip, web_leads, google_ads, learn — so it loads LAST and
no dependency loop is possible, §5.71), and (b) edits to every **noupdate=0** satellite seed
(`biz_bi_cms`, `health_care_command`, `health_care_command_channels` ×3,
`health_care_command_voip`, `health_web_leads`, `health_google_ads`, `health_learn` generated,
`health_cms_sidebar/data/cms_sidebar_items_ops_schedule.xml`) so a later `-u` cannot undo the
move (program §1.1). Coverage test t05b: hook-written rows must be noupdate=1 — satisfy it
the way `health_cms_coverage/hooks.py` does. `xmlids never change`; `parent_id` cleared
explicitly with `eval="False"` where a former child becomes a root (§5.69b). Sequences unique
per section, step in tens; children step in tens under their parent.

## 1. Scope

| # | Item |
|---|---|
| A | `health_cms_ia` module: `consolidate_ia(env)` hook (post_init + migration), idempotent, logs every move; `RENAME`, `MOVE`, `NEST`, `PROMOTE`, `GATE` tables keyed by xmlid |
| B | Section renames (display names only; keys/xmlids/sequences unchanged): CRM → "CRM"; OPERATIONS MANAGER → "Operations"; FINANCE → "Finance"; CLINICAL → "Clinical"; INTEROP & COMPLIANCE → "Compliance"; ANALYTICS → "Analytics"; ADMIN → "Settings"; plus M1's Home/Learn |
| C | The moves per §2 below |
| D | Gate re-map per §2b (owner rulings Q6 + Q8–Q11 of 2026-09-29): **no entry stays ungated** ("no gate = everyone" leaked CRM/Interop screens to 52 nurses and 18 doctors on the live menu — M1 report); area gates on sections; per-entry gates as listed; a new parent tab's gate = union of its children's gates, children keep theirs |
| E | Satellite seed edits (the noupdate=0 files) to match the final positions |
| F | `health_learn`: `fixture.js:549-630` + `docs/tutorial_crm/practice-data.js` + `learn_stations.xml` `sidebar_key`s + any lesson step naming a menu path → regenerate; `test_bundle`/`test_coach` green |
| G | Access home vocabulary: Screens lens block row label "Area", entries "Tabs", children "Inside the tab" (biz_access strings stay generic: "block/entry/sub-entry" → rename to "area/tab/inside" ONLY if the provider exposes a vocabulary hook; else leave generic and put the words in health_access's provider `labels()`); passport mini-rail drawn as rail + tab column + segments (mirror M1's shell, read-only) |
| H | Tenancy: `feature_key` walk still finds keys after moves (`_feature_key_of` item→section→parent) — re-stamp with `wire_features` and assert the feature-off preview still hides the right entries |
| I | Tests + per-user reachability diff + browser QA + deploy |

Non-goals: new screens, Vietnamese (AR-3), coach anchors (AR-3), retiring any action,
changing record rules, the PWA, the admin tab strip.

## 2. The moves (source = live 2026-09-29 dump in `MENU_IA_PROGRAM.md` §2.2; resolve xmlids
by module + name and PIN them in the hook — never match by display name at runtime)

Notation: **Tab** = root item; → children = segments. `(new)` = create a parent row (module
`health_cms_ia`, noupdate=1, icon given). Sequences are the target ones.

### CRM (section_crm)
10 Dashboard · 20 Care Command · 30 **Channels (new, fa fa-comments-o)** → Channel Center 10,
Unrouted Contacts 20, Channel audit 30, Channel messages 40, Watchlist phrases 50 ·
40 **Phone** (existing voip parent; keep) → Calls 10, Call backs 20, Recordings 30, Records
from the phone system 40 (Extensions + Phone system MOVE to Settings › Connections) ·
50 **Contacts** (existing leaf becomes a parent: keep its action on the parent? NO — rule:
parents never navigate; so: new parent "Contacts" (fa fa-address-book) with children Contacts
10 (the existing leaf, renamed "All contacts"), Relationships 20) · 60 Activities ·
70 **Web & Ads (new, fa fa-globe)** → Web Touchpoints 10, Lead Analysis 20, Google Ads 30 ·
Training (seq 90) already moved to Learn in M1.

### Operations (section_ops)
10 Dashboard · 20 Bookings · 30 Clients · 40 **Schedule (new, fa fa-calendar)** → Staff
Schedule 10, Time Off 20, Workload 30 · 50 Collections · 60 Family Inbox · 70 Routes (rename
"Route Feasibility") · 80 **Exceptions (new, fa fa-exclamation-circle)** → First-visit offers
10, Timecard mismatches 20 · 90 **Development (new, fa fa-line-chart)** → Employee development
10, Coaching 20.

### Clinical (section_clinical) — area gate Doctor + Owner + Admin
10 Observations · 20 **Care Intelligence** (existing parent) → Worklist 10 (rename
"Deterioration Worklist"), Alerts 20 (rename "Deterioration Alerts"), NEWS2 30 (rename "NEWS2
Scores") · 30 **Medications** (existing parent "Medications (eMAR)", rename) → Orders 10
(rename "Medication Orders"), Administration Register 20 · 40 Assessments · 50 **Incidents**
(existing parent) → Register 10 (rename "Incident Register"), Corrective Actions 20, Analysis 30
· 60 Consents (rename "Expiring Consents") · 70 **Notes (new, fa fa-file-text-o)** → Unsigned
Notes 10, Voice Notes 20, Coding Review 30.

### Finance (section_finance)
10 Dashboard · 20 Invoices · 30 **Receivables (new, fa fa-money)** → AR Dashboard 10, AR
Transactions 20, Overdue Clients 30 · 40 **Payments (new parent; the existing "Payments" leaf
becomes child "All payments" 10; existing parent "AR Management" is RETIRED (active=False)
and its children re-parented)** → All payments 10, Account Payment 20, Cash In Transit 30,
Refund / Credit 40 · 50 VAT Log · 60 BHYT Claims · 70 Service Packages · 80 Red Invoice Log.

### Compliance (section_interop)
10 **Terminology** (existing parent "Medical Terminology", rename) → Medical Codes 10, Coding
Systems 20, Import Codes 30 · 20 **EMR (VN) (new, fa fa-exchange)** → Export 10 (rename
"EMR Export (VN)"), Readiness 20 (rename "EMR Readiness") · 30 Visit Messaging · 40 EVV Events.

### Analytics (section from biz_bi_cms)
10 Analytics · 20 Explore · 30 Dashboards & schedules · 40 **Data** (existing parent "Where the
numbers come from", rename) → Sources 10, Datasets 20, Refresh jobs 30, Pipelines 40, Semantic
model 50, Glossary 60.

### Learn (section_learn, from M1)
10 Training · 20 **Training admin** (the existing expander, rename) → Lessons 10, Stations 20,
Learner progress 30, Learning events 40, Training wording 50.

### Settings (section_admin)
10 Overview (rename "Dashboard") · 20 **People (new, fa fa-users)** → Users & Roles 10, Access
& roles 20, Healthcare Staff 30 · 30 **Master data (new, fa fa-database)** → Facilities 10
(the existing "Master Data" leaf), Pricing 20, Equipment 30, Public Holidays 40, Observation
Types 50, Medication Catalog 60, Form Templates 70, Monitoring Devices 80, Field Requirements
90 · 40 **Connections (new, fa fa-plug)** → Channels (setup) 10, Reply Templates 20, Channel
Go-Live 30, Website Connector 40, Google Ads application 50, Phone system 60 (from CRM›Phone),
Extensions 70 (from CRM›Phone) · 50 **Records (new, fa fa-archive)** → Audit Log 10, Data
Lifecycle 20, Consent Check Log 30 · 60 Menu (rename "CMS Sidebar Config") · 70 Settings ·
80 About Viet Uc Care · 90 Customers (platform-only gate unchanged) · (`item_feature_off_shell`
stays inactive where it is).

## 2b. The gate matrix (owner rulings 2026-09-29 — binding; Owner and Admin keep everything)

Live fact (M1 report + Fable's check as khoa.bv / dhcmc): a Nurse's or Doctor's menu today is
Home + CRM (Channel Center, Unrouted Contacts, Phone, Web Touchpoints, Google Ads, Lead
Analysis) + all of INTEROP + Learn — the UNGATED entries — and none of their work. Fix:

| Area / entry | Roles that open it |
|---|---|
| **Operations area** | Owner, Admin, Operations Manager, Branch Manager (area gate); **Bookings, Clients** additionally Doctor + Nurse (+ CRM on Clients as today); **Schedule** (Staff Schedule, Time Off, Workload) additionally Nurse; everything else in the area keeps today's gate |
| **Clinical area** | Doctor, Owner, Admin (Q6). Nurse NOT. Entry gates inside inherit; Voice Notes keeps OM+Owner as well |
| **CRM area** | CRM, Owner, Admin, Operations Manager (area); Channel Center + Unrouted Contacts → CRM, Owner, OM; Web & Ads (Touchpoints, Lead Analysis, Google Ads) → CRM, Owner; Channels children keep CRM+Owner; Phone → the roles holding "Handle calls" (see Phone) |
| **Finance area** | Accountant, Owner, Admin (area); Invoices additionally OM (today) |
| **Compliance area** | Owner, Admin, Doctor (area); BHYT Claims stays in Finance with Accountant |
| **Analytics area** | as today (Owner, OM, BM, Accountant) |
| **Learn area** | everyone (Training journey ungated ON PURPOSE — the single deliberate exception, documented in the hook); Training admin → Admin, Owner |
| **Settings area** | Owner, Admin (area); Settings, Data Lifecycle, Channel Go-Live, Google Ads application, Website Connector → Owner, Admin; Customers stays Owner-only; Monitoring Devices etc. keep Admin (+Owner via area) |
| **Phone abilities** (from AR-2, held by nobody) | "Handle calls" → Owner, CRM, Operations Manager; "Set up the phone system" → Owner, Admin. Written onto the ROLE bundles through the same seam AR-2 used (`ensure_catalogue`/role ability_ids, create-only) + audit line; then Phone (CRM) gate = Owner, CRM, OM and Settings › Connections › Phone system/Extensions = Owner, Admin |
| **Home rule tweak** (M1 shipped admin>ops>front_desk>finance>clinical) | Nurse → **Bookings**; Doctor → Observations; and a generic guard: if the resolved landing is not on the person's menu, fall back to the FIRST entry the person can see (never a screen they cannot find again) |

Resulting menus to assert in tests (test 4/5): Nurse = Home, Operations (Bookings, Clients,
Schedule), Learn. Doctor = Home, Clinical (all 7 tabs), Operations (Bookings, Clients), Learn.
Owner/Admin = everything. Reachability diff: nurses/doctors LOSE the leaked CRM/Interop entries
(expected, list them), GAIN their work screens; no other role loses anything.

Cross-check after the hook: every action that was on the live menu on 2026-09-29 (114 rows)
is still on exactly one active entry; no active parent without an action or active children
(coverage t07); no sequence clash per section; no child in another section than its parent.

## 3. Design notes
- Hook shape: clone `health_cms_coverage/hooks.py` (`RETIRE/RELOCATE/COLLAPSE/ATTACH_MATCH`
  tables + `_apply` idempotent writers + migration calling it). Create new parents with
  `ir.model.data` xmlids `health_cms_ia.parent_<key>` so they are re-findable.
- New parents: `match_action_xmlids` = union of children's actions (so the tab stays lit —
  §5.150 — but the leaf's own action is matched first). Remove the same xmlids from any OLD
  claimant (the `_release_borrowed_matches` precedent in `health_access/hooks.py`).
- Renames write `name` (translated field; write en_US only — AR-3 adds vi).
- Gate rules (D) run AFTER moves, in the hook, through the same `biz_role_ids` writes the
  Access provider uses; log per entry old→new. Then run `health_access`'s
  `access_snapshot`/`access_snapshot_diff` (`health_access/diff.py`) per user before/after —
  expected: 0 lost; gains only in Clinical for Doctor/Owner.
- M1's tab-label ellipsis list: the renames above shorten the long ones; check every remaining
  root label fits the 60px box, and add a `short_name` ONLY if the M1 shell exposes one
  (else rename).
- Learn: the practice fixture mirrors the CRM/OPS/FIN menus by label + sequence — update it
  to the new tabs/segments; lessons that say "open X under Y" must say the new path.

## 4. Tests (numbered)
1. Hook idempotent: run twice on a clone → second run logs 0 moves, 0 renames.
2. Every one of the 114 live actions is on exactly one active entry after the hook; parents
   never navigate; no clash; no cross-section child (coverage suite green incl. t05b/t07).
3. `-u` of each noupdate=0 satellite (biz_bi_cms, voip, channels, web_leads, google_ads,
   care_command, learn) after the hook leaves every moved row where the hook put it.
4. Reachability diff per user on a clone of live (all 74 users): 0 lost; gains only Clinical
   for Doctor/Owner holders; Nurses unchanged.
5. Clinical area gate = {Doctor, Owner, Admin}; a Doctor's `get_sidebar_data` shows the
   Clinical section with its 7 tabs; a Nurse's does not.
6. Feature switches: with `care_command` off the Channels tab, Care Command, Channel Go-Live
   and Reply Templates are absent for everyone; with `voice` off, Phone and its Settings
   children are absent (`health_tenancy` TestFeatureGate green; `menu_preview` shows the same).
7. Access home: Screens lens rows follow the new tree (areas, tabs, segments); "through <Area>"
   tags correct; passport mini-rail matches `visibility_for` for Owner, Doctor, Nurse,
   Accountant (`health_access` test_provider "the home draws exactly what the menu draws").
8. Highlight: opening every one of the 114 actions lights its tab (and pill) and section —
   automated over `get_match_keys` + the M1 resolver (JS test or HttpCase loop over 20
   representative actions incl. the former borrowed ones: Relationships, Deletion Reasons,
   channel audit/messages).
9. Learn: `test_bundle`, `test_coach`, `test_anchor_registry` green; the fixture matches the
   new CRM/OPS/FIN menus.
10. Full suites on the clone: health_cms_sidebar, health_cms_coverage, health_cms_clinical,
    health_cms_ia, health_access, health_tenancy, health_learn, biz_bi_cms, care_command_voip,
    care_command_channels, health_web_leads, health_google_ads, health_catchment_scope,
    health_fieldservice (sidebar tests); counts before/after.

## 5. Browser QA
Owner, Doctor, Nurse, Accountant, CRM: every area's tab column and every segment strip;
click through the 114 actions (scripted via the tour), catchment pill still scopes lists,
Settings › Connections › Phone system opens the voice config; Access › Screens shows the
new tree. Pixel pass on labels. Screenshots → `docs/handovers/menu_m2_shots/`.

## 6. Deploy
Clone rehearsal (neutralise `biz_tenant` rows; run the 74-user diff there) → backups
`/var/backups/menu_m2/` → master → template (crons OFF after) → hhh, one sitting (`-i
health_cms_ia` on all three) → asset bump → live per-user diff = 0 lost → screenshots.

## 7. Report back
Tests 1-10, suite counts, the move log (counts per table), the per-user diff summary,
deviations, ledger entries, commit hashes, live evidence, anything undone. Plain English +
engineering appendix.
