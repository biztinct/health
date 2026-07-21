# Care Command — Phase 4 Handover: "AI Assist" (config-gated, Ollama-first, never auto-send)

**For:** Opus implementation session · **Designed/reviewed by:** Fable
**Read first:** `docs/strategy/HANDOVER-CONVENTIONS.md` (§5.45, §5.51–5.59)
**Binding visual spec:** `docs/care-command-center/care-command-combined.html` — the AI Assist
drawer + `.ai-only` affordances (drafts, brief). AI OFF must look EXACTLY like Phase 3.
**Prior phases:** 1–3 live on vietuat, all reviewed (care_command 19.0.3.0.0, bridge 19.0.1.1.0).

## 1. Why this phase & the philosophy (binding)

The user base may be AI-averse (healthcare). Therefore: AI is a **configuration, not a
feature of the core**. Phase 1–3 shipped a complete deterministic tool; Phase 4 adds an
OPTIONAL layer that (a) lives in its OWN module so the core keeps its "grep AI = 0" purity,
(b) is OFF until a manager turns it on, (c) is Ollama-first (on-prem sovereignty; cloud
requires a second explicit opt-in), (d) NEVER sends anything — every AI output lands in an
editable composer or a labeled card, and the only send path remains the existing human one.

## 2. Scope (deliverables)

New module **`health_care_command_ai`** (depends: `health_care_command`, `biz_bi`;
`auto_install: False` — installing it is itself an opt-in):

1. **Settings** (`res.config.settings` _inherit, own section, CRM-manager visible):
   `care_ai_enabled` (master, default False), `care_ai_provider_id` (m2o `bi.ai.provider`),
   `care_ai_allow_cloud` (default False), capability toggles `care_ai_drafts` +
   `care_ai_brief` (default True — they only matter when the master is on). Store as
   `ir.config_parameter` via the standard config_parameter= field attribute.
2. **Reply draft**: a "Draft" button in the composer area (rendered ONLY when the runtime
   gate §5.2 passes). Service `ai_draft_reply(conv_id)`: group-gate + company-scoped fetch
   (clone `_guarded`), build a REDACTED context (§5.3), call `provider._complete(system,
   user, force_json=False)`, return `{text}` → JS puts it in the composer marked "AI draft —
   review before sending". No send call anywhere in this path.
3. **Continuity brief**: an "AI" card at the top of the care rail with a "Generate brief"
   button (on-demand, never automatic — cost + surprise control). Service
   `ai_brief(conv_id)` → 3–5 bullet summary of the redacted timeline + "generated now by
   <provider.name>" stamp. Rendered with a visible AI label; dismissible.
4. **UI gating**: workspace payload gains `ai: {enabled, drafts, brief}` (computed by a
   hook the AI module overrides — the BASE module ships `ai: False` untouched… NO: the base
   module must not know about AI at all. Instead the AI module patches/extends the OWL
   action via a registry patch or `patch()` from its own asset bundle, and fetches its own
   flags via a small gated service `ai_flags()`). AI OFF or module absent → zero AI DOM.
5. Tests T33–T38; deploy per §7.

## 3. Binding NON-goals

- **NO auto-send. Permanently.** No code path from AI output to `action_send_*` — the POC's
  settings drawer literally labels it "permanently unavailable". Do not even ship a disabled
  button for it.
- **NO junk scoring, NO intent widgets, NO booking proposals, NO wall re-ranking by AI** —
  later phases if ever. Drafts + brief only.
- **NO edits to `health_care_command` core** (its AI-purity grep must stay 0 hits; the AI
  module composes from outside via its own assets + services). No edits to biz_bi /
  health_ai_coding either — consume `bi.ai.provider` as-is.
- **NO clinical content in prompts**: context = the care_command timeline (already
  non-clinical by design, §Phase-1 §3) + status/booking facts. NEVER pull from health_emr /
  condition / telemonitoring / consent.
- **NO real model calls from tests or deploy verification.** All tests mock
  `provider._complete`. On the server: report provider/config state only (§6). One live
  smoke call ONLY if the user explicitly approves it after your report.
- **NO provider/credential creation or modification on vietuat.**

## 4. Verified plumbing (do not re-derive)

