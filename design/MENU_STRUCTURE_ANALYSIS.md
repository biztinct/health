# Healthcare System Menu Structure & Action Definitions Analysis

## Current Menu Architecture

### 1. Root Menu Level
**File:** `/Users/adity/Documents/GitHub/health-1/addons/health_landing/views/landing_menus.xml`

```xml
<!-- Home Menu Item - Primary Entry Point -->
<menuitem id="menu_health_landing_home"
          name="Home"
          sequence="1"
          action="action_health_landing_dashboard"
          web_icon="health_landing,static/description/icon.png"
          groups="health_base.group_healthcare_base,health_base.group_healthcare_receptionist,..."/>
```

**Key Points:**
- Uses `action="action_health_landing_dashboard"` to link to a client action
- Web icon served from health_landing module
- Visible to all healthcare groups
- Sequence 1 places it at the top of the menu

### 2. Healthcare Root Menu
**File:** `/Users/adity/Documents/GitHub/health-1/addons/health_base/views/health_menus.xml`

```xml
<!-- Main Healthcare Menu -->
<menuitem id="menu_healthcare_root" 
          name="Healthcare" 
          sequence="5"
          web_icon="health_base,static/description/icon.png"
          groups="group_healthcare_base,..."/>
```

**Menu Hierarchy Structure:**
```
Healthcare (sequence 5)
├── Patient Management (sequence 10)
│   └── Patient Registry (action_health_patient)
├── Clinical Intelligence (sequence 20)
│   ├── Clinical Protocols
│   ├── Medication Safety
│   └── Risk Assessment
├── Service Packages (sequence 25)
├── Billing & Invoicing (sequence 26)
├── Facilities (sequence 30)
│   └── Healthcare Facilities (action_health_facility)
└── Configuration (sequence 40)
    ├── Patient Categories (action_health_patient_category)
    ├── Service Types (action_health_service_type)
    ├── Medical Specialties (action_health_medical_specialty)
    ├── Symptoms (action_health_symptom)
    ├── Referral Sources (action_health_referral_source)
    ├── Insurance Providers (action_health_insurance_provider)
    ├── Urgency Levels (action_health_urgency_level)
    └── Vietnamese Districts (action_health_vietnamese_district)
```

## Action Definitions

### 1. Healthcare Landing Dashboard Action
**File:** `/Users/adity/Documents/GitHub/health-1/addons/health_landing/views/landing_dashboard_views.xml`

```xml
<record id="action_health_landing_dashboard" model="ir.actions.client">
    <field name="name">Healthcare Dashboard</field>
    <field name="tag">health_landing_dashboard</field>
    <field name="target">fullscreen</field>
</record>
```

**Action Type:** `ir.actions.client` (client-side action)
- Uses tag: `health_landing_dashboard`
- Renders in fullscreen mode
- Implemented in JavaScript

### 2. FSO Dashboard Action (Hub-and-Spoke Pattern)
**File:** Button defined in `/Users/adity/Documents/GitHub/health-1/addons/health_landing/views/fso_dashboard_button.xml`
**Implementation:** `/Users/adity/Documents/GitHub/health-1/addons/health_landing/models/health_fieldservice_order.py`

```python
def action_open_fso_dashboard(self):
    """Open FSO Hub-and-Spoke Dashboard"""
    self.ensure_one()
    return {
        'type': 'ir.actions.client',
        'tag': 'health_landing.fso_hub_spoke_action',
        'params': {
            'fso_id': self.id,
            'fso_name': self.name,
        }
    }
```

**Button XPath Location:**
```xml
<record id="view_health_fieldservice_order_form_dashboard_button" model="ir.ui.view">
    <field name="name">health.fieldservice.order.form.dashboard.button</field>
    <field name="model">health.fieldservice.order</field>
    <field name="inherit_id" ref="health_fieldservice.view_health_fieldservice_order_form"/>
    <field name="arch" type="xml">
        <xpath expr="//div[@name='button_box']" position="inside">
            <button name="action_open_fso_dashboard"
                    type="object"
                    class="oe_stat_button"
                    icon="fa-tachometer"
                    string="Dashboard"
                    help="Open FSO Workflow Dashboard"/>
        </xpath>
    </field>
</record>
```

**Client Action Registration:**
**File:** `/Users/adity/Documents/GitHub/health-1/addons/health_landing/static/src/js/fso_hub_action.js`

```javascript
// Register the client action
registry.category("actions").add("health_landing.fso_hub_spoke_action", FSOHubSpokeAction);
```

**Action Template:**
**File:** `/Users/adity/Documents/GitHub/health-1/addons/health_landing/static/src/xml/fso_hub_action.xml`

```xml
<t t-name="health_landing.FSOHubSpokeActionTemplate">
    <div class="o_action">
        <FSOHubSpokeWidget
            fsoId="state.fsoId"
            fsoName="state.fsoName"
            onBack="() => this.onBack()"
        />
    </div>
</t>
```

