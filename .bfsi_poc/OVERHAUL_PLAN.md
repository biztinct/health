# AI Performance Coaching — UX/UI Overhaul Plan
*Module: `hr_development_ai` (BFSI part) · Odoo 19 · Persona focus: Branch Manager*

---

## 1. What the module actually does (so we're aligned)

A banking performance-coaching system. The data + workflow spine:

```
KPIs logged (input/behavior/output/outcome)
   → scored & ranked per banker, per branch
   → coaching priority computed (low→critical)
   → manager generates an AI COACHING STRATEGY (diagnosis, questions, roleplay)
   → runs a COACHING SESSION (notes, AI chat assist)
   → assigns an ACTION PLAN (KPI-linked items, check-ins)
   → progress tracked → loop repeats
```
Supporting: Regions/Branches org, KPI Targets, external KPI Integrations, AI Coach panel.

The **models are strong**. The OWL dashboard is genuinely premium. The problem is **everything between the dashboard and the data** — navigation and forms.

---

## 2. Diagnosis — why users get lost (observed live as Branch Manager)

| # | Problem | Evidence |
|---|---------|----------|
| 1 | **Cohesion break** | Beautiful OWL dashboard → click "Coach" → dumped into a raw Odoo form with 6 notebook tabs and an empty "Coaching Strategy" field. No "what next". |
| 2 | **Menu sprawl & My/Team duplication** | "AI Coaching" alone = 6 items (Coaching Strategies, Strategic Selection, Team Action Plans, My Action Plans, My Coaching Sessions, Coaching Sessions). |
| 3 | **Broken "Strategic Selection"** | Raw KPI grid grouped by month showing *summed* scores ("1,164.80", "264.30") — meaningless and un-actionable. |
| 4 | **Workflow split across 4 models** | strategy → session → action plan → monitor each live in a separate model/menu/form with manual state buttons. The user must assemble the journey themselves. |
| 5 | **Form density** | KPI Targets = 5 notebook pages; coaching session shows overlapping AI-question fields from 3 different sources. |
| 6 | **No single source of "next best action"** | Nothing tells the manager *who* to coach, *why*, or *what to do* — they have to dig. |

**Root insight:** the module is organized around **data models** (one menu per table), not around the **manager's job-to-be-done**. The fix is to organize around the *job*.

---

## 3. Strategy — three principles

1. **One spine, not four menus.** Collapse strategy → session → action-plan into a single **guided coaching flow** (an OWL wizard). The manager never leaves it mid-journey.
2. **The Command Center is the app.** A single home that answers *"who needs me, why, what do I do next?"* — so navigation is the exception, not the rule. Minimal clicks = the answer is already on screen.
3. **AI does the heavy lifting, the manager decides.** Diagnosis, questions, action items are pre-generated; the manager reviews/edits and commits. No blank forms.

---

## 4. New Information Architecture (menus)

**From ~16 BFSI menu items → 4 top-level:**

| New top menu | Replaces | Who |
|---|---|---|
| **Command Center** (home, client action) | Manager Dashboard + Strategic Selection + Realtime KPI + My Performance | role-adaptive (manager = team cockpit, banker = my performance) |
| **Coaching** | Coaching Strategies + Sessions + Action Plans (My/Team merged, filtered by role automatically) | all |
| **Performance** | KPI records + Targets + Integration | manager/admin |
| **Organization** | Branches + Regions | manager/admin |
| *(Configuration)* | AI Provider + templates | admin only |

My/Team duplication dies: a single list, auto-scoped by record rules + a "Me / My team" filter toggle.

---

## 5. The hero flow (built in the POC)

### 5a. Command Center
- **Pulse strip**: Team Score, Revenue Forecast, Needs Coaching (critical/high split), Active Plans.
- **Coaching Queue**: every banker ranked by *who'll move the needle most*, each row showing the **AI "why"** (e.g. *"Score 6/100, root cause: objection handling"*), a score ring, priority badge, and a one-click **✨ Coach**.
- **Today sidebar**: alerts, risers to reinforce, due reviews, branch trend sparkline.

### 5b. Banker Cockpit (slide-over)
Click a banker → drawer with: 30-day score trend, **KPI-vs-target bars** (what's driving the gap), **AI root-cause read** with confidence — and one primary CTA: **Start AI-Guided Coaching**.

### 5c. Guided Coaching Wizard (replaces the 6-tab form)
A 4-step OWL wizard with a progress stepper:
1. **Diagnose** — AI strengths / gaps / root cause, confidence meter → "Looks right".
2. **Strategy** — coaching themes + opening/probing/closing questions (accordions) + tips + optional **AI roleplay practice**.
3. **Session** — live cockpit: talking-point checklist + quick notes + **real-time AI assist chat**.
4. **Action Plan** — AI-drafted, **KPI-linked** action items (target, due date) → send to banker to commit.
- **Done** → success state explaining what auto-happens next; banker moves to *Monitoring*, Active Plans increments.

This is the whole point: **one continuous, guided journey** instead of hunting across Strategy → Session → Action Plan menus and forms.

---

## 6. Visual direction
Evolve the existing premium aesthetic (kept, made consistent everywhere):
- Deep-indigo header gradient `#1e1b4b → #4338ca`, violet/indigo accents `#7C3AED / #4F46E5`.
- White cards, 16px radius, soft shadows, Inter.
- Score color logic: ≥50 green, 25–49 amber, <25 red. Priority badges crit/high/med/low.
- Same palette applied to the *forms* too, not just the dashboard — that's what fixes cohesion.

---

## 7. Phased implementation (after you approve)

| Phase | Scope | Effort |
|---|---|---|
| **0 · IA cleanup** | Collapse menus to 4; kill My/Team dupes via record rules + filters; rename/fix "Strategic Selection" (avg not sum, or fold into Queue). Low risk, immediate relief. | S |
| **1 · Command Center** | New OWL home merging manager dashboard + coaching queue + today. Reuse existing `bfsi.ai.dashboard` API. | M |
| **2 · Banker Cockpit drawer** | Slide-over with KPI story + root cause + single CTA. | M |
| **3 · Guided Coaching Wizard** | The 4-step OWL flow wiring existing actions (`action_generate_strategy`, `action_create_session`, `action_create_action_plan`) behind one UI. Biggest win. | L |
| **4 · Form polish** | Apply card system + progressive disclosure to KPI Target (collapse 5 pages), de-dupe session AI fields. | M |
| **5 · Banker mirror** | Role-adaptive Command Center for the coachee (my KPIs, my plan, AI coach). | M |

Each phase ships independently; the module stays usable throughout.

---

## 8. Open decisions for you
- Keep the floating AI Coach panel, or fold it into the Command Center sidebar?
- "Strategic Selection" — delete it (the Coaching Queue replaces it) or keep as a power-user list?
- Localization: ship English + Vietnamese in lockstep for new UI strings?
- Do you want Phase 0 (menu/IA cleanup) landed first as a quick win before the big OWL build?

---

*POC: open `index.html` in this folder. Flow: Command Center → click a banker's **View** or **✨ Coach** → drawer → **Start AI-Guided Coaching** → 4-step wizard → done.*
