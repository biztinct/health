# Operations Manager — Bookings, Staff & the Service Workflow

The Operations Manager section is where you run day-to-day home-visit operations: seeing what is happening today, taking bookings from first request through to a closed, paid visit, managing your clients and staff, assigning nurses, and reconciling the cash they collect in the field.

This section contains: the **Dashboard** (Operations Center), **Bookings**, **Clients**, **Staff** (Roster / Schedules / Time Off), **Staff Assignment**, **Collections**, and **Workload**.

## Dashboard (Operations Center)

### Operations Center

The Operations Center is your live "command desk" for the day. Use it first thing in the morning and throughout the day to see every booking, spot the ones that still need a nurse, and assign staff in a single click.

![The Operations Center dashboard with KPI cards, booking queue, staff roster, and timeline](IMG:ops_01_dashboard.png)

**What you see on this screen:**

- **Top controls:** date navigation (previous / next arrows and the current date), a period filter (Today / Week / Month / All / Custom), a Facility filter (All Facilities or a single facility), and a refresh button.
- **KPI cards:** Total Bookings, Needs Assignment (with an urgent / normal breakdown), Active Now (visits in progress), Completed, and Revenue.
- **Booking Queue panel** with three tabs: "Needs Staff" (with a badge count), "All Today", and "Issues". Each booking card shows the time, the booking ID, an **URGENT** badge if it is high priority, a status chip, a 3-dot menu, the client name, and the service type, duration, and location. Unassigned cards also have an inline **Assign:** dropdown.
- **Staff Roster panel:** each staff member shown with an avatar, a status dot, their name, and today's booking count.
- **Today's Timeline:** a time grid from 7am to 6pm with a row per staff member and colored service blocks. A legend explains the colors: Home Visit, Clinic, Consult, Follow-up.
- **Footer buttons:** "View All Bookings" and "Create Booking".

**How to use it:**

1. Set the **period filter** (Today / Week / Month / All / Custom) and the **Facility filter** to choose what you are looking at; the whole dashboard updates to match.
2. Use the **prev / next** arrows to move the date backward or forward, and **refresh** to pull the latest data.
3. Read the **KPI cards** to gauge the day at a glance; the Needs Assignment card tells you how many bookings (and how many urgent ones) still have no nurse.
4. In the **Booking Queue**, click the **Needs Staff** tab to see only bookings waiting for a nurse, **All Today** for everything today, or **Issues** for problem bookings.
5. To staff an unassigned booking fast, open its **Assign:** dropdown — it lists available staff together with their current workload — and pick one. The nurse is assigned in a single click.
6. To do more with a booking, open its **3-dot menu**: View Details, Assign Staff, Start Service, Collect Payment, or Cancel. Each opens the matching screen or action.
7. In the **Staff Roster**, click any staff member to open their record.
8. Use **Create Booking** to start a new booking, or **View All Bookings** to jump to the full Bookings list.

**Tip:** The "Needs Staff" badge count and the "Needs Assignment" KPI are the two numbers to keep at zero — clear them and every client for the day has a nurse.

## Bookings

A booking is one scheduled home visit, from the moment you create it to the moment it is closed and paid. This is the heart of your day, so the workflow below is described step by step.

### Viewing bookings (List & Calendar)

You can view your bookings as a sortable list or as a calendar, whichever suits the task.

![The Bookings list view](IMG:ops_02_bookings_list.png)

![The Bookings calendar view](IMG:ops_02d_bookings_calendar.png)

**What you see on this screen:**

- A **list view** of all bookings.
- A **calendar view** that can be switched between Day, Week, and Month.

**How to use it:**

1. Use the **list view** to scan and sort many bookings at once.
2. Switch to the **calendar view** and choose **Day**, **Week**, or **Month** to see bookings laid out by time.
3. Click any booking to open its full record.

### The booking record

Every booking opens to a single record that shows you exactly where it is in its life and what to do next.

![A completed booking detail with lifecycle bar, summary cards, and quick actions](IMG:ops_02b_booking_detail.png)

**What you see on this screen:**

