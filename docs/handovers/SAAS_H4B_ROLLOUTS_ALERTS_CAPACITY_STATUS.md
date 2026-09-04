# SAAS H4b — updating the fleet safely, noticing when it breaks, knowing when it is full, and saying so in public

Read FIRST: `docs/handovers/SAAS_PORT_PROGRAM.md` (decisions, plumbing, rails R1–R13, design bar,
ledger H1–H76 — H61–H76 are H4a's and describe the cockpit you are extending), then
`docs/SAAS_RUNBOOK.md`, then `SAAS_H4A_TENANT_COCKPIT.md`. This phase ports FLEET **P2B** (rollout)
and **P3** (alerts, capacity, status page). Its binding ledger entries: **F23, F24, F25, F26, F27,
F28, F29, F30, F31, F32, F33, F34, F35, F36, F37, F38, F39, F40, F41, F42, F43, F44, F50, F51**,
plus H4a's **H62** (cloning goes through the framework, not `createdb`) and **H70** (a threshold must
exclude the incident that motivated it). Source to port (READ-ONLY, rail R10):
`gitlocal/pb_tenants/models/{rollout*,alert*,service.py}` and its cockpit JS/XML/SCSS.

Design bar (verbatim, binding): **"Extreme WOW, intuitive, out-of-this-world experience, best in
class."** H4b's hero: **the rollout screen** — a release walking the fleet as a living diagram, ring
by ring, each customer a card that fills as its window opens, its update runs and its health gate
passes, with Pause / Continue now / Retry / Skip / Abort always one press away and always saying
what they will do. Second hero, and the one that earns its keep today: **the Alerts screen**, because
with no mail account it is the only place a problem can be seen. Zero dead-ends, plain language,
motion with purpose, `ic()` icons, no emoji, no gradients. Chrome validation mandatory.

White-label rule (binding): "Odoo" never in a user-visible string — **including the public status
page and any alert text** (F43: the word reached a user-visible string through a system account
name; the test that caught it asserts `'odoo' not in text.lower()` for every alert kind, and it is
worth copying here). The product name comes from `biz_tenants.brand`.

---

## 0. The owner's decisions that shape this phase (2026-09-04)

1. **Build mail, leave it silent.** There is still no outgoing mail account (1,034 messages sit in
   `exception`). Everything that would send is built, tested and honest about being dark.
   **Consequence for the design, and it is not a small one: the ALERTS SCREEN is the primary
   channel, not the fallback.** Email is the second channel that lights up the day an account is
   connected. Anything that would have been sent is recorded and readable in the cockpit, so a
   problem is visible to a person who opens the platform even though nothing was posted to them.
