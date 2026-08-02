# Loading the full ICD-10 release — operations runbook

**Register item:** G8 (terminology loaded with starter seed only).
**Engineering status (Phase GC-2, 2026-08-02):** tooling complete and
verified on a committed sample. **Operational status:** not started — the
licence acceptance, the file acquisition and the load itself are ops actions
with an ops owner (§10.11 of the compliance tracker).

Today the database holds a **starter seed of ~31 ICD-10 codes** against a WHO
release of tens of thousands. Everything below is what turns that into a real
code table. Nothing here needs an engineer.

---

## 0. What you will end up with

`medical.code` rows in the `icd10` coding system, each with an English
`display`, a Vietnamese `display_vi`, a `parent_code` link (chapter → block →
category) and optional `synonyms` for the typeahead. The FHIR facade serves
them through `CodeSystem/$lookup` and `ValueSet/$expand`, and clinicians pick
them on the note form — the Vietnamese text is what they search and see.

Two properties make this safe to do on a live system:

- the importer is **idempotent** — re-running the same file creates nothing
  and updates nothing (proven by
  `health_fhir_terminology/tests/test_terminology.py::TestIcd10SampleLoad`);
- **imported codes are archived, never deleted** — a code that leaves the
  release keeps its rows and history intact.

So a partial or interrupted load is fixed by running it again.

## 1. Licence — do this first

ICD-10 is WHO copyright. Using it in a product requires acceptance of the WHO
licence terms; the classification is available from the WHO ICD portal
(`icd.who.int`) after registering and accepting them.

**No script in this repository downloads it**, deliberately: a licence is
accepted by a person, not by a cron job. The converter transforms a file that
is already on disk and never touches the network.

Record in the dossier: who accepted the licence, on what date, for which
release year, and the terms' scope (internal use vs redistribution). Vietnam
uses **ICD-10** for BHYT claim coding, so the release year should match what
the MOH/BHXH expects for the claim period.

The Vietnamese translation is a separate acquisition: the **MOH-KCB**
(Cục Quản lý Khám, chữa bệnh) Vietnamese ICD-10 table, usually distributed as
`.xlsx`. Record its provenance and version too — a translation table with no
version is not evidence.

## 2. Files you need

| File | Source | Format |
|---|---|---|
| ICD-10 ClaML | WHO ICD portal, after licence acceptance | XML (~50 MB) |
| Vietnamese table | MOH-KCB | `.xlsx` → convert to CSV (§3.2) |

## 3. Converting

Run on a workstation with Python 3 — **not on the server**. Nothing gets
installed: both scripts are standard library only.

### 3.1 ClaML → importer CSV

```bash
python3 tools/icd10_claml_to_csv.py ICD10_2019_ClaML.xml -o icd10.csv
```

It prints a summary to stderr — read it:

```
classes read      : 12447
rows written      : 12388
skipped (kind)    : 41      # deleted/retired classes
skipped (chapter) : 0
skipped (no label): 18      # no preferred label → nothing to display
unhandled ClaML elements inside <Class> (skipped): History=1204
```

`rows written` is what will reach the database. If `skipped (no label)` is
large, the file is not what it claims to be — stop and check the download.

To load one chapter at a time (a sensible first run):

```bash
python3 tools/icd10_claml_to_csv.py icd10.xml --chapter I -o icd10_I.csv
```

### 3.2 Adding Vietnamese

Convert the MOH `.xlsx` to CSV first — LibreOffice does it headlessly:

```bash
soffice --headless --convert-to csv moh_icd10_vi.xlsx
```

(Excel: *Save As → CSV UTF-8*. The encoding matters — a CP-1258 export loses
the diacritics and there is no way to recover them afterwards.)

```bash
python3 tools/icd10_vi_merge.py icd10.csv moh_icd10_vi.csv -o icd10_vi.csv
```

