# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains healthcare modules for Phòng khám Gia đình Việt Úc (VAFHS) - a comprehensive healthcare management system built on Odoo 17 Community Edition. The system integrates clinical workflows, patient management, accounting, and mobile applications with multilingual support and compliance features.

## Platform & Technology Stack

- **Platform**: Odoo 17 Community Edition
- **Enhancement Strategy**: Open-source libraries and technologies where Odoo capabilities are insufficient
- **Target Markets**: Multi-country deployment with focus on Southeast Asia
- **Compliance**: HIPAA, GDPR, Vietnam Ministry of Health standards
- **Languages**: English, Vietnamese, with extensible multilingual support

## Core Modules to Implement

### Clinical Management
- Patient Relationship Management (PRM)
- Electronic Health Records (EHR) integration via APIs
- Appointment Scheduling & Telemedicine
- Home Health Services with remote monitoring

### Operations
- Field Appointment & Dispatch
- Work Order Management  
- Medical Equipment Maintenance
- Inventory Management

### Financial
- Billing with Vietnam VAT compliance
- Accounting System with multi-currency support
- HR & Payroll management

### Patient Engagement
- Patient Portal with self-service capabilities
- Multilingual Communication (SMS, WhatsApp, Zalo)
- Marketing Automation
- Survey & Feedback collection

### Infrastructure
- Mobile Access with offline functionality
- SLA & Compliance monitoring
- Reporting & Analytics dashboards
- Multicountry Customization Framework

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

## Module Structure

```
addons/
├── vafhs_patient_management/
├── vafhs_appointments/
├── vafhs_billing/
├── vafhs_inventory/
├── vafhs_hr/
├── vafhs_mobile_api/
├── vafhs_multilingual/
├── vafhs_compliance/
└── vafhs_analytics/
```

## Implementation Timeline

Single-phase implementation targeting 3-month completion with focus on:
1. Core clinical workflows
2. Patient engagement features
3. Compliance and security
4. Mobile and multilingual capabilities

## Customization Framework

Built for multicountry deployment with:
- Region-specific compliance configurations
- Dynamic tax and currency handling
- Multilingual interface support
- Cloud infrastructure with multi-region replication