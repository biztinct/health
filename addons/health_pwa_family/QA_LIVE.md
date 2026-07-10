# health_pwa_family — Live verification (vietuat / care.biztinct.com)

PWA family messaging for the field nurse (FB-044 loop close + FB-047). Proven by
**72 module tests (0 failed)** across `/health_pwa_family` (15) +
`/health_family_messages` + `/health_pwa_daystrip` + `/health_scribe`, plus the
live browser evidence below.

## Test result (verbatim)

    2026-07-10 06:15:52 INFO vietuat odoo.tests.result: 0 failed, 0 error(s)
        of 72 tests when loading database 'vietuat'

`/web/login` → HTTP 200 after the final restart.

## Browser QA (care.biztinct.com, nurse PWA, phone 390×844)

A QA nurse (`qa_pwa_nurse`) was assigned to a live visit whose patient has an
opted-in family relation + data-sharing consent; messaging was temporarily
enabled, then re-darkened.

1. **PWA bell family_message card** (the sanctioned app.js edit) — the bell
   showed a real card: green "FAMILY MESSAGE" badge (`notif-badge-family`),
   patient row, the message preview, a green "Xem (View)" button + "OK" +
   dismiss ×. "Xem" navigates to `#/order/<fso>` (the visit screen).
2. **Visit-context panel** — the "Tin nhắn gia đình (Family messages)"
   collapsible panel renders on the order screen with the relation label, the
   inbound family bubble ("Bố tôi cần điều dưỡng nói tiếng Anh…"), and a reply
   composer. Driven by the real `GET /health_pwa/api/fso/<id>/family_messages`
   (returned `enabled:true, can_update:true, threads:[…]`).
3. **Nurse reply** — typed a reply, tapped Gửi → `POST …/reply` created the
   'out' row; the panel refreshed showing the reply bubble ("QA PWA Nurse").
4. **Reply reaches the family** — the family token page now shows the nurse's
   reply bubble ("Vâng, tôi nói được tiếng Anh…", QA PWA Nurse).
5. **FB-047 one-tap update** — `POST …/update` → `{sent:1}` "Update sent to 1
   family recipient(s)"; the update appeared as a third bubble on the family
   token page ("Ca thăm khám đã hoàn tất tốt đẹp…").
6. **SW / shell refresh** — `/health_pwa` serves `fammsg.js?v=1.10.0` +
   `fammsg.css?v=1.10.0` + `daystrip.js?v=1.10.0`; the shell HTML contains
   `1.10.0` and **no stale `1.9.0`** (hard-reload verified).
7. **Dark check (report-back g)** — with `health_family_messages.enabled=False`:
   `GET …/family_messages` → `enabled:false`; `POST …/reply` → **403**;
   `POST …/update` → **403**. Pre-existing bell rows stay dismissable (the card
   always renders; OK/dismiss/×  work regardless of the switch).

### Nurse-scope proof (report-back b)

The `GET …/family_messages` endpoint returned the thread data ONLY because the
QA nurse is assigned to the order. Scope domain shipped (server-side):
`health.staff.assignment` where `fso_id = order AND staff_id = caller.employee_id
AND state != 'cancelled'`; sudo is applied only AFTER that check. (A separate,
pre-existing health_pwa gap: the base `api_fso_detail` reads FSO + sale.order
WITHOUT sudo, so a synthetic minimal nurse needs catchment + sale-order read to
render the *base* order screen — unrelated to this module; the panel was proven
by injecting the standard `.order-details/.order-actions` scaffold and letting
the real fetch-wrap + render path populate it from the live endpoint.)

## FB-047 fan-out counts (report-back c)

QA patient had 2 relations — 1 opted-in (eligible), 1 not. The update fanned out
to exactly **1** recipient (`sent:1`); the non-opted-in relation was skipped.
`family_update` outbound rows: created only when
`health_pwa_family.zns_template_update` is set (empty default ⇒ 0 rows, message
still delivered in-thread); deduped on retry (`famupd-<fso>-<relation>`).

## PWA 1.10.0 checklist (report-back d)

5 spots in `health_pwa/views/pwa_templates.xml` bumped 1.9.0 → **1.10.0**
(`pwa_asset_version` t-set, `version:`, `PWA_SW_VERSION`, SW header comment,
`CACHE_VERSION`) + `health_pwa/__manifest__.py` (`19.0.1.0.23`). Pin tests
updated to 1.10.0: **health_pwa_daystrip** `test_daystrip.py` and
**health_scribe** `test_scribe.py`; plus this module's own shell pin test
(`fammsg.js?v=1.10.0`).

## Post-deploy config (verified on vietuat)

    health_family_messages.enabled          = False   (still dark)
    health_family_messages.zns_template_reply = (empty)
    health_pwa_family.zns_template_update    = (empty) (no update ping until set)
    health_messaging.enabled                 = False   (untouched)
    health_messaging.dry_run                 = True    (untouched)

## QA cleanup (report-back e)

Created for QA: 1 thread + 3 messages (1 in, 1 reply, 1 update) + 1 link +
1 FSO/SO + 2 relations + 2 partners + 1 consent + bell rows + 1 nurse user.
Removed: thread (messages + family_message bell rows cascade), the family_*
outbound rows, link, relations, FSO. Left: the QA nurse account, the two test
partners (FK-held by the immutable consent), and the consent (audit record).
Final live count: **threads = 0, messages = 0**.
