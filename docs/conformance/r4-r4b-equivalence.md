# R4 / R4B equivalence for the health19 FHIR facade

**Status:** committed engineering claim. **Register item:** G11 (“R4 declared,
R4B validated”). **Phase:** GC-1. **Date:** 2026-08-02.

## The question

The facade's CapabilityStatement declares `fhirVersion: 4.0.1` — FHIR **R4**.
Its validator, `health_fhir_core.serializers.base.validate_resource`, constructs
the **R4B** model classes from the `fhir.resources` package
(`fhir.resources.R4B.<type>`, falling back to `fhir.resources.<type>`). A
conformance reviewer is entitled to ask whether the thing we validate against is
the thing we claim to serve.

## The claim

**It is, for every resource type this facade serves.**

R4B (4.3.0) is a *targeted* release, not a general revision of R4 (4.0.1). Its
substantive normative and content changes are confined to three families:

| Family | Resources changed in R4B |
|---|---|
| Subscriptions (rewritten backport of the R5 topic-based model) | `Subscription`, `SubscriptionStatus`, `SubscriptionTopic` |
| Evidence-Based Medicine | `Evidence`, `EvidenceVariable`, `EvidenceReport`, `Citation` |
| Medication definition | `MedicinalProductDefinition`, `PackagedProductDefinition`, `AdministrableProductDefinition`, `Ingredient`, `ClinicalUseDefinition`, `ManufacturedItemDefinition`, `RegulatedAuthorization`, `SubstanceDefinition` |

Every other resource's `StructureDefinition` is unchanged from R4 to R4B.

## The 21 resource types this facade serves

None of them appears in the table above.

| # | Resource | Registered by | In an R4B-changed family? |
|---|---|---|---|
| 1 | `Patient` | health_fhir_core | No |
| 2 | `Practitioner` | health_fhir_core | No |
| 3 | `Organization` | health_fhir_core | No |
| 4 | `Location` | health_fhir_core | No |
| 5 | `Encounter` | health_fhir_core | No |
| 6 | `Appointment` | health_fhir_core | No |
| 7 | `ServiceRequest` | health_fhir_core | No |
| 8 | `DocumentReference` | health_fhir_core | No |
| 9 | `Observation` | health_fhir_core | No |
| 10 | `CarePlan` | health_fhir_core | No |
| 11 | `Goal` | health_fhir_core | No |
| 12 | `Task` | health_fhir_core | No |
| 13 | `MedicationRequest` | health_fhir_core | No |
| 14 | `MedicationAdministration` | health_fhir_core | No |
| 15 | `Questionnaire` | health_fhir_core | No |
| 16 | `QuestionnaireResponse` | health_fhir_core | No |
| 17 | `AdverseEvent` | health_fhir_core | No |
| 18 | `Flag` | health_fhir_core | No |
| 19 | `Consent` | health_fhir_core | No |
| 20 | `CodeSystem` | health_fhir_terminology | No |
| 21 | `Condition` | health_condition | No |

Two further R4B payload shapes are produced by the terminology operations and
validated the same way — `Parameters` (`CodeSystem/$lookup`) and `ValueSet`
(`ValueSet/$expand`) — and neither is in a changed family either.

`MedicationRequest` and `MedicationAdministration` deserve an explicit word,
because the *medication definition* family sounds adjacent: it is not. That
family covers the regulatory/product-catalogue resources introduced for
medicinal product definition. The prescribing and administration resources —
the two we serve — are unchanged R4 → R4B.

## Conclusion

Because the StructureDefinitions of all 21 served types (and of `Parameters` /
`ValueSet`) are identical between R4 and R4B, validating a resource with the
R4B class proves exactly what validating it with the R4 class would prove.
Declaring `fhirVersion 4.0.1` while validating with R4B classes is therefore
sound, and the declaration remains the honest one: R4 is what we serve, and it
is what a consumer should generate their client against.

Two consequences are binding on future phases:

1. **The claim is scoped to the served list.** Adding any resource from the
   three families above (a `Subscription`, in particular, is a plausible future
   ask) invalidates this document for that resource. Whoever adds it must either
   validate it against a real R4 class or amend this file with the delta.
2. **The claim is scoped to the pinned library.** It rests on the R4B model set
   `fhir.resources` 8.x ships. That is why the dependency is pinned.

## The pin

`requirements-fhir.txt` (repo root):

```
fhir.resources==8.3.0
```

Installed and verified on `vietuat`. `health_fhir_core/tests/
test_fhir_conformance.py` asserts at test time that `fhir.resources.R4B.patient`
imports and that `importlib.metadata.version('fhir.resources')` starts with
`8.` — so an environment that resolves the dependency differently fails loudly
rather than silently validating against another specification.
