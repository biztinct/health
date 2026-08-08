# CareJioX Learn — in-app learning system for the CRM section

A runnable, no-build prototype of a **bilingual (EN / VI), animated, self-sufficient
in-app learning system** covering the **CRM section** of CareJioX — the eight leaves a
user sees under `CRM` in the left sidebar.

It is a port of the strategy in [`../tutorial_poc/DESIGN_SPEC.md`](../tutorial_poc/DESIGN_SPEC.md).
The strategy is carried over unchanged; **every piece of content was re-derived from this
repository** (menu inventory, urgency arithmetic, roles, state pipelines, terminology,
design tokens). Nothing is copied from the Payobook reference.

---

## Run it

No build step, no dependencies, no network calls.

```bash
open docs/tutorial_crm/index.html                    # macOS
```

Or, to avoid the one benign `file:` origin warning Chrome logs for local pages:

```bash
cd docs/tutorial_crm && python3 -m http.server 8000  # then http://localhost:8000
```

Progress, language, role and reduced-motion survive a refresh (localStorage key
`cjxLearn`). **Reset progress** in the top bar clears it.

---

## Navigate

The hub (`#/hub`) opens the three surfaces. Everything is reachable by hash route:

| Route | What it is |
|---|---|
| `#/hub` | Concept hub — the three surfaces, starting modes, resume card |
| `#/journey` | Station map: 2 lines, 8 stations, progress, search, badge |
| `#/journey/lesson/L1` | ★ Flagship lesson — **Care Command** (10 steps + quiz) |
| `#/journey/lesson/L2` | ★ Flagship lesson — **Channel Center** (9 steps + quiz) |
| `#/sim` | Safe Practice Clinic — 2 full missions + 2 written outlines |
| `#/companion` | The live CRM shell with the Coach launcher on it |

Non-flagship stations open as **labelled outlines** (model parts 1–4 + 7, written in
full, both languages) from the station map.

### The Coach is always on

It is not a place you navigate to. On every in-scope screen there is a **“Stuck?” launcher**
(bottom right) and a **`?` shortcut**; both open a drawer that is grounded in the screen you
are standing on. The drawer deliberately does *not* dim or block the page behind it — you open
it *because* you are stuck on that screen, so the screen has to stay readable. During a mission
the step panel moves out of its way rather than being buried.

Two deliberate exceptions: it is hidden inside a lesson (the coach card is already the
coaching), and `?` is ignored while you are typing.

### Controls that exist everywhere

- **EN / VI** — switches *everything* live: chrome, content, quiz explanations, coach
  answers, and number formats (`450.000 ₫` / `30,0%` in VI, `450,000 ₫` / `30.0%` in EN).
- **Role switcher** (CRM / Nurse / Ops / Owner) — re-gates the sidebar and changes what
  the Coach answers. As **Nurse**, four CRM leaves disappear; this is not decoration, it
  reproduces the measured production behaviour (see *Provenance* below).
- **Reduce motion** — collapses the spotlight move, the trace dot, the pipeline stepper
  and every pulse to instant states. `prefers-reduced-motion` does the same automatically.

### Keyboard

- Lesson player: `←` `→` step, `Space` autoplay, `Esc` exit (position is saved).
- `Esc` closes any dialog. Focus rings are visible everywhere; narration cards are
  `aria-live` regions.

### Fastest tour (about 6 minutes)

1. `#/journey/lesson/L1` → press `→` to **step 5** (the *trace*: the watch phrase
   travelling into the `+15` term) and **step 8** (the *morph*: what "Junk?" really does).
2. Finish the lesson → the quiz is a judgement, and a wrong answer gets **recovery**,
   not rejection.
3. `#/sim` → *Work the wall to zero* → step 4 is the seeded anomaly; pick the tempting
   wrong option deliberately to see the recovery dialog. Step 5 shows the consequence
   interception before a message is "sent".
4. `#/companion` → ask **"why is this 110"**, then switch the role to **Nurse** and ask
   **"take over"** to see an honest refusal. Type something off-topic (e.g. "what dose")
   to see the grounded fallback.

---

## Files

| File | Role |
|---|---|
| `index.html` | Shell + inline SVG sprite (no icon font, no CDN, no emoji) |
| `practice-data.js` | **The practice fixture.** The only file that mirrors the product: the worked case, menu inventory, and every practice record the screens render |
| `data.js` | **The content spine.** i18n, glossary, 8 stations, 2 lessons, 4 missions, 17 coach intents |
| `app.js` | Engine: spotlight, trace, morph, pipeline, resolver, the simulated CMS shell, surface controllers, router, state |
| `styles.css` | CareJioX design tokens + all surfaces |
| `contract.json` | Every product fact the tutorial asserts, and where it came from |
| `TENANT_DEFAULTS` (in `practice-data.js`) | 38 named slots a clinic may override — roles, contacts, shift times, policy names |
| `tools/check_contract.py` | Re-reads the addons and fails when a declaration stops holding |
| `analysis.html` | Coverage matrix, decision table, deployment design, roadmap, metrics, integration checklist |
| `screenshots/` | Captured states (desktop, mobile, VI, reduced motion) |

