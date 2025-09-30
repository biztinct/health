# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains a comprehensive **Patient Interaction and Clinic Management System** built on Odoo 18 Community Edition for **Vietnam-Australia Family Health Service Company Limited (VAFHS)**. The system integrates clinical workflows, patient management, accounting, and mobile applications with multilingual support (Vietnamese & English) and regulatory compliance features.

## Contract Deliverables & Business Requirements

**Contract**: Services Agreement 2025/IADCX/VAFHS-01 between I Am Dream Catcher Ltd and VAFHS/Hibiscus Health Holdings

### Key Deliverables (6-8 Week Implementation)
1. **Fully integrated Patient Interaction and Clinic Management System** for VAFHS Vietnam operations
2. **Core modules**: CRM, Appointment Booking, Assignment & Status Monitoring, Clinical Summary Recording, Invoicing & Accounts Receivable, API Integration, Basic Reporting
3. **Multilingual interface** (Vietnamese & English) optimized for desktop and mobile
4. **Role-based access control** system
5. **Real-time data synchronization** and offline functionality for mobile clinical users

### Critical Business Priorities
1. **Eliminate delays in regulatory invoice submission** - Real-time submission to Vietnamese Tax Authorities
2. **Complete lead source tracking** - Facebook, Zalo, website, calls, referrals with full audit trail
3. **Automated patient interaction workflow** - Lead → Contact → Booking → Assignment → Clinical Notes → Invoicing → MOH Submission
4. **Ministry of Health compliance** - Clinical records and prescription submission (JSON/XML API)
5. **Mobile-first approach** - Field staff (nurses/doctors) require mobile-responsive interface

## UI/UX Design Considerations
- Need to develop the most professional and best-in-class UI design
- Take inspiration from top-tier applications and software tools
- Prioritize mobile-friendly design for Progressive Web Application (PWA)
- Focus on creating a sleek, modern, and intuitive user interface that meets the highest professional standards
- Ensure responsive design that works seamlessly across different devices and screen sizes

## Development Guidelines
- Do not make any changes, until you have 95% confidence that you know what to build ask me follow up questions until you have that confidence
- When you do any modification in the code, think well and follow the established design principles of inheritance etc. Then inform me of what you are going to do before proceeding

## Module Architecture & Inheritance Design

**CRITICAL: Always inherit from health_base models - NEVER duplicate**

### Base Module Structure
```
health_base/          # Foundation module - core healthcare models
├── health.patient    # Base patient model with all standard fields
├── health.facility   # Healthcare facilities/clinics
├── health.service.type # Base service types with pricing, duration, etc.
└── res.partner       # Extended partner functionality
```

### Extension Module Pattern
```
health_calendar/      # Appointment booking functionality
├── health.patient    # _inherit = 'health.patient' (add appointment_ids only)
├── health.appointment.type # _inherit = 'health.service.type' (add booking config only)
├── health.appointment # New model for appointments
└── booking controllers/views
```

### Inheritance Rules
1. **Always check health_base first** - If a model exists there, inherit from it
2. **Never duplicate fields** - Base models have comprehensive field sets
3. **Only add domain-specific fields** - Calendar adds booking, Clinical adds medical records
4. **Maintain dependency chain** - All health_* modules depend on health_base
5. **Use _inherit for extensions** - Never create duplicate _name models

### Field Inheritance Examples
```python
# ❌ WRONG - Duplicating base model
class HealthPatient(models.Model):
    _name = 'health.patient'  # This already exists in health_base!
    name = fields.Char(...)   # Duplicating base fields

# ✅ CORRECT - Extending base model
class HealthPatient(models.Model):
    _inherit = 'health.patient'  # Extend existing model
    appointment_ids = fields.One2many(...)  # Add domain-specific fields only
```

This prevents field conflicts, reduces code duplication, and maintains consistent data models across all healthcare modules.

## Scalability Considerations
- The application will scale later as it will be installed in other countries as well. So keep that in design (e.g., currency, internationalization)

## Odoo 18 Development Notes & Critical Learnings

### XML File Structure Requirements
**CRITICAL**: Odoo 18 has very strict XML schema validation requirements. Use these exact patterns:

#### For Data Files (demo data, sequences, etc.):
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="record_id" model="model.name">
        <field name="field_name">value</field>
    </record>
</odoo>
```

#### For View Files (forms, lists, etc.):
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="view_id" model="ir.ui.view">
        <field name="name">view.name</field>
        <field name="model">model.name</field>
        <field name="arch" type="xml">
            <form>...</form>
        </field>
    </record>

</odoo>
```

#### For Security Files:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="category_id" model="ir.module.category">
        <field name="name">Category Name</field>
        <field name="description" />
        <field name="sequence">20</field>
    </record>

</odoo>
```

### Key XML Requirements
1. **NO `<data>` wrapper tags** - Use direct `<odoo>` structure
2. **Empty line after `<odoo>`** for security/data files
3. **Required fields**: `ir.module.category` MUST have `name` field
4. **Self-closing tags**: Use `<field name="description" />` pattern when appropriate
5. **View types**: Use `list` not `tree` in Odoo 18
6. **Indentation**: Match official Odoo project module patterns exactly
7. **XML Entity Escaping**: MANDATORY for all special characters in string attributes

### XML Entity Escaping Rules (CRITICAL - REPEATED MISTAKE)
**ALWAYS escape these characters in XML string attributes:**
```xml
<!-- ❌ WRONG - Causes xmlParseEntityRef errors -->
<page string="Location & Travel">
<page string="Terms & Conditions">
<filter domain="[('date', '>', 'value')]">

