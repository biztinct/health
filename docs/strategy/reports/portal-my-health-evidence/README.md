# Portal "My Health" (Phase 4E) — browser evidence pack

Real-data drive on **care.biztinct.com** (vietuat), Demo Patient 861
("Demo Patient - Hanoi (Near ~2km)"), the only patient with real conditions.
Navigation is the real user path from the hub (no deep-link that skips the flow).

| Shot | Path taken | What it proves |
|------|-----------|----------------|
| `01-hub-with-health-link.png` | `GET /my/care/<token>` (hub) | New **"Sức khỏe của tôi →"** nav link renders first in the hub nav list, above Records + Consents. |
| `02-health-conditions-vitals.png` | Clicked "Sức khỏe của tôi →" → `GET /my/care/<token>/health` | **Chẩn đoán đang theo dõi**: 2 active diagnoses — `I10` **Tăng huyết áp vô căn (nguyên phát)** and `E11` **Đái tháo đường típ 2**, each with code chip + "từ 08/07/2026" (Vietnamese-first). **Sinh hiệu gần đây**: honest empty state "Chưa có sinh hiệu được ghi nhận." — 861 has **0** top-level observations. NO risk fields shown. |
| `03-neutral-invalid-token.png` | `GET /my/care/deadbeef_not_a_real_token/health` | Neutral page ("Liên kết không khả dụng") — byte-identical to the hub neutral, no patient name / PHI leak, no existence oracle. |

## Real 861 render counts (data-honesty)
- Active conditions: **2** (I10, E11) — both `recorded_date` 2026-07-08.
- Recent top-level vitals (final/amended, parent_id=False): **0** → empty state
  shown. No prod data was seeded to prettify the screenshot.

## Server-side rows the /health access created
`_record_access('health', ip)` appends one `health.portal.access.log` row
(section `'health'`) per page load and bumps the access counter — same audit
path as every other section.

## Console
Only one benign notice on every portal page: *"Page layout may be unexpected due
to Quirks Mode"* — pre-existing to the shared `portal_layout` shell (no
`<!DOCTYPE>`; affects 4A–4D identically), NOT introduced by this phase. No errors.
