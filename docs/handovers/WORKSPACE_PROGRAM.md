# WORKSPACE — record screens redesign (programme)

Owner decision 2026-09-29: build **Option B · Workspace** from the approved concept
`design-poc/record-screens.html` (published as the artifact "Record Screens Redesign"),
starting with the booking screen. Delivery: phased Fable-designs / Opus-implements, one
session, phases back-to-back.

## What the owner asked for (verbatim intent)
The contact, booking and client screens look old, chaotic and not premium. Specifically:
unnecessary big tiles for counts; the workflow/stage bar is not premium; groups inside the
form leave large empty spaces (a group with no data still takes a whole card).

## The six fixes every phase applies (from the approved concept)
1. Big count tiles → one slim "At a glance" list in a right-hand panel; zeros go grey, only
   problems are coloured.
2. Stage bar → a journey (segmented bar with dates) plus a **Next step** banner that says
   what is wrong in one sentence and offers one button to fix it.
3. Groups pack tightly (masonry, no stretched columns); groups whose fields are ALL empty
   fold into one "Not filled yet" line of chips; clicking a chip opens the group.
4. Many buttons → the next-step button, 2-3 helpers, the rest under a **More** menu
   (Delete / Archive / Cancel / Duplicate never sit next to the main action).
5. Read first, click to edit: values render as plain text until hovered/focused.
6. One type scale and spacing rhythm; the same header / journey / panel on all three screens.

Chatter stays at the bottom, full width (standing rule).

## Phases
| Phase | Screen | Doc | Status |
|---|---|---|---|
| WS-1 | Booking (`health.fieldservice.order` ops form) + the reusable Workspace kit in `health_theme` | `WORKSPACE_WS1_BOOKING.md` | **DONE 2026-09-29** — live on carejiox, carejiox_template, hhh; report `WORKSPACE_WS1_REPORT.md` |
| WS-2 | Client (ops client profile, `res.partner`) on the kit | written after WS-1 reports | — |
| WS-3 | Contact (CRM contact form, `crm.lead`/contact) on the kit | written after WS-2 reports | — |

Later polish (owner saw it in the concept; not scheduled): one-line plain-English summary
at the top of the record, and a Ctrl K command box.
