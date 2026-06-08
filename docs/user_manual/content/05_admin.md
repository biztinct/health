# Admin — Users, Master Data, Pricing & Settings

The Admin section is where you set up and configure the whole system: the people who can log in, the reference lists every other screen relies on, how prices are calculated, and your company-wide options. Most day-to-day staff will only visit a few of these screens, but everything that powers the bookings, quotes, and scheduling lives here.

## Getting your bearings

### Admin Dashboard

The Admin Dashboard is your starting point. It gives you a one-glance health check of the system and fast shortcuts to the things you set up most often.

![The Admin Dashboard with KPI cards, Quick Actions, and Recent Activity](IMG:admin_01_dashboard.png)

**What you see on this screen**

- **KPI cards** (each one is clickable and opens the matching list):
  - Active Users
  - Active Facilities
  - Service Types
  - Pricing Rules
  - Equipment Items
  - Audit Events Today
- **Quick Actions grid** with one-click buttons: Add User, Add Facility, Pricing Rules, Audit Log, Master Data, Healthcare Staff.
- **Recent Activity feed** showing the most recent audited changes in the system.

**How to use it**

1. Read the **KPI cards** at the top to see current totals at a glance.
2. Click any **KPI card** to jump straight into that list (for example, click *Active Users* to open the user list).
3. Use a **Quick Action** button to start a common task immediately — for example, *Add User* opens the new-user wizard, or *Add Facility* opens a new facility form.
4. Scan the **Recent Activity feed** to see what was changed recently and by whom.

**Tip:** When you are not sure where to start, the Quick Actions grid covers the most common admin jobs, so you rarely need to hunt through menus.

## People & access

### Users & Roles

This is the list of internal user accounts — the people who can log in to the system. Crucially, this is also where you control **what each person is allowed to see and do**, by assigning them a role.

![The Users & Roles list of internal accounts](IMG:admin_02_users.png)

**What you see on this screen**

- A list of all internal user accounts.
- A button/option to create a new user, which opens a user wizard.

**How roles control access**

A role bundles together the permissions (groups) that decide which menus and records a person can see. Some examples:

| Role | What they can see |
| --- | --- |
| Nurse | Only their assigned bookings and the clients in their catchment |
| Operations Manager | All bookings in their catchment |
| Finance | Finance-related records |
| Owner / Admin | Everything |

**How to use it**

1. Open **Users & Roles** to view the list of accounts.
2. To add a person, start a new user — this opens the **user wizard**.
3. In the wizard, enter the person's **name**, their **login / email**, and assign a **role**. The role automatically applies the right permissions and groups.
4. Save the user. They can now log in and will only see the menus and records their role allows.
5. To change what an existing person can access, open their account and **change their role / groups** here.

**Note:** Visibility is driven entirely by the assigned role. If someone says they "can't see" a booking or client, the fix is almost always to review and adjust their role on this screen.

## Reference data the whole app uses

### Master Data

Master Data is a tabbed navigator over all the reference (lookup) tables that the rest of the app draws from. Anything that appears in a dropdown elsewhere — service types, symptoms, insurance providers, and so on — is defined and maintained here.

![The Master Data tabbed navigator over reference tables](IMG:admin_03_master_data.png)

**What you see on this screen**

A set of tabs, each one a simple list-plus-form for a single reference table:

- **Facilities** — clinics / home-care centres
- **Catchments** — geographic service areas (these drive client and staff matching)
- **Service Types**
- **Symptoms**
- **Referral Sources**
- **Insurance** providers
- **Urgency levels**
- **Patient Categories**
- **Medical Specialties**
- **Districts**

**How to use it**

1. Open **Master Data** and choose the **tab** for the list you want to manage (for example, *Service Types*).
2. To add an entry, create a new record in that tab's list and fill in the form.
3. To change an entry, open it from the list and edit it.
4. Save. The new or updated entry now appears in the matching **dropdowns across the app**.