## FSO Hub-and-Spoke Dashboard Structure

### Widget Architecture
**File:** `/Users/adity/Documents/GitHub/health-1/addons/health_landing/static/src/js/fso_hub_spoke_widget.js`

The FSO dashboard uses a flowchart layout with:

1. **Node Types:**
   - Stage Indicators (Stage nodes): Draft, Booked, Assigned, In Progress, Completed
   - Action Indicators (Oval/action nodes): Confirm Booking
   - Info Nodes (Rectangles): Service Packages, Quote, Equipment, Staff Assignment, Clinical Notes, Invoice, Payment tracking

2. **Node Properties:**
   ```javascript
   {
       id: "node_id",
       label: "Node Label",
       icon: "fa-icon-name",
       color: "#HexColor",
       lightColor: "#LightHexColor",
       type: "action|info|stage",
       shape: "rect|oval|circle",
       x: 120,  // X position in SVG
       y: 40,   // Y position in SVG
       width: 140,   // For rect
       height: 60,   // For rect
       radius: 55,   // For oval
       actionField: "field_name",  // FSO field to link
       description: "Help text"
   }
   ```

3. **FSO Spoke Nodes Defined:**
   - Service Packages (top-left)
   - Quote (top-middle)
   - Confirm Booking (top-right oval)
   - Equipment (left-middle)
   - Booking Hub (center)
   - Staff Assignment (right-middle)
   - Start Service (below hub)
   - Clinical Notes (bottom-left)
   - Invoice (bottom-middle)
   - Pay Now (bottom-right-upper)
   - Pay Later (bottom-right-upper)
   - Collect Cash (bottom-right sub)
   - Payment Received (bottom-right sub)
   - Completed (bottom-far-right)

### Dynamic Indicators
The FSO model computes which arrows/spokes should "blink" (show as active):

```python
show_draft_indicator = (state == 'draft')
show_booked_indicator = (state == 'confirmed')
show_assigned_indicator = (state == 'assigned')
show_in_progress_indicator = (state == 'in_progress')
show_completed_indicator = (state in ['completed', 'completed_pending_invoice', 'closed'])

show_clinical_notes_arrow = (state == 'in_progress' or (...and not clinical_notes_submitted))
show_invoice_arrow = (clinical_notes_submitted and not invoice_submitted)
show_pay_now_arrow = (state == 'in_progress' and clinical_notes_submitted and (invoice_submitted or sale_order_id))
show_pay_later_arrow = (state == 'in_progress' and clinical_notes_submitted and (invoice_submitted or sale_order_id))
show_collect_cash_arrow = (payment_method == 'cash' and cash_collected_by_nurse and not cash_received_by_om)
show_payment_received_arrow = (payment_method == 'pay_later' and not payment_received_date)
```

## Appointment/Booking Structure

### Location: Appointments are in health_fieldservice module

**File:** `/Users/adity/Documents/GitHub/health-1/addons/health_fieldservice/models/health_appointment.py`

**Base Model:** `health.appointment` in health_fieldservice

**Base Views Referenced (Expected in health_calendar module - being created):**
- `health_calendar.health_appointment_view_form`
- `health_calendar.health_appointment_view_list`
- `health_calendar.health_appointment_view_search`

### Appointment Form View Inheritance Pattern
**File:** `/Users/adity/Documents/GitHub/health-1/addons/health_fieldservice/views/health_appointment_views.xml`

The form structure expected:
```xml
<form string="Appointment Name">
    <header>
        <field name="state" widget="statusbar"/>
    </header>
    <sheet>
        <group name="appointment_details">
            <!-- Core appointment fields -->
        </group>
        
        <group name="location_staff">
            <!-- Location and staff fields -->
        </group>
        
        <notebook>
            <!-- Tabbed content -->
        </notebook>
    </sheet>
    <chatter reload_on_follower="True"/>
</form>
```

### Key XPath Locations Used in Inheritance:
- `//header/field[@name='state']` - Add buttons before state
- `//group[@name='appointment_details']` - Add staff assignment after
- `//field[@name='urgency_level']` - Add assignment priority after
- `//group[@name='location_staff']` - Add realtime status after
- `//notebook` - Add tabs inside

### Appointment Assignment Workflow States
```python
assignment_state in [
    'draft',
    'sales_review',
    'ops_manager_review',
    'head_nurse_assign',
    'staff_assigned',
    'staff_confirmed',
    'ready'
]
```

## Landing Dashboard Navigation Pattern

### JavaScript Components
**File:** `/Users/adity/Documents/GitHub/health-1/addons/health_landing/static/src/js/landing_dashboard.js`

The landing dashboard uses a module-based navigation system:
```javascript
this.modules = [
    {
        id: "patient",
        name: "Patient Management",
        icon: "fa-users",
        description: "Manage patient records and information",
        class: "module-patient",
        submenus: [
            {
                name: "Client",
                icon: "fa-user-circle",
                action: "hub_spoke",  // Special action type
                description: "View patient hub-and-spoke dashboard"
            },
        ],
    },
    // ... more modules
]
```

