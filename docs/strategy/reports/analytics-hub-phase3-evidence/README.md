# AH-3 browser evidence pack — Analytics Hub polish + hardening

Driven on **https://care.biztinct.com** (vietuat) on 2026-08-07 between
04:05 and 04:40 UTC, in an isolated browser context, as a **throwaway
Operations-Manager-role persona** (`ah3_qa`, uid 8128) created for this pass
and deleted afterwards (`qa-fixture-cleanup.txt`).

The persona is a **plain BI creator**: `has_group('biz_bi.group_bi_creator')`
is True, `group_bi_modeler` is False, and `bi.ai.provider` /
`bi.ai.log` are unreadable to it — proven from its own browser session in
`security-probe.txt`, not asserted.

Every screen was reached by **clicking**, starting at the login page:

```
/web/login  →  (log in)  →  /bizapp shell  →  sidebar ANALYTICS ▸ Analytics
            →  Create Report  →  step 1 dataset card  →  step 2
            →  "Build it for me" (live LLM)  →  step 3  →  Save report
            →  the new dashboard, with the CMS chrome  →  sidebar ▸ Analytics
```

There is no deep link anywhere in this pack. The one URL typed by hand is
`/bizapp/action-1723`, and only to re-enter a screen already reached by
clicking, after a server restart between pixel cycles.

---

## 1. The walk (before the pixel pass)

| # | File | What it shows |
|---|---|---|
| 01 | `01-login.png` | the real entry point |
| 02 | `02-shell-sidebar-analytics.png` | the CMS shell; ANALYTICS ▸ Analytics is in the sidebar for this role |
| 03 | `03-hub-landing-1440-en.png` | hub landing, 4 workspaces, 7 dashboards |
| 04 | `04-wizard-step1-1440-en.png` | wizard step 1 (**before** the pixel pass — note the wrapped dataset names) |
| 05 | `05-wizard-step2-ai-box-1440-en.png` | **the AH-3 headline: the AI box is VISIBLE to a plain creator.** AH-2's pack had to record its absence |
| 06 | `06-wizard-step3-ai-result-1440-en.png` | the AI's answer materialised; the target list says "You don't have a dashboard of your own yet" |
| 07 | `07-wizard-step2-ai-materialised-1440-en.png` | Back from step 3: the AI config is in the ORDINARY pickers (measure `Total Price`, breakdown `Scheduled Date`/Month, split `Facility`, range `Last 12 months`) |
| 08 | `08-wizard-step3-preview-1440-en.png` | a real chart in the preview |
| 09 | `09-saved-dashboard-1440-en.png` | saved: dashboard 445 with widget 51, CMS chrome intact |
| 10 | `10-hub-recents-before-pixel-1440-en.png` | the recents strip picked it up |

The AI round trip was a **real** `bi.ai.nlq_chart` call to the configured
OpenAI provider (`bi_ai_log` id 28, `accepted = t`, 04:14:35 UTC), made by a
user who cannot read one row of `bi.ai.provider`. That is §4.1 working.

## 2. Writable targets vs the old read-scoped list

`security-probe.txt` records both lists, taken from the creator's own session:

* before saving anything: `get_wizard_targets()` → **`[]`**, while
  `search_read('bi.dashboard')` → **7** dashboards. The old wizard offered all
  seven; the save would have refused all seven.
* after saving one: `get_wizard_targets()` → **1** (`AH3 QA Dashboard`, the
  one they own), `search_read` → 8.
* `25-final-wizard-step3-targets-1024-en.png` is the same fact on screen.

## 3. First-run + degraded states

Staged by temporarily group-scoping workspaces 1–3 to `group_bi_admin` (raw
INSERT into `bi_workspace_groups_rel`, reverted — see `qa-fixture-cleanup.txt`),
which leaves the persona seeing exactly one workspace holding no dashboard.

| File | State |
|---|---|
| `20-hub-accesserror-fallback-1440-vi.png` | the AH-1 AccessError fallback, still rendering (in Vietnamese). **It fired for a bug this pass then fixed** — see §5 below |
| `21-firstrun-card-1440-vi.png` | the first-run card, creator variant, with the CTA |
| `22-firstrun-card-noncreator-1440-en.png` | the same card for a viewer-only persona: no CTA, "Ask your administrator to set up Analytics…" |

Wizard step 1 with no published datasets is not stageable on this deployment
without unpublishing six live datasets; the branch is the pre-existing AH-2
empty state (`No data is published for you yet`), unchanged by this phase and
covered by the template.

## 4. Pixel cycles

Three audit → fix → re-audit cycles, each driven by `evaluate_script`
computed-style measurements, not by eye. Full changelog in the phase report §6.

| Cycle | Before | After | Headline measurement |
|---|---|---|---|
| 1 | `03`, `04` | `11-cycle1-after-hub-1440-en.png`, `12-cycle1-after-wizard-step1-1440-en.png` | card heights in one row **203/210/179 → 222/222/222 px**; counts row **406/413/413 → 408/408/408** |
| 2 | `12` | `13-cycle2-after-wizard-step1-1440-en.png` | the CERTIFIED badge sits in the same place in all six cards instead of inline-or-wrapped |
| 3 | `18-cycle2-wizard-step2-1440-vi.png` | `19-cycle3-after-wizard-step2-1440-vi.png` | footer column **270–1170 = the pane's own box**; Back's left edge **294 = the heading's left edge**; the picker block **~350 → 321 px** with the dead column gone |

Both languages and both widths:
`16-cycle2-hub-1024-vi.png`, `17-cycle2-hub-1440-vi.png`,
`18`/`19` (wizard, vi, 1440), `14`/`15` (wizard, en, 1024),
`23-final-hub-1440-en.png`, `24-final-hub-1024-en.png`,
`25-final-wizard-step3-targets-1024-en.png`.

Keyboard (measured, with a **trusted** key press — §5.126):
opening the wizard puts focus on `.bi-wizard-pane` (`document.activeElement`
is the pane), and `Escape` closes it (`wizardStillOpen: false`).

## 5. A defect this pass found and fixed

Staging the first-run card is what exposed it. `bi.audit.log.get_recents`
finishes with `d.workspace_id.name`; a dashboard can be readable while its
workspace is not (the dashboard rule grants `owner_id = user` on its own).
With the workspaces group-scoped, the persona's own recent dashboard raised
`AccessError` on the WORKSPACE read, `get_hub_data` propagated it, and the
whole landing fell back to "analytics access has not been set up for your
account" — screenshot `20`. Fixed in `biz_bi_cms/models/bi_workspace.py`
(`_hub_recents` catches `AccessError` only, §5.47) and pinned by
`test_ah3_04b_recents_accesserror_does_not_kill_the_hub`. `21` is the same
scenario after the fix.

## 6. Console

`console-log.txt`. Zero errors and zero warnings on every screen. The single
`[issue]` advisory is pre-existing and **measured**, not assumed: a DOM sweep
over every `input`/`select`/`textarea` on the page returns exactly one element
without an `id` or a `name`, and it is the CMS shell's own
`select.cms-catchment-select`.

## 7. Fixtures

`qa-fixture-cleanup.txt` — every row this pass created, by id, and the
fresh-cursor (psql, separate connection) proof that all of it is gone,
including the `bi_audit_log` rows that had to go out with a raw scoped
`DELETE` before the account could be unlinked (§5.128).
