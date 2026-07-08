# health_telehealth — Live browser QA (care.biztinct.com)

Performed on the vietuat UAT server, phone viewport (402×874), against the
deployed 1.8.0 shell. Demo data: online/telemedicine FSO for patient "An Xu",
nurse `ds_qa_nurse`. Service-worker cache verified as `health-pwa-v1.8.0`
(the version bump is live).

## Patient waiting room — `/tele/visit/<token>` (no-login, public)

1. **Pending (upcoming)** — session `pending`, FSO `confirmed`.
   Renders: brand header, chip **"Sắp diễn ra (Upcoming)"**, title
   "Khám trực tuyến cho An Xu", "Video sẽ mở khi bác sĩ bắt đầu", the visit
   **Date 08/07/2026**, **Time 15:00 - 16:00** (wall-clock; scheduled 08:00 UTC
   → 15:00 ICT), **Doctor** given name. **No Join button** — the room URL is
   absent from the HTML. `<meta http-equiv="refresh" content="60">` present so
   the page self-flips when the doctor starts.

2. **Open (live)** — after `action_start_service` (session `open`).
   Renders: chip **"Đang diễn ra (Live)"**, "Buổi khám đã bắt đầu", and the big
   blue **"Vào phòng khám (Join)"** button whose `href` is the room URL
   `https://meet.jit.si/vu-2262-…` (slug tail redacted). This is the ONLY state
   in which the room URL appears in the page — the URL gating is verified.

3. **Closed (ended)** — after `action_complete_service` (session `closed`).
   Renders: chip **"Đã kết thúc (Ended)"**, "Buổi khám đã kết thúc", a thank-you
   line, **no summary and no room URL**. Meta refresh gone.

(Neutral: a bogus token renders the identical "Không có thông tin để hiển thị"
page — asserted in the HttpCase test.)

## Nurse PWA — Today view

- Three cards for the day. The **"Vào video (Join video)"** action is injected
  ONLY into the two **Telemedicine/Online** cards, sharing the daystrip
  swipe-to-reveal row: the revealed row on the 19:30 online card shows three
  actions side by side — **Gọi** (teal) · **Đang đến** (blue, daystrip) ·
  **Vào video** (violet camera). The 17:00 **Home Visit** card shows no
  "Vào video" (correct location scoping).
- Tapping the Join action calls `GET /health_pwa/api/fso/<id>/tele/join` as the
  logged-in assigned nurse. Verified over real HTTP:
  - confirmed online visit 2263 → `{"url":"https://meet.jit.si/vu-2263-…"}`
  - completed online visit 2262 → `{"url":""}` (state-gated, no room URL)
  The room URL is never placed in any cached/offline payload.

## Backend

- On the FSO form, a **"Join Video"** header button appears only while the
  session is `open` (`telehealth_session_state == 'open'`) and calls the same
  `_tele_join_url` access-checked accessor.