### Navigation Flow
1. **Home Dashboard** - Click on "Home" menu
   - Shows module cards (Patient, Scheduling, CRM, etc.)
   
2. **Submenu Dashboard** - Click on module card
   - Shows submenu actions for that module
   
3. **Action Window** - Click on submenu action
   - Executes ir.actions.act_window or client action
   - Special "hub_spoke" actions render hub-and-spoke widgets

### Navigation States:
```javascript
this.state = useState({
    currentView: "main",      // "main", "submenu", "hub_spoke", or "modal"
    currentModule: null,
    modalModule: null,
    selectedPatientId: null,
    selectedPatientName: null,
    selectedSpoke: null,
    breadcrumb: ["Home"],
});
```

## Action Types Used

### 1. Client Actions (`ir.actions.client`)
```xml
<record id="action_id" model="ir.actions.client">
    <field name="name">Action Name</field>
    <field name="tag">module_name.action_tag</field>
    <field name="target">fullscreen|new|current</field>
    <!-- Optional: params field for passing data -->
</record>
```

**Registered in JavaScript:**
```javascript
registry.category("actions").add("module_name.action_tag", ComponentClass);
```

### 2. Window Actions (`ir.actions.act_window`)
```xml
<record id="action_id" model="ir.actions.act_window">
    <field name="name">Action Name</field>
    <field name="res_model">model.name</field>
    <field name="view_mode">form,list,kanban</field>
    <field name="view_id" ref="view_id"/>
    <field name="target">current|new|fullscreen</field>
    <field name="context">{...}</field>
    <field name="domain">[...]</field>
</record>
```

### 3. Python Method Actions
```python
def action_method(self):
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'model.name',
        'view_mode': 'form',
        'view_id': view_id,
        'target': 'new',
        'res_id': record_id,
        'context': {...}
    }
    
    # OR for client actions:
    return {
        'type': 'ir.actions.client',
        'tag': 'module.action_tag',
        'target': 'fullscreen',
        'params': {'key': 'value'}
    }
```

## Form View Patterns

### Standard Form Structure (from health_fieldservice FSO form)
```xml
<form string="Record Name" class="o_form_record_class">
    <header>
        <field name="state" widget="statusbar"/>
        <!-- Action buttons -->
    </header>
    <sheet string="Record">
        <div class="oe_button_box" name="button_box" groups="base.group_user">
            <!-- Smart buttons -->
        </div>
        <div class="oe_title">
            <h1 class="d-flex justify-content-between align-items-center">
                <field name="name" class="o_text_overflow"/>
            </h1>
        </div>
        <group>
            <group string="Left Column">
                <!-- Left fields -->
            </group>
            <group string="Right Column">
                <!-- Right fields -->
            </group>
        </group>
        <notebook>
            <!-- Tabbed content -->
        </notebook>
    </sheet>
    <chatter reload_on_follower="True"/>
</form>
```

### Button in Smart Button Box
```xml
<button name="action_open_fso_dashboard"
        type="object"
        class="oe_stat_button"
        icon="fa-tachometer"
        string="Dashboard"
        help="Open FSO Workflow Dashboard"/>
```

## Menu Access Group Patterns

**Files:** `/Users/adity/Documents/GitHub/health-1/addons/health_base/views/health_menus.xml`

Groups referenced:
- `group_healthcare_base` - Base healthcare access
- `group_healthcare_receptionist` - Front desk staff
- `group_healthcare_nurse` - Nursing staff
- `group_healthcare_head_nurse` - Nurse supervisors
- `group_healthcare_doctor` - Physicians
- `group_healthcare_manager` - Healthcare managers
- `group_healthcare_admin` - System administrators
- `group_healthcare_owner` - Company owners
- `group_healthcare_operations_manager` - Operations managers

## Summary of Key Patterns

### Menu Structure Pattern
```
Root Menu Item
└── action="action_id" (links to ir.actions.client or ir.actions.act_window)
    └── Which calls JavaScript component or opens view

Parent Menu
└── Child Menu Item
    └── action="action_id"
```

### Action Registration Pattern
```
1. Define action in XML (ir.actions.client or ir.actions.act_window)
2. Register JavaScript component (for client actions):
   registry.category("actions").add("module.tag", ComponentClass)
3. Define component template
4. Component renders the UI
```

### Dashboard Navigation Pattern
```
Dashboard Home (fullscreen client action)
└── Modules (cards)
    └── Submenus (action items)
        └── Actions (windows or client actions)
            └── Special: hub_spoke type renders custom widget
```

### FSO Dashboard Pattern (Hub-and-Spoke)
```
Button in FSO Form
└── Calls action_open_fso_dashboard method
    └── Returns ir.actions.client with tag='health_landing.fso_hub_spoke_action'
        └── JavaScript component loads FSO data
            └── Renders SVG flowchart with interactive nodes
                └── Nodes trigger wizard dialogs on click
```