The code and Vietnamese columns are auto-detected from the header (`Mã ICD`,
`Tên tiếng Việt`, `code`, `display_vi`, …). If the file uses something else:

```bash
python3 tools/icd10_vi_merge.py icd10.csv moh.csv -o icd10_vi.csv \
    --vi-code-col "Ma benh" --vi-display-col "Ten benh"
```

Codes are matched case-insensitively and with the dot ignored (`i10`, `I10`
and `I 10` all match `I10`), because spreadsheet exports are inconsistent
about all three.

Read the summary, and **do not skip the two lists**:

```
base rows          : 12388
translations read  : 10233
display_vi filled  : 10102
untranslated rows  : 2286   # ICD-10 codes with no Vietnamese yet
unmatched codes    : 131 → icd10_vi.csv.unmatched.csv
```

- **untranslated rows** load fine and display in English. Expected on a first
  pass; worth a second translation source later.
- **unmatched codes** are translations whose code exists in the MOH file but
  NOT in the WHO release — a stale local code, a typo, or a different release
  year. They are written to a sidecar file rather than dropped. Send it back
  to whoever supplied the table; do not "fix" them by hand.

## 4. Loading

1. **Take a database backup first.** The load is idempotent, not reversible:
   there is no "un-import".
2. Odoo → **Terminology → Medical Codes → Import** (`medical.code.import`).
3. **Coding System** = `ICD-10`; upload `icd10_vi.csv`; leave the delimiter at
   `,` and *File Has Header Row* ticked.
4. **Import.** A 12k-row file takes a few minutes; the wizard writes in
   batches of 1,000.
5. Read the result counters:
   - **Created / Updated** — on a first run, Created ≈ `rows written` above.
   - **Skipped** — rows with no code or no display, plus in-file duplicates.
   - **Errors** — the first 20 problems, one line each, including
     `unknown parent_code` for any hierarchy link that did not resolve.
6. Re-run the SAME file. The second run must report **0 created, 0 updated**.
   If it does not, the file has duplicate codes or a column is shifting —
   investigate before loading anything else.

Parents may appear anywhere in the file: the importer resolves the hierarchy
in a second pass, so a children-first export loads correctly.

## 5. Verifying the load

```bash
ssh VietUcUAT 'sudo su - postgres -c "psql -d vietuat -tAc \
  \"SELECT count(*) FROM medical_code mc JOIN medical_coding_system s \
    ON s.id = mc.system_id WHERE s.code = '"'"'icd10'"'"'\""'
```

Then in the UI:

- **Terminology → Medical Codes**, search `I10` → one row, Vietnamese display
  visible, parent chain populated.
- On a clinical note, the **diagnosis code** picker: type `tăng huyết áp` and
  confirm Vietnamese typeahead returns results (`name_search` is
  Vietnamese-first).
- Externally, through the FHIR facade:
  `GET /fhir/r4/CodeSystem?url=http://hl7.org/fhir/sid/icd-10` → the `count`
  element is the live row count.

## 6. After the load — coding density

Loading codes does not make the record coded. Register item G8's second half
is **density**: the share of clinical notes carrying at least one ICD-10 code,
targeted at ≥80%. That is a clinical-practice change (clinicians select codes
as they write), supported by the AI coding-suggestion queue in
`health_ai_coding`. It is measured on the readiness report, not here.

## 7. Sample / dry run

A licence-safe 50-row sample lives at
`addons/health_fhir_terminology/tests/fixtures/icd10_sample_50.csv`.
It is entirely synthetic (`ZZ*` codes — no WHO content), and exercises the
awkward parts: children before parents, Vietnamese diacritics, a malformed
row, and a re-import. Use it to walk through §4 once before touching the real
file. The automated test loads this exact file twice on every deploy, so the
path in §4 is exercised continuously, not just when someone runs it.

---

*Operational owner: client + clinical lead (licence, files, load, density).
See §10.11 of `docs/strategy/hl7-fhir-compliance-response.html`.*
