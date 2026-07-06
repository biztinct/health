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
    )
}
