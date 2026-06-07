# Screenshots 8-39 Vietnamese Translation Pass

## Implemented

- `health_base`: corrected healthcare role translations and stored Vietnamese
  facility names without changing English source values.
- `health_theme`: localized the shared booking progress rail.
- `health_crm`: corrected escalation roles and localized activity filters.
- `health_fieldservice`: localized booking calendars, weekdays, time periods,
  list filters, booking states, priorities, staff dashboard roles/statuses,
  client age text, and calendar popovers.
- `health_flow`: restored the active `Audit` JavaScript translation key.
- `health_landing`: localized all admin navigator tabs shown in screenshots
  37-39.
- `health_invoicing`: localized invoice, package, and payment filters; payment
  methods; workflow states; invoice payment badges; dashboard breakdowns; and
  relative-time text.
- `hr_development_ai`: localized the Skills Matrix and corrected the Odoo 19
  virtual dashboard model declaration that caused registry errors.
- Odoo core `calendar`, `hr`, `account`, and `sale`: backed up, patched, and
  force-imported reviewed Vietnamese translations.

## Data Handling

- Personal, nurse, and staff names remain unchanged.
- `health.facility.name` retains its English value and uses language-specific
  Vietnamese values for `vi_VN`.
- Technical selection keys remain unchanged; only user-facing labels are
  translated.

## Excluded

- Icon-shape inconsistencies and other non-translation annotations.
- Functional workflow errors highlighted in screenshots.
- User-entered record names that were outside translation red borders.

## Deployment And Validation

- Deployed sequentially to `VietUcUAT` on Odoo 19 and checked the new server
  log segment after every module upgrade.
- Final deployed versions include `health_fieldservice` `19.0.2.3.5` and
  `health_invoicing` `19.0.1.1.2`.
- Runtime probes confirmed Vietnamese booking/service selections, workflow
  steps, staff assignment states, duty status, payment methods, and payment
  states.
- Runtime probes confirmed employee names remain unchanged and facility names
  resolve as Vietnamese in `vi_VN` and English in `en_US`.
- `health_fieldservice`: 2,290 translated entries, 0 untranslated, 0 fuzzy.
- `health_invoicing`: 1,205 translated entries, 0 untranslated, 0 fuzzy.
- Both catalogs passed GNU gettext format checks with no placeholder or
  HTML/XML markup mismatches.
- The Odoo service remained active and the deployment checks found no new
  `ERROR` or `CRITICAL` log entries.

## Follow-up Fixes

- Core `mail`: translated the messaging popup tab `Chat` as `Trò chuyện`.
- `health_crm` `19.0.1.5.4`: made escalation roles, request types, and urgency
  values language-aware.
- `health_base` `19.0.1.3.4`: localized age display and separated its computed
  cache by language, preserving English output.
- `health_fieldservice` `19.0.2.3.6`: replaced stale direct iteration over
  callable selections in client profile and timeline methods.
- Live validation confirmed Vietnamese and English age output, translated
  escalation values, successful client profile reads, and the deployed Chat
  catalog entry.
