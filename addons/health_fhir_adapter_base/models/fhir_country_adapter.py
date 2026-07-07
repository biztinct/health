# -*- coding: utf-8 -*-
"""Common country-adapter interface (architecture-interop.md §3).

Reusable by future SG/ID/AU adapters — one abstract contract, national
adapters (fhir.adapter.vn, …) inherit it and implement the three verbs."""

from odoo import models


class FhirCountryAdapter(models.AbstractModel):
    _name = 'fhir.country.adapter'
    _description = 'FHIR Country Adapter (interface)'
    adapter_code = None   # e.g. 'vn'
    adapter_name = None

    def transform(self, bundle):   # canonical Bundle dict -> national payload
        raise NotImplementedError()

    def transport(self, payload):  # submit / export, returns receipt dict
        raise NotImplementedError()

    def reconcile(self, receipt):  # map ack/error back onto the log row
        raise NotImplementedError()
