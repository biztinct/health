# Care Command — Phase 4 Report: "AI Assist"

**Implementer:** Opus 4.8 · **Date:** 2026-07-21 · **DB:** vietuat
**Handover:** `docs/strategy/handovers/care-command-phase4.md`
**Result:** `0 failed, 0 error(s) of 34 tests` (2026-07-21 07:50:39 UTC, pid
1949216), EXIT:0, HTTP:200 — combined `/health_care_command_ai` +
`/health_care_command` tags.

---

## 1. What was built (file list)

New module **`health_care_command_ai`** (version **19.0.1.0.0**; `auto_install:
False`; depends `health_care_command`, `biz_bi`). The core stays AI-free — its
"grep AI = 0" purity holds; the AI layer composes from OUTSIDE via the core's
public seams (`_ensure_access` / `_guarded` / `_detail_timeline`) and a
`patch()` on the already-exported `CareCommand` OWL component.

### Deliverable 1 — settings (`res.config.settings` _inherit)
- **`models/res_config_settings.py`** — `care_ai_enabled` (master, default
  False), `care_ai_provider_id` (m2o `bi.ai.provider`), `care_ai_allow_cloud`
  (default False), `care_ai_drafts` + `care_ai_brief` (default True). Stored as
  `ir.config_parameter`. **`set_values()` overridden to persist explicit
  `'True'/'False'`** so the two default-True toggles can actually be switched
  off (§5.36 — a falsy `set_param` unlinks the row and the default snaps back).
- **`views/res_config_settings_views.xml`** — a CRM-manager-gated settings
  block under the health app (clones the health_ai_coding placement).

### Deliverable 2 — reply draft
- **`care.ai.assist.ai_draft_reply(conv_id)`** — group-gate + company-scope via
  `care.conversation._guarded`, run the runtime gate, build the REDACTED context
  (§below), call `provider._complete(system, prompt, force_json=False)`, return
  `{text}`. **No send, no post** — the ONLY write on this path is the audit row.
- **JS/XML** — a `Draft` button in the composer (before the send button,
  rendered ONLY when `aiCanDraft`). Clicking fills the composer (appended on a
  newline) and toasts "AI draft — review before sending". Never sends.

### Deliverable 3 — continuity brief
- **`care.ai.assist.ai_brief(conv_id)`** — same gate; returns
  `{bullets, stamp}` where `stamp = "Generated just now by <provider.name>"`.
  On-demand only.
- **JS/XML** — an "AI" card at the TOP of the care rail (above the Care/History
  tabs), rendered only when `aiCanBrief`. A `Generate brief` button →
  3–5 bullets + a visible provider stamp + a dismiss ×. The card is keyed to the
  open conversation (`briefConvId === state.selected`) so switching threads
  hides a stale brief.

### Deliverable 4 — UI gating (no core edit)
- **`care.ai.assist.ai_flags()`** returns `{enabled, drafts, brief,
  provider_name}` (group-gated). The OWL `patch` fetches it on `onWillStart` and
  every `.ai-only` node is gated on `aiCanDraft` / `aiCanBrief`. **AI OFF (or
  the module absent) → zero AI DOM**, so the wall is byte-for-byte Phase 3.
- **Seam used:** a `patch(CareCommand.prototype, …)` importing the core's
  already-exported `CareCommand` (`export class CareCommand` was present from
  Phase 1 — no new core export line needed), plus a `t-inherit` extension
  template. See §5.

### The runtime gate + redaction (the kernel)
- **`_gate()`** (handover §5.2): `enabled = master AND provider exists AND
  provider._is_usable() AND (provider == 'ollama' OR allow_cloud)`. The
  health_ai_coding cloud-refusal shape, cloned; config params read DIRECTLY
  (never cached — §5.48).
- **`_ai_context(rec)`** (§5.3): last 15 `_detail_timeline()` events →
  `IN/OUT/NOTE: <text>` lines + Channel/Status/Next-booking/Lead-stage facts,
  then redacted, capped 4000 chars. No ids, no phone/email, no raw HTML.