**The split matters.** `data.js` is teaching content; `practice-data.js` is facts about the
product. If you find yourself typing a number into a lesson step, it belongs in the fixture —
the contract checker can only guard what lives in one place.

`data.js` is the shape a production `carejiox.learn.*` model should take — port the schema,
keep the content.

## Keeping it honest without a demo tenant

There is no demo tenant and none is needed: the practice clinic is a JavaScript fixture, so a
practice action is *structurally* incapable of reaching a real patient — there is no server on
the other end of it. The banner is the last line of defence rather than the only one.

The cost of a fixture is drift. That is paid by:

```bash
python3 docs/tutorial_crm/tools/check_contract.py          # run it in CI
python3 docs/tutorial_crm/tools/check_contract.py --quiet  # errors only
```

21 checks today: the urgency weights (by exact occurrence count), four selection sets, the
sidebar inventory, the shipped Vietnamese labels, the role gate, the consent types, and the
anchor registry. When one fails it names **which fixture entries** and **which lessons** quote
the broken fact.

Verified by breaking it on purpose: re-weighting the watch-phrase term 15 → 25 in the real
model made it fail and name `CASE.urgency` plus the six pieces of content that quote it.
Translating "Care Command" in the `.po` made the known-gap check fail with *"GOOD NEWS: …
update MENU and delete this entry"*. The addons were restored afterwards.

> The first version of that check was presence-only and stayed **green** through the re-weight,
> because `score += 15` appears twice and the other one still matched. It now asserts exact
> counts — which also fires when a new term is added, as it should.

---

## Provenance — what was re-derived, and from where

Everything below was read out of this repository or measured against the live UAT
deployment. Nothing is assumed.

**Menu inventory (8 active CRM leaves)** — from the `cms.sidebar.item` seeds, in sequence
order: Dashboard (10), Care Command (11), Channel Center (12), Unrouted Contacts (13),
Contacts (20), Web Touchpoints (21), Lead Analysis (23), Activities (50). Six leaves that
*used* to be in CRM were retired or moved to ADMIN by the `19.0.1.2.0` consolidation
(`health_cms_coverage/hooks.py`); they are listed with their replacements in
`analysis.html` rather than silently dropped.

**Vietnamese labels** — the *shipped* strings from `i18n/vi*.po`, not our translations:
Bảng điều khiển · Trung tâm kênh · Danh bạ chưa được định tuyến · Liên hệ · Điểm chạm web
· Phân tích khách tiềm năng · Hoạt động. **"Care Command" ships untranslated** — that is a
real gap, flagged in `analysis.html`, and the prototype keeps the shipped label rather
than inventing one.

**Role gating** — `access.role` rows carry no xml-id, so the gate is written in Python
(`health_cms_coverage/hooks.py`). Verified in the browser against `care.biztinct.com`: a
session without Owner/CRM sees exactly the four ungated leaves. The role switcher
reproduces that.

**Urgency arithmetic** — the stored compute in
`health_care_command/models/care_conversation.py`: needs-reply `+40`, booking within 24h
`+30`, unread `+15`, unhandled missed call `+10`, watch phrase `+15`, ageing
`min(20, whole hours)`. The worked case sums to **110** everywhere it appears.

**Risky actions** (→ consequence previews and missions) — sending a reply from the wall
(no draft, no recall, PHI to a possibly-unpermitted recipient); `Junk?` (which *also*
spams the linked lead and flags the phone number); booking from a conversation (the
duplicate-client check); take-over (manager-only); re-authorising a channel (a live
channel leaves service and **nothing queues**).

**State pipelines** — conversation `needs_reply → waiting → closed` with `junk_suspect`
as a branch; channel connection `not_connected → authorizing → select_resource →
configuring → testing → ready`; contact lifecycle `New → Lead → Appointment Scheduled →
Service Used` with Cancelled/Spam branching.

**Terminology** — the bilingual CRM chapter of the shipped user manual
(`docs/user_manual/content/02_crm.md` and `content_vi/02_crm.md`) is the source for the
Vietnamese domain vocabulary, so the tutorial and the manual agree word for word.

