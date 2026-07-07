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
