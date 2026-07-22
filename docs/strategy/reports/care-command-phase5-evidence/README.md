# Care Command Phase 5 — Browser Evidence Pack

Live surface: `https://care.biztinct.com/bizapp/action-1680` (CMS → CRM → Care
Command), user = Operations Manager, reloaded with cache ignored after deploy.
**Console: zero errors/warnings across every state below.**

## Navigation path (real user, from the CMS sidebar)
CMS sidebar → **CRM → Care Command** → lands directly on the **chat screen**.

## 01-chat-first-default.png
The default screen is **chat**, not the wall:
- Top sub-label reads **CONVERSATION** (chat-first); a **Wall** button sits one
  click away.
- Dock shows **all 8 channels active** — ZALO, CALLS (badge **167**), EMAIL,
  ZNS, WHATSAPP, FB MSGR, TELEGRAM, WEB CHAT — plus **ALL 167**.
- The attention chat list is **empty** ("No conversations." / "Pick a
  conversation.") — HONEST: 0 conversations have real channel activity yet.
- Auto-select correctly falls through to the empty state (no needs-mine /
  needs-un rows exist to open).
- The **Leads bucket** is pinned under the (empty) list:
  **"Leads · 167 › Not yet reached on any channel · 167 need reply"**.

## 02-leads-view.png
Clicking the Leads bucket switches to the **leads view**:
- **"← Live conversations"** back affordance at the top.
- Header note: *"Contacts not yet reached on any channel — reply, call or
  message to move them onto the live wall."*
- The 167 declared-only leads grouped by status:
  **NEEDS REPLY — MINE · 1** and **UNCLAIMED — ANYONE CAN TAKE · 166**, each row
  carrying the `lead` chip, the "New lead · first message" reason and a CLAIM
  button. Clicking "← Live conversations" returns to the attention list.

## Server-side truth (psql, post-migration)
- `care_conversation`: 167 rows, all lead-anchored, `has_channel_activity` on
  **0** (no traffic), `channel_declared` derived on **all 167** (every one
  `call` — every existing lead's `mode_of_contact` is the default `phone`).
- Module version `19.0.4.0.0`; migration log line present.

Data honesty: attention ≈ 0 until ops wires inbound channels — exactly what the
handover predicted. The 167 dormant leads now live behind the Leads bucket
instead of flooding the wall.
