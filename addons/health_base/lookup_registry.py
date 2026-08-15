# -*- coding: utf-8 -*-
"""The Tier-1 dropdown vocabularies, and where each one is used.

This file is the single source of truth for the Selection -> Many2one
conversion. Everything reads it rather than repeating itself:

  * health_base seeds `health.lookup.category` / `health.lookup.value`
    from CATEGORIES (idempotently, on install and on upgrade);
  * each owning module back-fills its own columns from CONVERSIONS via
    `backfill_lookup_field` in lookup_migration.py;
  * the xlsx template generator makes one sheet per category;
  * the tests iterate both lists, so a new vocabulary is covered the
    moment it is declared here.

The English labels and codes were captured from the live Selection
definitions before they were removed, so no wording changed in the
conversion. The Vietnamese labels that already existed (the handful of
callable selections that went through env._()) came across with them;
the rest are blank for the client to fill in through the EN/VI globe.

CODES ARE A CONTRACT. They are what a re-import matches on and what any
future Tier-2 conversion will compare against (`rec.field_id.code ==`).
Never rename one — add a new value and archive the old.
"""

# category code -> {name, values: [(code, en, vi)]}
CATEGORIES = {
    "body_position": {
        "name": "Body Position",
        "used_by": ["health.observation.body_position"],
        "values": [
            ("sitting", "Sitting", ""),
            ("standing", "Standing", ""),
            ("lying", "Lying", ""),
            ("unknown", "Unknown", ""),
        ],
    },
    "cancellation_reason_type": {
        "name": "Cancellation Reason Type",
        "used_by": ["health.booking.cancellation.reason.reason_type"],
        "values": [
            ("patient", "Patient-initiated", ""),
            ("provider", "Provider-initiated", ""),
            ("system", "System/Technical", ""),
            ("emergency", "Emergency/Force Majeure", ""),
        ],
    },
    "careplan_category": {
        "name": "Care Plan Category",
        "used_by": ["health.careplan.category"],
        "values": [
            ("home_care", "Home Care", ""),
            ("post_acute", "Post-Acute", ""),
            ("chronic", "Chronic Disease", ""),
            ("palliative", "Palliative", ""),
            ("rehabilitation", "Rehabilitation", ""),
            ("other", "Other", ""),
        ],
    },
    "contact_reason_category": {
        "name": "Contact Reason Category",
        "used_by": ["health.contact.reason.category"],
        "values": [
            ("sales", "Sales Inquiry", ""),
            ("om", "Operations Management", ""),
            ("support", "Customer Support", ""),
            ("emergency", "Emergency Contact", ""),
            ("follow_up", "Follow-up Contact", ""),
            ("other", "Other", ""),
        ],
    },
    "equipment_power_source": {
        "name": "Equipment Power Source",
        "used_by": ["health.portable.equipment.power_source"],
        "values": [
            ("battery", "Battery Powered", ""),
            ("mains", "Mains Power", ""),
            ("both", "Battery + Mains", ""),
            ("manual", "Manual Operation", ""),
            ("none", "No Power Required", ""),
        ],
    },
    "equipment_type": {
        "name": "Equipment Type",
        "used_by": ["health.portable.equipment.equipment_type"],
        "values": [
            ("diagnostic", "Diagnostic Equipment", ""),
            ("therapeutic", "Therapeutic Equipment", ""),
            ("monitoring", "Monitoring Equipment", ""),
            ("safety", "Safety Equipment", ""),
            ("supplies", "Medical Supplies", ""),
            ("documentation", "Documentation Equipment", ""),
        ],
    },
    "facility_type": {
        "name": "Facility Type",
        "used_by": ["health.facility.facility_type"],
        "values": [
            ("main_clinic", "Main Clinic", ""),
            ("branch_clinic", "Branch Clinic", ""),
            ("home_care_center", "Home Care Center", ""),
            ("telemedicine_center", "Telemedicine Center", ""),
            ("mobile_unit", "Mobile Unit", ""),
            ("partner_clinic", "Partner Clinic", ""),
        ],
    },
    "form_template_category": {
        "name": "Form Template Category",
        "used_by": ["health.form.template.category"],
        "values": [
            ("assessment", "Assessment", ""),
            ("screening", "Screening", ""),
            ("intake", "Intake", ""),
            ("outcome", "Outcome Measure", ""),
            ("other", "Other", ""),
        ],
    },
    "gender": {
        "name": "Gender",
        "used_by": ["res.partner.gender", "crm.lead.gender"],
        # Codes are the FHIR AdministrativeGender values plus the legacy
        # `prefer_not_to_say`, which health_fhir_core maps to "unknown".
        # DO NOT rename them: the PWA, the public /api/v1 payloads and the
        # FHIR Patient facade all emit `gender_code` verbatim.
        "values": [
            ("male", "Male", "Nam"),
            ("female", "Female", "Nữ"),
            ("other", "Other", "Khác"),
            ("prefer_not_to_say", "Unspecified", "Không xác định"),
        ],
    },
    "incident_outcome": {
        "name": "Incident Outcome",
        "used_by": ["health.incident.outcome"],
        "values": [
            ("no_harm", "No Harm", ""),
            ("minor_harm", "Minor Harm", ""),
            ("moderate_harm", "Moderate Harm", ""),
            ("severe_harm", "Severe Harm", ""),
            ("death", "Death", ""),
        ],
    },
    "lead_reason_applies_to": {
        "name": "Lead Reason Applies To",
        "used_by": ["health.lead.reason.lead_type"],
        "values": [
            ("lead", "Lead", ""),
            ("opportunity", "Opportunity", ""),
            ("both", "Both", ""),
        ],
    },
    "lead_reason_category": {
        "name": "Lead Reason Category",
        "used_by": ["health.lead.reason.category"],
        "values": [
            ("service_interest", "Service Interest", ""),
            ("referral", "Referral", ""),
            ("marketing", "Marketing Campaign", ""),
            ("website", "Website Inquiry", ""),
            ("social_media", "Social Media", ""),
            ("event", "Health Event/Fair", ""),
            ("emergency", "Emergency Need", ""),
            ("follow_up", "Follow-up Opportunity", ""),
            ("other", "Other", ""),
        ],
    },
    "medication_form": {
        "name": "Dosage Form",
        "used_by": ["health.medication.form"],
        "values": [
            ("tablet", "Tablet", ""),
            ("capsule", "Capsule", ""),
            ("liquid", "Liquid/Syrup", ""),
            ("injection", "Injection", ""),
            ("patch", "Patch", ""),
            ("cream", "Cream/Ointment", ""),
            ("inhaler", "Inhaler", ""),
            ("drops", "Drops", ""),
            ("suppository", "Suppository", ""),
            ("other", "Other", ""),
        ],
    },
    "monitor_device_type": {
        "name": "Monitoring Device Type",
        "used_by": ["health.monitor.device.device_type"],
        "values": [
            ("bp_monitor", "Blood-pressure monitor", ""),
            ("pulse_oximeter", "Pulse oximeter", ""),
            ("thermometer", "Thermometer", ""),
            ("glucometer", "Glucometer", ""),
            ("scale", "Weighing scale", ""),
            ("wearable", "Wearable", ""),
            ("other", "Other", ""),
        ],
    },
    "package_service_type": {
        "name": "Package Service Type",
        "used_by": ["product.template.healthcare_package_type"],
        "values": [
            ("physiotherapy", "Physiotherapy", ""),
            ("blood_pressure_monitoring", "Blood Pressure Monitoring", ""),
            ("diabetes_management", "Diabetes Management", ""),
            ("home_visit", "Home Visit", ""),
            ("clinic_visit", "Clinic Visit", ""),
            ("consultation", "Consultation", ""),
            ("emergency", "Emergency Care", ""),
            ("follow_up", "Follow-up Care", ""),
            ("preventive", "Preventive Care", ""),
            ("rehabilitation", "Rehabilitation", ""),
            ("vaccination", "Vaccination", ""),
            ("diagnostic", "Diagnostic Services", ""),
            ("other", "Other Service", ""),
        ],
    },
    "preferred_shift": {
        "name": "Preferred Shift",
        "used_by": ["hr.employee.preferred_shift"],
        "values": [
            ("morning", "Morning Shift", ""),
            ("afternoon", "Afternoon Shift", ""),
            ("evening", "Evening Shift", ""),
            ("night", "Night Shift", ""),
            ("flexible", "Flexible", ""),
        ],
    },
    "referral_source_type": {
        "name": "Referral Source Type",
        "used_by": ["health.referral.source.source_type"],
        "values": [
            ("facebook", "Facebook", ""),
            ("zalo", "Zalo", ""),
            ("website", "Website", ""),
            ("google", "Google", ""),
            ("doctor", "Doctor Referral", ""),
            ("hospital", "Hospital Referral", ""),
            ("friend", "Friend/Family", ""),
            ("advertisement", "Advertisement", ""),
            ("other", "Other", ""),
        ],
    },
    "service_interest": {
        "name": "Service Interest",
        "used_by": ["crm.lead.service_interest"],
        "values": [
            ("consultation", "Medical Examination", "Bác sĩ khám"),
            ("wound_care", "Wound Care", "Chăm sóc vết thương"),
            ("injection", "Injection", "Tiêm"),
            ("iv_infusion", "IV Infusion", "Truyền"),
            ("catheter", "Catheter Insertion/Removal", "Đặt, rút sonde"),
            ("sputum_care", "Sputum Suction, Chest Percussion", "Hút đờm, vỗ rung đờm"),
            ("enema", "Enema", "Thụt tháo"),
            ("palliative", "Palliative Care", "Chăm sóc giảm nhẹ"),
            ("personal_care", "Personal Care", "Chăm sóc cá nhân"),
            ("lab_test", "Laboratory Testing", "Xét nghiệm"),
            ("imaging_procedures", "Imaging & Procedures", "Ảnh y tế & Thủ thuật"),
            ("nursing_other", "Nursing Other", "Điều dưỡng Khác"),
            ("other", "Other", "Khác"),
            # Present in live crm.lead data but never declared in the old
            # Selection — the back-fill surfaced 2 codes it could not map, and
            # dropping them would have silently blanked those leads.
            ("home_visit", "Home Visit", "Khám tại nhà"),
            ("clinic_visit", "Clinic Visit", "Khám tại phòng khám"),
        ],
    },
    "service_location": {
        "name": "Service Location",
        "used_by": ["product.template.healthcare_service_location"],
        "values": [
            ("home", "Patient Home", ""),
            ("clinic", "Clinic Visit", ""),
            ("remote", "Remote/Telemedicine", ""),
            ("flexible", "Flexible Location", ""),
            ("hospital", "Hospital", ""),
            ("care_facility", "Care Facility", ""),
        ],
    },
    "staff_skill_category": {
        "name": "Staff Skill Category",
        "used_by": ["health.staff.skill.skill_category"],
        "values": [
            ("medical", "Medical", ""),
            ("nursing", "Nursing", ""),
            ("technical", "Technical", ""),
            ("administrative", "Administrative", ""),
            ("emergency", "Emergency Response", ""),
        ],
    },
    "symptom_category": {
        "name": "Symptom Category",
        "used_by": ["health.symptom.category"],
        "values": [
            ("general", "General", ""),
            ("pain", "Pain & Discomfort", ""),
            ("respiratory", "Respiratory", ""),
            ("cardiovascular", "Cardiovascular", ""),
            ("digestive", "Digestive", ""),
            ("neurological", "Neurological", ""),
            ("skin", "Skin & Dermatological", ""),
            ("musculoskeletal", "Musculoskeletal", ""),
            ("mental_health", "Mental Health", ""),
            ("other", "Other", ""),
        ],
    },
    "task_not_done_reason": {
        "name": "Task Not-Done Reason",
        "used_by": ["health.careplan.task.not_done_reason"],
        "values": [
            ("client_refused", "Client Refused", ""),
            ("client_unavailable", "Client Unavailable/Asleep", ""),
            ("clinical_judgement", "Withheld — Clinical Judgement", ""),
            ("no_supplies", "Missing Supplies/Equipment", ""),
            ("out_of_time", "Ran Out of Time", ""),
            ("other", "Other", ""),
        ],
    },
    "travel_zone": {
        "name": "Travel Zone",
        "used_by": ["health.vietnamese.district.travel_zone"],
        "values": [
            ("zone_1", "Zone 1 (Inner City)", ""),
            ("zone_2", "Zone 2 (Suburban)", ""),
            ("zone_3", "Zone 3 (Outer Areas)", ""),
        ],
    },
    "vn_region": {
        "name": "Vietnam Region",
        "used_by": ["health.province.region", "health.vietnamese.district.region"],
        "values": [
            ("north", "Northern Vietnam", ""),
            ("central", "Central Vietnam", ""),
            ("south", "Southern Vietnam", ""),
        ],
    },
    "consent_type": {
        "name": "Consent Type",
        "used_by": ["health.consent.consent_type"],
        "values": [
            ("service", "Service Delivery", ""),
            ("data_sharing", "Data Sharing", ""),
            ("photography", "Photography/Media", ""),
            ("emergency_treatment", "Emergency Treatment", ""),
            ("marketing", "Marketing Communications", ""),
        ],
    },
    "employment_type": {
        "name": "Employment Type",
        "used_by": ["hr.employee.employment_type"],
        "values": [
            ("full_time", "Full-Time Staff", ""),
            ("part_time", "Part-Time Staff", ""),
            ("casual", "Casual/Contract", ""),
        ],
    },
    "holiday_type": {
        "name": "Holiday Type",
        "used_by": ["advanced.pricing.rule.holiday_type", "resource.calendar.leaves.holiday_type"],
        "values": [
            ("national", "National Holiday", ""),
            ("tet", "TET Holiday", ""),
            ("regional", "Regional Holiday", ""),
            ("observance", "Observance", ""),
        ],
    },
    "infection_control_level": {
        "name": "Infection Control Level",
        "used_by": ["health.clinical.protocol.infection_control_level"],
        "values": [
            ("standard", "Standard Precautions", ""),
            ("contact", "Contact Precautions", ""),
            ("droplet", "Droplet Precautions", ""),
            ("airborne", "Airborne Precautions", ""),
            ("enhanced", "Enhanced Precautions", ""),
        ],
    },
    "medication_route": {
        "name": "Medication Route",
        "used_by": ["health.medication.order.route"],
        "values": [
            ("oral", "Oral", ""),
            ("sublingual", "Sublingual", ""),
            ("topical", "Topical", ""),
            ("subcutaneous", "Subcutaneous", ""),
            ("intramuscular", "Intramuscular", ""),
            ("intravenous", "Intravenous", ""),
            ("inhalation", "Inhalation", ""),
            ("rectal", "Rectal", ""),
            ("ophthalmic", "Ophthalmic", ""),
            ("otic", "Otic", ""),
            ("nasal", "Nasal", ""),
            ("other", "Other", ""),
        ],
    },
    "mode_of_contact": {
        "name": "Mode of Contact",
        "used_by": ["crm.lead.mode_of_contact"],
        "values": [
            ("phone", "Phone Call", "Cuộc gọi điện thoại"),
            ("zalo", "Zalo", ""),
            ("facebook", "Facebook", ""),
            ("email", "Email", ""),
            ("website", "Website", "Trang web"),
            ("chatbox", "Chatbox", "Hộp trò chuyện"),
            ("walk_in", "Walk-in", "Đến trực tiếp"),
        ],
    },
    "protocol_complexity": {
        "name": "Protocol Complexity",
        "used_by": ["health.clinical.protocol.complexity_level"],
        "values": [
            ("basic", "Basic", ""),
            ("intermediate", "Intermediate", ""),
            ("advanced", "Advanced", ""),
            ("specialist", "Specialist", ""),
        ],
    },
    "relationship_type": {
        "name": "Relationship Type",
        "used_by": ["health.client.relation.relationship_type"],
        "values": [
            ("spouse", "Spouse", ""),
            ("child", "Child", ""),
            ("parent", "Parent", ""),
            ("sibling", "Sibling", ""),
            ("grandparent", "Grandparent", ""),
            ("grandchild", "Grandchild", ""),
            ("relative", "Other Relative", ""),
            ("professional", "Professional Service Provider", ""),
            ("friend", "Friend", ""),
            ("neighbor", "Neighbor", ""),
            ("other", "Other", ""),
        ],
    },
    "staff_availability_status": {
        "name": "Staff Availability Status",
        "used_by": ["hr.employee.availability_status"],
        "values": [
            ("available", "Available", ""),
            ("busy", "Busy", ""),
            ("break", "On Break", ""),
            ("offline", "Offline", ""),
        ],
    },
    "symptom_urgency": {
        "name": "Symptom Default Urgency",
        "used_by": ["health.symptom.urgency_level"],
        "values": [
            ("low", "Low Priority", ""),
            ("medium", "Medium Priority", ""),
            ("high", "High Priority", ""),
            ("emergency", "Emergency", ""),
        ],
    },
    "touchpoint_type": {
        "name": "Touchpoint Type",
        "used_by": ["health.lead.touchpoint.touchpoint_type"],
        "values": [
            ("form_submit", "Website Form Submission", ""),
            ("manual", "Manual Entry", ""),
            ("click_to_call", "Click to Call", ""),
            ("zalo_click", "Zalo Click", ""),
            ("messenger_click", "Messenger Click", ""),
            ("call_cdr", "Call Record (CDR)", ""),
        ],
    },
    "unrouted_contact_reason": {
        "name": "Unrouted Contact Reason",
        "used_by": ["care.contact.capture.reason"],
        "values": [
            ("unknown_resource", "Unrecognised account", ""),
            ("not_ingestable", "Channel not connected yet", ""),
            ("no_identity", "No sender id in the message", ""),
            ("no_anchor", "Nothing to follow up on", ""),
            ("no_voip_config", "Calls not set up", ""),
            ("unmatched_call", "Caller not recognised", ""),
            ("webchat_abandoned", "Web chat opened, nothing sent", ""),
            ("spam_suspect", "Rejected as spam", ""),
        ],
    },
}

