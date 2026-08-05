# Vietnamese Translation Workspace

This directory is the permanent workspace for Vietnamese (`vi_VN`)
localization of the Odoo 19 `health_*` modules.

## Module Scope

Installed on VietUcUAT:

- `advanced_pricing`
- `health_base`
- `health_cms_sidebar`
- `health_crm`
- `health_field_requirements`
- `health_fieldservice`
- `health_flow`
- `health_invoicing`
- `health_landing`
- `health_migration`
- `health_pwa`
- `health_redinvoice`
- `health_theme`
- `health_user_admin`

Present but not installed on VietUcUAT:

- `health_roster`
- `health_voip24h`
- `health_zalo`

## Directory Layout

- `scripts/`: reusable export, merge, audit, and translation helpers
- `po_backups/`: catalog snapshots taken before replacement
- `exports/`: fresh module-specific Odoo 19 exports and merge candidates
- `reports/`: untranslated-entry and QA reports
- `reference_exports/`: historical CSV/XLSX translation inventories
- `core_overrides/`: reviewed fixes for incomplete Odoo 19 core translations

## Safe Module Workflow

1. Export one installed module from VietUcUAT in `vi_VN`.
2. Back up the repository module's current `i18n/vi.po` or
   `i18n/vi_VN.po`, preserving whichever filename the module already uses.
3. Merge the current catalog and fresh export with GNU gettext, preferring
   reviewed repository translations for identical `msgid` values.
4. Apply only reviewed exact-match translations.
5. Run `msgfmt --check --check-format`.
6. Audit untranslated, fuzzy, same-as-source, placeholder, and HTML entries.
7. Replace the module catalog only after all checks pass.
8. Upgrade only that module.
9. Import the reviewed PO with `overwrite=True` and `force_overwrite=True` so
   stale or `noupdate` master-data translations cannot override the catalog.
10. Run English and Vietnamese smoke tests.

VietUcUAT currently loads duplicate module names from the first matching
directory in `addons_path`. For modules such as `advanced_pricing`, the active
copy is `/odoo/odoo-server/addons/<module>`, not the lower-priority
`/odoo/custom/addons/<module>`. Confirm the active source before deploying.

All Odoo shell commands must use a dedicated `--pidfile` under `/tmp`. Reusing
the live service PID file can leave the legacy SysV service wrapper reporting
active while no Odoo process is listening.

Do not use the legacy word-replacement scripts as an automatic production
translation source. They are retained as terminology references and for
controlled review.

`draft_translate_po.py` may be used to create a machine-generated JSON draft
for untranslated entries. It protects placeholders and markup and never edits
the module PO directly. Its output must be reviewed, applied through
`po_catalog.py`, and pass every validation gate before deployment.

Odoo omits `msgstr` values that are intentionally identical to `msgid` when it
exports a catalog. Review those round-trip blanks as proper names, codes,
units, Vietnamese source text, or technical identifiers rather than treating
every one as a missing Vietnamese translation.

## Catalog Audit

```bash
python3 VietTranslation/scripts/po_catalog.py audit \
  addons/health_base/i18n/vi_VN.po
```

## Export And Refresh One Module

```bash
python3 VietTranslation/scripts/export_module_uat.py health_base
python3 VietTranslation/scripts/refresh_module_po.py health_base \
  VietTranslation/exports/health_base/vi_VN_odoo19_export_YYYYMMDD.po
```

Export all installed `health_*` modules in one Odoo shell session:

```bash
python3 VietTranslation/scripts/export_health_uat.py
```

## Import One Reviewed Module

```bash
python3 VietTranslation/scripts/import_module_uat.py health_base
```

## Deploy A Reviewed Odoo Core Override

Core translations are namespaced by their source module. Use the restricted
core deployer when Odoo's bundled Vietnamese catalog is blank or translates a
term back to English. Odoo 19 deliberately ignores JavaScript `type=code`
entries in `TranslationImporter`, so this utility backs up and patches the
active full core catalog instead:

```bash
python3 VietTranslation/scripts/deploy_core_override_uat.py mail
python3 VietTranslation/scripts/deploy_core_override_uat.py resource_mail
python3 VietTranslation/scripts/deploy_core_override_uat.py web
```

The allowlist is intentionally narrow. Keep these catalogs separate from the
`health_*` catalogs because a later Odoo core deployment may require the
overrides to be deployed again. Restart Odoo after deploying all required core
catalogs so the JavaScript translation cache is rebuilt.

## Apply A Reviewed Mapping

```bash
python3 VietTranslation/scripts/po_catalog.py apply \
  VietTranslation/exports/health_base/vi_VN_merged_candidate.po \
  VietTranslation/translations/health_base.json \
  --output VietTranslation/exports/health_base/vi_VN_reviewed.po
```

Fill blank entries from translations that have one consistent reviewed value
across the existing `health_*` catalogs:

```bash
python3 VietTranslation/scripts/fill_from_health_memory.py --apply
```

After wrapping JavaScript UI literals in `_t()`, synchronize literal calls that
are not yet present in the module catalogs:

```bash
python3 VietTranslation/scripts/sync_health_js_po.py --apply
```