**Tip:** Keep Catchments accurate — they drive which clients and staff get matched together, so an out-of-date catchment can affect who gets assigned to bookings.

### Pricing

Pricing holds the rules that the quote engine uses to calculate charges automatically. When a booking is quoted, these rules add the right amounts without anyone keying them in by hand.

![The Pricing rules used by the quote engine](IMG:admin_04_pricing.png)

**What you see on this screen**

- **Pricing rules**, which can depend on factors such as:
  - Distance (distance bands / per-km)
  - Zone
  - Service type
  - Time
  - Urgency
- **Pricing engines**
- **Healthcare packages**

**How to use it**

1. Open **Pricing** to see the existing rules.
2. To add a charge, create a new **pricing rule** and choose what it depends on (for example, a distance band, a zone, a service type, a time, or an urgency level) and the amount it adds.
3. Save the rule. From then on, the **quote engine** applies it automatically when a matching booking is quoted.
4. Manage your **pricing engines** and **healthcare packages** from the same screen as needed.

**Note:** The driving distance calculated on a booking feeds the distance-based rules here, so travel charges are applied automatically — you do not need to add them by hand.

## Staff, equipment & scheduling

### Healthcare Staff

This is the master list of your healthcare staff (nurses and doctors). What you record here decides who can be assigned to bookings.

![The Healthcare Staff master list](IMG:admin_05_healthcare_staff.png)

**What you see on this screen**

- A list of all healthcare staff.
- For each person, their profile, role, facility / catchment, skills, and service areas.

**How to use it**

1. Open **Healthcare Staff** to view the list.
2. To add someone, create a new staff record and fill in their **profile**, **role**, **facility / catchment**, **skills**, and **service areas**.
3. To update someone, open their record and edit these details.
4. Save. These details drive **who can be assigned to bookings** — for example, matching staff skills and service areas to a booking's needs.

**Tip:** Keep each person's catchment, skills, and service areas current so the system suggests the right people when bookings are assigned.

### Equipment

Equipment is your inventory of portable equipment that can be attached to bookings.

![The Equipment inventory](IMG:admin_06_equipment.png)

**What you see on this screen**

- A list of portable equipment items.

**How to use it**

1. Open **Equipment** to view the inventory.
2. To add an item, create a new equipment record and save it.
3. The item is then available to be **attached to bookings**.

### Public Holidays

A calendar of public holidays that affect scheduling and pricing. Add the dates here so the system knows which days are holidays when it schedules visits and calculates quotes.

![The Public Holidays calendar](IMG:admin_07_holidays.png)

## Compliance & configuration

### Audit Log

A read-only record of who changed what and when, kept for compliance. You cannot edit it — you use it to look back and confirm what happened. The Recent Activity feed on the dashboard is a quick window into the same information.

![The Audit Log of changes](IMG:admin_08_audit.png)

### Field Requirements

This is where you configure which form fields are mandatory. Use it to make sure staff fill in the information you consider essential before they can save a record.

![The Field Requirements configuration](IMG:admin_09_field_req.png)

### CMS Sidebar Config

An advanced screen that defines the left-hand menu itself — the sections and the items inside them. Changing it reshapes the navigation everyone sees, so it is normally only touched during setup.

![The CMS Sidebar configuration](IMG:admin_10_cms_sidebar.png)

**Warning:** Because the CMS Sidebar Config controls the menus for all users, only change it when you are confident about the effect — a wrong edit can hide menus people rely on.

### Settings

Settings is the home for system-wide configuration — the company-wide options that apply to everyone.

![The system Settings screen](IMG:admin_11_settings.png)

**What you set here**

- Map provider / API key
- Invoicing options
- Integrations

**How to use it**

1. Open **Settings**.
2. Find the option you need (for example, the **map provider / API key**, **invoicing**, or an **integration**).
3. Enter or update the value and save. The change applies across the whole company.

**Note:** These are company-wide options, so a change here affects every user — set them once during setup and revisit only when something like an API key or integration needs updating.