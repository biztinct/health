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
  health_careplan/i18n/vi.po).
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
5. All code committed on branch `19.0` and **pushed**, message format
   `feat(<area>): <summary>` with body, ending:
   `Co-Authored-By: <your model name> <noreply@anthropic.com>`.
6. Final report states: what was built (file list), every deviation from
   the handover design with reasoning, test results verbatim
   (x/x passed), anything deferred, and any new gotcha discovered
   (so it can be added to §5).
