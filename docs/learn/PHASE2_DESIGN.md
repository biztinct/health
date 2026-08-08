# Phase 2 — The Care Coach, always on

Module: **`health_learn`** → `19.0.2.0.0` · builds on [Phase 1](PHASE1_DESIGN.md)

Phase 1 built the spine and proved it. Phase 2 is the highest deflection per unit
of work in the whole roadmap, because the content already exists: the Coach adds
a **retrieval surface over the same records**, plus 17 intents.

The user's binding requirement, in their words: *"this training/coach is always
active in live screens via some icon at the bottom so that if user gets stuck they
can click on this and understand the screen and flow properly at any time during
live production."*

---

## 1. Scope

**In:**

1. **A launcher on every screen** — mounted once in the web client shell, not per
   screen, so it survives new screens being added. Plus the `?` shortcut.
2. **A drawer**, not a modal: it does not dim, does not block, and never covers
   the thing you are stuck on. You reach for it *because* of that screen.
3. **Deterministic retrieval** over Phase-1 records + 17 new intents.
4. **Rich answers**: paragraphs, numbered steps that point at a real control,
   the calc breakdown, warn/ok callouts, an honest "grounded in" line.
5. **Capability-aware answers** read from the *real* gates, including honest
   refusals.
6. **Honesty rules enforced in code**, not in prose.
7. **One resolver seam** so an LLM can be plugged in later without touching the
   content spine or the honesty rules.

**Binding non-goals:**

- **No missions.** Phase 3.
- **No LLM.** The seam ships; the implementation stays retrieval.
- **No new content for OPS/CLINICAL/FINANCE.** The launcher appears there and
  says so honestly. Phase 4 fills it in.
- **The Coach never acts.** No button in an answer performs a product action.

---

## 2. What "always on" costs, and the mount point

