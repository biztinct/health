# Mobile Nurse App

The Mobile Nurse App is what field nurses use on their phone to see their visits, open patient details, start and complete services, and stay in sync with the office. It is a Progressive Web App (PWA), which means it runs in your phone's web browser but can behave just like a regular app.

## Getting Started

### Opening and Installing the App

This is the very first thing you do on your phone before any visit. You open the app in your browser, log in once, and (optionally) add it to your Home Screen so it opens like a normal app from then on.

**How to use it:**

1. Open your phone's web browser and go to **care.biztinct.com/health_pwa**.
2. Log in with your nurse account (the same username and password the office gave you).
3. To make it behave like a real app, use your browser's **Add to Home Screen** option. An app icon appears on your phone, and tapping it opens the Nurse App directly.

**Tip:** Adding it to your Home Screen means you no longer have to type the web address each time. Just tap the icon.

**Note:** The app caches (saves) data on your phone so it keeps working even with poor signal. Your changes sync back automatically once you are online again.

### The Bottom Navigation and Top Header

Wherever you are in the app, the same bottom navigation and top header are always available, so you can move around quickly.

- **Bottom navigation (four tabs):** Booking, Patients, Call, Profile. Tap a tab to switch to that screen.
- **Top header language switch (VI/EN):** tap to switch the app between Vietnamese and English.
- **Notifications bell:** shows a count of new notifications; tap it to view them.

**Note:** When a new version of the app is available, a banner appears. Tap **Update Now** to refresh to the latest version.

## Booking Tab

The Booking tab is your home base for the day. It shows your assigned visits and lets you view them by Day, Week, or Month.

### Booking — Day View

Use the Day view to see everything scheduled for a single day, one visit per card. This is the view you will use most while out on visits.

![Day view listing each visit as a card with time, status, and quick actions](IMG:pwa_01_today_day.png)

**What you see on this screen:**

- A header with the current **date**, a **Today** button, **previous/next** arrows, and a **calendar picker** to jump to any date.
- A **Day / Week / Month** switcher to change how visits are displayed.
- A **visit card** for each appointment, showing:
  - The **time** and **duration** of the visit.
  - The **status** (for example, Completed or Assigned).
  - The **client name and ID**.
  - The **service type**.
  - Quick **Call** and **Map** buttons.

**How to use it:**

1. Tap **Today** to jump back to the current day's visits at any time.
2. Tap the **previous/next** arrows to move one day at a time, or tap the **calendar picker** to jump straight to a specific date.
3. On a visit card, tap **Call** to phone the client, or tap **Map** to get directions to the visit location.
4. Tap anywhere else on the visit card to open its detail sheet (see *Opening a Booking* below).

**Tip:** The status on each card updates in real time, so you can always see at a glance which visits are done and which are still ahead of you.

### Booking — Week View

Use the Week view when you want to see how your visits are spread across the whole week.

![Week view grouping visits by day](IMG:pwa_03_week.png)

**What you see on this screen:**

- The same date header and **Day / Week / Month** switcher.
- Your visits **grouped by day** across the week.

**How to use it:**

1. Tap **Week** in the switcher to open this view.
2. Use the **previous/next** arrows or the **calendar picker** to move between weeks.
3. Tap any visit to open its detail sheet.

### Booking — Month View

Use the Month view to get a big-picture overview of which days have visits scheduled.

![Month view as a calendar with dots on days that have visits](IMG:pwa_04_month.png)

**What you see on this screen:**

- A full **calendar** for the month.
- **Dots** on the days that have visits scheduled.

**How to use it:**

1. Tap **Month** in the switcher to open this view.
2. Look for the **dots** to spot which days have visits.
3. Tap a day to see its visits.

### Opening a Booking and the Nurse Service Flow

Tapping a visit opens its detail sheet, where you carry out the visit step by step using the service action buttons. This is the core of your daily work in the app.

![Booking detail sheet with the service action buttons](IMG:pwa_02_booking_detail.png)

**What you see on this screen:**

- The visit's details.
- The **service action buttons** that walk you through the visit (Accept, Start Service, Complete).

**How to use it (the nurse service flow):**

1. **Accept** the assignment to confirm it. This tells the office you have taken on the visit.
2. On arrival, tap **Start Service** to start the visit timer.
3. **Record your clinical notes** during the visit.
4. When you are finished, tap **Complete** to close out the service.

| Button | What it does |
| --- | --- |
| Accept | Confirms the assignment |
| Start Service | Starts the visit timer (tap on arrival) |
| Complete | Marks the service finished |

**Note:** As you move through these steps, the booking status updates in real time and syncs back to the office, so the team always sees your current progress.

## Patients Tab

### Patients List

The Patients tab lets you look up the people in your care so you can review their details before or during a visit.

![Patients tab with searchable patient list and details](IMG:pwa_05_patients.png)

**What you see on this screen:**

- A **search** box to find a patient.
- The **patient list** and patient **details**, limited to the patients within your catchment (your assigned area).

**How to use it:**

1. Type a name in the **search** box to find a patient.
2. Tap a patient to view their details.

**Note:** You only see patients within your catchment area.

## Call Tab

### One-Tap Clinic Call

The Call tab is a quick shortcut to phone the clinic whenever you need to reach the office.

![Call tab with one-tap dial to the clinic's phone number](IMG:pwa_06_call.png)

**How to use it:**

1. Tap the **Call** tab.
2. Tap to **dial the clinic's phone number** in one tap.

## Profile Tab

### Your Profile, Sync, and Log Out

The Profile tab shows who you are signed in as and gives you the controls to sync your data and log out securely.

![Profile tab showing name and email, Sync Data, and Log Out](IMG:pwa_07_profile.png)

**What you see on this screen:**

- Your **name** and **email**.
- A **Sync Data** button.
- A red **Log Out** button.

**How to use it:**

1. Tap **Sync Data** to pull the latest data from the office and push up any changes you made while offline.
2. Tap **Log Out** when you are done using the app.

| Button | What it does |
| --- | --- |
| Sync Data | Pulls the latest data and pushes your offline changes |
| Log Out | Signs you out and clears cached patient data from the device |

**Warning:** Logging out clears the cached patient data stored on the device for privacy. Only log out when you intend to fully sign off, and make sure you have synced any offline changes first.

**Tip:** If something looks out of date, tap **Sync Data** to refresh. This is also how your offline changes reach the office once you have signal again.