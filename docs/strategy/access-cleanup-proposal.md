# Who can do what — a clean-up proposal for the owner

Written 2026-11-03 at the end of the Form Studio work. Nothing in this document has been changed on
the live systems: it lays out what is true today and asks you to decide. Each decision is a few
clicks in Settings › Access once you have made it.

## Decided 2026-11-03 (and done the same day)

The owner read this proposal and ruled: **Owners only** may export lists (an "Export lists" ability
now sits on the Owner role); the **demo login is switched off**; the **Admin role is renamed "Office
Admin"** ("Quản trị văn phòng") rather than widened; the seven stray Mac files and the empty old plain
health columns are **removed**. The rest of this document is the picture as it was before those
changes.

## In short

1. **Nobody in the clinic can export a list today.** The "Export" choice in a list's action menu is
   only open to the platform's own accounts and to one old test login called `demo`.
2. **The `demo` login is still switched on** on carejiox.com. It has never signed in, but it can
   export lists. We suggest switching it off.
3. **The "Admin" role is not usable on its own.** Somebody who has only the Admin role cannot open a
   Client, a Contact or a Booking. Either give it the two missing permissions or rename it.
4. **The blank system that new clinics are made from must never hold client information.** The
   deploy check now says so after every update.

## What each role can do today (measured 2026-11-03)

People = active staff accounts that hold the role on **carejiox.com** (in brackets: on the blank
system / on hhh). "Opens" was measured on a copy of carejiox.com by signing in as a test person who
holds only that role and opening a real record of each kind with every field on the screen.

| Role | People | Opens a Client | Opens a Contact | Opens a Booking | Form Studio | Export lists | Analytics designer |
|---|---|---|---|---|---|---|---|
| Owner | 6 (0 / 2) | Yes | Yes | Yes | Yes | No | No |
| Admin | 9 (0 / 2) | **No** — stopped at the client's invoices | **No** — no access to contacts | **No** — stopped at the booking's invoices | Yes | No | No |
| Operations Manager | 3 (0 / 0) | Yes | Yes | Yes | Yes on carejiox.com (No on the blank system — see note) | No | No |
| Branch Manager | 3 (0 / 0) | No — stopped at invoices | No | No | No | No | No |
| Doctor | 22 (0 / 2) | No — stopped at invoices (earlier screen test: bounced back to Clinical) | No | Partly — stopped at the booking's equipment list here; an earlier screen test opened bookings | No | No | No |
| Nurse | 57 (0 / 2) | Yes, clients in their area | No | Only their own visits | No | No | No |
| Accountant | 7 (0 / 0) | No | Yes | Yes | No | No | No |
| CRM | 8 (0 / 0) | No | Yes | Yes | No | No | No |

Who CAN export lists today: on carejiox.com the platform administrator (`ash@biztinct.com`) and the
`demo` login; on the blank system and on hhh only the platform's own recovery and administrator
accounts. Who can design Analytics datasets: only the platform administrator.

Notes. Many people hold several roles, so most of them can do more than their row says (an Owner who
is also listed under Admin opens everything). The test person reads every field of the screen, so a
"No" can be stricter than what a person sees in the browser, where some sections are simply left
out; in an earlier browser test a Doctor could open bookings but was sent back from the Clients entry.
On the blank system the Operations Manager role is made of a slightly different set of permissions
from carejiox.com and does not reach Form Studio there — worth aligning when the roles are next
reviewed. Form Studio still needs the right to change that kind of record, so in practice the
Client and Contact Studio is the Owner's.

## The `demo` login

| | carejiox.com | Blank system | hhh |
|---|---|---|---|
| Exists | Yes (account number 5) | No | No |
| Switched on | **Yes** | — | — |
| Last sign-in | Never | — | — |
| Can export lists | **Yes** | — | — |
| Other permissions | Contacts manager, sales, stock, projects, timesheets, attendance officer, time-off officer, e-learning officer, several companies | — | — |
| Holds a role | No | — | — |

It is a leftover from the system's demonstration data. Nobody uses it, and an account that can
export and has never signed in is exactly the kind of door that gets forgotten. **Suggestion: switch
it off** (Settings › Users › demo › Archive). Nothing else depends on it.

## Who should be able to export lists

Exporting takes a list (clients, bookings, invoices) out of the system as a spreadsheet. Health
information is never in an export whatever you choose — the system refuses it — but names, phone
numbers and addresses are.

| Option | What changes on screen | What it costs | What you lose |
|---|---|---|---|
| A. Nobody (as today) | Nothing | Nothing | Every list that has to leave the system has to be asked of us |
| **B. Owner only** (recommended) | Owners see "Export" in the action menu of every list | One permission added to the Owner role | Managers still ask an Owner for a spreadsheet |
| C. Owner and Operations Manager | Owners and the three Operations Managers see "Export" | The same permission on two roles | Three more people can take client lists out of the system |

**Recommendation: B.** Six people, all of whom can already see everything, gain a button they need
for month-end and audits; nobody else does. If an Operations Manager needs a list every week, add
them later — giving is one click, and so is taking away.

## The Admin role — two defects, one paragraph

A person who holds only the **Admin** role can open Form Studio but cannot open a Client, a Contact
or a Booking: the Client and Booking screens show the record's invoices, which the role may not read,
and the role has no access to Contacts at all. Today nobody notices because all nine Admins also hold
other roles. **Recommended fix:** give the Admin role read access to invoices and the Contacts
ability, so that it does what its name says. If you would rather keep it narrow, **rename it**
"Settings administrator" so that nobody gives it to a person expecting them to manage clients.
Nothing has been changed.

## The blank system (the template new clinics are made from)

The blank system must hold **no client information at all** — no identity numbers, no health fields
from Form Studio, no files. Each system on the platform locks its encrypted information with its own
key, and a new clinic made from the blank system gets a new key: anything encrypted on the blank
system would arrive in the new clinic as text nobody can ever read again. Since this release the
update procedure checks this after every update of the blank system and stops with a warning if a
single encrypted value is there; it also switches the blank system's scheduled jobs off by itself.
Today the blank system holds none.
