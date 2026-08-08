# Phase 3 — Practice missions

Module: **`health_learn`** → `19.0.3.0.0` · builds on [Phase 1](PHASE1_DESIGN.md) and
[Phase 2](PHASE2_DESIGN.md)

A lesson shows you. A mission makes you decide. This is where the brief's hardest
rules land: completion is demonstrated judgement, a wrong choice is a recovery
rather than a rejection, and every risky action is intercepted by a consequence
card *before* it happens.

---

## 1. The one decision that shapes everything: where a mission runs

The roadmap said "mission engine driving the **real** screens through the anchor
registry". Building it, that turned out to be the wrong call, and the reason is
worth stating plainly:

**A mission tells you to press Junk. On a real screen, that is a real Junk.**

Mission step 5 of M1 is "send the reply" and step 7 is "release the claim". Driven
against production those are a real message to a real phone and a real ownership
change on a real conversation — and the one thing a practice surface must never do
is have consequences the learner did not intend.

So missions run on the **practice replica**: the versioned fixture with no server
behind it, structurally incapable of touching a patient, a phone or an invoice
(analysis §8). The banner is the last line of defence rather than the only one.

**The anchors still earn their keep.** A mission step names `cc-claim`, and that
one name addresses the replica's claim bar *and* the real Care Command banner —
which is what lets Phase 2's Coach point at the live control using the same key
the mission taught. One vocabulary, two surfaces, no translation layer.

**In:** the mission engine, M1 and M2 in full, M3/M4 as labelled outlines with
content, consequence interception, seeded anomalies, recovery, debrief and
confidence.

**Binding non-goals:** no product action is ever invoked; no mission writes
anything except the learner's own progress and events; no new content outside CRM.

---

## 2. Models

Four, following the Phase-1 shape.

**`learn.mission`** — `key`, `line` (daily|reach), `icon`, `name` T, `summary` T,
`duration_min`, `kind` (full|outline), `outline_note` T, `confidence_key`,
`confidence_gain`, plus the two blocks every flagship mission carries:

```
consequence_title / consequence_scope / consequence_reversible / consequence_verify   (T)
anomaly_title / anomaly_body                                                          (T)
```

The consequence four-field shape is the brief's, not mine: **what this touches ·
can I undo it · what to check first** is the question set a person actually needs
before a risky action, and splitting it into fields stops an author from writing
three sentences and omitting reversibility.

**`learn.mission.step`** — `sequence`, `key`, `nav` (screen), `target` (anchor),
`instruction` T, `detail` T, `hint` T, `is_decision`, `is_consequence`, `is_undo`,
`option_ids`.

**`learn.mission.option`** — `label` T, `is_correct`, `recovery` T. Recovery text
is required on every wrong option: an option that can be chosen and not explained
is a rejection.

**`learn.mission.note`** — the debrief, `kind` in (did|check). "What you did" and
"before doing this for real, always check".

---

## 3. Rules enforced in code, not by authoring discipline

| Rule | Enforcement |
|---|---|
| One decision per step | `_check_one_decision`: a step with options may have no other role |
| A wrong option always recovers | `@api.constrains`: `is_correct = False` ⇒ `recovery` required |
| Exactly one right answer | `@api.constrains` on the step |
| A risky step is intercepted | `is_consequence` steps refuse to advance until the card is acknowledged |
| Missions never act | the mission view renders into the practice shell only; no `orm.call` except progress/events |
| Every target is a registered anchor | extends the Phase-1 anchor lint |

**The anomaly is not decoration.** Each flagship mission seeds exactly one
situation where the obvious answer is wrong — M1: everything says *hurry* and the
consent record says *no*. It is revealed in the debrief, after the decision, so
the learner meets it as judgement rather than trivia.

---

## 4. Confidence

`learn.progress` gains `confidence` (a JSON-free integer per key, stored on a new
`learn.confidence` row: `user_id`, `key`, `score`). A completed mission adds its
`confidence_gain`; **a recovery reduces the gain**, because a mission you had to
be talked out of is not the same as one you got right.

That asymmetry is the honest part: without it, "confidence" measures completion,
which the learner already sees as a tick.

---

## 5. Tests

1. Every mission step's `target` is a registered anchor.
2. Every wrong option has recovery text, in both languages.
3. Exactly one correct option per decision step.
4. Every full mission has a consequence card with all four fields.
5. Every full mission has exactly one anomaly.
6. Debrief has both `did` and `check` notes.
7. Confidence: completing with a recovery scores strictly lower than clean.
8. No unresolved tokens in any mission string.
9. The mission view calls no product method (source scan, as Phase 2).
10. Phases 1 and 2 still pass.
