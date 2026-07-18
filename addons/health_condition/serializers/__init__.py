# -*- coding: utf-8 -*-
"""Register the Condition serializer into health_fhir_core's REGISTRY.

Cloned from health_fhir_terminology's CodeSystem downstream-registration
pattern: the registry, CapabilityStatement, controller routing, scopes and
audit logging are all registry-driven, so instantiating + assigning here (at
import time, after health_fhir_core is fully loaded — it is a hard dependency)
is all the Condition search/read needs. The capability cache is cleared so a
stale (pre-Condition) statement is dropped; $everything picks it up via the
patient-compartment convention (it carries a ``patient`` search param)."""

from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.capability import clear_capability_cache

from .condition import ConditionSerializer


def _register():
    serializer = ConditionSerializer()
    REGISTRY[serializer.resource_type] = serializer
    clear_capability_cache()


_register()