**Design tokens** — mapped from `addons/health_theme/static/src/scss/vu_tokens.scss`:
brand `#1565C0`, deep navy `#0F1E45` (the coach layer), ok `#10B981`, warn `#B45309`,
danger `#DC2626`, canvas `#F4F6FB`, plus the workflow-state accents for the pipeline
animation. The reference's indigo palette is not used anywhere. No gradients — the app's
own token file makes that a hard rule, so the status donut is a segmented bar instead.

---

## Scope of this prototype

**In:** the CRM section only, as the brief asked.

**Deliberately not built** (and honestly labelled in the UI):

- Six of the eight stations ship as **outlines**, not full lessons. The outline content is
  complete and useful; the guided step machine is not built for them.
- The Coach is **deterministic retrieval**, not an LLM — which is exactly why it can promise
  never to invent a price, a rate or a clinical fact. `Resolver` in `app.js` is the single seam
  where an LLM could be plugged in later; it must still return a human-written intent or null,
  never synthesise blocks.
- Two of the four missions are **outline missions** — their consequence, seeded anomaly
  and debrief are written; the step machine is not built.
- The practice tenant is a faithful *shell*, not the real OWL components. In production
  the missions should drive the real screens through the anchor registry.

## Tenant overrides — 38 named slots

Content never hard-codes a clinic-specific fact. It writes `{{key}}`, and `tx()` resolves
**tenant value → default → the visible key** (an unknown key renders as `{{key}}` on purpose, so
a typo is obvious rather than an empty gap).

```js
B("Escalate to {{roleDutyDoctor}} before {{handoverTime}}", "…")
//  defaults      -> "Escalate to Duty Doctor before 17:00"
//  overridden    -> "Escalate to On-call Physician before 16:45"
```

Slots cover identity, contact routes, geography, escalation titles, access paths, shift times,
policy names and locale. 8 are in use today; 30 are spare capacity, which cost nothing to carry.

**These are not the practice fixture.** The fixture is fake data, module-shipped, identical
everywhere. An override is a *real* fact about one clinic — its actual hotline number — and a
module ships identical bytes to every tenant, so overrides cannot live in a shipped file. In
production this is **one small DB row per tenant** holding exactly these keys: JSON-shaped and
authored like JSON, but DB-resident. It never reads or writes a patient, a booking or an
invoice, which is what makes it safe to expose to a tenant admin.

**The hard rule:** overrides fill named slots. They can never replace a lesson step, a quiz
option, a consequence card or a coach answer. Let a tenant edit prose and you have twelve
divergent tutorials that no check can guard. `token-lint` fails on any undeclared slot.

## Measuring it, with no history to compare against

There is no onboarding baseline and no ticket record, and manufacturing a control group by
withholding training from the first cohort would be slow and wrong. The decision (`analysis.html`
§6): a **self-referential baseline** — instrument on release day, treat **month 1 as the
reference period**, apply relative targets from month 2.

Two exceptions are **absolute from day one**, because "fewer consent breaches than last month"
is not a standard: consent-breach near-misses = **0**, and mis-routed channel incidents = **0**,
detected within one business day. Today the second is invisible until someone notices a quiet
week, so detecting it at all is the first win.

Provisional targets are published so the team can steer from week one, each labelled as an
assumption to be replaced after four weeks. Two of the metrics judge the *content*, not the
learner: quiz first-try correctness has a healthy band of **50–80%** per item, and mission
recovery-dialog frequency **30–70%** — zero is a failure there, not a success.

**One hard requirement on Phase 1: the event log ships in release 1**, not release 4. It is a
handful of event types, and if it slips the pre-tutorial reference period is gone permanently.

## Where this gets installed

Settled in `analysis.html` §8: **installed in every tenant, content authored centrally, no
master training tenant.** Tenancy here is `res.company` inside one database — `cms.sidebar.item`
and `access.role` carry no `company_id`, so navigation and roles are database-global while
transactional data is company-scoped.

| Part | Lives in |
|---|---|
| Content spine | Odoo records, shipped as module data files (`noupdate="0"`) |
| Journey + Coach | Every tenant, always on — both are screen-grounded and cannot work from elsewhere |
| Practice fixture | A static JS/JSON asset. Never the ORM |
| Learner progress | Odoo records, per user; aggregated into `biz_bi` for the metrics |

The rule that makes it robust: **never make tutorial content a tenant-editable record set.**
Otherwise one tenant holds "the good version" and the rest silently drift.

## The one thing to carry into production first

**The anchor registry.** Every control the content points at carries `data-a="…"`, and
content references anchors by name. Add a CI lint that compares anchors named in content
against anchors present in templates, so a screen change breaks the tutorial *loudly at
build time* instead of silently at runtime. Without it, this system rots within two
releases. The integration checklist in `analysis.html` starts there.