<!-- ✅ CORRECT - Properly escaped -->
<page string="Location &amp; Travel">
<page string="Terms &amp; Conditions">
<filter domain="[('date', '&gt;', 'value')]">
```

**Required XML Entities:**
- `&` → `&amp;`
- `<` → `&lt;`
- `>` → `&gt;`
- `"` → `&quot;` (in attributes)
- `'` → `&apos;` (in attributes)

### Debugging XML Issues
- **Schema validation errors**: Check XML structure matches patterns above
- **Database constraint violations**: Ensure all required fields are present
- **Add files incrementally**: Test one XML file at a time to isolate issues
- **Reference working modules**: Always check official Odoo modules (like `project`) for correct patterns

### Common Mistakes to Avoid
- ❌ Using `<data>` wrapper tags in regular XML files
- ❌ Missing `name` field in `ir.module.category` records
- ❌ **CRITICAL: Using `tree` instead of `list` for view types in Odoo 18** - ALWAYS use `list` for list views and `'list'` in view_mode fields
- ❌ **CRITICAL: Using `'tree'` in ir.actions.act_window view_ids** - ALWAYS use `{'view_mode': 'list'}` not `{'view_mode': 'tree'}`
- ❌ Incorrect indentation or formatting
- ❌ Adding all XML files at once without incremental testing
- ❌ Including menu items in view files (causes schema validation errors)
- ❌ **CRITICAL: Unescaped ampersands in XML strings** - ALWAYS use `&amp;` instead of `&`
- ❌ **CRITICAL: Wrong chatter pattern** - Use `<chatter reload_on_follower="True"/>` outside `</sheet>`, NOT `<div class="oe_chatter">`
- ❌ **CRITICAL: Fields pushed to left** - Use proper `<group><group>` nesting pattern from project module
- ❌ Custom CSS classes that interfere with Odoo's responsive layout system

### Proper Odoo 18 Form Structure (Based on Project Module Analysis)
**CRITICAL PATTERN** - Follow this exact structure to avoid layout issues:
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

### Field Definition Requirements
When creating views that reference model fields, ensure all fields exist in the model:
- **Many2one fields**: Use `Many2one('target.model', string='Field Name')`
- **Monetary fields**: Use `Monetary('Field Name', currency_field='currency_id')`
- **Computed fields**: Include proper `@api.depends()` and compute methods
- **Action methods**: Must be defined in the model for button calls in views
- **Related fields**: Don't include selection/domain attributes (inherited from source field)
- **Create methods**: Use `@api.model_create_multi` for batch operations in Odoo 18

### Successful Module Structure
The health_calendar module now follows this working pattern:
1. **Models**: Complete field definitions with all referenced fields
2. **Security**: Minimal working security with proper XML structure
3. **Data**: Demo data with `noupdate="1"` pattern
4. **Views**: Separated from menu items to avoid validation errors
5. **Menus**: In separate file to prevent schema conflicts

## Memory Notes
- Note to take care that the model is not defined again as duplicate
- **CRITICAL: NO FIELDSERVICE MODULE INHERITANCE** - Do NOT inherit from any fieldservice modules (fsm.order, fsm.team, etc.) as fieldservice modules are NOT installed. Only use for inspiration, never inheritance.
- Follow odoo 18 standards and remember that attrs and states attributes are no longer used

## Debugging Guidelines

### Critical: Check for Duplicate Methods Across Modules
**ALWAYS verify that the same method is not defined in multiple modules when debugging action issues.**

#### Common Issue Pattern:
```python
# ❌ PROBLEM: Same method in multiple modules
# advanced_pricing/models/sale_order.py
def action_save_and_return_to_fso(self):
    # Version A implementation

# health_fieldservice/models/sale_order.py
def action_save_and_return_to_fso(self):
    # Version B implementation
```

#### Debugging Steps for Action/Button Issues:
1. **Search all modules** for the method name:
   ```bash
   grep -r "def method_name" addons/*/models/
   ```

2. **Check inheritance chain** - Later loaded modules override earlier ones

3. **Verify single method definition** - Only one module should define the method

4. **Use module dependencies** - Method should be in the module that owns the functionality

#### Resolution Strategy:
- **Keep method in primary module** (where the functionality belongs)
- **Remove duplicate methods** from other modules
- **Use proper inheritance** if method needs to be extended
- **Add debug logging** to verify which method executes

#### Example Fix:
```python
# ✅ CORRECT: Single method definition
# health_fieldservice/models/sale_order.py (PRIMARY MODULE)
def action_save_and_return_to_fso(self):
    """Save quote and return to FSO - PRIMARY IMPLEMENTATION"""
    # Implementation here

# advanced_pricing/models/sale_order.py (REMOVE DUPLICATE)
# Method removed - no longer defined here
```

This prevents action conflicts and ensures predictable behavior.

## Reference Documentation

For detailed implementation guides and reference materials, see:
- **CLAUDE_REFERENCE.md** - Complete module implementation guides (Healthcare Relationship Management, Timeline View, Biz Analytics, Health PWA)
- Contains full API documentation, data models, component architecture, and deployment guides
- Use when you need specific technical details about implemented modules
