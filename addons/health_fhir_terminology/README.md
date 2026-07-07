# health_fhir_terminology

Local-first medical terminology for health19: `medical.coding.system` +
`medical.code` tables, a CSV bulk importer, an ICD-10 coding sidecar on
clinical notes, and read-only FHIR terminology endpoints
(`CodeSystem`, `CodeSystem/$lookup`, `ValueSet/$expand`) on the existing
`health_fhir_core` facade.

The module ships the **importer and a starter seed** (6 coding systems, the
LOINC vital-signs core, ~30 common home-care ICD-10 codes) — **not** the full
licensed content.

## Loading the full ICD-10 (WHO + MOH VN)

Use **Configuration → Terminology → Import Codes**. CSV columns (fixed order):

```
code,display,display_vi,parent_code,synonyms
```

Only `code` and `display` are mandatory. Import is idempotent (upsert on
`(system, code)`); parents may appear after their children.

Where the content comes from (the module ships neither, for licensing):

- **WHO ICD-10 English** — the WHO ICD browser / classifications download,
  https://icd.who.int/browse10 (ICD-10 2019 release, tabular list).
- **Vietnam MOH ICD-10 translation (`display_vi`)** — the Bộ Y tế / Cục Quản
  lý Khám chữa bệnh (KCB) ICD-10 Vietnamese list distributed with the MOH
  EMR/Circular guidance (e.g. the "Danh mục ICD-10" spreadsheet). Map its
  code + Vietnamese-name columns into `code` + `display_vi`, and the WHO
  English name into `display`.

LOINC (`http://loinc.org`), RxNorm and UCUM full sets load through the same
importer against their respective seeded systems.