- **`_redact(text, rec)`**: the ai_coding `_redact` generalised to BOTH the
  partner's AND the lead's identity (name/phone/mobile/email + the
  conversation's own normalized phone/email), longest-first, `[BN]/[SĐT]/
  [EMAIL]` tokens + a per-name-token pass. The SAME redacted string is the only
  thing that could ever be logged.
- **Audit:** `bi.audit.log.sudo().log('ai_request', record=rec, payload={
  capability, conv_id, provider, duration_ms})` — capability + provider +
  duration only, **no content** at all. A provider failure surfaces a clean
  `UserError("AI is unavailable — continue manually.")` and writes NO audit row.

## 2. Test transcript + T33–T38 mapping

`2026-07-21 07:50:39,842 1949216 INFO vietuat odoo.tests.result: 0 failed,
0 error(s) of 34 tests`

| Test | Proves | Status |
|------|--------|--------|
| **T33** | gate: master off → `ai_flags().enabled` False + draft `UserError`; usable cloud provider + `allow_cloud` off → refused; + on → enabled; Ollama → enabled regardless | ✅ |
| **T34** | draft returns text, `force_json=False`, and creates NO mail.message / zalo.message; status + unread UNCHANGED | ✅ |
| **T35** | partner name/phone/email seeded into a timeline note → captured prompt contains `[BN]/[SĐT]/[EMAIL]` and NOT the raw values | ✅ |
| **T36** | brief → bullets; exactly ONE `ai_request` audit row with `capability='brief'` + provider + conv_id + duration_ms; no content key in the payload | ✅ |
| **T37** | plain (non-CRM) user → `AccessError` on `ai_flags`/`ai_draft_reply`/`ai_brief`; a company-2 conversation is unreachable from a company-1 CRM user (`UserError`) | ✅ |
| **T38** | `_complete` raising → clean `UserError`, no crash, no audit row | ✅ |
| T1–T32 (core) | Phase 1–3 suites still green after the core vi.po touch | ✅ (of 34) |

## 3. Server reality (§6 — report, don't fix)

| Item | Finding |
|------|---------|
| `health_care_command_ai` | installed, **19.0.1.0.0** |
| `health_care_command` | upgraded, **19.0.3.0.1** (i18n touch only) |
| `bi.ai.provider` rows | **4**: Anthropic (no key, inactive), OpenAI (has key, active), **Ollama "Ollama (local)"** `llama3.1:8b` (no key, inactive), **Ollama "AI Coding Demo (local)"** `qwen2` @ `127.0.0.1:11434` (active). An Ollama sovereignty path EXISTS. **Reachability NOT probed — no model was called.** |
| `health_care_command_ai.*` config params | **0 rows** → settings default **OFF**. `ai_flags().enabled` is False; with AI off the UI is byte-identical to Phase 3 (zero AI DOM). |

No live model call was made (handover §3/§6 — requires explicit user approval).
No provider/credential was created or modified.

## 4. Deviations (declared)

1. **No new core JS export.** The handover offered "export the component class …
   that ONE export line is the single permitted core touch". It was
   unnecessary: `CareCommand` was ALREADY `export`ed from Phase 1
   (`care_command.js:31`). So the ONLY core change is the i18n touch below —
   under the "one declared export/i18n touch max" budget.
2. **Core i18n touch (sanctioned by §7).** Added the two missing Phase-3 gear
   tooltips `"Manage reply templates"` / `"Manage watchlist phrases"` to
   `health_care_command/i18n/vi.po` (`#. odoo-javascript`) and bumped the core
   to **19.0.3.0.1**. No code/logic change.
3. **Brief card placement = above the rail tabs** (top of the care rail), not
   inside a specific tab — matches "an 'AI' card at the top of the care rail".
4. **No live browser drive** — no `/odoo` credentials this session; the
   draft/brief/off-state surfaces are declared for the reviewer's selective
   pass (§6 below). This is the handover's own instruction.

No other deviation: no AI in the core module, no auto-send anywhere (no code
path from AI output to any `action_send_*`; no disabled send button either), no
junk-scoring / intent / booking / re-ranking, no edit to biz_bi /
health_ai_coding, no clinical content in prompts, no provider/credential change.

## 5. Seam used (for the reviewer)

- **Component patch:** `patch(CareCommand.prototype, {…})` importing
  `@health_care_command/js/care_command`. `super.setup()` runs the core setup;
  the patch adds `this.ai = useState(…)` + an `onWillStart` that calls
  `ai_flags()`, plus `aiDraft`/`aiBrief`/getters. No core JS edit.
- **Template:** `<t t-inherit="health_care_command.CareCommand"
  t-inherit-mode="extension">` with two xpaths (before `.sendbtn`; before
  `.crail-tabs`). No core XML edit.
- **Services:** `care.ai.assist` (AbstractModel, no table/ACL) borrows the
  core's group gate + company scope on every entry point.

## 6. Browser QA required (reviewer to drive — no creds this session)

1. **AI OFF == Phase 3** — with no config params set (current state), open Care
   Command: NO Draft button, NO AI card, console clean. Byte-identical to
   Phase 3.
2. **Turn it on** — Settings → Care Command AI Assist → enable master + pick the
   active Ollama provider (id 40) → save. Reload Care Command.
3. **Draft** — open a Zalo/email conversation → `Draft` button appears in the
   composer; clicking fills the composer (does NOT send) and toasts "review
   before sending". (Live text needs Ollama reachable at 127.0.0.1:11434; if
   down, expect the clean "AI is unavailable" toast — that is the correct
   failure path, not a bug.)
4. **Brief** — the "AI" card shows at the top of the care rail; `Generate brief`
   → 3–5 bullets + "Generated just now by …" stamp + dismiss ×.
5. **Cloud refusal** — switch the provider to OpenAI (id 2) with `allow_cloud`
   OFF → the Draft/AI affordances disappear (gate returns disabled); turn
   `allow_cloud` ON → they return. (Do NOT drive a real OpenAI call.)
6. **Off again** — flip the master off → all AI DOM gone; confirm the toggle
   actually persists off (the §5.36 fix).

## 7. Proposed ledger entry (fresh gotcha) — ADDED as §5.60

- **§5.60 — a local variable named `context` holding a non-dict breaks Odoo 19's
  `_()`** with `AttributeError: 'str' object has no attribute 'get'`.
  `translate.py`'s `_get_lang(frame)` reads `local_context.get('lang')` off
  whatever caller-frame local is named `context`; a plain string there (e.g. a
  built LLM prompt) raises at the next `_(...)` call — masking the real path (in
  Phase 4 it turned `_complete`'s intended `UserError` into an `AttributeError`,
  and killed `ai_brief`'s stamp). Fix: never name a code local `context` unless
  it is an Odoo context dict; use `prompt`/`body`/`user_message`. Hit live +
  fixed (rename to `prompt`); both T36/T38 went RED→green. Now in the ledger.
