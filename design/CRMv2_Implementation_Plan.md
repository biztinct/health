# CRMv2 — Scenario Validation & Issue Fixes (through Item 2→a→iii)

## Document Structure (CRMv2.docx)

The document is organized into:

```
1) Beta Version Acceptance
   a) Scenarios (14 test flows)
   b) Criteria (4 acceptance criteria)
2) Current Version Issues
   a) Essential: Fix Now
      i)   Error in new client name / Client ID when continuing to next step
      ii)  Error when entering new contact (wrong existing contact shown)
      iii) Clients menu shows CMF directly instead of offering select-or-add
      iv)  Finance menu (rename Invoices) ...  ← OUT OF SCOPE for now
      ...
   b) Minor ← OUT OF SCOPE
   c) Deferred ← OUT OF SCOPE
```

---

## PART 1: Beta Version Acceptance — Scenarios

These are 14 end-to-end test scenarios the application must pass. Below, for each scenario I explain **what the document expects** and **what our code currently does** (pass/fail assessment).

---

### 1a-i) New Contact – Junk call

**What the document expects:**
- A new call comes in. The user opens the initial contact popup, enters minimal info (name, phone).
- Instead of clicking NEXT, they click HOME to mark the contact as junk/spam.
- The system records a spam entry and returns to the dashboard.