# (model, old Selection field, new Many2one field, category code, owning module)
CONVERSIONS = [
    ("health.facility", "facility_type", "facility_type_id", "facility_type", "health_base"),
    ("health.referral.source", "source_type", "source_type_id", "referral_source_type", "health_base"),
    ("health.symptom", "category", "category_id", "symptom_category", "health_base"),
    ("health.vietnamese.district", "region", "region_id", "vn_region", "health_base"),
    ("health.vietnamese.district", "travel_zone", "travel_zone_id", "travel_zone", "health_base"),
    ("health.booking.cancellation.reason", "reason_type", "reason_type_id", "cancellation_reason_type", "health_base"),
    ("health.contact.reason", "category", "category_id", "contact_reason_category", "health_crm"),
    ("health.lead.reason", "category", "category_id", "lead_reason_category", "health_crm"),
    ("health.lead.reason", "lead_type", "lead_type_id", "lead_reason_applies_to", "health_crm"),
    ("health.province", "region", "region_id", "vn_region", "health_crm"),
    ("crm.lead", "service_interest", "service_interest_id", "service_interest", "health_crm"),
    ("health.portable.equipment", "equipment_type", "equipment_type_id", "equipment_type", "health_fieldservice"),
    ("health.portable.equipment", "power_source", "power_source_id", "equipment_power_source", "health_fieldservice"),
    ("health.staff.skill", "skill_category", "skill_category_id", "staff_skill_category", "health_fieldservice"),
    ("hr.employee", "preferred_shift", "preferred_shift_id", "preferred_shift", "health_fieldservice"),
    ("health.medication", "form", "form_id", "medication_form", "health_emar"),
    ("health.monitor.device", "device_type", "device_type_id", "monitor_device_type", "health_telemonitoring"),
    ("health.form.template", "category", "category_id", "form_template_category", "health_forms"),
    ("product.template", "healthcare_package_type", "healthcare_package_type_id", "package_service_type", "health_invoicing"),
    ("product.template", "healthcare_service_location", "healthcare_service_location_id", "service_location", "health_invoicing"),
    ("health.careplan", "category", "category_id", "careplan_category", "health_careplan"),
    ("health.careplan.task", "not_done_reason", "not_done_reason_id", "task_not_done_reason", "health_careplan"),
    ("health.observation", "body_position", "body_position_id", "body_position", "health_vitals"),
    ("health.incident", "outcome", "outcome_id", "incident_outcome", "health_incident"),
    # --- Tier 2: same machinery, but code appears in python comparisons,
    # which were rewritten to `rec.<field>_id.code == 'x'`. ---
    ("health.client.relation", "relationship_type", "relationship_type_id", "relationship_type", "health_crm"),
    ("crm.lead", "mode_of_contact", "mode_of_contact_id", "mode_of_contact", "health_crm"),
    ("hr.employee", "employment_type", "employment_type_id", "employment_type", "health_fieldservice"),
    ("hr.employee", "availability_status", "availability_status_id", "staff_availability_status", "health_fieldservice"),
    ("health.clinical.protocol", "complexity_level", "complexity_level_id", "protocol_complexity", "health_fieldservice"),
    ("health.clinical.protocol", "infection_control_level", "infection_control_level_id", "infection_control_level", "health_fieldservice"),
    ("health.medication.order", "route", "route_id", "medication_route", "health_emar"),
    ("advanced.pricing.rule", "holiday_type", "holiday_type_id", "holiday_type", "advanced_pricing"),
    ("advanced.pricing.rule", "service_location", "service_location_id", "service_location", "advanced_pricing"),
    ("resource.calendar.leaves", "holiday_type", "holiday_type_id", "holiday_type", "health_base"),
    ("care.contact.capture", "reason", "reason_id", "unrouted_contact_reason", "health_care_command_channels"),
    ("health.lead.touchpoint", "touchpoint_type", "touchpoint_type_id", "touchpoint_type", "health_web_leads"),
    ("health.consent", "consent_type", "consent_type_id", "consent_type", "health_consent"),
    # Gender was left out of Tiers 1-2 because it is read by more non-view
    # consumers than any other vocabulary (FHIR, /api/v1, the PWA, the MoH
    # report). It converts on the same machinery; every one of those readers
    # now goes through `gender_code`, so the wire format did not change.
    ("res.partner", "gender", "gender_id", "gender", "health_base"),
    ("crm.lead", "gender", "gender_id", "gender", "health_crm"),
]


# NOT in CONVERSIONS, deliberately — health.symptom.urgency_level became a
# Many2one to `health.urgency.level`, an existing client-editable model with
# its own Master Data tab, rather than a parallel vocabulary here. Its codes
# differ from the old Selection values, so health_base's migration maps them
# explicitly (low->LOW, medium->MED, high->HIGH, emergency->EMERG).
SYMPTOM_URGENCY_MAP = {
    'low': 'LOW', 'medium': 'MED', 'high': 'HIGH', 'emergency': 'EMERG',
}


def conversions_for(module):
    """The subset a given module owns — what its migration must back-fill."""
    return [c for c in CONVERSIONS if c[4] == module]

