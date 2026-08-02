# -*- coding: utf-8 -*-
"""Serializer registry — one instance per FHIR resource type (§C.2).

The CapabilityStatement, the controller routing and the tests are all driven
from REGISTRY; adding a resource means adding a serializer class here.
"""

from . import base
from . import fso_common
from .patient import PatientSerializer
from .practitioner import PractitionerSerializer
from .organization import OrganizationSerializer
from .location import LocationSerializer
from .encounter import EncounterSerializer
from .appointment import AppointmentSerializer
from .service_request import ServiceRequestSerializer
from .document_reference import DocumentReferenceSerializer
# Phase 2 — clinical-spine resources.
from .observation import ObservationSerializer
from .careplan import CarePlanSerializer, GoalSerializer, TaskSerializer
from .medication import (
    MedicationRequestSerializer, MedicationAdministrationSerializer,
)
from .questionnaire import (
    QuestionnaireSerializer, QuestionnaireResponseSerializer,
)
from .adverse_event import AdverseEventSerializer, FlagSerializer
from .consent import ConsentSerializer

REGISTRY = {
    serializer.resource_type: serializer
    for serializer in (
        PatientSerializer(),
        PractitionerSerializer(),
        OrganizationSerializer(),
        LocationSerializer(),
        EncounterSerializer(),
        AppointmentSerializer(),
        ServiceRequestSerializer(),
        DocumentReferenceSerializer(),
        # Phase 2 — clinical-spine resources.
        ObservationSerializer(),
        CarePlanSerializer(),
        GoalSerializer(),
        TaskSerializer(),
        MedicationRequestSerializer(),
        MedicationAdministrationSerializer(),
        QuestionnaireSerializer(),
        QuestionnaireResponseSerializer(),
        AdverseEventSerializer(),
        FlagSerializer(),
        ConsentSerializer(),
    )
}

# --------------------------------------------------------------------------
# Operations registry (A1 / G2) — the CapabilityStatement is generated from
# these, never hand-listed. Downstream modules append to BOTH dicts at import
# time (health_fhir_terminology adds CodeSystem/$lookup + ValueSet/$expand)
# exactly as they extend REGISTRY, then clear the capability cache.
# --------------------------------------------------------------------------

#: resource type (WITH a serializer in REGISTRY) -> list of operation dicts
OPERATIONS = {
    'Patient': [{
        'name': 'everything',
        'definition': ('http://hl7.org/fhir/OperationDefinition/'
                       'Patient-everything'),
    }],
}

#: resource type with NO serializer (operation-only: no read/search-type
#: interaction, no searchParam) -> list of operation dicts
OPERATION_ONLY_RESOURCES = {}
