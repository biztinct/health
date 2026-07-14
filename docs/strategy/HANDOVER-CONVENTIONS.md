# health19 — Implementation Conventions & Handover Ground Truth

Read this ENTIRE document before writing any code. It encodes hard-won
knowledge from seven shipped modules; every rule here was paid for with a
live failure on the UAT server. It is referenced by every per-phase
handover document in `docs/strategy/handovers/`.

## 1. Environment ground truth

- **Odoo 19 Community Edition** (never treat as Odoo 17 or other versions).
  OWL 2, QWeb, PostgreSQL. Python per server (3.10 on UAT).
- UAT server SSH alias: **VietUcUAT**. Database: **`vietuat`** (never
  `vietuc_uat` / `odoo_vietuc`). Addons live at `/odoo/odoo-server/addons/`
  (never `/odoo/custom/addons/`).
- Odoo writes logs to `/var/log/odoo/odoo-server.log` (configured logfile —
  redirecting odoo-bin stdout captures only docutils RST noise; always read
  the server log for install/test results, with `grep -a`, the file is
  treated as binary).
- Server python libs already installed: fhir.resources, authlib,
  cryptography 49, pyOpenSSL 26.3.0, urllib3 1.26.20. **Do NOT pip install
  anything** without flagging it in your report first — a pip upgrade of the
  cryptography chain has taken the server down before.

## 2. Deploy + test workflow (the only accepted procedure)

```bash
# 1. copy (from repo root/addons)
ssh VietUcUAT 'rm -rf /tmp/<mod>'
scp -r <mod> VietUcUAT:/tmp/
ssh VietUcUAT 'sudo rm -rf /odoo/odoo-server/addons/<mod> \
  && sudo cp -r /tmp/<mod> /odoo/odoo-server/addons/ \
  && sudo chown -R odoo:odoo /odoo/odoo-server/addons/<mod>'

# 2. install/upgrade WITH tests (stop server first)
ssh VietUcUAT 'sudo service odoo-server stop && sleep 6 && \
  sudo su - odoo -s /bin/bash -c "/odoo/odoo-server/odoo-bin \
    -c /etc/odoo-server.conf -d vietuat -i <new_mods> -u <changed_mods> \
    --test-enable --test-tags /<mod1>,/<mod2> \
    --stop-after-init --no-http --workers 0"; echo EXIT:$?; \
  sudo service odoo-server start; sleep 12; \
  curl -s -o /dev/null -w "HTTP:%{http_code}\n" localhost:8069/web/login'

# 3. results are in /var/log/odoo/odoo-server.log:
ssh VietUcUAT 'sudo grep -a "odoo.tests.result" /var/log/odoo/odoo-server.log | tail -3'
```

Run test commands in the background if your harness supports it; a full
run takes several minutes. If an SSH session drops mid-run the server-side
process usually survives — check with
`pgrep -af "python3.*odoo-bin.*test-enable"` before assuming failure.

## 3. PWA version bump rule (MANDATORY on any PWA-facing deploy)

Any deploy that changes PWA assets, the app shell, or any module that
injects JS into the shell requires bumping `health_pwa`:

- `health_pwa/views/pwa_templates.xml` — the version string appears
  **5 times** (`pwa_asset_version` t-set, `version:`, `PWA_SW_VERSION`,
  the SW comment line, `CACHE_VERSION`). `sed` all occurrences.
- `health_pwa/__manifest__.py` — bump the last version segment.
- Read the CURRENT version from `pwa_templates.xml` (never trust a doc's
  hardcoded value). Co-resident PIN TESTS hard-assert it and MUST be
  bumped in the same change: `health_pwa_daystrip/tests/test_daystrip.py`,
  `health_scribe/tests/test_scribe.py`,
  `health_pwa_family/tests/test_pwa_family.py`.
- Deploy health_pwa alongside (add `-u health_pwa` to the upgrade).

## 4. Module structure conventions

- **A phase edits ONLY the modules/files its handover doc explicitly
  sanctions** (each sanctioned edit named: module + file + what may
  change). Absent a sanction, shared modules (`health_pwa`,
  `health_fieldservice`, `web_timeline`, `health_messaging`, …) are
  READ-ONLY — except the §3 version bump, which is always required when
  PWA assets change. Precedents: pwa-family (sanctioned bell card in
  app.js), schedule-canvas (sanctioned web_timeline + health_fieldservice
  edits). Satellite modules keep the pattern: each ships its own JS in
  `<mod>/static/src/js/` (plain `window.*` globals, no module system)
  injected via QWeb inheritance of `health_pwa.app_shell` in
  `views/pwa_shell_inherit.xml`, with `?v=#{pwa_asset_version}`
  cache-busting. Add `health_pwa` to `depends` when you do this.
- PWA API endpoints: routes under `/health_pwa/api/...`, `type='http'`,
  `auth='user'`, `csrf=False`, manual `json.loads(request.httprequest.data)`.
  Duplicate the `_check_api_access()` + `_prepare_json_response(data,
  error, status_code)` helpers verbatim from an existing module
  (health_consent/controllers/api.py is a clean reference). Envelope:
  `{"success", "timestamp", "data"|"error"}`.
