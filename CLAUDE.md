# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains a comprehensive healthcare management system built on Odoo 17 Community Edition. The system integrates clinical workflows, patient management, accounting, and mobile applications with multilingual support and compliance features. Designed for healthcare providers specializing in both clinic-based and home care services.

## MVP (Minimum Viable Product) Focus

The initial implementation follows an MVP approach addressing operational, regulatory, and customer service requirements for healthcare providers specializing in clinic-based and home care services. The MVP streamlines lead capture, automates client bookings, ensures clinical and financial compliance, and enhances staff productivity.

### MVP Priority Areas
1. **Eliminate delays in regulatory invoice submission** - Real-time submission to local Finance/Tax Authorities
2. **Establish reliable source tracking** - Track leads from Facebook, Zalo, website, calls, referrals
3. **Integrate marketing channels** - Automate lead intake from multiple sources
4. **Ensure regulatory compliance** - Local Ministry of Health and tax authority requirements

## Platform & Technology Stack

- **Platform**: Odoo 17 Community Edition
- **Enhancement Strategy**: Open-source libraries and technologies where Odoo capabilities are insufficient
- **Target Markets**: Multi-country deployment with configurable regional compliance
- **Compliance**: HIPAA, GDPR, and local Ministry of Health standards
- **Languages**: Multi-language support with configurable localization

## MVP Core Modules

### 1. CRM & Lead Management Module
- **Multi-channel lead intake**: Website forms, Facebook Messenger, Zalo, Chatbot, VoIP hotline, referrals
- **Zapier integration** for cross-platform lead syncing
- **Auto-contact creation** from inquiries with complete client profiles
- **Contact/client differentiation** with automatic ID generation
- **Client communication history** tracking all interactions
- **Configurable lookup codes** for standardized data entry

### 2. Call Center & VoIP Integration Module
- **VoIP hotline integration** with call logging and contact matching
- **Headset support** for sales/front desk staff
- **Automatic client lookup** on incoming calls
- **New contact creation** for unknown callers
- **Conversation logging** and details capture

### 3. Booking & Scheduling Module
- **Multi-role booking workflow**: Sales staff → Operations Manager → Head Nurse
- **Service location support**: Clinic (<5%), Home visits (≈95%), Telemedicine
- **Comprehensive booking fields**: Type, preferred date/time, duration, travel time, client category
- **Assignment system**: Doctor/Nurse roles with multiple assignments per booking
- **Status tracking**: Scheduled → Booked → Assigned → Started → Finished → Deferred/Cancelled
- **Central calendar** with staff availability and geographic optimization
- **Real-time notifications** to supervisors and clients

### 4. Clinical Management Module
- **Clinical notes recording** by nurses/doctors
- **Prescription capture** and management
- **Regulatory submission** of clinical records and prescriptions (JSON/XML API)
- **Compliance tracking** with local Ministry of Health standards

### 5. Invoicing & Financial Module
- **Auto-draft invoice generation** upon assignment
- **Editable invoices** post-service completion
- **Tax-compliant invoicing** for local tax regulations
- **Direct Tax Authority submission** with real-time processing
- **Multi-facility price lists** support
- **Excel export** for accounting integration

### 6. Integration & Communication Module
- **HR/Attendance system** integration (configurable)
- **Mobile app notifications** for assigned staff
- **Multi-channel client notifications** (SMS, email, in-app)
- **Regulatory API integration** for health authority submissions

### 7. Reporting & Analytics Module
- **Source tracking reports** (Facebook, Zalo, website, calls, referrals)
- **New vs returning client identification**
- **Client flow analytics** and booking patterns
- **Revenue reporting** and invoice submission timelines
- **Performance dashboards** for operational metrics

## Development Commands

Since this is an Odoo-based project, typical commands will include:

```bash
# Odoo development server
python3 odoo-bin -d database_name -i module_name --dev=reload

# Module installation/upgrade
python3 odoo-bin -d database_name -i module_name -u module_name

# Testing
python3 odoo-bin -d test_database --test-enable --stop-after-init

# Linting (when configured)
flake8 addons/custom_modules/
pylint addons/custom_modules/
```

## Architecture

The system follows Odoo's MVC architecture with custom modules extending base functionality:

- **Model Layer**: Custom models extending Odoo's ORM for healthcare entities
- **View Layer**: XML views, QWeb templates, and JavaScript components
- **Controller Layer**: HTTP controllers for API endpoints and custom routes
- **Integration Layer**: APIs for EHR integration and third-party services

## MVP Module Structure

```
addons/
├── health_crm/                   # CRM & Lead Management
├── health_voip/                  # Call Center & VoIP Integration  
├── health_booking/               # Booking & Scheduling
├── health_clinical/              # Clinical Management
├── health_invoicing/             # Invoicing & Financial
├── health_integration/           # Integration & Communication
├── health_reporting/             # Reporting & Analytics
├── health_base/                  # Base configurations & lookup codes
└── health_compliance/            # Regulatory Integration & Compliance
```

### MVP Service Distribution
- **Home visits**: ~95% of services
- **Clinic visits**: <5% of services  
- **Telemedicine**: Zalo/Messenger based
- **Geographic focus**: Configurable by region with multi-language support

## MVP Implementation Timeline

**Target**: 3-month MVP completion with modular rollout:

### Phase 1: Foundation (Month 1)
1. **CRM & Lead Management** - Multi-channel lead intake
2. **VoIP Integration** - Call center functionality  
3. **Base Module** - Lookup codes and configurations

### Phase 2: Core Operations (Month 2)
1. **Booking & Scheduling** - Complete workflow from sales to assignment
2. **Clinical Management** - Notes, prescriptions, basic regulatory compliance
3. **Integration Module** - HR/Attendance and notification systems

### Phase 3: Financial & Compliance (Month 3)
1. **Invoicing Module** - Tax-compliant invoicing and Finance Authority integration
2. **Regulatory Compliance** - Full health authority submission capabilities
3. **Reporting & Analytics** - Source tracking and performance dashboards

### MVP Success Criteria
- ✅ Zero delays in regulatory invoice submission
- ✅ Complete lead source tracking from all channels
- ✅ Automated booking workflow from inquiry to completion
- ✅ Local regulatory compliance (Health Authority + Finance Authority)
- ✅ Mobile-responsive interface for field staff

## MVP Technical Requirements

### Platform & Device Support
- **Backend**: PC access for admin/staff operations
- **Frontend**: Mobile-responsive for nurses/doctors in field
- **Multi-language**: Configurable language interface support

### Integration Requirements
- **Zapier**: Cross-platform lead data synchronization
- **VoIP System**: Hotline integration with call logging
- **HR/Attendance Systems**: Staff attendance and assignment notifications (configurable)
- **Health Authority APIs**: Clinical records and prescription submission (JSON/XML)
- **Tax Authority**: Tax-compliant invoice direct submission
- **External Channels**: Facebook Messenger, Zalo, website forms

### Compliance & Performance
- **Local Tax Authority**: Tax-compliant invoice real-time submission
- **Ministry of Health**: Clinical and prescription data compliance
- **Data Security**: Healthcare data protection standards
- **Real-time Processing**: Eliminate manual delays in critical workflows

### Customization Framework
- **Configurable lookup codes**: Client-provided standardized data entry
- **Multi-facility support**: Different price lists per location
- **Modular architecture**: Independent module deployment and updates
- **Scalable design**: Support for business growth and additional locations