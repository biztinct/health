# Viet UC care workspace concept

An approval-stage interactive HTML prototype for contact, booking and client records. All data is fictional demonstration content; no live healthcare or payment services are connected. Edits last only for the current browser page session.

Open `public/poc.html` directly for the portable HTML version. Google Fonts enhance the typography when online; system fonts remain usable offline. The Sites entry point embeds the same HTML, so the deployed and portable designs share a single implementation.

## Design decisions

- One compact identity header and one summary strip replace oversized tiles.
- A quiet workflow line shows status; a contextual panel presents the next useful action.
- Independent, content-sized columns eliminate empty rows from matched card heights.
- Optional groups expand in place; deeper care, billing and activity details live in tabs.
- Assignment, scheduling, notes and sample booking creation use focused drawers.
- The mobile layout preserves the three primary screens, stacks content and supports touch controls.
- Dialogs support Escape, focus return, focus trapping, and background inertness. Reduced-motion preference is respected.

## Run and publish

`npm install`, then `npm run dev`. Build with `npm run build`. Hosting is an owner-private Sites preview. No Odoo environment or database migration is in scope for this standalone approval prototype.

## Review paths

Switch among Contacts, Bookings and Clients. Assign a professional, reschedule, start/complete a sample visit, log an activity, edit/save/discard fields, expand charges, simulate a payment, create a sample booking and use workspace search. Reload resets the demonstration.