- A **lifecycle progress bar:** Created → Confirmed → Assigned → In Progress → Completed → Closed.
- **Summary cards:** Scheduled, Service Type, Duration, Facility, and Catchment.
- **Client Information** and **Staff Assignment** panels.
- A **Next Best Action** panel that tells you the single most useful thing to do next.
- **Quick Actions:** Client Details, View Quote, View Payments, and View Assignments.

**How to use it:**

1. Read the **lifecycle progress bar** to see which stage the booking is at.
2. Follow the **Next Best Action** panel — it surfaces the right button for the current stage.
3. Use the **Quick Actions** to jump to the client, the quote, the payments, or the assignments without leaving the booking.

### The full booking workflow

This is the complete journey of a booking. Each step lists the action you take, what it does, and what appears next.

![A draft booking showing the Create Quote next best action](IMG:ops_02c_booking_draft.png)

1. **Create the booking (Draft).** Click **Create Booking** (from the Operations Center or from a client profile). Fill in the client (the system de-duplicates so you do not create the same client twice), the service type, the facility, the date and time, and the duration. The booking saves as a **Draft**.
2. **Create the quote (still Draft).** On a draft booking, the **Next Best Action** panel shows **Create Quote**. Click it to add priced service lines, then save. Pricing can automatically apply distance-based travel charges.
3. **Confirm the booking (→ Confirmed).** Once a quote exists and the date is set, click **Confirm Booking**. This finalises the booking number and moves it to **Confirmed** — the client is now booked.
4. **Assign staff (→ Assigned).** Click **Assign Staff** (or use the **Assign** dropdown in the Operations Center). This creates the staff assignment(s): the first nurse is the **Lead** and any others are **Support**. The assigned nurse(s) receive a push notification.
5. **Start the service (→ In Progress).** Click **Start Service**. This stamps the actual start time and starts a timer; the booking now shows as **Active Now**.
6. **Add clinical notes.** During the visit, add clinical notes on the **Clinical tab**. This is required before you can complete the booking.
7. **Complete the service (→ Completed).** Click **Complete Service**. This stamps the end time. Bookings handled by full-time staff move to **Completed**; bookings handled by part-time staff move to **Completed-Pending-Invoice**, which means Operations must raise the invoice.
8. **Create the invoice.** Click **Create Invoice**. This opens the quote for a final review and generates the invoice.
9. **Collect payment.** Record the payment as cash or transfer.
10. **Close the booking (→ Closed).** Click **Close**. This finalises the booking and locks it.

**Alternatives at any time before completion:**

- **Cancel Booking** (available before Completed) opens a cancel wizard where you enter a reason and notes; it cancels the assignments and notifies the staff.
- **Reschedule** changes the date and time and reassigns staff.

**Button reference:**

| Button | What it does | State after |
| --- | --- | --- |
| Create Booking | Creates a new booking from the client and visit details | Draft |
| Create Quote | Adds priced service lines (may include travel charges) | Draft |
| Confirm Booking | Finalises the booking number; client is booked | Confirmed |
| Assign Staff | Creates assignment(s); first = Lead, others = Support; notifies nurses | Assigned |
| Start Service | Stamps start time and starts the timer | In Progress |
| Complete Service | Stamps end time | Completed (or Completed-Pending-Invoice for part-time staff) |
| Create Invoice | Opens the quote for review and generates the invoice | Completed |
| Close | Finalises and locks the booking | Closed |
| Cancel Booking | Opens cancel wizard; cancels assignments and notifies staff | Cancelled |
| Reschedule | Changes date/time and reassigns | (date/time changed) |

**Note:** The difference between full-time and part-time staff matters at step 7. Part-time visits land in **Completed-Pending-Invoice** and will not finish on their own — you must raise the invoice for them.

**Warning:** Clinical notes are required before you complete a service (step 6). If they are missing, you will not be able to move the booking to Completed.

## Clients

### Clients list

The Clients list is your directory of patients. Use it to find a client and immediately act on them.

![The Clients list with patient details and quick actions](IMG:ops_03_clients_list.png)

**What you see on this screen:**

