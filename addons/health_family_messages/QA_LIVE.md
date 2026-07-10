# health_family_messages — Live verification (vietuat / care.biztinct.com)

FB-044 secure two-way family↔team messaging. Proven by **46 module tests
(0 failed)** across `/health_family_messages` (20) + `/health_family_link` +
`/health_messaging`, plus the live browser evidence below.

## Test result (verbatim)

    2026-07-10 04:52:49 INFO vietuat odoo.tests.result: 0 failed, 0 error(s)
        of 46 tests when loading database 'vietuat'

`/web/login` → HTTP 200 after the final restart.

## Browser QA (care.biztinct.com, real token page, phone width 390×844)

A live family link was minted on vietuat (eligible relation + data-sharing
consent + confirmed visit) and messaging temporarily enabled.

1. **Token page composer** — the standalone family page renders the visit card
   PLUS a "Nhắn tin với đội chăm sóc (Message the care team)" section: empty-state
   line, a textarea, a green "Gửi (Send)" button, and the "Kênh nhắn tin mở trong
   24 giờ…" window note. Mono colors, inline SVG send icon, no emoji.
2. **Family → team send** — typed a message, submitted; the POST route created an
   inbound row and PRG-redirected back; the message rendered as a right-aligned
   bubble with the relation label ("QA FamMsg Patient ↔ QA FamMsg Rep (Caregiver -
   Child)") + timestamp.
3. **Backend inbox** — Operations Center ▸ **Family Messages** (action 1664) lists
   the thread: Patient, Family Relation, Facility (Hanoi Facility), Last Message,
   **Unread = 1**, State Active. The thread form shows the Conversation tree
   (Direction "Family → Team", the message body, Visit "…(BK1778)", Seen) and a
   Reply box.
4. **Team → family reply** — typed a reply; the "Send reply" header button appears
   only once `reply_text` is set; clicking it created an outbound row, reset Unread
   to 0, and cleared the box. The reply shows as "Team → Family" from the ops user.
5. **Reply visible to family** — reloading the token page shows BOTH bubbles: the
   inbound (green) and the outbound reply (grey) from the team member + timestamp.
   (The out message's `read_by_family` flips on this render.)
6. **Dark check (report-back g)** — set `health_family_messages.enabled=False` and
   restarted: the same token page now renders ONLY the visit card — no message
   section, no composer, no thread. Messaging is fully dark with the switch off.

## Post-deploy config (verified on vietuat)

    health_family_messages.enabled          = False   (dark; go-live is a manual flip)
    health_family_messages.zns_template_reply = (empty) (no reply ping until configured)
    health_family_messages.max_per_hour      = 10
    health_messaging.enabled                 = False   (untouched)
    health_messaging.dry_run                 = True    (untouched)

PWA stays **1.9.0** (`pwa_asset_version` t-set + manifest `19.0.1.0.22`) — this
phase changed NO PWA asset, so per §3 there is NO bump.

## PWA bell notification (report-back c)

The shipped PWA bell (`health_pwa` app.js) `v-if`/`v-else-if`-switches on
`notif.type` for `assignment`/`cancelled`/`rescheduled` with **no `v-else`**, so
a new `family_message` type renders an empty card in today's app shell. We add
the correct data-model selection value (`health.pwa.staff.notification`
`notification_type='family_message'`) so the queue rows are honest and a future
PWA-versioned phase can add the render case; the working in-app signal today is
the **VAPID push** (own title/body, not subject to the type switch) plus the
`mail.activity`. We touched NO PWA asset (§3/§4). This is the handover's
"reuse-or-report" fallback, reported rather than shipping a misleading badge.

## QA cleanup (report-back e)

Live records created for QA: 1 thread + 2 messages (1 in, 1 out) + 1 family link
+ 1 FSO/SO + 1 relation + 2 partners + 1 consent. Removed after QA: the thread
(messages cascade), link, FSO, relation. Left in place: the two test partners
(FK-referenced by the immutable consent) and the data-sharing consent itself
(consents are audit records — `Only draft consents can be deleted`). Final live
count: **threads = 0, messages = 0, family_message_reply outbound rows = 0**.
