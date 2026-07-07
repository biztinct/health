# -*- coding: utf-8 -*-
"""Register the CodeSystem serializer into health_fhir_core's REGISTRY.

The registry tuple lives in health_fhir_core; this module extends it at
import time (this package is imported from the module's top-level __init__,
after health_fhir_core is fully loaded because it is a hard dependency).
The CapabilityStatement, controller routing, scopes and audit logging are
all registry-driven, so adding the instance here is all that CodeSystem
search/read needs. The capability cache is cleared so a stale (pre-CodeSystem)
statement built before this import is dropped."""

from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.capability import clear_capability_cache

from .code_system import CodeSystemSerializer


def _register():
    serializer = CodeSystemSerializer()
    REGISTRY[serializer.resource_type] = serializer
    clear_capability_cache()


_register()
