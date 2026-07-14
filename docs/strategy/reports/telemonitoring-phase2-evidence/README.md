# Telemonitoring Phase 2 — browser evidence pack (vitals-FAB rider)

Real-user path drive of the §6 rider: the vitals FAB is now reachable from the
shared booking modal for an in-progress visit, closing the Phase-1 review
finding (FAB was hash-gated on `#/orders/<id>`, unreachable from the modal-first
flow).

## User + entry point
- User: **ds_qa_nurse** (`base.group_user` + `health_base.group_healthcare_nurse`)
- URL: `https://care.biztinct.com/health_pwa#/today` (served shell **v1.17.0**)
- QA fixture: FSO **5906** (patient "ZZ QA FAB Patient"), scheduled today,
  assigned to the nurse (state `assigned`). Created + deleted for QA;
  fresh-cursor confirmed removed (`fso5906=0 fabpatient=0`).

## Navigation (click-by-click, the real path — NOT a deep link)
1. Bottom-nav **Booking** tab → booking-card list shows the visit card
   → `01-today-booking-card.png`
2. **Tap the visit card** → shared booking-detail modal opens. Visit is
   `assigned` (not in progress) → **no FAB** (rider correctly withholds it)
   → `02-modal-assigned-no-fab.png`
3. **Tap "Start Service"** inside the modal → visit flips to `in_progress`;
   the rider intercepts the `/start` POST response and the **"Record Vitals"
   FAB appears on the modal** → `03-modal-inprogress-fab-visible.png`
4. **Tap the FAB** → the vitals entry sheet opens for FSO 5906
   → `04-vitals-sheet-open.png`
5. Close the modal → FAB removed (rider cleanup verified).

Deliberately driven via the booking MODAL, never `#/orders/<id>` — that dead
deep link is exactly what hid the Phase-1 bug (conventions §8.1, ledger §31).

## Measured facts
- FAB present only when modal open AND status `in_progress` (assigned → absent,
  in_progress → present). Gate matches the modal's own action buttons.
- FAB z-index **9300** > modal-backdrop **2000** → clears the backdrop; rendered
  52×52 at bottom-right, `display:block visibility:visible opacity:1`, in viewport.
- Vitals sheet z-index **9400** > FAB → opens above it.
- Rider JS loaded: `window.__vitalsFabFetchWrapped === true`,
  `window.__vitalsFabObserver` present.
- Console: **no JS errors/warnings** (`console-log-full.txt`). Two Chrome a11y
  `[issue]` advisories on form fields are pre-existing (vitals-sheet inputs),
  flagged for honesty.

## Modal seam facts found in fammsg.js (for the conventions ledger)
- Detail endpoint: `GET /health_pwa/api/fso/<id>` (bare id, at end or before `?`;
  the `/start` `/update` sub-routes are excluded by the regex).
- Status field in the response envelope: **`data.state`** (`'in_progress'` when
  a visit is running). The modal updates its state LOCALLY after Start Service
  without re-fetching the detail, so the rider ALSO intercepts the
  `POST …/fso/<id>/start` response to catch the → in_progress flip.