2. **Alerts go to the owner alone, plus a morning summary.** Recipients are a setting
   (`biz_tenants.alert_to`, default the platform administrator's own address); the summary is a
   daily cron. Both are built; neither sends until §3.2's gate opens.
3. Carried forward: brand from the setting; never-list from H4a; the apex is `carejiox.com`; the
   pilot customer is `hhh`.

## 1. Scope

1. **Rollout** (§3.1): `biz.release` grows a rollout; rings; per-customer night windows in their own
   time zone; a queued worker with a lock, a retry and a health gate; Pause / Continue now / Retry /
   Skip / Abort; the rehearsal on a restored copy (rail R4) enforced, not hoped for.
2. **Alerts** (§3.2): `biz.alert` with kinds, severities, dedup and reconciliation; the sweep;
   the Alerts screen and the fleet banner; delivery built and dark; "Send a test email" that says
   plainly why it cannot; the platform checklist's mail row made honest.
3. **Capacity** (§3.3): the gauge, the provisioning refusal (H4a already refuses below a memory
   floor — this replaces that floor with the real guard), the cost setting, the link to
   `docs/SAAS_RESIZE_RUNBOOK.md`.
4. **Status page** (§3.4): the writer, the nginx location H3 already installed, no customer names,
   self-declared staleness, the platform's own zone named.
5. Tests (§5), commits (§6), ledger from H77, runbook update, report (§7).

## 2. Binding NON-goals

- No feature switches, plans, invoices, trials, seat limits, the paused door, or support access —
  **H4c**. Build no model for them.
- Do not connect a mail account, do not create one, do not sign up for a sending service. If you
  find credentials lying about, do not use them.
- Do not run a real rollout against `hhh` that installs anything the master does not already have;
  the live validation is a rollout of the CURRENT release (a no-op update) plus a rehearsal on a
  restored copy. Rail R3 (master, then template, then customers) and R1 (never a silent write).
- No changes to nginx, certbot, sudoers or the conf (H3 owns them). `/var/www/carejiox-status/`
  already exists and is owned by `odoo` — write into it, do not re-create it.
- Do not "improve" H4a's provisioning, meters or backups beyond the capacity guard swap (§3.3).

## 3. Architecture

### 3.1 Rollout — a release walks the fleet

`biz.rollout` (one release, one walk): `release_id`, `state`
(`draft|rehearsing|running|paused|done|aborted`), `ring` (the current one), `started_at`,
`ring_done_at`, `note`, `task_ids`. `biz.rollout.task` (one customer, one attempt): `tenant_id`,
`ring`, `state` (`waiting|due|running|done|failed|skipped`), `window_start`, `window_end` (UTC),
`attempts`, `log`, `health_verdict`, `error_lines`.

**Rings, in order**: `rehearsal` (a restored copy of the canary — never a customer),
`template`, `canary` (one named customer), `early` (a named few), `everyone`. A ring only opens
when the one before it finished clean.

Rules, each with its ledger number, and each of them a **pure function with its own test** (R6):
- **Windows are the customer's night, said in the customer's clock.** Store UTC; render with
  `to_local(dt, tz)` and NAME the zone ("tonight 22:00–01:00 · their time · Asia/Ho_Chi_Minh") —
  **F32**; the operator's own typing converts the other way — **F17**. `render_range` formats what
  it is handed and will happily print a lie.
- **An unset Datetime is `False`, not `None`** — **F23**. Test falsiness. It broke Payobook's state
  machine the first time a wave finished.
- **"Continue now" skips the window, never the queue** — **F30**. `advance()` only ever looks at the
  CURRENT ring; setting "run now" on a customer in a later ring must be a refusal **by name**
  pointing at the right button, not a silent no-op.
- **The health gate** reads the target's ERROR/CRITICAL lines since the update started, from the
  last ≤ 20 MB of `/var/log/odoo/odoo-server.log`, matching the database column, comparing
  timestamps as strings because the box and the framework are both UTC — **F27**. It honours
  `biz_tenants.health_ignore` (H4a already has it) and **records ignored lines rather than dropping
  them** — **F25**. A restore logs errors of its own, so a rehearsal's window starts when the
  UPDATE starts, not when the restore does — **F26**.
- **Rail R4 is enforced.** No usable backup for the canary + at least one live customer = a blocker
  on Start, naming the customer and the button that takes a backup — **F31**. The rehearsal restores
  the canary's latest backup to `<slug>-staging` and drops it in a `finally` that wraps the restore
  itself (**F26**). H4a's restore-to-practice already does this; reuse it, do not rewrite it.
- **One rollout at a time, enforced by the database.** `pg_advisory_xact_lock(hashtext('biz_tenants.rollout_start'))`
  on entry to `rollout_start`, because the whole rehearsal runs before the first commit and two
  presses inside ninety seconds are two rollouts destroying each other's practice copy — **F50**.
  And the practice copy is a shared resource with one name — **F51** — so a paused rollout must be
  called off rather than left lying about.
- **The worker is a cron that only does what a person queued** (R1): it picks due tasks in the
  current ring, updates through H4a's `_tenant_env` (which signals — **F56**), writes a per-customer
  log line, and stops the whole rollout on a failed health gate. It never opens a new ring on its
  own if the previous ring had a failure.
- **Measured, not guessed** (**F33**): record the real per-customer time on this fleet in the report.

### 3.2 Alerts — and the screen that is the channel

`biz.alert`: `kind` (a stable key), `severity` (`info|warning|critical`), `tenant_id` (optional),
`subject`, `body_text`, `first_seen`, `last_seen`, `count`, `state` (`open|acknowledged|resolved`),
`spoken_at` (when it was actually delivered), `channel_state` (`dark|sent|failed`).

**Kinds to ship** (each with a plain-English sentence and a "what to do next"): `tenant_unreachable`,
`tenant_errors`, `backup_missing`, `backup_stale`, `backup_small` (H4a's F59 verdict), `cert_expiring`,
`cert_missing`, `disk_low`, `memory_low`, `capacity_full`, `rollout_stopped`, `status_page_unwritable`,
`mail_not_configured`. The last one is not noise: it is the honest statement that the platform
cannot reach a human, and it stays open until an account exists.

- **The sweep** is one cron every 15 minutes. It reads the log **once** for every database it cares
  about, not once per customer — **F39** — and the master's own error count is gathered and
  deliberately NOT alerted on, because this box logs its own test runs.
- **Dedup and reconcile**: raising the same kind for the same target updates `last_seen`/`count`;
  a reading that shows the problem gone resolves it. **A resolved critical shows on the public page
  as an incident for seven days** — so alerts raised while validating must be **deleted, not
  resolved** (**F41**), and your live validation must end that way.
- **Never stamp "we told you" unless it left** — **F40**. `spoken_at` is written per record only
  after a successful send. With mail dark, `channel_state` stays `dark` and `spoken_at` stays empty
  — which is the truth, and which is why the screen matters.
- **Severity floor**: an `info` alert must not be announced as "something needs your attention" —
  **F68**. The digest says "For information" when nothing worse is in the group.
- **The Alerts screen** (the phase's second hero): open alerts grouped by severity, newest first,
  each card carrying the plain sentence, the customer, when it started, how many times it has
  happened, the ignored-line count where relevant, and two buttons (Acknowledge / Resolve). A
  **"Since you were last here"** strip at the top — because with no mail this screen is how the
  owner finds out anything happened. A critical anywhere paints a banner across the fleet screen
  (**F40**'s `alert_channel_down` precedent, generalised).
- **Delivery, built and dark.** `_send_alert_mail` builds the message and asks the platform whether
  it can send: no `ir.mail_server` row, or no `mail.default.from`, means it returns
  `('dark', reason)` — it does NOT raise, does NOT queue 1,035th failed message, and writes the
  reason on the alert. **"Send a test email"** exists and answers, in plain words, "There is no
  outgoing mail account on this platform yet, so nothing can be sent. Connect one under … and press
  this again." — never a stack trace, never a lie. The platform checklist row for mail is RED with
  that sentence (**F5**: the original check tested `ir_mail_server` count > 0 and was a lie by
  omission; **F42**: the checklist must not hide itself once the other rows are green).
- **The morning summary** is a daily cron building the same digest; dark today, and it says so.
- **Under `config['test_enable']` the send path is skipped entirely** — the suite's own attempts
  wrote five ERROR lines per run into the log the health gate reads (**F67**/F25/F44).

### 3.3 Capacity

Replace H4a's raw memory floor with the real guard. `biz_tenants.tenant_cost_mb` — a **setting**,
default **60**, and the report must state plainly that this is a **policy, not a measurement**
(**F34**). The measurement is H4a's: a customer's registry costs ~11 MB across the three processes
on this box; sessions, asset caches and a working clinic's working set are the rest, and they are
transient and unmeasurable at rest. `biz_tenants.capacity_reserve_mb` default 400. Room =
`(free − reserve) ÷ cost`, floored at 0. The gauge sits on the fleet screen; provisioning refuses at
zero **by name**, pointing at `docs/SAAS_RESIZE_RUNBOOK.md` (H3 wrote it) and at the setting. The
`memory_low` and `capacity_full` alerts come from the same numbers. Do not size anything from the
registry LRU — it is derived from `limit_memory_soft` and is not a real bound (**F6**).

### 3.4 The public status page

`/var/www/carejiox-status/index.html`, written by the application, served by nginx (H3 installed
`location = /status` and `location ^~ /status/` — the `^~` is load-bearing against the static-asset
regex). Temp file plus `os.replace`, so a reader mid-write gets the old page.
- **It names no customer, ever.** One pure function `status_state(...)` is the only door between
  what the platform knows and what the page says, and a test feeds it customer names and asserts
  none come out.
- **A file has no reader to ask what time it is** — **F38**. Render windows in the platform's own
  zone and NAME it ("tonight 19:34–01:34 · Asia/Ho_Chi_Minh"). Setting `biz_tenants.status_tz`,
  default the platform company's zone.
- The page checks its own age in the reader's browser and says so after 15 minutes; on the platform
  side a missing or unwritable folder raises `status_page_unwritable`.
- Driven by a 5-minute cron, by the end of every alert sweep, and by every notice sent or cleared.
- **`_write_status_page` returns early when `config['test_enable']` is set** — **F44**, at the
  writer, not in each test, because a file written by a model is not rolled back by a test and a
  suite run on the live platform once published a page built from invented customers. Prove it: the
  page's timestamp must not move across a full test run, and must move again on the next cron.
- White-label: run F43's assertion over every string the page can contain.

### 3.5 Cockpit

New views `rollout` and `alerts` beside H4a's `fleet | wizard | detail | sync`. All of F35 (the
stylesheet's root blocks), F36 (`min()` units), F37 (`.bzk` specificity), F57 (`bzk-modal-scrim`),
F15/F16 (`t-foreach` names, no built-ins in templates), F47 (`useState`'s return value IS the
subscription; watch a signature string, not a map rebuilt every poll), F58 (`t-att-` and boolean
`true`), F10 (bind `document` with capture) apply again — H4a hit several of them; read its ledger
before writing SCSS.

## 4. Order of execution

Rehearse on a scratch clone of `carejiox` (**always `--db-filter=^<clone>$`** — ledger H32) with a
throwaway customer provisioned on it, because a rollout needs a fleet. Then live, in this order:
1. Deploy through `carejiox-deploy`; `biz_tenants` upgrades on the master only; `biz_tenancy` and
   `health_tenancy` upgrade on the master, **the template** (`-D carejiox_template`, then re-record
   its crons — **F9**) and **`hhh`** (`-D hhh`).
2. Alerts: let one real sweep run; read the Alerts screen; confirm `mail_not_configured` is open and
   honest; press "Send a test email" and confirm the plain refusal.
3. Capacity: the gauge on the fleet screen with real numbers; provisioning's refusal proven by
   temporarily setting `tenant_cost_mb` absurdly high, then **putting it back**.
4. Status page: `curl -sI https://carejiox.com/status` shows nginx's `Last-Modified` and `ETag`
   (the proof it is a file and not the application); the body names no customer.
5. Rollout: cut a release from the master with real notes; run a rollout whose canary is `hhh`, with
   the rehearsal on a restored copy. The update itself is a no-op (`hhh` is already in step), which
   is exactly the safe live test. Watch the rings; pause it; continue; let it finish.
6. **Delete the alerts your validation raised** (**F41**) and confirm the public page shows no
   incident that never happened.
7. 15-minute error watch; memory; no stray `odoo-bin`; clone and throwaway dropped.

## 5. Numbered test cases

1. Ring order and gating (pure): a ring opens only when the previous finished clean; a failure stops
   the walk; `advance()` looks only at the current ring; "run now" on a later ring is refused **by
   name** (F30).
2. Windows: stored UTC, rendered in the customer's zone with the zone named (F32); the operator's
   local typing converts to UTC and the preview equals what is delivered (F17); an unset window is
   falsy-safe (F23).
3. The lock: two `rollout_start` calls in one transaction — the second waits and then gets the
   refusal, never a second rollout (F50).
4. R4: with no usable backup and a live customer, Start is blocked and the message names the
   customer and the button (F31). The rehearsal's restore lives inside the try whose finally drops
   the copy — prove the copy is gone after a raised restore (F26).
5. Health gate: ignored lines are counted and recorded, not dropped (F25); the window starts at the
   update, not the restore (F26); the log query reads one tail for many databases (F39).
6. **The suite must stand down the real fleet** (F28): `setUp` decommissions the real customers and
   aborts real rollouts inside the transaction that is rolled back. And the cursor's commit refusal
   is patched on the **instance**, not the class (F29) — H4a hit this too (H69).
7. Alerts: dedup increments `count` and moves `last_seen`; a clean reading resolves; `spoken_at`
   stays empty while dark (F40); an `info` group is announced as "for information" (F68); every
   alert kind's text passes the no-"Odoo" assertion (F43).
8. Delivery dark: with no mail server, `_send_alert_mail` returns `('dark', reason)`, raises
   nothing, queues nothing, and writes the reason; "Send a test email" returns the plain sentence;
   the checklist row is red and the card does not hide itself (F5/F42).
9. Under `test_enable`: no mail is attempted at all (F67) and `_write_status_page` returns early
   (F44) — assert the page's mtime is unchanged across the run.
10. Capacity: room = (free − reserve) ÷ cost, floored at 0; provisioning refuses at zero naming the
    runbook; the refusal disappears when the setting is restored. `tenant_cost_mb` is read as a
    setting, not a constant.
11. Status page: `status_state()` fed customer names emits none (the F44-adjacent privacy test);
    windows carry the platform zone by name (F38); a missing folder raises
    `status_page_unwritable`; the file is written temp+replace.
12. Full suites over every module touched (F49): `/biz_tenants,/biz_tenancy,/health_tenancy,
    /biz_access,/biz_kit`.
13. Chrome on the clone (`docs/handovers/saas_h4b_shots/clone_*.png`): the rollout screen through a
    whole walk including a pause and a continue; the Alerts screen with several severities; the
    capacity gauge at zero showing the refusal; the status page in a browser.
14. Chrome on live (`live_*.png`): the Alerts screen with the real `mail_not_configured` alert; the
    test-email refusal; the gauge with real numbers; `https://carejiox.com/status` in a browser and
    its `curl -sI` headers; a real rollout over `hhh` with the rehearsal, paused and continued; the
    fleet banner while a critical is open, and gone after it is deleted.
15. Live health: master and `hhh` both answer 200 throughout; the 15-minute watch is clean; the
    validation alerts are **deleted** and the public page shows no incident (F41); memory recorded.

## 6. Commits (explicit staging, no push)

1. `feat(biz_tenants): rollout — rings, night windows, the health gate, pause and continue`
2. `feat(biz_tenants): alerts — the screen that is the channel while there is no mail account`
3. `feat(biz_tenants): the capacity gauge and the refusal that points at the resize runbook`
4. `feat(biz_tenants): the public status page, written by the platform and served by the web server`
5. `docs(saas): H4b handover, ledger H77+, runbook update, screenshots`

## 7. Report back

1. **Owner summary (6 lines)**: what a release now does to the fleet; where problems appear and the
   plain fact that nothing is emailed yet; how many more customers fit; the public page's address.
2. Per numbered test with evidence.
3. The `odoo.tests.result` lines; the log ERROR grep.
4. Rollout timings measured on this fleet, per ring and per customer (F33).
5. The capacity numbers as they read live, and the sentence distinguishing the **policy** (60 MB)
   from the **measurement** (H4a's ~11 MB) — in the owner's words.
6. The alert kinds as shipped, with each one's plain sentence and its "what to do next".
7. Proof the status page is served by the web server and not the application (`Last-Modified` +
   `ETag`), and the privacy test's output.
8. Confirmation the validation alerts were **deleted**, and that the public page shows no incident.
9. Ledger entries (from H77); commit hashes; clone and throwaway dropped; runbook updated.
10. Decisions the handover did not cover; and the list of seams H4c needs (features, plans,
    invoices, seat limits, the paused door, support access).