`health_fieldservice` already patches `web.WebClient` to inject an
always-mounted `<SidebarHost/>` as a sibling of `<ActionContainer/>`
([ops_webclient_patch.xml:7](../../addons/health_fieldservice/static/src/xml/ops_webclient_patch.xml#L7)).
A `<CoachHost/>` beside it is the same move with a precedent to clone.

One patch, every screen, forever. Mounting per screen would have to be repeated
for each new client action and would be forgotten the first time.

**Which screen am I on?** The `ACTION_MANAGER:UI-UPDATED` bus event plus
`actionService.currentController.action.tag` — exactly how `SidebarHost._resolve`
already works. A new `learn.screen.action_tag` column maps a product action tag
to a learn screen key, so the mapping is data rather than a hard-coded dict.

---

## 3. New models

**`learn.screen`** — one row per screen the Coach knows.
```
key         Char   # "carecommand"
name        Char T
blurb       Text T # what this screen is, in one sentence  (SCREEN_CTX)
next_step   Text T # the honest "what should I do next here"
action_tags Char   # csv of product action tags that resolve to this screen
sidebar_key Char   # the leaf, for the visibility check
suggest_ids M2M learn.intent  # what to offer before anything is typed
```

**`learn.intent`**
```
key         Char unique
label       Char T          # the question, as a person would ask it
screens     Char            # "*" or csv of learn.screen keys
dynamic     Selection       # none | screen_blurb | next_step
show_me     Char            # csv of anchor keys the answer can point at
simpler     Text T          # the "explain more simply" rewrite, when one exists
practice_key Char           # a Phase-3 mission id; inert until Phase 3
active      Boolean
```

**`learn.intent.phrase`** — `intent_id`, `text` Char, **not translatable**.
The prototype's `match` list mixes English and Vietnamese in one bag, which is
right: a learner types in whichever language they think in, and both must hit.

**`learn.intent.block`**
```
intent_id, sequence
capability  Selection  # any | no_access | operator | manager | owner
kind        Selection  # p | steps | calc | calc_kpi | ok | warn | refusal | who | how | source
body        Text T
step_ids    One2many learn.intent.step
```

**`learn.intent.step`** — `block_id`, `sequence`, `text` T, `anchor` Char.

---

## 4. Capability, not role name

The prototype had four role names. The product has **real gates**, and the Coach
must read those or it will confidently tell someone they can do something they
cannot:

| Capability | Determined by |
|---|---|
| `no_access` | the screen's leaf is not in this user's sidebar — from `get_sidebar_data`, the same call Phase 1 already uses |
| `operator` | sees the screen, no CRM Manager group |
| `manager` | `health_crm.group_health_crm_manager` |
| `owner` | `access_roles.access_role_group_administrator` |

The four `takeover` variants map onto these one-for-one, and the mapping is
*checkable* rather than asserted: `nurse → no_access`, `crm → operator`,
`om → manager`, `owner → owner`.

**This is the drift-proof part.** If the CRM manager group is renamed or the leaf
is re-gated, the Coach's answer changes with it, because it asks the same
question the sidebar asks.

---

## 5. The resolver — and the seam

```python
learn.intent.resolve(text, screen_key) -> {intent_key, score} | None
```

Scoring, in order: exact phrase → phrase is a substring of the question →
question is a substring of a phrase → ≥2 topic-word overlap. `+25` when the
intent is scoped to the screen the user is actually on. Below a floor of 20,
**return nothing** — a wrong answer costs more than no answer.

Two properties the prototype learned the hard way and this keeps:

- **A stopword list in both languages, diacritic-folded.** Without it "what dose
  of antibiotic" matched *"what does this page do"* on the word "what" alone.
- **≥2 topic words, or one fully-matched phrase of ≥6 characters.** One shared
  common word is not a match.

**The seam:** `_resolve_hook(text, screen_key, candidates)`. Retrieval is the
default and returns an intent key or `None`. An LLM implementation would return
the same shape — *an intent key from the candidate list* — never free text. That
is what preserves the promise below: the model may choose, but it may not speak.

---

## 6. Honesty, enforced in code

Four rules, each with a test rather than a convention:

1. **Never claims to have acted.** No block kind renders a control that calls a
   product method. `test_coach_never_acts` asserts no answer HTML contains a
   `data-act` outside the Coach's own closed set (point-at, simpler, open
   lesson, ask another).
2. **Never invents a domain fact.** Answers are assembled from stored blocks
   only; there is no free-text path from the resolver to the screen. The `price`
   intent exists precisely to *refuse* — prices are not in the spine.
3. **Fallback says what it CAN answer.** No answer → the screen's suggested
   intents, named. Never a bare "I don't know".
4. **Grounded-in line.** Every answer that makes a factual claim carries a
   `source` block. `test_every_factual_intent_cites_a_source` enforces it.

---

## 7. Anchors on a live screen

Point-at reuses `flashRing(anchor)` from Phase 1, which returns `false` when the
anchor is not in the DOM. That return value is the honesty mechanism: an anchor
of kind `practice` in `anchors.json` has **no product control**, so the Coach
must say "this is a teaching view, not a control on your screen" rather than
scroll to nothing. Phase 1 declared that distinction for exactly this moment.

---

## 8. Tests

1. `test_resolver_precision` — the clinical questions that leaked in the
   prototype ("what dose of antibiotic", "what is her blood pressure") resolve to
   **nothing**, in both languages.
2. `test_resolver_recall` — every intent's own label resolves to itself.
3. `test_capability_answers` — a user without the CRM Manager group gets the
   refusal variant; one with it gets the affirmative.
4. `test_coach_never_acts` — no product action reachable from an answer.
5. `test_every_factual_intent_cites_a_source`.
6. `test_fallback_names_what_it_can_answer` — never empty.
7. `test_every_screen_is_reachable` — every in-scope leaf maps to a
   `learn.screen`, and every `action_tag` resolves.
8. `test_show_me_anchors_are_registered` — extends the Phase-1 anchor lint to
   intent `show_me` and step anchors.
9. `test_no_unresolved_tokens_in_answers` — both languages, every capability.
10. The Phase-1 suite still passes.

---

## 9. Report-back

- Intent count, phrase count, and the resolver's precision/recall numbers.
- Which screens have real answers vs. an honest "not covered yet".
- Bundle size delta.