- Each client row shows the **Patient ID**, **phone**, and **last visit**.
- Quick actions on each row: **Book**, **Recurring**, **Collect**, and **Payment**.

**How to use it:**

1. Find the client you need in the list.
2. Use the row quick actions: **Book** to create a one-off booking, **Recurring** to set up a repeating booking, **Collect** to record collected cash, or **Payment** to take a payment.
3. Click the client to open their full profile.

### Client profile

The client profile is the complete picture of one patient — their history, their spend, where they live, and the route your nurse will drive.

![A client profile with KPI cards, address, map route, and quick actions](IMG:ops_03b_client_profile.png)

**What you see on this screen:**

- **KPI cards:** Total Bookings, Active Packages, Total Spent, Outstanding, Satisfaction, and Referrals.
- **Address Details**, including the **driving distance** to the clinic.
- A **Map Location** showing the route.
- A **Create Booking** button and a **Quick Actions** panel: View Bookings, Create Recurring Booking, Quick Package Purchase, Create Invoice, View Invoices, and Purchased Packages.

**How to use it:**

1. Review the **KPI cards** to understand the client's history and any outstanding balance at a glance.
2. Enter or edit the **address** — it auto-geocodes, and the **route and distance** appear on the map.
3. Use **Create Booking** to start a booking for this client, or pick from **Quick Actions** to view bookings, set up recurring visits, purchase a package, create or view invoices, or see purchased packages.

**Note:** The driving distance shown here feeds your pricing — it is what powers the distance-based travel charges that can appear on a quote.

## Staff

### Roster

The Roster shows who is on and how busy they are right now.

![The staff roster showing availability and today's load](IMG:ops_04_staff_roster.png)

**What you see on this screen:**

- Each staff member's **availability** and **today's load**.

**How to use it:**

1. Check the roster to see who is available before assigning work.
2. Read each person's today's load to balance assignments fairly.

### Schedules

Schedules show each staff member's regular working hours.

![Staff working-hours schedules](IMG:ops_05_schedules.png)

**What you see on this screen:**

- Each staff member's **working hours**.

**How to use it:**

1. Open Schedules to confirm a nurse's working hours before booking them into a visit.

### Time Off

Time Off lists staff leave so you do not assign someone who is away.

**What you see on this screen:**

- A list of staff **leave**.

**How to use it:**

1. Check Time Off before assigning a visit to make sure the nurse is not on leave.

## Staff Assignment

### Staff Assignment timeline

Staff Assignment is a timeline view of every assignment across all your staff and the day, so you can see who is doing what and when.

![The staff assignment timeline across staff and time](IMG:ops_06_staff_assignment.png)

**What you see on this screen:**

- A **timeline** of assignments laid out across staff and time.

**How to use it:**

1. Read the timeline to see each nurse's assignments through the day.
2. Track each assignment through its lifecycle: **assigned** → **confirmed** (the nurse accepts in the mobile app) → **in_progress** (the nurse starts) → **completed**.

**Note:** Nurses accept, start, and complete their assignments from the mobile app. See the Mobile chapter for how the nurse side works.

## Collections

### Collections

Collections is where you reconcile the cash your nurses collect in the field. When a nurse takes cash on a visit, it is marked "pending delivery" to the office; here is where the office confirms it has arrived.

![The collections screen for reconciling field cash](IMG:ops_07_collections.png)

**What you see on this screen:**

- Cash collected by nurses in the field that is **pending delivery** to the office.

**How to use it:**

1. Review the cash listed as pending delivery.
2. Reconcile each amount as it is handed in to the office.

**Tip:** Reconciling Collections regularly keeps your field cash and your office records in sync, so nothing collected on a visit goes unaccounted for.

## Workload

### Workload

Workload is a dashboard of how busy your staff are, so you can spread visits evenly and avoid overloading anyone.

![The workload dashboard of staff utilisation and assignment load](IMG:ops_08_workload.png)

**What you see on this screen:**

- A dashboard of **staff utilisation** and **assignment load**.

**How to use it:**

1. Review each staff member's utilisation and assignment load.
2. Use what you see to rebalance work — move assignments away from overloaded staff toward those with spare capacity.