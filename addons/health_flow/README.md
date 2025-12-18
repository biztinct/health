# Health Flow Dashboard

Interactive circular workflow dashboard for Vietnam-Australia Family Health Service healthcare operations.

## Features

### Primary Circles
- **CRM**: Customer relationship management workflows
- **Booking**: Appointment and field service booking management
- **Invoicing**: Billing and accounts receivable
- **Analytics**: BI Dashboard (direct access)
- **Audit**: System audit log (direct access)
- **Admin**: System configuration and settings

### Center Circle
- **Client**: Patient registry access

### Panel Actions

#### CRM Panel
- Search opportunities
- Initial contact leads
- Planned activities
- CRM calendar view

#### Booking Panel
- Booking calendar (visual scheduler)
- Staff assignment & workload
- Draft bookings
- Assigned bookings
- Scheduled bookings

#### Invoicing Panel
- AR Dashboard
- Payment transactions
- Invoices list

#### Admin Panel
- Pricing Engines
- Package Products
- Pricing Rules
- Quick Edit Rules
- Portable Equipment
- Healthcare Facilities
- Patient Categories
- Service Types
- Symptoms
- Referral Sources
- Insurance Providers
- Urgency Levels

## Technical Details

- **Built with**: Odoo 19 OWL Framework
- **Design Pattern**: Circular/radial navigation with slide-in panel
- **Interactions**: Click-based (no hover interactions)
- **Responsive**: Mobile-friendly design
- **Animations**: Smooth transitions and fade-in effects

## Installation

1. Copy the module to your Odoo addons directory
2. Update the apps list
3. Install "Health Flow Dashboard"
4. Access via the "Health Flow" menu item

## Dependencies

- health_base
- health_crm
- health_fieldservice
- health_invoicing
- advanced_pricing

## License

LGPL-3