- Offline mutations carry a `client_mutation_id`; the server no-ops on
  replay (search first, return the existing record).
- Security: groups reference `privilege_id` →
  `health_base.res_groups_privilege_healthcare` (Odoo 19 has NO
  `category_id` on res.groups). Group ladder:
  `health_base.group_healthcare_{base,receptionist,nurse,head_nurse,
  doctor,operations_manager,manager,admin,finance,owner}`.
  Client-scoped models get the catchment-province record rule pair
  (see health_consent/security/health_consent_security.xml for the
  template) plus an owner sees-all rule.
- Every module ships `i18n/vi.po` (copy header format from
  health_careplan/i18n/vi.po). If the module ALREADY ships a Vietnamese
  catalog under another name (e.g. health_pwa's `vi_VN.po`), extend that
  file — never create a competing second catalog.
- UI: flat mono colors only (NO gradients/dual-tone), `hf-wt-ico`
  CSS-mask SVG icons (NEVER emoji or font-awesome), form chatter at
  bottom full-width (never side column).
- Sequences: `data/ir_sequence.xml` with `noupdate="1"`.

## 5. Odoo 19 gotcha ledger (every entry was hit live — violate at your peril)

1. `_sql_constraints` are NOT materialized. Create unique/check indexes
   in `def init(self)` with `CREATE UNIQUE INDEX IF NOT EXISTS`
   (mandatory for any `ON CONFLICT` upsert or uniqueness contract).
2. `@api.constrains` does NOT fire on create when none of the constrained
   fields are in vals — call the checks explicitly from a `create()`
   override too.
3. **A DB unique index fires before Python constraint checks** — for
   uniqueness that user input can violate (idempotency keys), pre-check
   in `create()` BEFORE `super()` and raise `ValidationError`; otherwise
   the IntegrityError poisons the transaction.
4. **uid 1 always runs as su** (Odoo forces `su=True` for SUPERUSER_ID),
   and tests run as uid 1 — any `if not self.env.su:` guard is dead code
   in tests and for admin. Append-only / evidence-lock / audit guards
   must be UNCONDITIONAL (see health_evv event + health_consent).
5. `copy()` does not reliably duplicate One2many children — copy them
   explicitly in a `copy()` override, guarded (`if not new.child_ids:`).
6. NEVER name a One2many `activity_ids` on a model inheriting
   `mail.activity.mixin` — it shadows the mixin field and breaks
   registry load with `KeyError: 'activity_type_id'`.
7. `('some_m2o', 'not in', [0])` silently matches NOTHING. Never use [0]
   sentinels — build the domain conditionally and omit the criterion
   when the id list is empty.
8. `assertRaises` accepts a SINGLE exception class (tuples raise
   TypeError). Its savepoint rollback also voids all in-transaction
   writes made before the raise — don't assert on state persisted
   inside an `assertRaises` block.
9. Raw-SQL fixture updates race pending ORM flushes:
   `env.flush_all()` before `cr.execute`, `env.invalidate_all()` after.
10. Search views: put group-by `<filter>`s directly in `<search>` (no
    `<group expand="0" string="Group By">` wrapper). No `attrs=` /
    `states=` anywhere (use `invisible=`/`readonly=` python expressions).
11. `post_init_hook` signature is `(env)`.
12. Separate-cursor writes (e.g. persisting audit data before raising)
    MUST happen before any same-transaction write to the same row, and
    use `SET LOCAL lock_timeout` — otherwise self-deadlock
    (see health_emar `_persist_interaction_result`).
13. Custom field search methods may receive `OrderedSet` (not list/set
    builtins) and the domain optimizer rewrites `=` to `in [..]` —
    handle generic iterables and falsy members.
14. `mail.template` renders every subject/body AT INSTALL
    (`_check_can_be_rendered` constraint) against a bare sample record —
    any variable you meant to inject later via
    `_render_field(add_context=...)` raises NameError and blocks
    install. Templates must be self-contained on `object.*`; for
    tz-correct datetimes use `{{ format_datetime(object.dt,
    tz=object.booking_timezone, dt_format='HH:mm') if object.dt
    else '' }}`.
15. `health_base`'s `normalize_vn_phone(value)` RAISES ValidationError
    on a non-empty invalid number (it returns the value only when
    falsy). `res.partner` also validates `mobile` on create, so the
    real "no usable phone" case is an EMPTY mobile — wrap the helper in
    try/except when you want falsy-on-invalid semantics.
16. `res.groups` has NO `.users` attribute in Odoo 19 — it is
    `.user_ids` (mirrors the `groups_id`→`group_ids` rename). Also
    `crm.lead` has NO `mobile` field (only `phone`) — guard with
    `getattr(lead, 'mobile', '')`. And `action_create_from_quick_
    booking_owl(vals)` writes `contact_outcome` on the lead when
    `lead_id` is passed, which re-runs `_get_or_create_patient` and
    raises "Catchment Province is required" if the new patient lacks
    one — pass `patient_id` (already resolved) and OMIT `lead_id`.
    FSO `action_confirm_booking` requires a quote line or prepaid
    package, so any programmatic booking must attach `product_lines`.
17. `selection_add` with `ondelete: cascade` on a model whose
    `unlink()` raises unconditionally (e.g. `health.evv.event` — its
    append-only guard has no `MODULE_UNINSTALL_FLAG` escape) makes the
    EXTENDING module un-uninstallable once rows with the new selection
    value exist: uninstall tries to cascade-delete them and crashes.
    Live example: health_pwa_daystrip's travel events. Either accept
    it (append-only chains SHOULD resist deletion — document it in the
    manifest) or add the uninstall-flag escape to the base unlink.
    Also: matrix/live-data test isolation — vietuat's
    `health.staff.availability.matrix` carries live rows including
    NULL-province ones that match every patient; tests touching the
    slot proposer must create their own province+facility+staff and
    locate their own slots by (staff, date, time), never index 0.
18. Stored computes that COPY a Selection value from another model
    must VALUE-MAP, not copy — `advanced_pricing.sale_order.
    fso_service_location` had a narrower Selection than FSO
    `service_location`, so any online/telemedicine booking with a
    quote was a latent `Value 'online' not in selection` crash at the
    NEXT `flush_all` (not at create — store-field crashes hide until
    something flushes). Fixed with an explicit map + valid-value
    guard (unknown → False). Corollary: when overriding an
    `@api.depends` compute you must re-declare the FULL decorator
    (plus your additions) or the field silently loses dependencies.
19. **PHI-encrypted fields are NON-STORED computes** — once
    `health_phi_encryption` is installed, `health.clinical.note`'s
    `diagnosis` / `clinical_notes` / `treatment_performed` / etc. are
    compute fields (no `store=True`) backed by stored `*_enc` Text
    columns. You CANNOT filter the plaintext field in an ORM domain
    (`('diagnosis','!=',False)` raises / can't be searched). Filter the
    stored backing column instead — `('diagnosis_enc','!=',False)` is
    non-empty iff the plaintext was non-empty (the inverse writes
    `enc = encrypt(v) if v else False`). Gate on
    `'diagnosis_enc' in Model._fields` so the module still works where
    encryption is not installed. Also: an append-only log that a note can
    cascade-delete must use `ondelete='set null'` on its `note_id`, NOT
    cascade — a DB-level SET NULL bypasses the ORM `unlink` guard, whereas
    a cascade would fire the guard and make notes undeletable (§17 class).
20. **Appending to an Html field ESCAPES a str RHS.** Reading an Html field
    (e.g. `clinical_notes`) yields a `markupsafe.Markup`; `Markup + str`
    escapes the str, so `note.clinical_notes = note.clinical_notes + '<p>x</p>'`
    stores `&lt;p&gt;x&lt;/p&gt;` and the tags render as literal text. Build
    the appended fragment as `Markup('...<p>%s</p>') % text` (the `%` escapes
    the interpolated value for you) so `Markup + Markup` stays raw. Compounds
    §5.19 for any transcript/notes append.
21. **`@string` is not a valid view-inheritance xpath selector** in Odoo 19 —
    `<xpath expr="//page[@string='Images']">` fails install with "View
    inheritance may not use attribute 'string' as a selector" (string is
    translatable). Select by `@name` (add one if the base page lacks it) or a
    structural node (`//notebook` position="inside", `//field[@name='x']`).
22. **`hr.contract` does NOT exist in Odoo 19** — employment/wage data moved to
    `hr.version` (columns `employee_id`, `wage` (monthly, numeric, nullable —
    ~0 default on auto-created versions), `contract_date_start/‑end`, `active`).
    hr.employee auto-creates one version on create. For an SQL per-employee
    rate: pick the active wage-bearing version
    (`WHERE employee_id=… AND active AND wage>0 AND (contract_date_end IS NULL
    OR >= CURRENT_DATE) ORDER BY contract_date_start DESC LIMIT 1`), COALESCE to
    a default. Also: FSO has **no `company_id`**, `sale.order.line` taxes are
    `tax_ids` (not `tax_id`), and `health_fieldservice_order.lead_staff_id` is a
    NON-STORED compute (use stored `primary_nurse_id` in SQL).
23. **Postgres `round(x, n)` requires `numeric`** — `round(double precision, int)`
    does not exist and fails view creation. Any division/`EXTRACT(EPOCH …)`
    yields double precision; cast the WHOLE argument
    (`round(expr::numeric, 2)`) before the 2-arg round. Bit finance/BI SQL views
    hard. Corollary for the biz_bi platform: an sql_view-rooted `bi.dataset`
    SKIPS `_check_company_gate` (it returns for non-`odoo_model` roots), so
    `company_field_id` is optional there.
24. **Reading ANY hr.employee field as a non-HR user trips the public-profile
    guard.** hr_employee `_check_private_fields` fires on the batched FETCH:
    even asking only for `healthcare_facility_id` or `name` on an
    `operations_manager`/nurse user raises `AccessError` ("fields
    access_role_id,is_duty_doctor,is_head_nurse,is_om_role … not available for
    employee public profiles") because the prefetch pulls the private fields
    into the same SQL read. In a server method already gated by a group check,
    `.sudo()` the employee records (and the FSO write that fires the staff
    notifications) — guard by group, then sudo the reads/writes (ai_coding
    precedent). Flaky-looking: the first read may hit cache and pass, a later
    one re-fetches and raises.
25. **`fields.Datetime(tracking=True)` is NOT a guarantee of a chatter
    message.** `health.fieldservice.order.scheduled_datetime` is `tracking=True`
    yet a write produces ZERO `mail.tracking.value` rows and NO chatter message
    (the FSO write override suppresses tracking). Don't rely on "tracking=True
    ⇒ free chatter/audit" — verify with a `mail.tracking.value` search_count and
    post an explicit `message_post` when you need the audit trail on the record.

26. **`hr.employee.working_hours_<day>` Char fields are only a FALLBACK** —
    `_working_intervals_for` prefers `resource_calendar_id`, and every
    employee gets the company default calendar (8-17) on create, so
    writing the char fields does NOTHING until you clear
    `resource_calendar_id = False`. Test fixtures that "restrict"
    working hours via the char fields silently test the default
    calendar instead (hit live in the schedule-drag suite).

27. **`search()` silently skips ARCHIVED rows — a data-cleanup hook must pass
    `active_test=False`.** health_schedule_canvas's post_init unlinked orphan
    `state='template'` assignments via `search([('state','=','template')])` and
    removed only **3** — but 47 more existed, all `active=False`. Any model with an
    `active` field has an implicit `('active','=',True)` added to every `search`,
    so archived rows are invisible to a naive cleanup (and to any migration/GC that
    means "ALL rows matching X"). Use
    `env[model].with_context(active_test=False).search(domain)`. Corollary: a
    `search_count`/`unlink` sweep that reports "N removed" can be silently
    incomplete — verify with a raw `active_test=False` count afterwards.

28. **vis-timeline background-item layout is super-linear — cap it.** Feeding vis
    ~900 `type:'background'` items (a 7-day × 60-staff off-hours overlay) froze the
    main thread ~18 s on a Day→Week switch (measured live); the server RPC returning
    them was only ~600 ms, so it *looks* like a slow network call but it's a
    synchronous render freeze (the pending XHR's `loadend` just fires late because
    the thread is blocked — a `.o_loading` spinner sits up the whole time). Never
    hand vis an unbounded background set: filter to the visible range, drop
    backgrounds that fall inside hidden (`hiddenDates`) columns, and hard-cap the
    remainder (health_schedule_canvas `OFF_BG_CAP=300`; past the cap ALL decorative
    'off' shading is dropped — partial shading would read as "the unshaded staff
    are on duty" — while 'leave' is always kept, with a console.warn). Diagnose
    with a `setInterval` main-thread-block detector, not the network panel.

29. **A hand-written `i18n/vi.po` MUST give every entry a `#. module: <name>`
    extracted-comment line, or registry load CRASHES.** Odoo's PO importer
    (`odoo/tools/translate.py` `__iter__`) does `match = re.match(r"(module[s]?):
    (\w+)", entry.comment); _, module = match.groups()` on EVERY entry — with no
    `#. module:` comment, `entry.comment` is empty, `match` is `None`, and it dies
    with `AttributeError: 'NoneType' object has no attribute 'groups'` inside
    `_update_translations` (the last step of `load_module_graph`). This is NOT a
    test failure — it's a `CRITICAL Failed to initialize database`, and every data
    file loaded fine first, so the traceback points at translation load, not your
    code. Copy a real module's body format (e.g. health_careplan/i18n/vi.po):
    each entry is `#. module: <module>\nmsgid "…"\nmsgstr "…"`. The header block
    alone is not enough.

30. **`ondelete='cascade'` deletes children at the SQL layer — the child's
    Python `unlink()` guard never runs.** The FK's `ON DELETE CASCADE` lives in
    PostgreSQL (no cascade handling exists in `odoo/orm/models.py`), so an
    append-only child model (EVV events, family messages) is only protected if
    EVERY cascade parent carries the same unlink guard too — or the FK uses
    `ondelete='restrict'`. Hit live in health_family_messages review: owner-level
    `perm_unlink` on `health.family.thread` would have silently cascade-deleted
    the whole append-only message history; fixed with a parent-level guard +
    `perm_unlink=0`. When auditing an append-only model, grep for every
    `Many2one` pointing at it AND every cascade FK it points out through.

31. **The PWA `#/order/<id>` "order screen" is DEAD CODE — the nurse's real
    visit surface is the booking-detail MODAL on the today screen.** The whole
    `order-detail-view` component (~1,600 lines incl. its `.order-details` /
    `.order-actions` markup) has been wrapped in a `/* LEGACY CODE */` block
    comment since 2025-11-09 ("the Booking List Modal View is the active
    interface"), but the route, `navigate('order', …)` callers (orders /
    past-bookings lists) and the component markup were all left in place — so
    grep "finds" the screen while Vue renders a blank page (unresolved
    `<order-detail-view>` tag; check `app._context.components` to see what is
    actually registered). Three review lessons paid for in full: (a) verify a
    UI seam by DRIVING the real screen and watching the network panel, never
    by grepping components — grep cannot see block comments, and
    `Function.prototype.toString()` shows commented-out code too; (b) when
    probing "does this code run", use `window.__flag = 1` side effects, not
    console.log, and suspect comments/strings when linear code "skips"; (c)
    the definitive tool is the AST statement list (acorn) — a swallowed
    region belongs to NO statement. Augmentation JS for the visit surface
    keys on the modal: wrap the bare `GET /health_pwa/api/fso/<id>` (fired on
    every modal open — clone the response, never consume) and inject into
    `.booking-detail-modal-content` before `.modal-footer`. Also from the same
    dig: `parseOdooDateTime` lived inside today-view's setup() closure while
    orders-view/past-bookings-view called it → ReferenceError, both list
    screens dead since Nov ("Failed to load orders") — helpers shared across
    components belong at file top-level.
    *(Postscript, pwa-reliability phase 64d8c602: the corpse is now DELETED
    and `#/order/<id>` / `navigate('order', …)` resolve to the shared
    booking modal via the root `openBooking()` bridge. The review lessons
    above still stand; the modal seam contract is unchanged.)*

32. **An HttpCase that triggers config-gated side-effects can poison LATER
    TransactionCase suites in the same test run.** HttpCase endpoint calls
    run against a separate cursor, so records they create do not roll back
    with the later suite's expectations — `TestOneTapEndpointScope`
    completing a visit created an `hr.attendance` for *today* (the E.4
    timecard hook), which broke `TestTimecardSync`'s
    `cron_reconcile_timecards(for_date=today)` when the suites ran in one
    run (each passed alone; isolation-verified). Non-transactional
    `ir.config_parameter` ORMCACHE compounds the confusion. Fix pattern:
    in the HttpCase `setUp`, pin OFF the config switch gating any
    side-effect you don't assert on, restore it in `tearDown` (see
    `TestOneTapEndpointScope.setUp` — `timecard_sync_enabled`). Corollary:
    any test asserting on "today's" data is exposed to every earlier
    HttpCase in the same run. Second corollary (QA, not tests): changing
    JS content while keeping the same `?v=` means SW/HTTP caches serve the
    OLD file — bump the version per content change, even mid-QA iteration.

33. **Child-row writes do NOT bump the parent's `write_date` — a delta feed
    keyed on the parent's `write_date` misses every child-driven change.**
    Cancelling a `health.staff.assignment` (state write) leaves the parent
    FSO's `write_date` untouched (the FSO's stored computes depend on
    `assignment_ids.staff_id`/`assignment_role`, NOT `.state`), so the
    pwa-sync-delta feed emitted no removal when a nurse was de-assigned —
    and, mirror image, a new assignment on an old order never upserted into
    the nurse's delta. Fix pattern: feed the candidate set from BOTH windows
    (parent changed-since ∪ parents-of-children-changed-since,
    sync.py `_get_fso_changes`). Test pattern: raw-SQL-backdate the parent
    row (write_date is ORM-managed) so ONLY the child window can produce the
    candidate — a far-past `since` in tests recaptures everything via
    `create_date` and MASKS this whole class (that is exactly how it slipped
    through review the first time). Same trap awaits any future incremental
    feed (`@api.depends` does not equal "bumps write_date"; only actual
    stored-compute WRITES do, and only for the fields that recompute).

34. **`odoo-bin shell` fed via piped stdin can silently discard writes even
    after `cr.commit()` printed success.** During pwa-offline-actions browser
    QA, a fixture `create()` printed a new id and called `cr.commit()`, yet a
    later shell showed the row absent — the piped console's transaction
    lifecycle rolled it back around the commit. Reliable recipe: create →
    `env.flush_all()` → `env.cr.commit()`, then confirm in a SEPARATE
    `ssh … odoo-bin shell` (or psql) invocation before trusting the state.
    Also `odoo.registry` / `odoo.api` are not shell globals — use
    `odoo.modules.registry.Registry` / `odoo.api.Environment`, or just
    re-search in `env` after the commit. Symptom when violated: a
    "persisted" record vanishes and downstream calls fail with spurious
    Access denied / missing-record errors. Corollary for QA state changes:
    ALWAYS re-verify the revert in a fresh cursor too — this phase's QA
    left an FSO `in_progress` + an orphan clinical note behind because the
    revert was trusted from the same shell that made it.

35. **A tamper-evident content hash that includes a timestamp set in the SAME
    write reproduces on reload ONLY because Odoo truncates datetimes to the
    second.** `fields.Datetime.now()` returns `datetime.now().replace(
    microsecond=0)` and PostgreSQL stores that second-precision value, so a
    hash computed at finalize (over the in-memory `now()`) equals a re-hash
    over the reloaded stored value — `fields.Datetime.to_string` emits
    `%Y-%m-%d %H:%M:%S` in both paths. If you ever hash a raw
    `datetime.datetime.now()` (with microseconds) while storing the truncated
    value, the seal will NEVER verify after reload — a silent, total failure
    of the integrity check. Rules for any integrity/audit hash: canonicalize
    with `json.dumps(sort_keys=True, separators=(',',':'))`; read PHI through
    the ORM (it decrypts transparently — the plaintext hashes deterministically
    while ciphertext would not); cover attachment bytes via
    `ir.attachment.checksum` (filter out falsy checksums before `sorted()`);
    and store an explicit `hash_version` so the scheme can change without
    re-sealing history (health_emr `_compute_content_hash`). Also §5.30
    applies: an `ondelete='cascade'` child (clinical note → FSO) is deleted at
    the DB level and NEVER fires its Python `unlink()` guard, so an
    immutability/retention guarantee on the child must ALSO be enforced by a
    parent-model `unlink()` override (health_emr `health_fieldservice_order`).

36. **A default-True Boolean settings toggle backed by `config_parameter`
    can NEVER be switched off from the Settings UI.** Core `set_values()`
    passes raw `False` to `ir.config_parameter.set_param()`, which UNLINKS
    the parameter for falsy values; a `get_param`-with-default helper then
    falls back to the hardcoded default (True) and `get_values()` re-shows
    the field default — the checkbox silently snaps back on. Kill-switches
    for clinical engines were inert (telemonitoring review HIGH-1). Tests
    mask it when they `set_param('False')` directly (a string is truthy —
    that path works). Fix pattern: override `set_values()` to persist
    explicit `'True'/'False'` strings (health_telemonitoring
    `res_config_settings.py`); same trap for Integer 0 (param unlinked →
    default returns — clamp or stringify). `health_workflow_auto` never hit
    it because its gates default False.

37. **The PWA vitals POST requires the nurse to be ASSIGNED to the FSO —
    and an Odoo 19 `AccessError` subclasses `UserError`, so a record-rule
    denial surfaces as HTTP 400, not 500.** `…/fso/<id>/vitals` reads
    `order.patient_id` as the authenticated user; the FSO record rule is
    assignment-based, so an in-catchment-but-unassigned nurse trips the
    rule on that read → AccessError → caught by
    `except (UserError, ValidationError)` → a 400 with the generic
    "top-secret records" message that LOOKS like bad input. Diagnose
    HTTP-only 400s by replaying the auth'd request and reading the error
    string. Fixture rule: HttpCase nurses must be assigned via
    `action_assign_staff_to_fso` (conventions §6). Corollary (method-gate
    integrity): if lifecycle actions write via `self.sudo().write()`, do
    NOT also grant users model-level write on those fields — add a
    `write()` guard restricting non-su writes to the user-editable fields
    (health_telemonitoring `health_monitor_alert.py`), else a direct RPC
    `write({'state': …})` bypasses the group gates.

38. **The gateway `@api_route` decorator swallows Odoo 19's readonly-cursor
    retry signal — do NOT build a WRITE endpoint on it.** Odoo 17.3+ runs each
    HTTP request on a **readonly cursor first** and retries on a read/write
    cursor only if `psycopg2.errors.ReadOnlySqlTransaction` propagates up to
    `service.model.retrying`. `health_api_gateway`'s `api_route` decorator wraps
    the handler in `try: … except Exception: return 500-envelope`, which
    **catches** that error, so the retry never fires and the FIRST write in ANY
    decorated endpoint dies as a generic 500. Reads work; `/oauth/token` works
    because it is NOT decorated (the error propagates, retry runs). Symptom under
    HttpCase: a POST returns an ERROR envelope with no `data` key → downstream
    `r.json()['data']` raises `KeyError: 'data'` (telemonitoring Phase-2 ingest:
    6 failed / 5 error before the fix). Fix for a gateway-fronted WRITE endpoint:
    do NOT use `@api_route`; declare
    `@http.route(type='http', auth='public', csrf=False, methods=['POST'],
    readonly=False)` (R/W cursor from the start) and IMPORT the gateway helpers
    `_gateway_authenticate` / `_scopes_satisfied` / `_envelope_response`
    (documented interface — no gateway edit). The existing `booking.write` routes
    only survive in production via the framework retry that the decorator + tests
    defeat. Corollary (modal seam, ledger §31): the PWA booking modal fires
    `GET /health_pwa/api/fso/<id>` on open with status in `data.state`, but
    **Start Service updates the modal's state LOCALLY** (`app.js:2551`) with no
    detail re-fetch — a fetch-wrap watching only the detail GET misses the
    → `in_progress` flip; also intercept the `POST …/fso/<id>/start` response
    (health_vitals vitals-FAB rider).

39. **A model-level Python `write()`/`unlink()` guard fires BEFORE the ACL,
    so a `perm_write=0` group gets `UserError`, not `AccessError`.** For an
    engine-only model whose writes are all sudo (e.g. `health.twin.risk`,
    `health.ews.score`), the unconditional guard (§5.4) that raises
    `UserError('… system-generated …')` runs before Odoo reaches
    `check_access`, so a non-privileged user's direct write raises the guard's
    UserError. Only the UN-guarded path (`create`, if you don't override it)
    surfaces the raw ACL `AccessError`. Test consequence: assert `UserError`
    for guarded write/unlink and `AccessError` for create — asserting
    AccessError on a guarded write fails (health_twin `test_12_acl`; this
    tripped its first run). Not a bug — know which exception each path raises.

40. **A composite *weighted-average* score dilutes a single strong signal —
    band it with hard clinical FLOORS, not the average alone.** health_twin's
    risk score is a weighted average of four components; under the shipped
    weights a *lone open critical alert* (alert component 100, everything else
    0) scores only `100·0.35 ≈ 35` → 'moderate', so the one signal the
    deterioration worklist exists to surface ranked mid-list and fell below the
    High+Critical default filter (handover D1). Fix pattern: after computing the
    weighted score, apply a `clinical_floor(score, open_critical, thresholds)`
    that raises it to the critical threshold when a critical alarm is open —
    the average still ranks patients ABOVE the floor when signals stack, so
    in-band order is preserved and the raw components stay in `factors_json`
    for transparency. General rule for any triage score: a weighted average is
    for RANKING; a clinically-critical single input needs a floor so it can't
    be averaged away.

41. **The user-facing patient form on vietuat is the STANDALONE ops profile
    view, NOT `health_base.view_health_patient_form`.** The CMS/ops surface
    opens a client via `doAction` with
    `context: {form_view_ref: 'health_fieldservice.view_health_patient_form_ops'}`
    (`health_fieldservice/static/src/js/ops_client_list.js:212`,
    `ops_client_list_view.js:143`) — a separate primary view (priority 0,
    `js_class="ops_client_profile_form"`) with its OWN `<notebook>`; it does
    NOT `inherit_id` the standard patient form. Its custom OWL template
    (`OpsClientProfileFormView`, `ops_client_profile_form.xml:154`) still
    renders that view's arch via `<t t-component="props.Renderer" …
    archInfo="archInfo"/>`, so a `<page>`/`<widget>` added by inheriting the
    OPS view DOES render — but a page added to the STANDARD form appears only
    in that view's `get_view()` and never on the user's screen (health_twin's
    Trends tab shipped invisible until it also inherited
    `view_health_patient_form_ops`; the pre-existing health_vitals
    Vitals/Alert-Thresholds tabs are still masked for the same reason). Rule:
    to add a tab/field to the client chart users actually use, inherit
    `health_fieldservice.view_health_patient_form_ops` (in addition to the
    standard form if you want both surfaces). Verify by which view renders on
    the CMS profile, NOT by `get_view()`. Sibling discoverability trap: the
    clinical-intelligence MENUS (telemonitoring + twin) live under the /odoo
    "Clinical Intelligence" menu but are NOT in the /bizapp CMS sidebar — that
    sidebar is a separate seed (see the noupdate-seed-cutover note). Minor:
    Odoo 19 `res.users` groups write field is `group_ids`, not `groups_id`.

42. **`get_view()['arch']` STRIPS group-gated `<page groups="…">` nodes for a
    caller who isn't a member of the group — so a correctly-merged tab looks
    absent in a test.** `get_view()` runs the post-processing that removes
    nodes the current user's groups exclude; in a TransactionCase the caller is
    SUPERUSER_ID, which is NOT a member of `health_base.group_healthcare_nurse`
    etc., so a `<page groups="…healthcare_nurse">` you correctly added via
    inherit is stripped from the returned arch and an
    `assertIn('name="my_page"', get_view()['arch'])` FAILS despite the view
    being right (health_cms_clinical `test_cms_clinical` — 1 failed on the
    first run). Assert view COMPOSITION with
    `view.get_combined_arch()` (applies inheritance/xpath but does NOT do the
    group node-removal), and prove per-ROLE rendering via the browser evidence
    pack (a real group member sees the tab). Companion to §5.41: §5.41 is
    "which view renders", §5.42 is "get_view lies about group-gated nodes in
    tests". (An `su`/admin caller in tests is a member of NOTHING group-wise
    unless explicitly added — do not assume SUPERUSER sees group-gated nodes.)

- **§5.43 — the twin staleness sentinel gives every patient with NO completed
    visit a constant +5 baseline composite; a twin test that expects a
    "no-signal" patient to score 0 (or that adds a few signals and asserts an
    absolute band) is wrong.** `_upsert_one` (`health_twin_risk.py`) sets
    `days_since_last_visit = _NO_VISIT_SENTINEL` (999) when a patient has no
    completed FSO, and `twin_score.staleness_component(999, threshold) = 100`,
    which at the default `0.05` staleness weight contributes
    `round(100 × 0.05) = 5` to the composite — so a signal-less patient lands
    at score **5 / band low**, not 0, and small added signals cross band
    boundaries ~5 points "early" (e.g. 3 warnings ≈ 21 → +5 = 26 tips into
    `moderate`). This bit `test_02`/`test_05` of `test_twin_history` RED→green
    on the first run (the ENGINE was correct; the test asserts were naïve). Fix
    the FIXTURE, not the engine: either give the patient a recent completed
    visit to zero staleness — `_recent_visit()` helper: create an FSO then
    `UPDATE health_fieldservice_order SET state='completed'` via raw SQL (§5.9),
    which drives `staleness_component → 0` — OR capture the first score
    dynamically (`first_score = row.composite_score`) and assert relative to it
    instead of a literal 0. The sentinel is an intentional low-weight
    attention-nudge (a long-unseen patient deserves a glance); know it perturbs
    band math in any fixture that drives absolute scores.

## 6. Test fixture requirements (or your tests fail on vietuat)

- Patient partners REQUIRE `catchment_province_id` (search existing
  province/facility first, create fallback — see any spine test file).
- `health.fieldservice.order` REQUIRES `facility_id + patient_id +
  scheduled_datetime`.
- FSO stage gates require `assigned_staff_ids` before
  `action_start_service`, and the current user needs an `hr.employee`.
- External HTTP is blocked in tests (geocoding warnings in the log are
  normal noise).
- Tag test classes `@tagged('post_install', '-at_install')`.

## 7. Cross-module service interfaces (build on these, don't reinvent)

- `env['health.observation'].create_coded(patient_id, loinc_code, value,
  uom=None, fso_id=None, effective_datetime=None, performer_id=None,
  source='manual', note=None)` and `create_panel(...)`;
  `env['health.vitals.type'].get_by_code(code)` (LOINC or short code).
- `env['health.consent'].check_consent(partner_or_id, consent_type,
  scope=None, at_date=None) -> bool` — NEVER raises, logs evidence;
  `require_consent(...)` raises AccessError only when ir.config_parameter
  `health_consent.enforce` is truthy (default log-only);
  `check_consents(partner, [types]) -> dict`. Types: service,
  data_sharing, photography, emergency_treatment, marketing.
- `env['health.evv.event'].append_event(fso, vals)` — append-only
  hash chain; canonical JSON recipe is mirrored byte-identical in JS
  (`healthEvvCanonical`) — change one side, change both.
- Gateway auth: `_gateway_authenticate(request)` → `(user, scopes)`
  in health_api_gateway/controllers/gateway.py; FHIR serializer registry
  in health_fhir_core/models/ (one serializer class per resource).
- Facility links: employee → `healthcare_facility_id`;
  client → `res.partner.primary_facility_id`.

## 8. Definition of done (EVERY phase — no exceptions)

Implementation sessions are kicked off with the canonical prompt in
`docs/strategy/KICKOFF-TEMPLATE.md` — keep that file and this section in
sync when either changes.

1. All new/changed module tests pass on **vietuat**: the log shows
   `0 failed, 0 error(s)` for your test tags, AND the earlier-module
   tests you may have touched still pass.
2. Server healthy after final restart: `/web/login` returns HTTP 200.
3. PWA version bumped per §3 if anything PWA-facing changed; verify the
   served shell shows the new version.
4. `vi.po` present and covering user-visible strings.
5. If anything user-facing changed: a **browser evidence pack** committed
   to `docs/strategy/reports/<phase>-evidence/` — the exact real-user
   navigation path (click by click, from the normal entry point, NOT a
   deep link that skips the flow), a screenshot per key state, the full
   console log per screen (pre-existing errors flagged), and the
   server-side rows the action created. QA fixtures deleted + fresh-cursor
   verified (§5.34).
6. All code committed on branch `19.0` and **pushed**, message format
   `feat(<area>): <summary>` with body, ending:
   `Co-Authored-By: <your model name> <noreply@carejiox.com>`.
7. Final report states: what was built (file list), every deviation from
   the handover design with reasoning, test results verbatim
   (x/x passed), anything deferred, and any new gotcha discovered
   (so it can be added to §5). The full report is COMMITTED to
   `docs/strategy/reports/<phase>-report.md` alongside the change (the
   reviewer reads it from the repo) and also pasted in the reply.

### 8.1 Reviewer browser pass — selective, not additive (token economy)

The implementer's browser evidence pack (DoD item 5) exists so the
**reviewer does not re-drive the whole UI** — driving the browser is
token- and image-heavy, and it belongs on the cheaper model. The reviewer:
1. READS the evidence pack (cheap: a few images + logs) and, critically,
   checks that the stated navigation path is the one a **real user takes** —
   the classic implementer blind spot is testing via a working deep link
   that skips the buggy flow (that is exactly how the Phase-1 telemonitoring
   vitals-FAB-unreachable bug hid from Opus's own green smoke-check).
2. Re-drives the browser **only selectively** — risky/ambiguous surfaces,
   money/PHI/security paths, or when the pack looks off or the path looks
   evasive.
Do NOT re-run a full independent drive on top of the pack — that pays the
expensive-model browser cost twice and erases the saving. The saving only
exists if the reviewer's pass is review-of-evidence + targeted re-drive.
For a backend-only phase the pack is trivial/absent and this whole step is
a no-op.