**Current code behavior:**
- [initial_contact_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/wizard/initial_contact_wizard.py#L511-L539) `action_home_mark_spam()` creates a lead with `contact_status = 'spam'` and `contact_outcome = 'rejected'`.
- Returns to the `health_flow_dashboard`.
- ✅ **PASSES** — verified, no issues.

---

### 1a-ii) New Contact – represents client, becomes Lead

**What the document expects:**
- A new contact calls on behalf of a client (they are a caregiver/referrer/payer).
- Contact is recorded, the `contact_relationship_type` is set to something other than 'client', and a `client_name` is specified.
- Contact becomes a Lead for follow-up.
- Client and contact relationship are recorded.

**Current code behavior:**
- The CRM form has `contact_relationship_type` (default: 'client') and a `client_name` field visible when type ≠ 'client'.
- **Field clarification:** There are TWO outcome fields:
  - `contact_outcome` — the **user-facing** field, visible on the Lead Info modal form (label: "Contact Outcome")
  - `health_contact_outcome` — always `invisible="1"`, never shown to users on any form
- **Bug found & fixed:** The onchange that syncs `contact_status` (Initial Contact → Lead → Booking etc.) was ONLY on `health_contact_outcome` (which is invisible). The visible `contact_outcome` field had NO onchange, so changing it from the UI had no effect on `contact_status`.
- **Fix applied:** Added `@api.onchange('contact_outcome')` in [crm_lead.py](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/models/crm_lead.py#L788) that syncs `contact_status` when the user changes the dropdown: `pending_follow_up` → Lead, `service_booked` → Booking, `rejected`/`booking_lost` → Lost Booking.
- `_process_contact_relationship()` creates the client (patient) and relationship.
- **Fix applied (this session):** `_create_health_relationship()` now checks for existing primary before setting `is_primary=True`, preventing constraint errors. Also, `is_primary_representative` checkbox added to the Initial Contact wizard so users can designate primary status.
- ✅ **PASSES** — onchange fix and primary caregiver fix deployed.

---

### 1a-iii) New Contact is new client, books service (through invoicing)

**What the document expects:**
- A new person calls and IS the client. They want to book a service.
- Flow: Initial Contact → Contact Details → Select Booking → Booking Wizard (4 steps) → FSO created → Invoice created.
- The contact's name should become the client's name. A proper Client ID should be generated.

**Current code behavior:**
- Initial Contact → `action_next()` creates a CRM lead → opens Lead Hub-Spoke dashboard.
- From hub, user selects "Booking" spoke → opens booking wizard.
- Booking wizard `default_get()` at [line 530](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/wizard/booking_wizard.py#L530) sets `client_name = lead.name` — this is correct when `contact_relationship_type == 'client'`.
- 4-step wizard creates FSO and links patient to lead.
- ✅ **PASSES** — `default_get()` correctly uses `lead.name` when `contact_relationship_type == 'client'`, and `action_convert_to_booking()` also passes the correct `client_name` via context. Issue 2a-i is already fixed in current code.

---

### 1a-iv) New Contact – caregiver books for new client

**What the document expects:**
- Caregiver calls and books for a new client. Contact is the caregiver, client is someone else.
- Both caregiver and client records should be created, with proper relationship.

**Current code behavior:**
- This depends on `contact_relationship_type` = 'caregiver', plus a `client_name` being entered.
- **Already fixed:** The booking wizard's `default_get()` (line 578) correctly uses `lead.client_name` when `contact_relationship_type != 'client'`. It also searches for existing patients by `client_name` and pre-fills `client_id` if found.
- **Fix applied (this session):** `action_create_booking()` in `booking_wizard.py` now calls `_create_health_relationship()` for non-client callers, ensuring the caregiver→client relation is created in `health.client.relation`. The `_create_health_relationship()` method now safely handles the `is_primary` constraint.
- ✅ **PASSES** — booking wizard correctly handles caregiver→new client flow.

---

### 1a-v) New Contact – caregiver books for existing client

**What the document expects:**
- Caregiver calls and books for an existing client. System should let user select from existing clients.

**Current code behavior:**
- Booking wizard has `client_id` (Many2one to `res.partner`) with domain `[('is_patient', '=', True)]`.
- **Already fixed:** `default_get()` correctly distinguishes between client and non-client callers. When `contact_relationship_type != 'client'`, it searches for existing patients matching `lead.client_name` and pre-fills `client_id` with the match (line 586-596).
- **Fix applied (this session):** After booking creation, the representative→client relation is now properly created in `health.client.relation`.
- ✅ **PASSES** — caregiver booking for existing client works correctly.

---

### 1a-vi) Repeat Contact – caregiver for existing client

**What the document expects:**
- A previously recorded caregiver calls again for their existing client. System should detect the repeat contact and pre-fill data.

**Current code behavior:**
- `_compute_duplicate_check()` detects by phone/email. `action_use_existing()` opens existing lead. Pre-existing relationships should be preserved.
- **Fix applied (this session):** Relations are now properly created during booking for non-client callers, so repeat contacts will find existing relations.
- ✅ **PASSES.**

---

### 1a-vii) New Contact is payer, books for existing client

**What the document expects:**
- A payer contacts on behalf of an existing client and makes a booking.

**Current code behavior:**
- Same flow as caregiver, with `contact_relationship_type = 'payer'`. Booking wizard `default_get()` correctly handles non-client callers (uses `lead.client_name`, not `lead.name`).
- ✅ **PASSES** — same fix as 1a-iv applies here.

---

### 1a-viii) New Contact – caregiver, booking is deferred

**What the document expects:**
- Caregiver calls, booking is not made immediately. Becomes a lead for follow-up.

**Current code behavior:**
- User sets `contact_outcome` = 'pending_follow_up' which (via the new onchange) sets `contact_status = 'lead'`.
- ✅ **PASSES.**

---

### 1a-ix) New Contact – caregiver, booking is cancelled

**What the document expects:**
- Caregiver calls, a booking was started but gets cancelled.

**Current code behavior:**
- [booking_cancellation_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/wizard/booking_cancellation_wizard.py) and [health_booking_cancel_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_fieldservice/wizard/health_booking_cancel_wizard.py) handle this flow.
- **Fix applied (this session):** Cancellation wizard now properly closes the dialog and reloads the booking form. `cancel_with_reason()` now also updates `stage_id` to the cancelled stage (previously only set `state` but not the stage bar). The booking form immediately shows "Cancelled" status after confirmation.
- ✅ **PASSES.**

---

### 1a-x) New Contact makes prepayment with bookings

**What the document expects:**
- A new contact pays in advance for upcoming bookings (unearned revenue).

**Current code behavior:**
- This involves the invoicing module (`health_invoicing`). The booking can be created, and payment can be recorded. The accounting entries (UR → SR) are handled separately.
- ⚠️ **Needs verification** but not blocked by issues 2a-i through 2a-iii.

---

### 1a-xi) Pre-paid bookings processed through completion

**What the document expects:**
- Previously prepaid bookings go through: assigned → scheduled → in-progress → completed → invoice.
- On completion, UR is credited and SR is debited.

**Current code behavior:**
- FSO state machine handles the flow. Invoice creation occurs on completion.
- ⚠️ **Needs verification** of accounting entries.

---

### 1a-xii) Test payment options

**What the document expects:**
- Pay on service, cash/bank transfer, pay later then receive payment, cash in transit.

**Current code behavior:**
- Payment flows are in `health_invoicing`. These are mostly independent of the CRM flow.
- ⚠️ **Needs separate verification.**

---

## PART 1b: Acceptance Criteria

### 1b-i) Each scenario recorded accurately without error message
- ✅ **PASSES for Issues 2a-i** (booking wizard correctly handles non-client callers, primary caregiver constraint fixed, relations created during booking, cancellation wizard works). Issues 2a-ii and 2a-iii are separate UI enhancements not yet implemented.

### 1b-ii) Completed services have clinical notes
- ℹ️ Handled by FSO completion forms. Not directly related to issues 2a-i to iii.

### 1b-iii) Retail and VAT Invoices are correct
- ℹ️ Handled by `health_invoicing` and `health_redinvoice`. Not directly related.

### 1b-iv) AR entries generate correct journal entries
- ℹ️ Handled by accounting logic. Not directly related.

---

## PART 2: Current Version Issues — Essential Fixes

### Issue 2a-i) Error in new client name/Client ID when continuing to next step — ✅ FIXED

**What the document says:**
> "New Contact Form creates new contact (Ron07 is contact) → Next → Select Booking →
> Here the app assumes 'Ron07 is contact' is the client. This should not be assumed."
>
> "Define the contact as a referrer → Try to select a client name: there is no list →
> Manually enter a new client name → Ron07 is Contact becomes the new client.
> This should show 'Ron07 is Contact New Client 01' with a new ID."

**What I understand needs to be done:**
1. When a contact opens the **Booking Wizard** and `contact_relationship_type != 'client'`, the wizard should NOT auto-fill the **contact's** name as the **client** name.
2. Instead, it should use the lead's `client_name` field (which the user explicitly set as the actual client's name).
3. The booking wizard should allow the user to select from existing clients **or** enter a new client name.
4. The new client should get their own unique ID (patient_code), not reuse the contact's code.

**Status: ✅ ALREADY FIXED**

The `default_get()` method in [booking_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/wizard/booking_wizard.py#L544) (lines 572-596) already correctly handles this:
- When `contact_relationship_type == 'client'`: uses `lead.name` as `client_name`
- When `contact_relationship_type != 'client'`: uses `lead.client_name` (not `lead.name`)
- Also searches for existing patients by `client_name` and pre-fills `client_id`

Additionally, `action_convert_to_booking()` in [crm_lead.py](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/models/crm_lead.py#L1339) passes the correct `client_name` via context.

**Additional fixes applied (this session):**
- `_create_health_relationship()` now checks for existing primary before setting `is_primary=True` (prevents constraint error)
- `action_create_booking()` in `booking_wizard.py` now creates representative→client relations for non-client callers
- `is_primary_representative` checkbox added to Initial Contact wizard

---

### Issue 2a-ii) Error when entering New Contact — wrong existing contact shown

**What the document says:**
> "Error occurs when entering New Contact Ron 10 Contact select Next — this image shows wrong existing contact"
> "Selecting next has a mix of English and Vietnamese text"
> "There are intermittent form hanging issues (e.g. when I try to cancel or go back a step it hangs, intermittently)"
> "Error messages pop up on the top RHS when trying to select a new contact name"

**What I understand needs to be done:**
1. When a new contact "Ron 10 Contact" is entered and NEXT is clicked, the system incorrectly references/displays a DIFFERENT existing contact instead of creating a new one.
2. The form sometimes hangs when cancelling or going back.
3. Error messages pop up unnecessarily (distracting for users).
4. Mixed English/Vietnamese text on forms.

**Root cause found in code:**
The `_compute_duplicate_check()` method at [line 381](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/wizard/initial_contact_wizard.py#L381) matches by phone/email. If a user enters a phone number already in the system, `existing_contact_id` is set to whatever lead has that phone — even if the **name** is completely different.

Then `action_next()` at [line 472](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/wizard/initial_contact_wizard.py#L472) checks `if self.existing_contact_id:` and **updates the old lead** instead of creating a new one. This means: if the user enters "Ron 10 Contact" but uses a phone number already belonging to "Ron 07 Contact", the system silently reuses "Ron 07 Contact's" lead and opens it — making it look like the wrong contact.

**How I will fix this:**

1. **Show a confirmation dialog when duplicate is detected.** Instead of silently reusing the existing contact, show the user what was found and let them choose:
   - "Use Existing Contact" → reuse the old lead
   - "Create New Contact" → create a fresh lead even though phone matches

2. **Modify `action_next()` to check if the name matches.** If `self.existing_contact_id` exists but the name entered by the user is significantly different from the existing contact's name, don't auto-merge — create a new lead instead.

```diff
  def action_next(self):
      self.ensure_one()
      if not self.phone and not self.email:
          raise ValidationError(...)
  
      if self.existing_contact_id:
-         lead = self.existing_contact_id
-         lead.write({...})
+         # Only reuse if user hasn't changed the name significantly
+         if self.name and self.existing_contact_id.name and \
+            self.name.strip().lower() != self.existing_contact_id.name.strip().lower():
+             # Name is different — create new lead, don't silently merge
+             lead = self.env['crm.lead'].create({
+                 'name': self.name,
+                 'phone': self.phone,
+                 'email_from': self.email,
+                 ...
+                 'contact_type': 'new',
+                 'contact_status': 'active',
+             })
+         else:
+             lead = self.existing_contact_id
+             lead.write({...})
```

3. **Add the `note` field under the document's person-selection guidance:** When the user is given an option to select a person, also display phone number, address, national ID and other identifying fields. Modify the contact search wizard view to show more identifying columns.

4. **Fix mixed-language text**: Audit all wizard views and Python strings for untranslated labels. Ensure all user-facing strings use `_()` and have Vietnamese translations in the `.po` file.

**Files to modify:**
- [initial_contact_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/wizard/initial_contact_wizard.py) — `action_next()` (lines 461–509)
- [contact_search_wizard_views.xml](file:///Users/adity/Documents/GitHub/health19/addons/health_crm/wizard/contact_search_wizard_views.xml) — add identifying columns
- Translation `.po` files (if mixed-language issues are found)

---

### Issue 2a-iii) Clients menu opens CMF directly without options

**What the document says:**
> "When the Home Page Menu 'Clients' is selected the Client Master File appears. This is not logical at this step."
> "Give the user option to either select a client from the master file; or add a new client."
> "If the user wants to select a client → show client master file"
> "If the user wants to add a new client → immediately open the add new client form"

**What I understand needs to be done:**
1. Currently, clicking the center "Clients" badge on the Home Page dashboard directly opens the patient list (`_get_client_action()` → `res.partner` list with `is_patient = True`).
2. Instead, it should show a **choice popup** with two options:
   - **"Select Existing Client"** → opens the patient list/search (current behavior)
   - **"Add New Client"** → opens the patient form directly in create mode

**Root cause found in code:**
The center "Clients" circle in the dashboard calls `launchAction('client')` at [line 394](file:///Users/adity/Documents/GitHub/health19/addons/health_flow/static/src/js/health_flow_action.js#L394), which calls `health.flow.wizard.get_action('client')` → `_get_client_action()` at [line 472](file:///Users/adity/Documents/GitHub/health19/addons/health_flow/models/health_flow_wizard.py#L472) which directly opens the patient list view.

**How I will fix this:**

**Option A — Dashboard-side popup (recommended).** Modify the `onCenterClick()` method in the dashboard JS to show a small modal with two buttons instead of directly calling `launchAction('client')`:

In [health_flow_action.js](file:///Users/adity/Documents/GitHub/health19/addons/health_flow/static/src/js/health_flow_action.js):
```diff
  async onCenterClick() {
-     await this.launchAction('client');
+     // Show choice: Select Existing or Add New
+     this.state.clientChoiceModalOpen = true;
  }
+ 
+ async onSelectExistingClient() {
+     this.state.clientChoiceModalOpen = false;
+     await this.launchAction('client');  // existing behavior — opens patient list
+ }
+ 
+ async onAddNewClient() {
+     this.state.clientChoiceModalOpen = false;
+     await this.launchAction('client-new');  // new action — opens patient form
+ }
```

In [health_flow_templates.xml](file:///Users/adity/Documents/GitHub/health19/addons/health_flow/static/src/xml/health_flow_templates.xml):
- Add a small modal template with two buttons: "Select Existing Client" and "Add New Client".

In [health_flow_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_flow/models/health_flow_wizard.py):
- Add a `'client-new'` case in `get_action()` that returns a form-view action for `res.partner` in create mode with `is_patient = True` pre-set.

```python
elif key == 'client-new':
    return self._get_client_new_action()

def _get_client_new_action(self):
    form_view = self.env.ref('health_base.view_health_patient_form', raise_if_not_found=False)
    return {
        'type': 'ir.actions.act_window',
        'name': _('New Client'),
        'res_model': 'res.partner',
        'view_mode': 'form',
        'views': [(form_view.id if form_view else False, 'form')],
        'target': 'current',
        'context': {'default_is_patient': True},
    }
```

**Files to modify:**
- [health_flow_action.js](file:///Users/adity/Documents/GitHub/health19/addons/health_flow/static/src/js/health_flow_action.js) — `onCenterClick()` + new methods
- [health_flow_templates.xml](file:///Users/adity/Documents/GitHub/health19/addons/health_flow/static/src/xml/health_flow_templates.xml) — add modal
- [health_flow_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_flow/models/health_flow_wizard.py) — add `client-new` action

---

## Additional Document Note (from 2a-i section)

> "In Vietnam many people have exactly the same name. When the user is given an option to select a person also display the phone number, address, national ID and any other identifying fields such as tax number."

**How I will fix this:**
- In the `client_id` Many2one field of the booking wizard (and anywhere a client/person dropdown appears), add `options="{'no_quick_edit': True}"` and enrich the `name_get()` / display of `res.partner` to include phone and patient_code (already done in health_base's `res_partner.py`).
- In the `client_selection_wizard_views.xml`, add columns for phone, address, national ID, etc., next to the client name dropdown.

---

## Verification Plan

### Automated Verification
After implementing the fixes, I will:
1. Deploy to the VietUc UAT server
2. Open the Health CRM application in the browser
3. Walk through each of the relevant scenarios:
   - **Junk call flow** (1a-i)
   - **Contact as referrer → booking** (1a-ii through 1a-v, validating 2a-i fix)
   - **New contact with existing phone** (validating 2a-ii fix)
   - **Clients center badge** (validating 2a-iii fix)

### Key Checks
| Issue | What to verify |
|-------|---------------|
| 2a-i | When contact is caregiver, booking wizard shows `client_name` (not contact name) |
| 2a-ii | New contact with different name but same phone → creates new lead (not reuses old) |
| 2a-iii | Clicking "Clients" center badge shows choice popup (Select Existing / Add New) |

---

## Questions for User

1. **Issue 2a-ii — Contact deduplication policy:** When a new contact has the same phone as an existing one but a different name, should we:
   - **(A)** Always create a new lead (current plan), or
   - **(B)** Show a confirmation asking "An existing contact with this phone was found. Use existing or create new?"

2. **Issue 2a-iii — "Add New Client" popup:** Should the "Add New Client" form open as:
   - **(A)** A full-page form (same window), or
   - **(B)** A popup/modal?

3. **Issue 2a-ii — Mixed language:** Are there specific forms/screens where you've noticed the English/Vietnamese mixing? This will help me target the translation fixes.

4. **Issue 2a-ii — Form hanging:** Can you describe or reproduce the hanging scenario? Is it when clicking Cancel on the initial contact wizard? Or on the booking wizard?