- `bi.ai.provider` model: `addons/biz_bi/models/bi_ai.py:32` — fields `provider`
  (anthropic/openai/ollama), `endpoint`, `model_name`, encrypted key, `max_tokens`,
  `temperature`, `timeout_s`; `_is_usable()` (ollama needs no key); **`_complete(system,
  user_message, force_json=True)` at :125** with per-provider impls (:130/:152/:174).
  Errors raise — catch and surface a clean UserError ("AI is unavailable — continue
  manually"); an AI failure must never block manual work.
- **Cloud refusal gate precedent** (clone the shape): health_ai_coding
  `ai_code_suggestion.py:252-259` — provider configured? if `provider.provider != 'ollama'
  and not allow_cloud` → refuse with a log. Config-param lookup precedent `_cfg/_provider`
  at :116-143 (remember §5.48: config-param ormcache is per-worker — read params directly,
  don't cache).
- **Redaction precedent** (clone + generalize): `ai_code_suggestion.py:149-186 _redact` —
  longest-first replacement of name/phone/mobile/email/address with `[BN]/[SĐT]/[EMAIL]/[ĐC]`
  tokens + per-name-token pass + whitespace collapse + char cap. For care_command redact
  BOTH the partner's and the lead's identity values (name, phone, email) from every timeline
  text before it reaches the prompt. The SAME redacted string is what you may log.
- Timeline source: `care.conversation._detail_timeline()`
  (health_care_command/models/care_conversation.py:583+) — reuse via a sudo call AFTER the
  gate; take the last ~15 events' text/kind/direction.
- Audit precedent: `bi.audit.log.sudo().log(...)` (bi_ai.py `_log_change`) — log capability,
  conv_id, provider name, duration_ms per AI call. Never log unredacted content.
- OWL patching: the AI module ships its own asset bundle extending the `care_command`
  action; `patch()` from `@web/core/utils/patch` on the exported component class (export it
  from the core JS if not already — that ONE export line is the single permitted core touch;
  declare it) or a registry wrapper component. Report which seam you used.
- Settings precedent: health_ai_coding/res_config_settings.py:23 (provider m2o with
  config_parameter).

## 5. Design details

### 5.1 System prompts (VN-first, plain)
- Draft: system = "You draft a short, polite Vietnamese reply for a home-care service's
  sales/care agent. Use only the provided conversation facts. If information is missing,
  ask one clarifying question. Never invent prices, times, or medical advice. Output the
  reply text only." User = redacted recent timeline + channel + status + next-booking fact.
- Brief: system = "Summarize this conversation for an agent taking over. 3–5 short
  Vietnamese bullets: who (role only, names are redacted), what they want, current state,
  what to do next. Facts only." Same context.

### 5.2 The runtime gate (one helper, used by every service AND ai_flags)
enabled = master param AND provider exists AND `provider._is_usable()` AND
(`provider.provider == 'ollama'` OR allow_cloud). Per-capability = gate AND its toggle.
`ai_flags()` returns `{enabled, drafts, brief, provider_name}` — group-gated like every
other service.

### 5.3 Redacted context builder
`_ai_context(rec)`: last 15 timeline events → "IN/OUT/NOTE: <text>" lines; append status,
channel, next_booking_at (date only), lead stage if any. Redact per §4. Cap ~4000 chars.
No ids, no phone/email, no raw HTML (timeline already plaintexts email bodies).

## 6. Data honesty & server reality

Report (don't fix): `bi.ai.provider` rows on vietuat (health_ai_coding is live — an Ollama
provider likely exists; state name/provider/endpoint reachability WITHOUT calling the
model), the settings' default state (must be OFF after install), and the fact that with AI
off nothing in the UI changed (screenshot-by-Fable item). NO live model call without
explicit user approval after your report.

## 7. Tests (T33–T38, all with `provider._complete` mocked)

- **T33** gate: master off → `ai_flags().enabled False` and `ai_draft_reply` raises
  UserError; master on + cloud provider + allow_cloud off → refused (the ai_coding-shaped
  gate); ollama provider → allowed.
- **T34** draft: mocked completion → returns text; asserts NO mail.message/zalo.message
  created and conversation status/unread UNCHANGED (draft must have zero side effects
  beyond the audit log).
- **T35** redaction: partner name/phone/email seeded into timeline text → captured prompt
  (mock call args) contains `[BN]/[SĐT]/[EMAIL]` and NOT the raw values (assert on the
  exact seeded strings).
- **T36** brief: mocked → returns bullets; audit log row written with capability +
  provider; no content beyond the redacted string in the log payload.
- **T37** access: plain (non-CRM) user → AccessError on ai_flags/draft/brief; company-2
  conversation not reachable via company-1 call (clone the T24 negative).
- **T38** failure path: `_complete` raising → clean UserError, no crash, no partial audit
  row claiming success.
Hygiene: §5.50, §5.58 (vi.po markers for every new string — including the two Phase-3 gear
tooltips "Manage reply templates"/"Manage watchlist phrases" that are missing from the core
vi.po; add them there as a declared one-line core i18n touch), no HttpCase.

## 8. Deploy (vietuat — §5.45)

1. Standard flow; modules: `health_care_command_ai` (-i), `health_care_command` (-u, only if
   the export-line/i18n touch happened).
2. `--test-enable --test-tags /health_care_command_ai,/health_care_command` one run;
   fresh TODAY-UTC result line by YOUR pid (log may rotate — quote pid + timestamp).
3. Verify: settings default OFF; UI unchanged with AI off (Fable will browser-verify both
   off and on states); versions: ai module 19.0.1.0.0, core → 19.0.3.0.1 if touched.
4. Report per §6 + any deviations + proposed ledger entries.

**Kickoff line for the Opus session:**
Implement `docs/strategy/handovers/care-command-phase4.md` (Care Command Phase 4 — AI
Assist: config-gated drafts + continuity brief in a NEW module `health_care_command_ai` on
the `bi.ai.provider` seam). Read `docs/strategy/HANDOVER-CONVENTIONS.md` first
(§5.48/§5.51–5.59). Follow the handover exactly: Ollama-first with the cloud-refusal gate,
redaction per the health_ai_coding precedent, never auto-send, zero AI in the core module
(one declared export/i18n touch max), all tests mock `_complete`, T33–T38 green, deploy to
vietuat per §8, report per §6/§8. No provider/credential changes, no live model calls
without explicit approval.
