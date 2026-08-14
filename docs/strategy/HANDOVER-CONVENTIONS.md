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
    --stop-after-init --workers=0 --http-port=8169 \
    --logfile=/tmp/gb/<mod>.log"; echo EXIT:$?; \
  sudo service odoo-server start; sleep 12; \
  curl -s -o /dev/null -w "HTTP:%{http_code}\n" localhost:8069/web/login'

# 3. results are in the logfile you named (or the server log if you didn't):
ssh VietUcUAT 'sudo grep -a "odoo.tests.result" /tmp/gb/<mod>.log | tail -3'
```

**`--no-http` is GONE from this command and must not come back, and
`--workers=0` is not optional.** Both are load-bearing, for independent
reasons, and having either wrong silently skips an entire class of test:

- `--no-http` leaves no HTTP server for an `HttpCase` to reach.
- `workers = 2` in `/etc/odoo-server.conf` starts a **PreforkServer**, whose
  `setUpClass` has no `.httpd` (§5.75).

With either in place every `HttpCase` in the run dies in `setUpClass`, the
runner counts them as errors, and the process exits 1 with a `FAIL:` count of
**zero** — which reads like unrelated breakage and got ignored for months.
Phase GB found **28 `HttpCase` classes across 15 modules that had never once
executed**, covering portal tokens, family links, self-booking, the PWA API
and the API gateway. Prefer a `--logfile` of your own and a spare
`--http-port`: the shared server log interleaves with the live service, and
8069 may still be draining.

Verify the suites really ran — a green result over zero executed HttpCases
looks identical to a green result over all of them:

```bash
ssh VietUcUAT 'sudo grep -ac "Starting .*Http\|ERROR: setUpClass" /tmp/gb/<mod>.log'
```

Run test commands in the background if your harness supports it; a full
run takes several minutes. If an SSH session drops mid-run the server-side
process usually survives — check with
`pgrep -af "python3.*odoo-bin.*test-enable"` before assuming failure.
When draining workers before `odoo-bin`, anchor the `pgrep` pattern
(`pgrep -c -f '^python3 /odoo/odoo-server/odoo-bin'`) — an unanchored one
matches the `bash -c` wrapper running the check and never reaches zero.

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
  `health_pwa_family/tests/test_pwa_family.py`,
  **`health_pwa_ergo/tests/test_pwa_ergo.py`** (`PWA_VERSION`).
  health_pwa_ergo was missing from this list until Phase GB, so its pin sat
  at `1.9.0` through ten bumps while the shell served `1.19.0` — and because
  it is an `HttpCase`, the procedure in §2 meant it never ran to say so. When
  you add a version pin anywhere, add the file to this list in the same
  commit; a tripwire nobody maintains is a tripwire nobody trips.
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
- Every module ships `i18n/vi.po` (copy the shape from
  health_condition/i18n/vi.po or health_care_command_channels/i18n/vi.po —
  both were repaired to the loader's actual requirements). If the module
  ALREADY ships a Vietnamese catalog under another name (e.g. health_pwa's
  `vi_VN.po`), extend that file — never create a competing second catalog.
  **The filename must be a language code**: `get_po_paths()` only ever opens
  `i18n/vi.po` and `i18n/vi_VN.po`, so anything else is never read at all
  (health_pwa shipped `viVNpo.po` for nine months — 146 translations, 122 of
  them live strings, dead on arrival; merged in Phase GB).
  Per entry you need all three of `#. module:`, the code marker, and a `#:`
  occurrence — see §5.58/§5.67, and note that a **field label is not a code
  translation**: it needs a `model:ir.model.fields,field_description:` (or
  `.selection`, or `model_terms:ir.ui.view,arch_db:`) occurrence instead, and
  giving it a `code:` one makes the catalogue load while the label stays
  English. `health_base/tests/test_i18n_catalogues.py` (G1/G2) enforces all
  of this repo-wide, including that the labels reach the database in
  Vietnamese — run it after any `.po` edit.
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

- **§5.44 — an Odoo 19 `auth='user'` HTTP route answers an UNAUTHENTICATED
    request with a 303 (See Other) login redirect, not 302.** A test that proves
    an endpoint "requires auth" by checking the deny status must include 303:
    `self.assertIn(resp.status_code, (302, 303, 401, 403))` (with
    `url_open(url, allow_redirects=False)` so the raw redirect status is visible,
    not the followed 200 login page). The framework redirects unauthenticated
    `type='http'` requests to `/web/login` with **303**; asserting only 302
    RED-lights a correctly-gated endpoint (hit live in
    `health_pwa/tests/test_pwa_sign_reminder.test_07`, first run). For an
    authenticated-but-unprivileged deny (`_check_api_access` failing on a logged-in
    non-health user) the same endpoint returns a JSON 403 envelope instead — the
    303 is specifically the not-logged-in case.

- **§5.45 — NEVER start a second `odoo-bin` process (e.g. `odoo-bin shell`)
    against `vietuat` while a `-u`/`-i` upgrade run is in flight — it poisons
    the upgrade's registry load and the whole run rolls back with EXIT:255.**
    The deploy in §2 stops the HTTP service and runs a standalone
    `odoo-bin … --stop-after-init` that holds the database. Launching a
    concurrent `odoo-bin shell` (e.g. to clean up a QA fixture mid-deploy)
    races that process: the symptom is a burst of `odoo.sql_db: bad query` on
    internal tables (`filter_registry`, `ir_module_module`) followed by
    `odoo.registry: Failed to load registry` + `CRITICAL … Failed to initialize
    database` and the run exits 255 — even though `service start` afterwards
    brings the server back up at HTTP 200 (masking it if you only check the
    curl). Confusingly, module *data* that committed before the crash (a
    version bump, config params) may still show applied, but the TEST phase
    never reports a result line. Fix: do all DB-touching cleanup (QA-fixture
    unlink, shell pokes) either BEFORE stopping the server or AFTER the deploy
    run fully returns; keep exactly ONE odoo process on the DB during a deploy.
    Always confirm the deploy by the `odoo.tests.result` line + `EXIT:0`, not
    just HTTP:200. (Hit live during the emr-phase1.7 reachability fix deploy.)

- **§5.46 — the BHYT §2.2 coverage kernel clamps only `total` for a negative
    eligible amount, NOT `covered` — so `coverage_split(-500, 80)` returns
    `(-400, 400)`, not `(0, 0)`.** `coverage_split` computes
    `total = _round(max(0, eligible))` but `covered = _round(eligible*rate/100)`
    from the RAW (un-clamped) eligible, so a negative input yields a negative
    `covered` and a compensating positive `copay`. The money invariant
    (`covered + copay == clamped total == 0`) still holds, so downstream totals
    never leak đồng — but the split is nonsensical for a negative. Harmless in
    Phase 1: `eligible_amount` is always an invoice `price_subtotal ≥ 0`. The
    bhyt-phase1 handover's own worked-vector said `(-500,80)→(0,0)`, which is
    what a naïve reader EXPECTS but NOT what the verbatim kernel does — the test
    must assert the true behavior (`sum(cs(-500,80))==0` AND `==(-400,400)`) so a
    real transcription slip is still caught. **RESOLVED at review (Fable, kernel
    owner):** rather than wait for Phase 2, `covered` is now clamped into
    `[0, total]` (`covered = max(0, min(covered, total))`), so a negative /
    credit-note / adjustment line nets `(0, 0)` and the split can never
    understate the BHYT bill or overcharge the patient. The §2.2 handover block +
    the kernel test now assert `(-500,80)→(0,0)`. General rule (the lasting
    lesson): a "clamp" that guards only the aggregate (`total`) does not protect
    the per-component split — clamp EACH component a sign-flip can corrupt, and
    when a worked-vector and the kernel code disagree, fix the code to match the
    documented intent, not the test to match the buggy code. (bhyt-phase1 review.)

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

- **§5.47 — a multi-model export is fragile to any ONE compartment model with a
    missing/absent `ir.model.access`: the whole operation 403s even with zero
    rows.** Hit live in fhir-everything: `health.fall.risk` (FHIR Flag) ships
    with NO ACL for any group, so `search_count` raised `AccessError` and would
    have killed the entire `$everything` bundle. Pattern for any operation that
    composes reads across N models (exports, bundles, dashboards): wrap the
    per-model read in `except AccessError` (ONLY AccessError — never blanket
    `Exception`), OMIT that model, and DECLARE the omission to the consumer
    (in FHIR: an OperationOutcome `warning/suppressed` entry) — the authz
    counterpart of "no silent truncation". Corollary flagged (not yet fixed):
    the Patient serializer bulk-reads group-gated `res.partner` fields
    (`credit_limit`, `signup_type`), so a token whose service user lacks the
    accounting group can 403 on ANY Patient serialization — a pre-existing
    facade quirk; catch it if a non-admin-grouped service user is ever issued.

- **§5.48 — an `ir.config_parameter` set from a separate `odoo-bin shell` is
    NOT seen by the running HTTP workers until a restart** — the param is read
    through a per-worker `ormcache`, and a write from another process does not
    invalidate the workers' caches. For QA that toggles a param (e.g.
    `consent_enforced`): set it via the shell, RESTART (or reload) the server,
    run the probe, set it back, restart again. Sibling of §5.32/§5.45 —
    cross-process state on a live server is never seen "for free".

- **§5.49 — a downstream module registering a new serializer into
    health_fhir_core's shared REGISTRY breaks any test that hard-asserts an
    EXACT capability/facade resource COUNT — and one such test lives OUTSIDE
    health_fhir_core.** The compartment/capability machinery is registry-driven
    and correct (adding a serializer is a legitimate +1), but a cross-module
    `assertEqual(len(listed), N)` is brittle coupling. health_condition's
    Condition registration took the CapabilityStatement 20 → 21 and RED-lit
    `health_fhir_terminology.tests.test_terminology.
    test_codesystem_serializer_and_capability` (`assertEqual(len(listed), 20)`)
    — NOT a health_fhir_core test, so a grep scoped to fhir_core misses it
    (the condition-spine handover §1 claimed "no test asserts an exact count",
    grep-verified only in fhir_core). Rule: when a phase adds a serializer,
    grep EVERY module's tests for an exact facade/capability count
    (`len(listed)`, `== <N>` near `build_capability`/REGISTRY) and relax them to
    `>=`. Editing that one test line is a FORCED sanction-list deviation —
    declare it; there is no way to register a resource without the count moving.
    (Hit live in condition-spine; fixed 20 → `assertGreaterEqual(…, 20)`.)

- **§5.50 — a test fixture that reuses a real SEEDED record inherits its live
    field values; assert on stable identifiers, never on mutable display
    text.** Portal-4E's fixture called the get-or-create ICD-10 helper, which
    on vietuat returned the SEEDED I10 whose `display_vi` is "Tăng huyết áp vô
    căn (nguyên phát)" — not the fixture's own literal — so
    `assertEqual(label, 'Tăng huyết áp vô căn')` red-lit on the server while
    passing on any fresh DB. Same family as the condition-spine test_09 first-
    run red. Rule: when a fixture may resolve to seeded/live data (any
    `.get()`/search-or-create helper), assert the stable code plus a substring
    of the display, never exact display text; and never overwrite the seed's
    text from a fixture. (Hit live in portal-my-health test_01, relaxed to
    code + substring.)

- **§5.51 — Odoo's libsass mangles data-URI `url()` mask icons in `.scss`;
    ship them in a plain `.css` file.** A `.scss` full of
    `--m:url("data:image/svg+xml,...")` compiles under dart-sass but Odoo's
    libsass fails with "Style compilation failed" and the whole page renders
    unstyled. Put the `.ic-*{--m:url(...)}` rules in `static/src/css/*.css`
    loaded before the `.scss`; keep only nesting/tokens in scss
    (advanced_pricing already follows this split). (Hit live in
    health_care_command — shipped unstyled until the split.)

- **§5.52 — a full-screen OWL client action must NOT use
    `position:absolute; inset:0` on its root.** Under the /bizapp CMS shell
    the action host is not a positioned ancestor, so `inset:0` escapes to the
    viewport and the left edge hides behind the CMS sidebar. Use
    `display:flex; width:100%; height:100%` and flow in the content area
    (crm_dashboard does). (Hit live in health_care_command.)

- **§5.53 — `crm.lead.action_mark_spam()` / `action_log_as_lead()` call
    `self.env.cr.commit()`, which Odoo 19's test cursor forbids**
    (`AssertionError: Cannot commit ... inside a test`). Any test that reuses
    these CRM actions must wrap the call in
    `with patch.object(self.env.cr, 'commit'):`. (Hit in care_command T5/T8.)

- **§5.54 — `zalo.message.action_send_message()` is upstream-broken: it
    references the unregistered model `self.env['zalo.api.client']`**
    (only the plain `ZaloAPIClient` class + `get_api_client(env)` exist —
    zalo_message.py:166, zalo_config.py:288). Any real text send KeyErrors.
    Consumers must mock `action_send_message` itself in tests, and outbound
    Zalo cannot work in production until health_zalo is fixed. (Found by
    care_command Phase 1; fix belongs in health_zalo.)

- **§5.55 — `try/except` around a create() does NOT protect the host
    transaction from a database-level error: wrap ingest hooks in
    `cr.savepoint()`.** If the caught exception is an IntegrityError (e.g. a
    unique index firing on concurrent double-delivery), the PostgreSQL
    transaction is already aborted — every later statement in the host flow
    (the webhook's own commit included) then fails with "current transaction
    is aborted" even though Python caught the exception. Exception-isolated
    hooks must run the guarded body inside `with self.env.cr.savepoint():`
    inside the try. (Care-command Phase-1 review finding, fixed pre-emptively.)

- **§5.56 — mail tracking messages post at precommit (Odoo 17+); a
    TransactionCase never commits, so tracking looks silent in tests.** To
    assert on chatter tracking (e.g. `owner_id`/`status` tracking=True), flush
    the callbacks explicitly: `self.env.flush_all()` then
    `self.env.cr.precommit.run()`. (Care-command T23; helper `_flush_tracking`
    in test_care_command.py.)

- **§5.57 — `_read_group` returns tuples `(group_value, *aggregates)`:**
    a Selection groupby yields the raw value, a Many2one yields a recordset,
    counts come via the `["__count"]` aggregate, and NULL groups come back as
    `False`. Don't expect the old `read_group` dict shape. (Care-command
    Phase-2 workspace counts.)

- **§5.58 — a hand-written `.po` without `#. odoo-python` /
    `#. odoo-javascript` markers is silently INERT for code translations on
    Odoo 19.** The loader (`odoo/tools/translate.py` `_load_python_translations`
    / `_load_web_translations`) keeps only entries whose comments contain
    those exact markers — a po with just `#. module:` comments ships, installs
    without warning, and translates nothing in Python `_()` or JS `_t`/QWeb.
    Put the right marker(s) above every entry (both when a term appears in
    both worlds); clone the style from health_voip24h/i18n/vi.po. Known
    pre-existing offender: health_family_messages/i18n/vi.po (fix on next
    touch). (Hit live: care-command Phase-2 vi.po shipped inert; annotated in
    review.)

- **§5.59 — verify the target model's actual field names before writing an
    act_window domain (or any cross-module field reference) into a handover;
    never trust prose.** The care-command Phase-3 handover specified a Consent
    action domain on `health.consent.partner_id` — but the model's patient
    field is `client_id` (health_consent.py:69); no `partner_id` exists. The
    literal domain would have opened a broken/empty view. Implementers: when a
    handover names a foreign field, grep the model first and declare the
    deviation if it's wrong (as Opus correctly did here). Designers: cite
    file:line for every cross-module field, same as for methods.

- **§5.60 — a local variable named `context` that holds a non-dict breaks
    Odoo 19's `_()` with `AttributeError: 'str' object has no attribute
    'get'`.** `odoo/tools/translate.py`'s `get_text_alias` → `_get_lang(frame)`
    walks the CALLER's frame locals looking for a language: it reads
    `local_context.get('lang')` where `local_context` is whatever local is
    named `context` (the idiom being a `self.env.context`-style dict). If your
    method has a local/param named `context` bound to a plain string (e.g. a
    built LLM prompt), the very next `_("…")` in that scope calls `.get('lang')`
    on the string and raises — NOT at the string's creation, but at the
    translation call, so the traceback points at an innocent `_()` (or a
    `UserError(_( … ))`, masking the real error path entirely — hit live in
    care-command Phase-4 where `_complete`'s failure branch raised
    `AttributeError` instead of the intended `UserError`, and `ai_brief`'s
    stamp `_("Generated just now by %s", provider.name)` died). Rule: never name
    a code local `context` unless it IS an Odoo context dict; call prompt/body
    text `prompt`/`body`/`user_message`. (Fixed by renaming to `prompt`;
    care_ai.py.)

- **§5.61 — the Zalo webhook is a TRAP precedent; clone the voip24h webhook
    posture instead.** Three latent defects found during care-command Phase-6
    design (2026-07-22, all pre-existing in health_zalo, none repaired yet):
    (a) `/zalo/webhook` **fails OPEN** — no configured secret → events accepted
    (health_zalo/controllers/webhook.py:130-140), the exact bug we fixed in
    voip24h; (b) it is a `type='jsonrpc'` route, so the HMAC is computed over
    RE-SERIALIZED JSON — providers (Meta especially) sign the **raw request
    bytes**, which only a `type='http'` route + `request.httprequest.get_data()`
    preserves; (c) it calls `.with_delay()` (webhook.py:46) but **no queue_job
    addon exists in ./addons** — the call would crash if that path were ever
    reached. Rule for any new inbound webhook: raw `http` route, fail-closed
    `hmac.compare_digest` verifier on raw bytes (clone
    health_voip24h/models/voip_config.py:422-442), inline cheap processing
    inside `cr.savepoint()` — never with_delay, never jsonrpc, never
    fail-open.

- **§5.62 — adding a default-narrowing clause to a workspace/list service
    default SILENTLY breaks every pre-existing test whose fixtures don't satisfy
    the new default, even tests that never touch the changed field.**
    Care-command Phase 5 flipped `get_workspace_data`'s default from "all open"
    to attention-first (`view="attention"` → `has_channel_activity=True`). Two
    pre-existing tests RED-lit on the first run — NOT the count-shape tests the
    handover sanctioned, but `test_24_workspace_search` (its lead conv carries no
    activity) and `test_25_capped_payload` (its cap+1 fixtures are directly
    created without `has_channel_activity`) — because the new default excluded
    their rows. Both were correct engine behavior; the fix is in the TEST (pass
    the explicit `view="all"` that restores the pre-change scope), never the
    engine. Rule: when a phase adds a default-narrowing domain clause to any
    workspace/list/search service, grep EVERY existing test that calls it with
    no explicit scope and confirm its fixtures satisfy the new default — the
    breakage set is wider than the "assert the counts shape" tests a handover
    usually names. (Hit live in care-command Phase 5; T24/T25 relaxed to
    `view="all"`.)

- **§5.63 — Odoo opens every DB connection at REPEATABLE READ, so a
    TransactionCase can never observe another transaction's later commits — a
    two-worker `FOR UPDATE NOWAIT` contention race is structurally unstageable
    in one.** A second cursor opened mid-test does not SEE the row the test
    transaction created (invisible → 0 rows matched → no lock taken → the
    "success" branch returns), which reads as "the lock doesn't work" when the
    lock is fine — exactly how channel-center CC-A's T85 first failed. Mirror
    trap: a fresh-cursor ORM write against a record created INSIDE the test
    transaction dies with MissingError for the same visibility reason. Also:
    registry test mode / `TestCursor` is entered by **HttpCase only**, so
    `Registry(db).cursor()` inside a TransactionCase really is a separate
    connection, not a savepoint on the test cursor. Test recipes that DO work:
    (a) prove the NOWAIT statement itself by executing it uncontended on the
    test cursor and asserting the row comes back; (b) prove the fresh-cursor
    persist helper end-to-end with a pre-committed row (or one created via a
    second cursor and cleaned up after); leave true two-worker contention to a
    live smoke check the first time the code path runs for real (CC-D rider
    for `_with_refresh_lock`). Corollary: an Odoo context propagates through
    every derived recordset — a fixture that creates through a bypass/internal
    context must re-`browse()` the record before exercising the guard under
    test, or the guard is silently disarmed. (Hit live building channel-center
    CC-A; recipes in docs/strategy/reports/channel-center-phaseA-report.md.)

- **§5.64 — an XML-escaped `<script>` (or any markup) written as literal text
    inside a QWeb template arch is served to the browser RAW, as a live
    element.** CC-B's web-chat demo page printed its embed snippet as
    `<code>&lt;script src="…" data-origin="…"&gt;&lt;/script&gt;</code>` and
    Odoo served an actual `<script>` tag: the widget loaded twice, and the
    second instance read `data-origin="…"` (a literal ellipsis) and built
    `/care_channels/webchat/…/widget.css`, which 404'd with a MIME-type console
    error — the symptom accused the stylesheet, the cause was the snippet. Show
    markup as text with `t-out`/`t-esc` on a value passed from Python, never as
    escaped entities in the arch. Corollaries paid for in the same fix: (a) a
    QWeb template whose root is `<html>` is served with **no doctype**, so the
    browser renders in quirks mode — prepend one in the controller with
    `Markup('<!DOCTYPE html>') + html` (`str + Markup` ESCAPES the doctype and
    ships a literal `&lt;!DOCTYPE html&gt;` — §5.20 again); (b) Odoo serves
    `/<module>/static/…` with `Cache-Control: max-age=604800` and no
    revalidation, so any **embeddable** asset needs a `?v=<module version>`
    stamp or visitor browsers keep the old copy for a week (the §3 PWA rule,
    generalised); (c) a script third parties embed needs an idempotence guard
    and must validate its own `data-*` inputs. (Hit live in channel-center CC-B
    browser QA.)

- **§5.65 — a `UserError` from an RPC rolls back the evidence of the failure it
    is reporting; write that evidence on an independent cursor FIRST.**
    `action_send_channel` must both raise (the agent needs a clean error) and
    remember (failed message row, redacted reason, and for a 401 the
    `authorization_valid = fail` that drops the connection to
    `action_required`). In-transaction writes cannot do both — the dispatcher
    rolls them back with the exception. Pattern (health_emar
    `_persist_interaction_result`, §5.12): a `_persist_*` helper opens
    `Registry(db).cursor()`, sets `SET LOCAL lock_timeout = '2s'`, writes,
    commits and returns True; the caller writes in-transaction ONLY when it
    returns False. It returns False under `--test-enable` on purpose (§5.63: a
    second cursor cannot see the test transaction's records), which is what
    lets the suites assert on the same evidence. Test-side corollary: assert on
    pre-raise evidence with `try/except UserError`, **never** `assertRaises` —
    Odoo wraps it in a savepoint and rolls back every write made before the
    raise (§5.8). (Hit live in channel-center CC-B.)

- **§5.66 — derived readiness plus a state-gated ingest can lock a channel out
    of the very traffic that would prove it.** CC-B's ingest gate is
    `{ready, expiring, testing, configuring}`, but `state == 'ready'` is
    DERIVED from the readiness checks: the first inbound on a `testing`
    connection whose required checks are not all `pass` flips it to
    `action_required` — which is not ingestable, so later traffic is dropped
    until a human finishes setup. Whenever a state machine both (a) gates an
    input and (b) is recomputed BY that input, walk the loop explicitly. Here
    the spec's gate was implemented as written and the ordering constraint
    handed to the UI phase (the stepper must complete its checks, or park the
    connection in `configuring`, before pointing a provider at us); the
    alternative — letting `action_required` ingest — reopens the "a disabled
    channel keeps filling the inbox" hole the gate exists to close.
    **RESOLVED CC-C (amendment F1): `testing` no longer demotes on missing
    checks.** `_recompute_ready` now separates "a required check FAILED" from
    "a required check has not happened yet": any `fail` ⇒ `action_required`
    from every recompute state (unchanged); all pass ⇒ `ready` (unchanged);
    merely missing/pending/`n_a` ⇒ a `testing` connection STAYS in `testing` —
    still ingestable, still not sendable — while `ready`/`expiring` keep the
    old demotion (a required check cannot go missing there except by
    deletion). The general rule stands: when a state machine both gates an
    input and is recomputed by that input, walk the loop explicitly, and make
    sure the state that means "being proven" survives its own evidence
    arriving. (T96 stages the exact §5.66 sequence.)

- **§5.67 — a hand-written `.po` entry with no `#:` OCCURRENCE line is read by
    NOTHING; the comment markers of §5.58 are necessary but not sufficient.**
    Odoo's `PoFileReader.__iter__` yields one row per entry *occurrence*
    (`for occurrence, line_number in entry.occurrences:` —
    odoo/tools/translate.py:849) and has no fallback branch: an entry with the
    right `#. module:` comment (§29) and the right `#. odoo-python` marker
    (§5.58) but no `#: …` reference produces **zero** rows, so
    `_load_python_translations` / `_load_web_translations` / the model-term
    loader never see it. The file installs silently and translates nothing.
    Hit live in channel-center CC-C: `health_care_command_channels/i18n/vi.po`
    had 182 entries and **0 occurrences** — the whole CC-A + CC-B Vietnamese
    catalogue had been inert since it shipped, and the one CC-C test that
    spot-checked a RUNTIME translation is what exposed it (`_('Connected')`
    under `lang='vi_VN'` returned `'Connected'`). Required shape per entry:
    `#. module: <mod>` + the code marker + `#: code:addons/<mod>/<file>.py:0`
    (Odoo's own `.pot` files use a literal `:0` — the line number is unused for
    code translations). Model/field/selection/menu labels need a *model*
    occurrence instead, e.g.
    `#: model:ir.model.fields.selection,name:<mod>.selection__<model>__<field>__<value>`
    or `#: model:ir.ui.menu,name:<mod>.<menu_xmlid>` — verify the xmlid exists
    in `ir_model_data` first. **Every hand-written catalog in this repo is
    affected** (`grep -c '^#:' addons/*/i18n/*.po` returns 0 for all of them) —
    fix module by module on next touch. Assert it in tests: every non-header
    block contains `\n#: `, and every block with a code marker contains
    `#: code:addons/<mod>/` (health_care_command_channels/tests/test_center.py
    `test_105`). Verify live with
    `code_translations.get_python_translations(mod, 'vi_VN')` in a shell — a
    length of 0 is the symptom (118 python + 48 web after the fix).

- **§5.68 — libsass evaluates CSS math functions as SASS functions, and ONE bad
    rule fails the WHOLE bundle's scss compilation, shipping every co-bundled
    module unstyled.** `width: min(560px, 100%)` — ordinary, valid CSS — makes
    Odoo's libsass raise `Internal Error: Incompatible units: '%' and 'px'`
    (SASS has its own `min()`), and the failure is NOT scoped to the offending
    file: `assetsbundle` logs a single WARNING and emits the bundle with **all**
    scss dropped, so a sibling module's stylesheet disappears too (measured on
    vietuat: `web.assets_web.min.css` fell from 2.19 MB to 40 KB and
    `.o_care_command` vanished from it — Care Command rendered unstyled because
    of a rule in a different addon). Sibling of §5.51 (data-URI `url()` in
    scss); same remedy family — keep CSS-native constructs out of `.scss`. Use
    `width:100%; max-width:560px`, or interpolate to hide it from the compiler
    (`#{"min(560px, 100%)"}`). Grep every new `.scss` for `min(` / `max(` /
    `clamp(` before deploying, and VERIFY the compile rather than assuming:
    `python3 -c "import sass; sass.compile(filename='…scss')"` on the server,
    then regenerate the bundle
    (`env['ir.attachment'].search([('url','like','/web/assets/%')]).unlink()`
    then `env['ir.qweb']._get_asset_bundle('web.assets_web', css=True, js=False,
    assets_params={}).css()`) and assert your selector AND a known-good sibling
    selector are both present. A green test run does not cover this — nothing
    in the test suite compiles the asset bundle. (Hit live in channel-center
    CC-C.)

- **§5.69 — a backend `menuitem` is NOT a reachable surface for the users who
    live in the /bizapp CMS shell; seed a `cms.sidebar.item` too, or the feature
    is deep-link-only.** CC-C shipped its Center as an `ir.actions.client` plus
    a menuitem under `health_care_command.menu_care_command_config` — correct,
    group-gated, and **visible to the user server-side** (an `ir.ui.menu` search
    as that user returns it). It was still unreachable: a real login lands in
    `/bizapp`, `https://…/odoo` redirects straight back into it, and the shell's
    app switcher lists only its own apps (on vietuat: *Viet UC CMS* and
    *Workflow Automations*), so the whole "CRM Center → … → Channel Center"
    path does not exist for that persona. This is §5.41's sibling trap with a
    price tag: the phase's entire deliverable was reachable only by deep link,
    which the DoD explicitly rejects as evidence. Fix = a `cms.sidebar.item`
    record (clone `health_care_command/data/cms_sidebar_items_care_command.xml`;
    `health_cms_clinical` is the glue-module precedent). Two traps inside the
    fix, both found by DRIVING the sidebar rather than reading the model:
    (a) seeding the new item as a **child** of an existing one silently breaks
    the parent — `cms_sidebar.js:124` makes any item with children a
    non-navigating expandable group ("leaves navigate"), so Care Command itself
    stopped opening; make it a SIBLING with the next `sequence`;
    (b) **deleting a field from an XML data record does not unset it** — an
    Odoo data update writes only the fields it names, so dropping `parent_id`
    left the old value in place and the item stayed a hidden child through a
    full deploy; write `<field name="parent_id" eval="False"/>` explicitly.
    General rule for every future phase: if the surface is aimed at CMS-shell
    users, the sidebar seed is part of "done", and the browser evidence must
    start from the login page, never from `/odoo/action-<id>`. (Hit live in
    channel-center CC-C browser QA; the telemonitoring and twin menus are still
    unreached for the same reason.)

- **§5.70 — Odoo's `assertRaises` cannot take a TUPLE of exception classes.**
    `odoo.tests.common` overrides `assertRaises` to wrap the block in a
    savepoint, and its implementation calls `issubclass(exception, AccessError)`
    on the argument directly — so the stock-unittest idiom
    `assertRaises((UserError, AccessError))` dies with
    `TypeError: issubclass() arg 1 must be a class` *inside the context
    manager*, which surfaces as a test ERROR that looks like a framework bug.
    When a call may legitimately raise either of two classes (e.g. a record
    rule hiding the row → `AccessError`, vs the explicit method gate →
    `UserError`), use the plain `try/except (A, B): raised = True` idiom —
    which is also the §5.8-safe form when the failure path's side effects must
    survive to be asserted. (Hit in the CC-C review fixes, T107.)

- **§5.71 — a manifest dependency you are told to add may close a loop that is
    invisible from either end.** CC-D's handover specified
    `health_zalo → health_care_command_channels`. The loop is three hops long
    (`… → health_care_command → health_zalo`) and health_care_command's
    dependency on health_zalo is old, undocumented in the channel architecture
    and load-bearing (`_inherit = 'zalo.message'`, hooks.py:27). The symptom is
    NOT an error at the new edge: `odoo.modules.module_graph` logs
    `module <X>: in a dependency loop, skipped`, then
    `its direct/indirect dependency is skipped, skipped` for everything
    downstream, and the run finishes **EXIT:0 with "0 failed, 0 error(s) of 0
    tests"** — a green result line that means nothing ran. Before adding any
    dependency edge, walk the target's own `depends` transitively; and treat
    "0 of 0 tests" as a failure signal, never as a pass. Two corollaries, both
    paid for in the same fix: (a) a **Many2one cannot point at a model from a
    later-loaded module** — Odoo runs an incremental `_setup_models__` after
    each module it loads (`odoo/modules/loading.py:185`), so the comodel must
    already exist by then; where the modules cannot be reordered, join on the
    target's own uniqueness key instead of an FK (CC-D joins `zalo.config` to
    `care.channel.connection` on `(channel, company_id)`, which a partial
    unique index already guarantees is unique); (b) a **migration script
    belongs in the module that loads LAST**, not in the module that owns the
    data — health_zalo could not migrate its own rows because the framework
    models it migrates them into were not in the registry yet. (Hit live on the
    first CC-D deploy.)

- **§5.72 — a source-grep test assertion matches the comment that explains the
    defect was removed.** Both of CC-D's "the old hazard is gone" tests failed
    on their first run against perfectly correct code:
    `assertNotIn('with_delay', inspect.getsource(module))` hit the 410 shim's
    own docstring explaining why `with_delay` was removed, and
    `assertNotIn('Demo Zalo Config', source)` hit the comment describing the
    fake configuration row that had just been deleted. Grep the *callable*
    (`inspect.getsource(cls.method)` — a handler is three lines), not the
    module, and assert on a fingerprint that cannot appear in prose: the
    literal `"'app_secret': 'demo'"` rather than the human-readable name of the
    thing. Same family as ledger §31's "grep cannot see block comments": a text
    search over source proves something about the TEXT, not about the program.

- **§5.73 — the one place a webhook must parse before it verifies, and how to
    keep that safe.** Zalo's developer portal allows exactly ONE webhook URL per
    app (architecture §13), so every tenant OA arrives at the same route and the
    per-OA secret to check the signature against is not known until the payload
    has been read. The safe ordering is: read the RAW bytes → `json.loads`
    **only** to lift the routing key (`oa_id`, falling back to `recipient.id`)
    → resolve the connection → verify `sha256(app_id + raw_body + timestamp +
    per-OA secret)` over the RAW bytes with THAT connection's secret → only then
    decode and ingest. Nothing else in the body may be touched before the
    verification, the routing key must never reach a log line or a response, and
    every refusal (missing signature header, missing timestamp, unknown OA, a
    connection with no secret, wrong mac, unparsable body, empty body) must be
    the SAME bodyless 403 — otherwise the route is an oracle for "which
    Official Accounts live on this deployment". Verified live on vietuat: seven
    distinct refusal classes, all `HTTP 403, 0 bytes`. Replay is bounded by a
    timestamp window (`channel_hub.zalo_webhook_skew_seconds`, default 300 s,
    accepting epoch seconds or milliseconds) because the timestamp is inside the
    signed string and therefore cannot be moved by an attacker, but a captured
    request would otherwise stay valid forever.

- **§5.74 — a row lock and a fresh-cursor write of the SAME row is a
    self-deadlock that PostgreSQL will never break.** CC-A shipped two
    primitives that each looked right alone: `_with_refresh_lock`
    (`SELECT … FOR UPDATE NOWAIT` on the connection row, so two workers cannot
    rotate a single-use refresh token at once) and `_persist_refreshed_tokens`
    (writes the rotated token on an **independent** cursor that commits
    immediately, so a later rollback cannot lose a grant the provider has
    already invalidated). CC-D became their first co-consumer — as the
    handover explicitly instructed — and the combination hangs: releasing the
    savepoint does **not** release a row lock, so the independent cursor's
    `UPDATE` blocks on the caller's own lock while the caller sits
    synchronously waiting for that cursor. PostgreSQL's deadlock detector sees
    no cycle (the outer session is merely *idle in transaction* while Python
    waits), and vietuat runs `lock_timeout = 0` and
    `idle_in_transaction_session_timeout = 0` — so the wait is **indefinite**
    until the worker is killed. Worse than a hang: by then the provider has
    already rotated, so the new refresh token dies unwritten and the grant is
    gone — precisely the disaster the fresh cursor exists to prevent. Rules:
    (a) if a critical section persists through an independent cursor, make the
    section's lock an **advisory** one (`pg_try_advisory_xact_lock(class, id)`)
    — same mutual exclusion, conflicts with no row write; (b) every
    fresh-cursor writer sets `SET LOCAL lock_timeout` (the CC-B send-failure
    writer already did; the token writer did not — copy the whole idiom, not
    the shape); (c) an advisory lock gives up the serialisation error a row
    lock produced under REPEATABLE READ, so re-read anything single-use on an
    independent cursor before spending it (`_committed_secret`). Bonus: an
    advisory key is just an integer, so two-connection contention is finally
    **stageable in a TransactionCase** — §5.63 blocked that only because a
    second cursor cannot *see* an uncommitted row (T125/T126). Never accept a
    lock smoke test whose callable is a no-op: it proves the refusal path and
    nothing about what runs inside the lock. (Found in CC-D review; latent,
    would have fired on the first real Zalo token rotation ~25 h after the
    first tenant signed in.)

- **§5.75 — running `odoo-bin` by hand against the deployment conf makes every
    `HttpCase` suite ERROR in `setUpClass`, and the run exits 1 with zero test
    failures.** `/etc/odoo-server.conf` sets `workers = 2`, so a manual
    `odoo-bin … --test-enable` starts a **PreforkServer**, and `HttpCase`'s
    `setUpClass` reaches for `odoo.service.server.server.httpd.server_port` —
    which only the threaded server has:
    `AttributeError: 'PreforkServer' object has no attribute 'httpd'`. Every
    HttpCase class in the run dies there (16 of them on vietuat, across
    health_family_link / family_messages / portal / pwa_daystrip / pwa_family /
    self_booking / telehealth / workflow_auto), the runner counts them as
    errors, and the process exits **1** even though `FAIL:` count is 0 — which
    reads exactly like "your change broke eight unrelated modules". It did not.
    Add **`--workers=0`** to any manual test run whose surface can reach an
    HttpCase. The trap only appears when the surface is wide: upgrading a
    low-level module (`health_zalo`) cascades post-tests to every module above
    it (75 → 318 on vietuat), which is why a narrowly-scoped run of the same
    code exits 0 and a wide one exits 1. Corollary for reviewers: an EXIT:1
    with `FAIL: ` count 0 is a prompt to read the `ERROR:` lines, never to
    assume either failure or success. (Hit in the CC-D review re-runs; see also
    §5.32, the HttpCase-poisons-TransactionCase sibling.)

- **§5.76 — a second `mock.patch(..., autospec=True)` on an already-patched
    method silently stops binding `self`.** `create_autospec` builds its spec
    from the CURRENT attribute, which on a re-patch is the first patch's mock;
    the result accepts anything, returns the mock's default, and never reaches
    the `side_effect` with the arguments you expect. Symptom: a call you mocked
    with data comes back empty, only in tests that re-arm the mock mid-flow
    (CC-E: 4 red tests, all "a listing with two rows returned none"). Multi-
    stage provider flows re-arm constantly. Patch with a PLAIN FUNCTION —
    `patch.object(cls, '_get', func)` where `func(self, …)` — an ordinary
    descriptor that stacks correctly any number of times. (Found in CC-E.)

- **§5.77 — a fixture timestamp becomes semantic the moment a phase adds a
    time window, and the breakage lands in tests that never mention time.**
    CC-B's canonical WhatsApp/Messenger payloads carried a fixed epoch six
    months in the past. CC-E added Meta's 24 h customer-service window, and
    every pre-existing `action_send_channel` test on those channels would have
    started refusing — correctly. Rule: when a phase makes recency load-
    bearing, grep every shared fixture for an absolute timestamp and make it
    relative to now, keeping an explicit override for tests that WANT an old
    event. Sibling of §5.62 (default-narrowing) and §5.50 (fixtures inheriting
    live values). (Found in CC-E.)

- **§5.78 — a readiness check that can leave `pass` is a traffic kill switch;
    provider-review state must not be wired to one — and `pending` is as
    deadly as `fail`.** `_recompute_ready` sends any required check that is not
    `pass` to `action_required` from `ready`/`expiring` (F1 only protects
    `testing`), and `action_required` is not in `INGESTABLE_STATES` — so the
    webhook still answers 200 while inbound is dropped, and Meta/Zalo never
    retry: the messages are lost. Opus wired Meta's provider-review state to
    `provider_approvals` moving only `pending↔pass` (never `fail`), reasoning
    that avoided the kill switch. **It did not** (CC-E review HIGH-1): a
    transient provider outage on the nightly approvals poll returns an
    `unreadable`/`pending` row, which lowers an *earned* `pass` back to
    `pending`, which demotes a LIVE channel and drops its inbox over a network
    wobble. Two rules, both required: (a) an ADVISORY poll (health cron, a
    Refresh button) must **latch** — once a review-derived check is `pass` it
    is never lowered by that poll again; a genuine loss of capability surfaces
    through the SEND path (`authorization_valid` / a failed send), which is the
    honest source of truth. (b) Only wire the checks that are true
    prerequisites to messaging AT ALL into the readiness gate; an *optional*
    capability (a WhatsApp template, needed only OUTSIDE the 24 h window, which
    has its own gate) must stay informational on the card, or a reply-only
    tenant is locked out of its own inbox forever. Same family as §5.66 (the
    state that means *being proven* must survive its own evidence) and §5.74
    (a safety mechanism that becomes the failure). (Found in CC-E review; the
    test that "covered" it never reached `ready`, so it could not see the
    demotion — a required-check kill-switch test MUST drive the connection to
    `ready` first.)

- **§5.79 — creating ONE `ir.mail_server` silently makes it the sender of
    every outgoing email in the database.** `_find_mail_server`
    (odoo/addons/base/models/ir_mail_server.py) walks the active servers in
    `sequence` order and tries the `from_filter` in three passes — but its
    **step 4 returns `mail_servers[0]` even when nothing matched**, logging
    only `"No mail server matches the from_filter, using … as fallback"`. On a
    database with no other row (which is vietuat: 0 `ir.mail_server` before
    CC-F) the first server anyone creates becomes the global default, so a
    per-tenant mailbox connected in a self-service wizard would start sending
    invoices, password resets and other tenants' notifications. Core provides
    the fix as an explicit hook: override
    `_find_mail_server_allowed_domain()` and exclude the owned rows
    (`domain & fields.Domain('care_connection_id', '=', False)`). The server
    stays fully usable through `send_email(..., mail_server_id=…)` — it is
    simply never *inferred*. A high `sequence` alone is NOT enough: it only
    reorders the fallback, it does not remove the record from it. Same family
    as §5.62 (a default that widens under you) but with a blast radius outside
    the module. (Found while building CC-F; the hazard was designed out before
    it shipped, and T-email asserts the exclusion.)

- **§5.80 — an Odoo `fields.Integer` is an int4, and a "far future" sentinel
    poisons the whole transaction.** `google_gmail_access_token_expiration` is
    a plain Integer holding a UNIX timestamp; a fixture writing `99999999999`
    (a habit that is harmless in Python and in most JSON) raises
    `psycopg2.errors.NumericValueOutOfRange: integer out of range` at flush
    time — which then cascades as
    `current transaction is aborted, commands ignored…` through every later
    statement, so **seven tests error with a message that names none of them**
    and the first traceback is in unrelated bookkeeping (`care.channel.audit`
    failing to write). Rule: epoch sentinels go through `int(time.time()) + n`,
    never a hand-typed run of nines; and when a suite errors in a block with
    `InFailedSqlTransaction`, read *upward* for the first `bad query:` line —
    the real cause is above the noise, not in it. (Hit on the first CC-F run.)

- **§5.81 — "no cron ships for X" is a claim about `ir_cron`, not about the
    repo, and the difference can be a live call to an endpoint nobody has
    verified.** The CC-F handover stated that no cron ships for VoIP24h's CDR
    sync. `data/voip24h_cron.xml` ships **three**, all `active=True`, and
    `ir_cron` id 133 is enabled on vietuat right now. It has simply never
    *done* anything, because `cron_sync_call_history` selects on
    `auto_sync_enabled = True AND state = 'connected'` and there are zero
    `voip.config` rows. That made the facade's create the dangerous line in the
    phase: a row written with the model's own defaults (`auto_sync_enabled`
    defaults **True**) and `state='connected'` would have started calling
    `https://api.voip24h.vn/v1/calls/history` — an unevidenced path — every
    15 minutes. The row is therefore created `draft` with auto-sync off and
    with `api_key`/`api_secret` deliberately EMPTY, because
    `_check_credentials()` refusing to build a client is what actually keeps
    the unverified endpoints unreachable. Rules: (a) verify cron claims with
    `SELECT id, active FROM ir_cron …`, never by reading the addon; (b) when a
    phase creates a row that an existing cron selects on, enumerate that cron's
    domain field by field and write every one of them explicitly — inheriting a
    default is how a dormant integration wakes up; (c) "0 rows today" is what
    makes a live cron invisible, not what makes it safe.

- **§5.82 — a UI branch keyed on a shared MODE hands the next channel its
    neighbour's words.** The Center's stepper screens were written as
    `t-if="state.mode === 'guided_secret' and state.step === 1"` — fine while
    Telegram was the only `guided_secret` channel. CC-E hit the first half of
    this (Zalo's copy would have leaked to any second `oauth_popup` channel)
    and re-keyed those branches to `isZalo`; CC-F closed the other side, where
    `call` joining `guided_secret` would have asked a clinic for a "Bot key"
    and told them to message @BotFather. The general rule: **a stepper branch
    keys on the CHANNEL, never on a capability enum that more than one channel
    can declare** — the enum describes how a flow works, not what to say about
    it. Assert it structurally rather than by eye: grep the template for the
    fingerprint `state.mode === '`, which can appear in a branch condition and
    essentially nowhere else (§5.72's caveat about prose does not bite on a
    string with an operator in it). (Found in CC-E, finished in CC-F, T155.)

- **§5.83 — "0 failed" over a suite that never executed is indistinguishable
    from "0 failed" over a suite that passed, and this repo lived in the first
    state for months.** Phase GB corrected §2 and found **28 `HttpCase`
    classes across 15 modules had never once run** — every test we own for
    public HTTP surface (portal tokens, family links, self-booking, the PWA
    API, the API gateway). Two independent causes had to be fixed together
    (`--no-http`, and `workers = 2` → PreforkServer, §5.75); fixing either
    alone leaves the other. Their signature is an `EXIT:1` whose `FAIL:` count
    is **zero**, which reads like unrelated breakage — so it was routinely
    ignored, and one real defect (health_telehealth's stale CSS pin) was only
    ever found by accident. Generalisation worth carrying past this repo:
    **when a class of test can fail to run, assert that it ran.** A count of
    executed tests is evidence; a count of failures is not. The corrected
    §2 command and its `grep -ac "Starting .*Http"` check are the standing
    form. (Phase GB.)

- **§5.84 — a `.po` whose FILENAME is not a language code is never opened,
    and nothing anywhere says so.** `get_po_paths(mod, lang)` builds exactly
    `i18n/<base>.po` and `i18n/<lang>.po` from `get_base_langs()` — there is
    no scan of the directory, no warning, no log line. `health_pwa` shipped
    `i18n/viVNpo.po`, a correctly-formed 223-entry catalogue with 232
    occurrence lines, dated 2025-10-29; Odoo read none of it for nine months.
    146 of its entries existed in no other file and **122 were strings the PWA
    still emits today**, in the field nurses' primary surface. This is the
    third distinct way a catalogue can be inert (with §5.58's missing marker
    and §5.67's missing occurrence) and the only one where the file itself is
    flawless. Merged into `vi_VN.po` and asserted by
    `health_base/tests/test_i18n_catalogues.py::test_g1c_filename_is_a_language_odoo_reads`.
    (Phase GB.)

- **§5.85 — a field label is NOT a code translation, and giving it a `code:`
    occurrence makes the catalogue load while the label stays English.** The
    three occurrence types travel different roads: `code:addons/<mod>/…`
    reaches `_()` / `_t()` through `code_translations` at runtime;
    `model:ir.model.fields,field_description:<mod>.field_<model>__<field>`
    (and `.selection`, `model:ir.model,name:`, `model_terms:ir.ui.view,arch_db:`)
    reaches the jsonb column via `_load_module_terms` **at upgrade**. Of the
    1,382 inert entries Phase GB repaired, only 492 were code strings — 1,143
    occurrences were model terms, i.e. the labels clinic staff actually read
    all day. Resolve each entry from source rather than pattern-matching:
    a string inside `_()` is code, a string in `fields.X(string=…)` /
    `selection=[…]` / a view arch is a model term, and **a string that is
    both gets both occurrences** (Odoo's own `.pot` files do exactly this;
    `PoFileReader` yields one row per occurrence). Watch three parsing traps
    that make a real string look dead: implicit concatenation across source
    lines (use `ast`, not a regex — Python has already joined it), Odoo 19's
    `self.env._()` form, and `selection=` pairs held in a module-level
    constant. Verify every model xmlid you derive against `ir_model_data`
    before writing it — a guessed reference passes a shape test and still
    translates nothing. (Phase GB; §5.67 is the necessary-but-not-sufficient
    half of this.)

- **§5.86 — an `HttpCase` that authenticates as `admin/admin` is testing a
    fresh demo database, not this one.** All five red tests in `biz_deroute`
    traced to that one literal: four errored in `self.authenticate`, and the
    fifth POSTed the same dead credentials to `/web/login`, got the login page
    re-rendered at 200, and failed as `200 != 303` — reading like a routing
    regression in the white-label layer when routing was never reached. Own
    the user: `new_test_user(...)` in `setUp` (note Odoo 19 defaults its
    password to `login + 'x' * (8 - len(login))`, so pass `password=` or use a
    login of 8+ chars). Corollary for triage: when several tests in one file
    fail with different-looking symptoms, look for the single shared fixture
    before believing you have several bugs. (Phase GB.)

- **§5.87 — the PWA has THREE translation paths and the `.po` is the last one
    consulted, so a correct catalogue can still change nothing on screen.**
    `health_pwa/static/src/js/app.js:35` defines its own `_t()` which tries
    (1) `window.PWAUtils.i18n.vi` — a 460-key hardcoded dictionary in
    `static/src/js/utils/pwa-utils.js`, then (2) `APP_VI_FALLBACK_TRANSLATIONS`
    — 25 more keys hardcoded in app.js itself, and only then (3) Odoo's
    `window.odoo._t()`, which is the one the catalogue feeds. Both dictionaries
    are keyed by the **English string**, so they shadow the catalogue silently
    and per-string. Measured in Phase GB: of 145 strings merged into
    `health_pwa/i18n/vi_VN.po`, **98 were already keys in those dictionaries**
    and only 47 could reach the catalogue at all. Consequences to carry:
    (a) a load-count check, a shape check and a green `get_web_translations`
    all say nothing about whether the PWA renders your translation — only a
    **PWA screenshot** does, and a backend screenshot is not a substitute;
    (b) editing the catalogue alone will not fix a wrong Vietnamese string in
    the app if that string is one of the ~485 dictionary keys — grep both
    dictionaries first; (c) this is §5.85 one layer deeper (a term that loads
    correctly and is then shadowed before it reaches the screen), and the same
    shape to watch for anywhere a client keeps its own i18n table.
    (Found by the Phase GB review, after the phase had already claimed
    otherwise.)

- **§5.88 — a privilege closure computed from the security XML is a claim
    about the ADDONS; the one that governs access is in
    `res_groups_implied_rel`, and on vietuat they disagree.**
    `health_base/security/health_security.xml:23` declares
    `group_healthcare_base → base.group_user`; the live table ALSO holds the
    reverse edge `gid=1 → hid=346`, which no module's XML asks for. So every
    internal user on this database carries the healthcare-base ACLs —
    `health.ews.score` read included — and no amount of narrowing a service
    group's own implications can take that away. Rules: (a) compute closures
    with a recursive query over `res_groups_implied_rel` on the TARGET
    database, never by reading `implied_ids` in source; (b) re-run the query
    after the change lands, because an implication removed from XML survives
    the upgrade unless explicitly cleared (§5.69(b) — `eval="[(5, 0, 0)]"`);
    (c) an audit that says "group X cannot reach model Y" must name which
    edge it measured. The inverted edge itself is an open remediation item,
    deliberately not fixed inside a feature phase. (Phase W2.)

- **§5.89 — `mail.activity` supports MODEL-LESS activities, and they are the
    honest shape for an alert about an absence.** `res_model_id` is
    `required=False`; the `_check_res_id_is_set_if_model` constraint allows an
    empty `res_model` when `user_id` is set; `action_notify()` skips them and
    `_compute_res_name` handles them; they still appear in the systray and My
    Activities. Hanging an alert on a proxy record (the `ir.cron` row, say)
    makes "mark as done" an `AccessError` for the recipient, because activity
    write access is checked against the RELATED document. Caveats measured in
    W2: the dedupe key for such an activity is whatever you search on —
    (user, summary) means changing the watcher param leaves the old user's
    open copy behind. (Phase W2.) **CORRECTED in W2.5:** this entry
    originally claimed a `user_ids[0]` fallback "does not apply the active
    filter". Measured on vietuat, that is wrong on Odoo 19:
    `res.groups.user_ids` honours the CALLER's `active_test` — with the
    relation row present and the user archived it reads `[]` in an ordinary
    context and returns the ghost only under
    `with_context(active_test=False)`. The general rule: the `active_test`
    behaviour of an x2many read is the caller's, not the field's — measure
    it on the target database before writing either "it filters" or "it
    doesn't" into a finding. A `.filtered('active')` guard is still kept in
    `_heartbeat_user()` because a caller CARRYING `active_test=False` would
    otherwise break it — defensive, not corrective. (Phase W2.5.)

- **§5.90 — the §5.83 executed-methods grep is fragile to a digit in a class
    name, one level below where W1 already found it fragile.**
    `grep -ac "Starting .*Http"` misses classes not named `…Http…` (W1);
    `Starting Test[A-Za-z]*\.test_` then silently drops `TestWebLeadsW2`
    because of the `2`. Use `grep -ac "Starting Test.*\.test_"` for the count
    and `grep -ao "Starting Test[A-Za-z0-9]*\.test_[a-z0-9_]*"` for the
    names, and COMPARE the count to the number of methods you expect — the
    comparison, not the regex, is what §5.83 asks for. (Phase W2.)

- **§5.91 — `crm.lead` has THREE standalone primary form views and TWO
    primary search views on this database, and the highest-priority one is
    the one the CMS persona actually opens.** §5.41 stated this for
    `res.partner`; it is worse here: `health_crm.view_healthcare_opportunity_form`
    (priority 1, backend lists + Lead Hub centre),
    `health_landing.view_lead_source_modal` (16, the Source spoke), and
    `health_crm.view_crm_contact_form_crm_center` (50, bound with its OWN
    primary search view by `action_crm_contact_list_native` — the CMS
    sidebar's Contacts). A tab or filter added to "the lead form" reaches
    nobody until it reaches the third one. Before touching any lead surface:
    `SELECT id, priority, inherit_id FROM ir_ui_view WHERE model='crm.lead'
    AND mode='primary'`, then CLICK the surface as the target persona and see
    which arch renders. (Phase W2, found by driving the sidebar — the W2
    handover itself had enumerated only two.)

- **§5.92 — when `/etc/odoo-server.conf` sets `logfile`, `odoo-bin` writes
    NOTHING to stdout: an empty captured stdout with `EXIT:0` means "look in
    the configured logfile", never "no tests ran".** Two independent
    reviewers tripped on this in one day: a
    `odoo-bin … --test-enable … > /tmp/run.log` produced `EXIT:0` and an
    empty file, which reads exactly like a silent no-op. The tests HAD run —
    the result line, the `Starting Test` lines, and every FAIL/ERROR line
    were in `/var/log/odoo/odoo-server.log` (grep them with `-a`, and scope
    the §5.90 executed-count grep to the run's PID, because the log
    accumulates every historical run: `grep -a "<pid>.*Starting
    Test.*\.test_"`). Corollary: `EXIT:0` + empty stdout is NOT evidence of
    success either — only the logfile's `odoo.tests.result` line for that
    PID is. (Phase W2.5 review.)

- **§5.93 — a `search_default_` group-by REPLACES a pivot/graph view's arch
    row groupbys; an action that ships both silently loses the arch
    dimension.** Measured in the browser during W3: an act_window whose
    context carried `search_default_groupby_outcome` erased the pivot arch's
    `catchment_province_id` row and the city axis disappeared. Put the second
    dimension in the arch as another `type="row"` element and ship the action
    with an empty context; and never prove a pivot by reading its arch —
    the search model can override it, so the proof is a browser drive plus a
    context assertion (`assertNotIn('search_default_'…)`). Sibling of §5.42
    ("get_view lies about group-gated pages") and §5.62 ("a default filter
    hides rows you swear you created"). (Phase W3, deviation D2.)

- **§5.95 — archiving the deployment's live rows inside a test transaction
    frees the ORM slot but NOT the index entry, and hides them from nothing
    that reads with `active_test=False`.** `health_care_command_channels`'
    shared fixture archives every `care.channel.connection` in `setUpClass`
    precisely so its own fixtures can take the partial unique index
    `(channel, company_id) WHERE active`. Three hours before the CC-G test run
    somebody drove the Center on vietuat and left an **active** `call` and
    `webchat` connection on company 1. Two pre-existing tests then failed on
    that live data, in two different ways, neither visible in the archive:
    (a) health_voip24h's `_migrate_legacy_connections` looks for an existing
    connection with `active_test=False` — correct, §5.27 — so it FOUND the
    archived row and reported "0 created, 1 already present"; T151b/T152 red
    against perfect code. (b) `test_85` INSERTs an **active** webchat row on an
    INDEPENDENT cursor: the unique index still carries the live row's entry,
    whose tuple this transaction had UPDATEd but not committed, so PostgreSQL
    made the INSERT wait on our XID while our transaction waited on the INSERT.
    No deadlock is reported (the outer session is merely *idle in
    transaction*), vietuat runs `lock_timeout = 0`, and the run hung for **20
    minutes** — with the HTTP service stopped, because `service odoo-server
    start` is downstream of `odoo-bin` in the §2 deploy command. The symptom is
    a logfile that simply stops advancing mid-suite. Rules: (i) a fixture row
    written on an independent cursor must sit OUTSIDE any partial unique index
    it could contend for (`active = false` was enough here — the flag proved
    nothing about the token write under test) and that cursor must
    `SET LOCAL lock_timeout` like every other fresh cursor in the module
    (§5.74); (ii) a test that counts what a migration CREATED must run on a
    company created inside the transaction, never on the deployment's own;
    (iii) a test log that stops advancing is a LOCK, not a slow test —
    `pg_blocking_pids()` names the blocker in one query, and every minute spent
    waiting is a minute the UAT server is down. Sibling of §5.74, §5.63 and
    §5.50. (Hit live in CC-G.)

- **§5.94 — `cms.sidebar.item.match_models` lands in a LAST-WINS index: a
    new leaf that declares a model an existing leaf already owns steals its
    highlight for every action without an `xml_id`.**
    `health_cms_sidebar/static/src/js/cms_sidebar.js:65` builds
    `this._modelIndex[model] = item.id` in catalogue order with no
    duplicate check, and `_resolveActiveItem` falls back to that index
    whenever the current action carries no tag/xmlid it knows. So a
    satellite leaf (a filtered view of `crm.lead`, say) that declares
    `match_models` would hijack Contacts' highlight. Satellite leaves
    declare `match_action_xmlids` only; `match_models` belongs to the
    model's ONE primary surface. (Phase W3, deviation D3.)

- **§5.96 — the many2one dropdown is rendered INLINE, so ANY containment on a
    wrapper that can hold a field makes it look "cut off halfway".**
    `web.AutoComplete` (the popup behind every many2one / many2many_tags /
    tags / char-autocomplete) renders its `<ul class="o-autocomplete--dropdown-menu">`
    inside the field itself as `position: fixed; z-index: 1056` — it is NOT
    portalled into `.o-overlay-container` the way `Dropdown` / `Popover` /
    `DateTimePicker` / `SelectMenu` are, so those are immune and this one is
    not. Declaring `contain: layout|paint|content|strict`, `container-type` /
    `container` (container queries IMPLY layout containment), `transform`,
    `filter`, `backdrop-filter`, `perspective`, `opacity < 1`, `will-change`
    or `isolation: isolate` on ANY ancestor does two things at once: the
    ancestor becomes a stacking context, so z-index 1056 is resolved *inside*
    it and the ancestor paints atomically at its own in-flow slot — every bit
    of markup LATER in DOM order (a notebook page, the next section card,
    x2many rows) paints straight over the open dropdown; and the ancestor
    becomes the containing block for the `fixed` `<ul>`, so ancestor
    `overflow` can clip it and its coordinates start depending on Odoo's
    position-correction pass. Nothing is clipped in the common case: the
    `<ul>` is fully laid out (`scrollHeight == clientHeight`), it is merely
    over-painted, which is why it reads as a clipping bug and gets "fixed"
    per-form forever. Diagnose by walking the ancestor chain for
    `contain`/`containerType`/`transform` — not by hunting `overflow`. Hit
    live 2026-07-30: `.o_inner_group.vu-sec { contain: layout style }`
    (vu_form_engine.scss) broke the Visibility field on the `ir.ui.menu`
    form and every other group card in the product. Fixed by deleting that
    declaration + `health_theme/static/src/scss/dropdown_trap_guard.scss`,
    which neutralises the never-load-bearing traps and lifts the host to
    `z-index: 20` for the ones that ARE load-bearing (the three-column
    workspace ladder needs its container queries). `contain:` in a backend
    stylesheet is now a test failure —
    `health_theme/tests/test_dropdown_trap_guard.py` walks every backend
    bundle in the repo. RULE: never put containment, transform or filter on a
    wrapper that can contain form fields.

- **§5.97 — a focused field must draw exactly ONE boundary; `outline` and the
    focus ring are not additive.**
    Four independent stylesheets in the same backend bundle each had an
    opinion about focus, and they all painted at once: `vu_form_engine.scss`
    gave the control `border-color: primary` + `box-shadow: var(--vuf-sh-ring)`,
    `backend_02_chatter_components.scss` added `outline: 2px solid` at
    `outline-offset: 2px` under `:focus-visible`, `field_indicators.scss`
    added a bespoke `0 1px 0 0` underline shadow, and `health_base.css:651`
    ships a universal `*:focus-visible { outline: 2px solid }`. Three visible
    rectangles on a plain input; on a COMPOUND widget (monetary, many2one)
    four — those draw their box on the WRAPPER (`.o_field_monetary > div`,
    `.o_field_many2one_selection`) while the outline was drawn around the
    naked inner `<input>`, so the two rings crossed. The trap is that
    `:focus-visible` was assumed to be keyboard-only: text inputs and
    textareas match it on a plain MOUSE CLICK too (only buttons/divs are
    click-exempt), so the "Tab-only" ring fired on every click. Fixed
    2026-07-31: `--vuf-sh-ring` is now THE focus indicator repo-wide —
    `0 0 0 1px var(--vuf-primary), 0 0 0 4px rgba(21,101,192,.14)`, a solid
    ring flush against the control's own 1px brand border so it reads as one
    crisp 2px edge (and clears WCAG 2.2 SC 2.4.11's 2px perimeter without a
    reflow-causing border-width change) fading into a halo. Boxed controls get
    `outline: none`; `button`/`a`/`[role=button]`/`.nav-link` keep the outline
    because they have no ring of their own — `button` excludes `.o_input`,
    which is how date fields render. The opt-out from health_base's universal
    rule is scoped to `.o_form_view .o_input` and `.o_cp_searchview input`
    ONLY: a standalone editable list view's cell inputs get no ring from the
    theme, so stripping their outline would leave them with NO focus
    indicator at all. Same trap on split controls: the searchview ring moved
    from `.o_searchview` to the `.o_cp_searchview` input-group wrapper (with
    `border-radius: 6px` so the shadow traces the pill), because a ring on
    the left half alone paints a line straight down the seam to the caret.
    RULE: one control, one ring, one stylesheet — reach for `--vuf-sh-ring`,
    never a fresh `outline` or a bespoke `box-shadow`.

- **§5.98 — flipping a deployment config parameter is a default-narrowing
    change of the §5.62 class, and the tests it breaks are not the tests about
    that feature.** Enforcing `health_fhir_core.consent_enforced` red-lit eight
    tests, none of which mentions consent: they test bundle shape, compartment
    isolation, `_type`/`_since` filters, truncation and an ACL-suppression path.
    They broke because the engine resolves the mode from `ir.config_parameter`
    when the caller does not pass one, so *the deployment's configuration was an
    implicit test fixture*. Two rules: (a) when a phase flips a parameter, re-run
    **every** suite that can reach the code path, not the ones named after the
    feature — and treat a handover's claim that "the suites are green in both
    modes" as a hypothesis to test, not a fact; (b) a test that lets behaviour
    resolve from live configuration is non-deterministic across databases — pin
    the mode explicitly and leave exactly one test asserting that the default
    reads the parameter. Sharpest edge: `test_06_record_rule_isolation` continued
    to PASS under enforcement — for the wrong reason (it asserts `FHIRNotFound`,
    which enforcement also raises). A green test can be destroyed by a config
    change without ever going red. (Phase GC-2.)

- **§5.99 — an `ondelete='cascade'` FK into an append-only *audit* model
    deletes the evidence and never runs the guard.** The §5.30 mechanism, applied
    to compliance logs: `health.consent.check.log` blocks `write`/`unlink` in
    Python and is described in its own docstring as evidence, yet deleting the
    patient removes the rows at the SQL layer. Any model whose purpose is "prove
    what we did with this person's data" needs `ondelete='restrict'` (or
    `set null`) on its subject FK, or the retention guarantee is only as strong as
    the convention that nobody deletes a patient. (Phase GC-2.)

- **§5.100 — an Odoo 19 route with `auth='none'` defaults to `readonly=True`,
    and a broad `except` around a write inside it converts the framework's
    retry into a 500.** `http.py:924`: `default_mode = routing.get('readonly',
    default_auth == 'none')`. The recovery path (`http.py:2246-2255`) depends on
    the `ReadOnlySqlTransaction` *escaping* the endpoint — so any `try/except
    Exception` around the write (an audit row, a counter, a log) eats the signal,
    leaves the transaction poisoned, and the next query dies with "current
    transaction is aborted". All three FHIR data routes had this. **It is
    invisible on a deployment with no read replica**, because
    `registry.cursor(readonly=True)` then returns an ordinary read/write cursor —
    so the bug ships, passes every `TransactionCase`, works in production, and
    detonates the day someone puts a replica in front of it. An `HttpCase` is
    what exposes it, because the test framework hands out a genuinely read-only
    cursor. Rule: any route that writes declares `readonly=False`, and "it is a
    GET" is not evidence that it doesn't write — auditing is a write. (Precedent
    already in the repo: `health_telemonitoring/controllers/ingest.py`,
    `health_web_leads/controllers/web_leads.py`.) (Phase GC-3.)

- **§5.101 — an `AccessError` from the ORM inside an API controller becomes the
    framework's HTML error page, and API clients cannot parse HTML.** The FHIR
    facade translated the *authentication* AccessError but not the one raised by
    the query, so a token whose service user lacked one `ir.model.access` row got
    `<!doctype html><title>403 Forbidden</title>` — with the Odoo user's name and
    id in the body — from a `application/fhir+json` endpoint. Rule for any
    machine-facing controller: catch `AccessError` at the route boundary
    alongside your own error type, and answer in the protocol's error shape with
    a diagnostic in the protocol's vocabulary (the FHIR resource type), never the
    ORM's (the model name, the rule name, the user). Corollary: this is only
    findable with a *minimally-scoped* token — an admin-grouped service user
    never hits it, which is the same blind spot G14 came from. (Phase GC-3.)

- **§5.102 — G14 is a PATTERN, not an incident: any Odoo model with a
    group-gated read surface breaks a minimally-scoped serializer, and
    `hr.employee` is the second one.** `res.partner` gates accounting fields
    behind the accounting group; `hr.employee` goes further and treats **every**
    field outside its public-profile whitelist as private
    (`hr/models/hr_employee.py::_check_private_fields`), raising on `fetch()`
    rather than on access. A blanket "read every stored field" prefetch therefore
    403s the whole resource for exactly the users an API token maps onto. Rule:
    a serializer over ANY model that another module extends with private or
    group-gated fields declares `prefetch_fields`, and the check is
    `fetch(<declared>)` **as a minimally-grouped user**, never as admin — an
    admin-grouped fixture cannot see this bug at all. Corollary for
    `hr.employee` specifically: a custom field added to it is private by default,
    so adding a field to a serializer's output can 403 the resource without any
    change to the serializer's own module. (Phase GC-3.)

- **§5.103 — `fhir.resources` does not validate required-binding membership.**
    Measured on vietuat 8.3.0: `Location(status='not-a-status')` validates clean;
    `meta.lastUpdated='not-a-date'` does not. `validate_resource` checks types
    and cardinality, not ValueSet membership, so runtime validation (C4) and the
    weekly cron (C5) **cannot** catch a wrong status code. The
    `test_fhir_bindings.py` tier is the only thing that does, and any new
    status-bearing resource needs a table there — including emit-only statuses,
    which the `test_66` search-param guard does not see (that is what GC-3 R2
    fixed for DocumentReference and Location). (Phase GC-3.)

- **§5.104 — `continue-on-error: true` rewrites a GitHub Actions step's PUBLIC
    conclusion to `success`, so it destroys exactly the diagnosis it looks like
    it preserves.** A step that fails under `continue-on-error` reports
    `outcome: failure` (visible only inside the workflow, to `if:` expressions)
    and `conclusion: success` (what the API and the run summary show). The first
    version of this gate used it on all four checks plus a verdict step, and
    produced a **red job whose four gate steps all read green** — with the reason
    only in a log that needs repo-admin rights to download. Use it only where the
    signal you want is *which step ran* (a deliberate fallback chain, like the
    three `pip install` attempts here, where a later attempt executing at all
    proves the earlier one failed); never on a check whose result is the thing
    you need to read. Checks should fail hard and in order: the first `failure`
    names the problem and everything after it reads `skipped`. (Phase GC-3.)

- **§5.105 — in a GitHub Actions *container* job, JavaScript actions run on the
    runner HOST, not in the container, so they cannot see container-only paths.**
    `actions/upload-artifact` reported *"No files were found with the provided
    path: /tmp/fhir-conformance.log"* for a file that existed — because the
    `run:` steps that created it execute inside `container:` while the upload
    action executes outside it. The two share exactly one directory: the
    workspace (`$GITHUB_WORKSPACE`). Anything a JS action must read is copied
    there first. The same split explains why `actions/checkout` works (it writes
    to the shared workspace) while a `/tmp` handoff silently does not — and the
    warning it emits reads like "your file is missing", not "I cannot see your
    filesystem", which is what makes it cost an iteration. (Phase GC-3.)

- **§5.106 — `pip install --target DIR` + `PYTHONPATH=DIR` SHADOWS every
    system package pip drags in, and the first casualty is the crypto chain.**
    Conventions §1 already says a pip upgrade of the cryptography chain has taken
    the *server* down; a container is no safer, and `--target` makes it worse
    because `PYTHONPATH` precedes `site-packages` unconditionally — order within
    `PYTHONPATH` is irrelevant, so you cannot "append" your way out of it.
    Installing `pywebpush` into a target dir pulled a newer `cryptography` in
    behind it; the image's system `pyOpenSSL` was built against the older one, and

    ```
    AttributeError: module 'lib' has no attribute 'GEN_EMAIL'
      → import OpenSSL → odoo.addons.base → "Failed to load server-wide module base"
    ```

    killed the run before a single module loaded. Rules: (a) prefer a system
    install (`--break-system-packages`) and only fall back to `--target`; (b) when
    you must use `--target`, **prune it** of everything the environment already
    provides, so only genuinely-new packages are on the path; (c) assert an
    `import` of the shadowed-chain canary (`OpenSSL`) immediately after
    installing, because every later failure will point somewhere else entirely. (Phase GC-3.)

- **§5.107 — a test that builds dates with `fields.Date.today()` against code
    that selects with `fields.Date.context_today()` is a time-of-day flake, and
    on this deployment the window is 22:00–24:00 UTC.** `today()` is UTC;
    `context_today()` is the *user's* timezone — and the superuser that runs
    tests has tz **Europe/Brussels** on vietuat (not Asia/Ho_Chi_Minh, which is
    the surprise). Any equality match on a date therefore disagrees by one day
    whenever Brussels has rolled over and UTC has not. `health_consent`'s renewal
    test passed three times at ≈20:40 UTC and failed at 23:26 UTC on identical
    code. Rules: derive fixture dates with the SAME helper the code under test
    uses; be suspicious of any date equality (`==`) in a test rather than a range;
    and when a test starts failing with no relevant code change, **check the clock
    before checking the diff** — the three green runs and the red one differed by
    nothing but the hour. (Phase GC-3.)

- **§5.108 — a gotcha that lives only in a phase report does not exist for
    the next phase.** Every kickoff prompt points the implementer at
    `HANDOVER-CONVENTIONS.md` and at the phase doc — and at nothing else, so a
    rule written into `docs/strategy/reports/<phase>-report.md` §8 is read by
    the reviewer once and by no implementer ever. Ten entries (§5.98–§5.107)
    accumulated unmerged across GC-2 and GC-3, and live code overtook them:
    `health_consent/models/health_consent_check_log.py` cites "gotcha ledger
    §5.99" against a ledger that stopped at §5.97, so the citation resolved to
    nothing. The merge belongs in the SAME commit as the report — a report
    section named "candidates for conventions §5" is a promise the next phase
    cannot see, and a reviewer's memory is not a distribution mechanism.
    (Phase SH-1.)

- **§5.109 — `./addons/mail` is a stale Odoo-18 snapshot, and every fact you
    read from a vendored core module in this repo is a fact about the WRONG
    program.** `addons/mail/__manifest__.py` says version `1.18` and
    `models/models.py` is 509 lines and still imports `odoo.osv.expression`
    (removed in Odoo 19); the live `/odoo/odoo-server/addons/mail` is `1.19`
    with a 926-line `models/models.py`. Two distinct costs, both paid in
    SH-1: (a) **deployment** — the §2 procedure copies repo modules INTO the
    core addons directory, so a routine `scp addons/mail` would downgrade
    core mail on a running system; never edit, copy, sync or deploy it; and
    (b) **analysis** — SH-1's handover cited `POST /mail/thread/data`
    (`addons/mail/controllers/thread.py:16`) as the reachable primitive for
    the public-ACL hole. That route exists ONLY in the stale copy: live it
    404s, and the Odoo 19 equivalent is `POST /mail/data`
    (`mail/controllers/webclient.py:20`, `auth="public"`), whose
    `["mail.thread", {...}]` fetch param reaches the identical
    `thread.sudo(False).has_access(mode)` gate at `mail_thread.py:5090`. The
    vulnerability was real and the route name was not — an analysis that had
    stopped at "the route does not exist" would have closed a live hole as a
    false positive. RULE: for any claim about core behaviour, read the file
    under `/odoo/odoo-server/addons/`, cite it with the server path, and
    confirm reachability with a live request — the repo's copy of a core
    addon is evidence of nothing. (Phase SH-1.)

- **§5.110 — the way to make an `hr.employee` field readable without an HR
    group is to declare it on `hr.employee.public`, and a Many2many may share
    the relation table because that model is `_auto=False`.**
    `hr._check_private_fields` (`hr/models/hr_employee.py:1134`) treats a
    field as public **iff a field of that name exists on
    `hr.employee.public`** — there is no separate whitelist to edit, and the
    module that must declare it is the one that OWNS the field, not
    `health_base` (SH-1's handover inherited that error from the GC-3 report:
    `healthcare_skill_ids` lives in `health_fieldservice`). Re-declaring the
    same Many2many is safe rather than a duplicate-relation error because
    `Many2many.setup_nonrelated` (`odoo/orm/fields_relational.py:1303-1306`)
    explicitly exempts pairs where the models differ and one of them is
    `_auto=False` — `hr.employee.public` is a SQL view, so the check passes
    and `update_db` no-ops on the existing relation table (no view
    regeneration, no new column). Corollary from §5.24/§5.102: publishing a
    field widens it to everyone who can read the public employee profile —
    that is a decision, and this codebase had already taken it for
    `license_number`, `specializations`, `qualifications` and
    `certifications`. (Phase SH-1.)

- **§5.111 — `service odoo-server stop` does not clear a hand-started
    `odoo-bin shell`, and SOMEONE ELSE's shell will kill your deploy with a
    lock error naming a column nobody has touched in years.** SH-1's first
    deploy died 15 s into `health_base`'s `_auto_init` with
    `psycopg2.errors.LockNotAvailable: canceling statement due to lock
    timeout` on `ALTER TABLE "res_partner" ALTER COLUMN "group_rfq" DROP NOT
    NULL` — a legacy column drop unrelated to the change, so the message
    points at core rather than at anything you did. Then `Transient module
    states were reset`, `Failed to load registry`, `CRITICAL Failed to
    initialize database`, **EXIT:255** — and `service odoo-server start`
    afterwards still answers HTTP 200, which masks the whole thing if you
    only check the curl (§5.45). The holder was a **29-minute-old
    `odoo-bin shell` belonging to a different session working on this
    database**, sitting `idle in transaction` with `AccessShareLock` +
    `RowShareLock` on `res_partner`, `res_users`, `res_company` and
    `ir_model_data`. Rules: (a) before every deploy, drain
    `until [ "$(pgrep -c -f '^python3 /odoo/odoo-server/odoo-bin')" = 0 ]`
    **and** assert `SELECT count(*) FROM pg_stat_activity WHERE
    datname='vietuat' AND state LIKE 'idle in transaction%'` is zero — the
    service stop only kills the service; (b) when a schema statement times out
    on a lock, `SELECT relation::regclass, mode FROM pg_locks WHERE pid=…`
    names the holder in one query; (c) **identify the shell before killing
    it** — `ls -l /proc/<pid>/fd` shows fd 0 (the script it is being fed) and
    fd 1 (where its output goes), which is what distinguishes your own
    leftover from a colleague's live work. SH-1 killed the blocker to get the
    deploy through and only established afterwards, from `/proc/<pid>/fd`,
    that it was **not its own** — an uncommitted transaction belonging to
    another session was rolled back as a side effect. Check `/proc` FIRST.
    (d) Wrap your own piped shells in
    `timeout` and confirm the process is gone afterwards; a console fed from
    piped stdin does not always exit at EOF. Sibling of §5.45 and §5.95.
    (Phase SH-1.)

- **§5.112 — a before/after test that toggles an `ir.rule` measures nothing
    unless you flush AND turn off `active_test`, and on this database
    `base.partner_root` is ARCHIVED.** SH-1's T6.2 — the test whose whole job
    is to prove a new `res.partner` rule widened access by exactly one record
    — failed twice on correct code, for two independent reasons. (a)
    `ir_rule._get_rules` selects from `ir_rule` with **raw SQL**
    (`self.env.execute_query`), so `rule.active = False` sitting unflushed in
    the ORM cache is invisible to it and the rule stays in force; clearing the
    `_compute_domain` ormcache is necessary but not sufficient — `flush_all()`
    first, then `registry.clear_cache()`, then search (§5.9's family). (b)
    `res_partner.active = f` for `base.partner_root` on vietuat (it is
    OdooBot's partner, renamed "Viet Uc Care" by `biz_debranding`), so a plain
    `search([])` carries the implicit `('active','=',True)` and drops the one
    record under test from BOTH sides — use `with_context(active_test=False)`
    (§5.27). Record rules still apply to `read` on an archived record, which
    is exactly why the chatter raised in the first place: a record can be
    invisible to `search` and still be the thing your ACL denies. (Phase SH-1.)

- **§5.113 — `ir.rule` IDS ARE NOT STABLE IDENTIFIERS on `health_fieldservice`,
    so a before/after security snapshot must be compared BY NAME.**
    `health_fieldservice/security/cleanup_rules.xml:5-14` issues ten
    `<delete model="ir.rule">` statements that later files in the same
    manifest recreate, so **every** `-u health_fieldservice` deletes and
    re-creates ten record rules. Measured on the SH-1 deploy: the FSO rules
    renumbered uniformly +55 (4691→4746, 4692→4747, 4693→4748, 4695→4750,
    4698→4753, 4699→4754) with no change in count, name, domain or group
    binding. Two consequences. (a) A reviewer diffing a `rules-before.txt`
    against a `rules-after.txt` by id will see nine security rules apparently
    vanish and nine appear — snapshot and compare on `name` + `domain_force`
    + the group set, never on `id`. (b) It is a standing latent risk: the
    delete/recreate window is real, and a future edit that drops a `groups`
    binding on recreation would silently turn a group rule into a GLOBAL one
    (§5.NN trap in SH-1 §6.1). Any phase upgrading this module should assert
    afterwards that the count of GROUPLESS active rules is unchanged.
    (Phase SH-1 review.)

- **§5.114 — Odoo 19 computes a user's group closure at READ time, so an
    implication edge is live-editable and granting a group NEVER expands its
    closure onto the user.** `res.users.all_group_ids` is a **non-stored**
    compute — `user.all_group_ids = user.group_ids.all_implied_ids`,
    `@api.depends('group_ids.all_implied_ids')`
    (`base/models/res_users.py:446-449`) — not the older Odoo behaviour where
    `UsersImplied.write` materialised implied groups into
    `res_groups_users_rel`. Three consequences, all paid for in SH-2:
    (a) granting `health_base.group_healthcare_doctor` (350) to ten users
    wrote exactly ONE relation row each, and 346 arrived transitively through
    the XML-declared `350 → 346` — so deleting the `1 → 346` edge could not
    strand them; (b) crucially, none of them picked up `base.group_no_one` as
    a **direct** group, which a write-time expansion would have done and which
    would have quietly invalidated `health_user_admin`'s
    `PROTECTED_DIRECT_GROUP_XMLIDS` reasoning
    (`res_users_saas.py:23-28`) for every user touched; (c) the closure that
    governs access is therefore the live `res_groups_implied_rel` graph and
    nothing else — §5.88's rule, now with the mechanism behind it. Remove an
    implication with
    `res.groups.write({'implied_ids': [Command.unlink(id)]})`, **never a raw
    `DELETE`**: the ORM path runs `ir.model.access.call_cache_clearing_
    methods()` and `registry.clear_cache('groups')`
    (`base/models/res_groups.py:180-197`), while a `DELETE` leaves both caches
    serving the old graph until someone restarts — the change looks applied in
    psql and is not applied in the running workers. Corollary for role
    plumbing: `access.role.write({'groups_ids': …})` is the reproducible way
    to change a role, because `_update_users_groups()` is what reconciles the
    role onto its linked users; hand-writing `access_role_res_groups_rel`
    updates nobody and leaves the `granted_group_ids` sync snapshot stale.
    (Phase SH-2.)

- **§5.115 — `ir.ui.menu.search()` does not answer "can this persona see this
    menu"; `_visible_menu_ids()` does.** Measured in SH-2 while proving ten
    doctors had not been locked out: `search([('id','in',menu_ids)])` run
    `with_user()` returned the **identical 5 of 7** menus for a doctor holding
    the gating group AND for three personas that had just lost it, while
    `env['ir.ui.menu'].with_user(u)._visible_menu_ids()` returned **5 and 0**.
    `search` answers a record-rule question; the group gate lives in
    `_visible_menu_ids` (`base/models/ir_ui_menu.py:74-86`), which filters on
    `['|', ('group_ids','=',False), ('group_ids','in', user._get_group_ids())]`
    and then prunes menus whose action no longer exists. Two more traps in the
    same method: it **discards `base.group_no_one` from the group set unless
    `debug`**, so a menu gated only on that group is invisible in normal mode;
    and a parent menu with no action of its own is visible only through a
    visible CHILD, so granting one group can make an entire branch appear or
    disappear. It is `@tools.ormcache`'d on
    `frozenset(self.env.user._get_group_ids())`, so two users with the same
    group set share an entry. Sibling of §5.42 ("get_view lies about
    group-gated nodes") and §5.69 ("a backend menuitem is not a reachable
    surface for CMS-shell users"): three different layers, three different
    ways a permission check answers a question you did not ask. (Phase SH-2.)

- **§5.116 — a `noupdate="1"` seed belongs to the business the moment it
    exists, so a test may assert its stable identity but never its display
    text.** `health_web_leads/data/utm_seeds.xml` seeds `utm_source_tiktok` as
    `tiktok` and its own header says *"noupdate='1': once these rows exist,
    marketing owns their names"* — yet `test_w3_11` asserted
    `record.name == 'tiktok'` on the line directly above the line where it
    asserts the record is `noupdate`. Somebody renamed the row to `TikTok` on
    the deployment and the test went red against perfectly correct code, in an
    unrelated phase's run (SH-2), costing a deploy cycle to attribute. This is
    §5.50 with the noupdate twist that makes it inevitable rather than merely
    likely: `noupdate` is a PROMISE that the value will drift. Assert the
    xmlid resolves, the model is right, and the name matches
    case-insensitively (which is also what the production matcher does —
    `_utm_ids` searches `=ilike`); that still catches the real hazard, an
    xmlid bound to the wrong record. General rule: if a data record is
    `noupdate`, its mutable fields are OUT of the test's contract. (Phase
    SH-2.)

- **§5.117 — a catchment record rule is a DENY-ALL for users whose own
    `catchment_province_id` is NULL, not a pass-through.** The domain used
    across the clinical models is
    `['&', ('catchment_province_id','=',user.catchment_province_id.id), ('catchment_province_id','!=',False)]`.
    When the acting user's field is empty the first leaf becomes
    `('catchment_province_id','=',False)` and the second excludes exactly
    those rows, so the conjunction is unsatisfiable — the user sees zero
    records, forever, with no error. On vietuat 8 of the 10 Doctor-role users
    are in that state (T-012). Two consequences for any phase: (a) granting a
    catchment-gated group is theatre unless you first assert the target users
    *have* a catchment province — assert it in the test, not in the report;
    (b) adding such a rule to a model that currently has none silently
    blackholes every NULL-catchment user who could previously read it, which
    is a lockout dressed as a security fix. (SH-2 review.)

- **§5.118 — a migration keyed on a human-readable name is not
    convergence-safe, and a failed preparatory step must never fall through to
    the destructive one.** SH-2's post-migrate resolved `access.role` by
    `('name','=','Doctor')` and `return`ed on miss — while `migrate()` went on
    to delete the implication row regardless. On any database whose role
    carries a different label (the UI already ships `Y tế: Bác sĩ`) every
    clinician would have lost healthcare access behind a single INFO log line.
    `access.role` rows have no xmlid on this platform, so name matching is
    unavoidable — which makes the *guard* the fix, not the lookup: the repair
    returns a boolean, `migrate()` raises `UserError` when it is False, and
    nothing is changed. Rule: when step N prepares the ground for a
    destructive step N+1, N's failure must `raise`, never `return`. Halting an
    upgrade costs a minute; silently de-authorising a workforce does not
    announce itself at all. (SH-2 review fix.)

- **§5.119 — column-type trap: `res_groups.name` is jsonb, but `ir_rule.name`
    and `access_role.name` are plain `varchar`.** `r.name->>'en_US'` on the
    latter two dies with `operator does not exist: character varying ->> unknown`.
    In a `psql -f` evidence script that kills the offending statement and lets
    the rest of the file continue, so the snapshot is silently INCOMPLETE —
    SH-2 shipped one (`sh-2-evidence/snapshot-before.txt:109`, the whole
    record-rule block missing). Check `psql` exit status per statement, or run
    the snapshot with `ON_ERROR_STOP=1`. An evidence file nobody can trust is
    worse than none, because the next phase quotes it.

- **§5.120 — phase deploy output does NOT land in the service log.** Test runs
    and migration logging go to `/tmp/<phase>/deploy.log` (SH-2's was 1.4 MB);
    `/var/log/odoo/odoo-server.log` contains **zero** `SH-2:` lines. A reviewer
    grepping the service log for the migration's own log statements will
    wrongly conclude it never ran. Also `grep` treats the deploy log as binary
    — use `grep -a`. Verify "the migration ran exactly once" by counting its
    opening log line in the deploy log, not the service log.

- **§5.121 — archiving a `res.users` does not archive its `hr.employee`.**
    SH-2 archived seven accounts; all seven `hr_employee` rows stayed
    `active = t` (ids 38–42, 44, 45), so the people remain assignable in staff,
    roster and FSO pickers while being unable to log in. `res.users.active` is
    a column on `res_users` itself — it does not delegate to the partner
    (which is why the partners correctly stayed active) and it does not
    cascade to the employee. If "decommission this person" is the intent, that
    is three separate decisions: the login, the employee, the partner. Name
    which ones the phase is authorised to make. (SH-2 review.)

- **§5.122 — `service odoo-server start` is a SILENT NO-OP when systemd still
    reports the unit `active (exited)`, and a stale pidfile blocks it a second
    way.** Hit during a live outage on 2026-08-04. The init script is LSB, so
    systemd cannot track the forked master; when the master dies, the unit stays
    `active (exited)` and `/var/run/odoo-server.pid` keeps the dead PID. A bare
    `start` then does **nothing at all** — no new log lines, no pidfile, no
    error, exit status 0 — because (a) systemd treats a start on an already
    "active" unit as satisfied, and (b) `start-stop-daemon --pidfile` sees the
    stale file. Diagnosing this by reading the Odoo log is a dead end: the log's
    last lines are from the *previous* run and look like a clean shutdown.
    **The recovery sequence is `stop` → remove the stale pidfile → `start`** —
    the `stop` is what clears the systemd state, which is the real reason the
    documented convention has always been stop-then-start rather than `start`
    alone. Confirm recovery on the LISTENER (`ss -lntp | grep :8069`), not on
    the service status, which lies. If you need to know whether the application
    itself is broken, run `sudo -u odoo odoo-bin -c /etc/odoo-server.conf` in
    the foreground for 30s: it either serves traffic (the app is fine, the
    problem is daemonisation) or prints the real traceback.

- **§5.123 — a page rendered in a DIFFERENT user's language is untestable
    with English literals.** GL-3's public invite page renders the step copy
    in the *sender's* language (`invited_by_id.lang`), so on a vi-VN
    deployment a test asserting `'Create the app' in body` is green only on
    an English database. Resolve every expectation through
    `with_context(lang=<that user>.lang)` on the same model method the page
    uses, and compare `markupsafe.escape()`d text (the page HTML-escapes).
    Same family as §5.50. (GL-3.)

- **§5.124 — a phase's own browser QA is the next run's live-data fixture.**
    GL-4's QA created a google `channel.platform.app` row; the suite's
    `setUpClass` archives the deployment's rows (§5.95's fix), which switched
    on a correct "archived application ⇒ dead end" branch and red-lit a
    correct HttpCase. A suite that archives the deployment's rows must CREATE
    every row its assertions depend on. And on an append-only / never-deleted
    model, any absolute `active_test=False` count measures the deployment's
    HISTORY — baseline the ids in `setUp` and assert on the delta. (GL-4.)

- **§5.125 — a declaration framework needs a UI affordance per
    (kind, verify, artifact) COMBINATION, not per kind.** GL-2's canvas
    offered "mark" only to `wait` steps; a `do` step with `verify: 'manual'`
    and no inputs is completable only by a mark, so it strands at "to do"
    while the server happily accepts the mark. Zalo's redirect step sat in
    exactly that state from GL-2 until GL-4. Before adding declarations, grep
    the template for which branch renders each combination. (GL-4.)

- **§5.126 — an untrusted `element.click()` on an OWL button can silently do
    NOTHING while a trusted click works.** Verifying UI behaviour with
    `evaluate_script`-driven clicks can "prove" a handler didn't fire (e.g.
    a validation error not rendering) when it renders fine under the real
    click tool. Drive QA with trusted input events. (GL-4.)

- **§5.127 — a phase that GRANTS a group inherits every latent ACL bug on
    every screen that group can now reach, and the ones that bite are in
    other modules' JS.** AH-1's whole job was to give nine business users
    `biz_bi.group_bi_creator`. The module itself was clean; the first thing
    the new audience saw on the phase's own CTA was *"You are not allowed to
    access 'BI AI Provider' (bi.ai.provider) records."* — `biz_bi`'s
    `explore_action.js` fires `orm.call("bi.ai", "is_available")` in
    `onWillStart` **without awaiting it and without a `.catch`**, so the
    rejection reaches the global error handler as a modal, and
    `bi.ai.provider`'s ACL starts one rung higher (`group_bi_modeler`) than
    the group being granted. The bug had existed since biz_bi shipped and had
    never once fired, because the only two accounts on the database holding
    any BI group were both BI *administrators* — a population of two, both
    privileged, is a test fixture, not a test. Three rules: (a) when a phase
    grants a group, enumerate the screens that group newly unlocks and DRIVE
    them as a member of exactly that group — not as admin, and not as the
    next rung up (this is §5.102's blind spot moved from API tokens to the
    UI); (b) a capability *probe* ("is feature X available to me?") must
    never be able to raise — it has an honest answer for every user, and for
    someone who cannot read the configuration table the answer is "no";
    (c) a fire-and-forget `orm.call(...).then(...)` in `onWillStart` has no
    error path at all, so an ACL failure in it becomes a modal on a screen
    that otherwise works perfectly — grep for `.then(` without `.catch(`
    when auditing a newly-reachable component. Fixed additively from the
    granting module by `_inherit`ing the model and catching `AccessError`
    (`biz_bi_cms/models/bi_ai.py`); the caller-side `.catch()` still belongs
    in biz_bi and is still open. Corollary measured in AH-2: the honest "no"
    means the AI box the wizard offers is **hidden for every plain creator**
    even though a usable provider is configured — a capability gate is not a
    bug, but say so in the evidence rather than letting a reviewer read the
    absence as breakage. (AH-1; corollary AH-2.)

- **§5.128 — an append-only log keyed on `res.users` makes a QA persona
    undeletable, and `search()`-based cleanup will not tell you.**
    `bi.audit.log.unlink()` raises (correctly — it is evidence), and its
    `user_id` is a `required=True` Many2one, which Odoo materialises as
    `ON DELETE RESTRICT`. So a throwaway QA account that merely *opens a
    dashboard* can no longer be removed through the ORM, and §5.34's "delete
    your fixtures" needs a raw `DELETE` scoped to that uid before the
    `unlink()`. Check for this class of blocker BEFORE creating a QA persona
    on any module with an append-only log keyed on the user (`bi.audit.log`,
    `bi.ai.log`, `health.evv.event`, `health.consent.check.log`), and record
    the raw delete in the evidence pack rather than leaving an orphan
    account behind. (AH-1, repeated in AH-2.)

- **§5.129 — a `.po` occurrence of the `model:<model>,name:<module>.<xmlid>`
    form works for arbitrary BUSINESS models, not only `ir.*` ones.**
    §5.85 lists the three occurrence *types*; this is the confirmation that
    the model half is not limited to core models —
    `model:cms.sidebar.item,name:biz_bi_cms.item_analytics_hub` correctly
    lands `Phân tích` in the jsonb column at upgrade, and the same works for
    `cms.sidebar.section`. Verify the xmlid exists in `ir_model_data` first
    (§5.67); a guessed reference passes a shape test and translates nothing.
    (AH-1.)

- **§5.130 — a second `odoo-bin` on the SAME database does not have to be
    yours, and its symptom is a serialization error in code that never
    touches the same table.** AH-2's second test run died in
    `setUpClass` with `could not serialize access due to concurrent update`
    on an ordinary `INSERT INTO bi_source … RETURNING id` — a table with no
    unique index and no contention of its own. The row's `model_id` FK takes
    a row-share lock on `ir_model`, and a concurrent
    `-u <module>` upgrade started by **another implementer's session**
    rewrites `ir_model`; under Odoo's REPEATABLE READ that is a
    serialization failure, not a lock wait, so nothing hangs and nothing
    names the real cause. Same run: the post-deploy `service odoo-server
    start` was a silent no-op (§5.122) and `/web/login` answered 500, then
    nothing. Rules: (a) §5.45's "exactly one odoo process on the DB" is a
    property of the DATABASE, not of your terminal — re-check
    `pgrep -c -f '^python3 /odoo/odoo-server/odoo-bin'` immediately before
    `service stop`, and treat a serialization error in unrelated fixture
    code as evidence that somebody else is deploying; (b) confirm recovery
    on the LISTENER (`ss -lntp | grep :8069`), never on `systemctl
    is-active`, which said `active` with no process at all; (c) the
    stop → `rm -f /var/run/odoo-server.pid` → start sequence is what
    actually brings it back. A browser QA session running against the same
    server will show the outage as a 502 burst plus `ConnectionLostError` —
    flag it in the evidence pack, do not attribute it to your own code, and
    re-drive the affected step. (AH-2.)

- **§5.131 — a landing page that composes N reads is only as available as its
    least-entitled compartment, and "the user owns this record" does not mean
    "the user can read what the record points at".** AH-3's hub calls
    `bi.audit.log.get_recents()`, whose last line is `d.workspace_id.name`.
    The `bi.dashboard` read rule grants `('owner_id','=',user.id)` on its own,
    while the `bi.workspace` rule has no such clause — so a dashboard the user
    OWNS can sit in a workspace they cannot read, and that one chip raised
    `AccessError` out of `get_hub_data`, sending the entire Analytics landing
    to the "analytics access has not been set up for your account" state.
    Nothing about it was theoretical: it fired on the first attempt to stage
    the phase's own first-run screenshot, i.e. the moment a workspace was
    group-scoped, which is the ordinary configuration a multi-team tenant will
    reach on day one. This is §5.47 ("wrap the per-model read in
    `except AccessError`, OMIT that compartment, and declare the omission") in
    a UI landing rather than a FHIR bundle, plus a rule-asymmetry lesson worth
    generalising: whenever a record rule grants access through OWNERSHIP,
    every relation that record dereferences is a second, unrelated
    authorisation question, and a helper that dereferences one for display
    will 403 for exactly the users the ownership clause exists to serve. Grep
    any get-my-recent-things helper for `.name` on a Many2one before trusting
    it. (AH-3; fixed in `biz_bi_cms/models/bi_workspace.py::_hub_recents`,
    pinned by `test_ah3_04b`.)

- **§5.132 — a group change made from `odoo-bin shell` is invisible to the
    running HTTP workers until a restart, exactly like §5.48's config
    parameter.** §5.114 is right that `res.groups.write({'implied_ids': …})`
    (and any ORM group write) runs `ir.model.access.call_cache_clearing_
    methods()` and `registry.clear_cache('groups')` — but it clears the cache
    of **the process that made the write**. AH-3 re-granted
    `biz_bi.group_bi_creator` to a QA persona through the ORM in a separate
    shell, saw the row present in `res_groups_users_rel` in psql, and watched
    `has_group()` keep answering **False** in the live workers for as long as
    they stayed up; the hub correspondingly kept hiding the creator CTA. Two
    consequences: (a) any browser QA that toggles a group must restart the
    service between the toggle and the drive, or it is measuring the old
    closure; (b) an audit that "proves" a group change did not take effect,
    without restarting first, has proved nothing. Same family as §5.48
    (ir.config_parameter ormcache) and §5.45 (cross-process state on a live
    server is never seen for free). (AH-3.)

- **§5.133 — a module's own suite being green is a hypothesis about THIS
    database, and `biz_bi`'s is not.** The AH-3 handover asked for
    "biz_bi's own suite must stay green after §4.1/§4.2"; on vietuat it was
    already 5 failed + 1 error before the phase touched anything. The way to
    settle a question like this without guessing is a **pristine baseline
    run**: copy the module's files back from `git show HEAD:` onto the server
    (grep the changed line to confirm the revert took), run the same tag, keep
    the log, then restore and re-run — identical counts and identical failure
    NAMES is proof, and it costs one extra `--stop-after-init` cycle. All six
    are the §5.50/§5.95 family: `biz_bi/tests/common.py` builds its dataset
    over `res.partner`, and this deployment has 77 partners carrying a
    latitude, while `res_country.name` is jsonb (`{"en_US":"Vietnam",
    "vi_VN":"Việt Nam"}`) so a row rule built from `country.name` in the
    caller's language matches nothing in the silver view. Corollary for
    designers: do not write "module X's suite must stay green" into a handover
    without having run it; write "must not REGRESS against a baseline you
    capture first". Corollary for reviewers: three of the six are in the RLS
    suite and every one of them fails **closed** (the restricted user sees
    `None`, never the unrestricted total), so a red RLS suite here is a broken
    fixture, not a leak — but that distinction has to be checked, not assumed.
    (AH-3.)

- **§5.134 — `code_translations.get_web_translations()` returns a
    `ReadonlyDict`, which is NOT a `dict` subclass, so the usual
    `isinstance(x, dict)` guard silently measures the wrong object.** An i18n
    verification script that falls back to `len(x)` on the container reports
    **1 message** for a catalogue holding 83, which reads exactly like "the
    .po is inert" — the fourth distinct way (with §5.58, §5.67, §5.84) to
    conclude a healthy catalogue is dead. Index it directly:
    `get_web_translations(mod, lang)["messages"]` is a tuple of
    `{'id', 'string'}` mappings. Also note the import moved: it is
    `from odoo.tools.translate import code_translations`, not
    `from odoo.tools import code_translations`. (AH-3.)

- **§5.135 — a `post-` migration sees only its OWN dependency closure of
    the registry; use `end-` when you need every installed module.** A
    biz_bi post-migration backfilling many2one metadata filled **27 of 252**
    columns: at post- time `account.move._fields` has no
    `catchment_province_id`, because the health_* module that adds it loads
    *after* biz_bi. Nothing raises — `_fields.get()` simply returns None and
    the loop skips on, so the script reports success and half the data is
    silently untouched. `end-` scripts run in `load_module_graph` STEP 3.5,
    after `registry._setup_models__()` and after every module in the graph
    has loaded (`odoo/modules/loading.py:489-493`); `migrate_module` accepts
    `('pre', 'post', 'end')`. Rule of thumb: touching only your own models →
    `post-`; introspecting `env[other_model]._fields` or `env.get(...)` for
    models you do not depend on → `end-`. Put the logic in a model method so
    it is testable and re-runnable, and have the script be a two-liner.
    (Analytics-hub follow-up.)

- **§5.136 — never name a model method `fetch`, `search`, `read`, or
    `browse` with a non-ORM signature.** `bi.query.cache` defined
    `@api.model def fetch(self, cache_key)`, which shadows
    `BaseModel.fetch(field_names)` — so ANY ORM field read of that model
    (`record.result_json`, a list view, a `search_read`) blew up with
    `operator does not exist: character varying = text[]`, the field-name
    list arriving where a cache key was expected. The model had an admin ACL
    with read=1, i.e. a UI path straight into the crash, and it went
    unnoticed because every caller used the custom method. Renamed to
    `fetch_result`. When adding a helper, check it against `BaseModel`'s
    method names first. (Analytics-hub follow-up.)

- **§5.137 — `int(ir.config_parameter.get_param(key))` is a silent 0 when the
    key does not exist, because `get_param` defaults to `False`, not `None`.**
    biz_bi's export ceiling read
    `try: cap = int(raw) except (TypeError, ValueError): cap = 20000` — which
    looks exhaustive and is not: an ABSENT parameter returns `False`,
    `int(False)` is `0`, no exception fires, and the following `max(1, cap)`
    turned the 20 000-row export into a **one-row** export. It never showed up
    as an error; the xlsx simply had one data row and an honest-looking
    "showing first 1 of N" notice, and the only reason it was caught is that a
    test asserted an exact row count. The same shape bites any integer setting
    (`timeout_ms`, page size, retry count) and is the read-side twin of §5.36
    (which is the write side: a falsy value UNLINKS the parameter, so
    "configured then cleared" lands you right back here). Rule: treat every
    falsy read as "not configured" — `int(raw) if raw else DEFAULT` — and pin
    it with a test that asserts the DEFAULT, not merely a truthy value.
    (records-table RT-1.)

- **§5.138 — an HTML5 drop is REJECTED outright when `dropEffect` and
    `effectAllowed` disagree, and the only symptom is that nothing happens.**
    The Records table accepts two gestures on one target: a new field dragged
    out of the field well (a *copy*) and a header dragged to reorder (a
    *move*). `dragstart` set `effectAllowed = "move"` for the header while the
    shared `dragover` handler set `dropEffect = "copy"`; the browser then
    silently declines the drop — no `drop` event, no console message, no
    visual cue. It reads exactly like a broken handler and it was only caught
    by DRIVING the reorder in a real browser (a unit test on the handler would
    have passed, because the handler is never called). Fix: set
    `effectAllowed = "copyMove"` on the drag source and pick the effect per
    payload in `dragover` —
    `dataTransfer.dropEffect = [...dataTransfer.types].includes('bi/column') ?
    'move' : 'copy'` (`dataTransfer.types` IS readable during dragover, only
    `getData` is blocked). Corollary for evidence packs: the chrome-devtools
    `drag` helper drives the real CDP drag machinery, so it reproduces this;
    a hand-dispatched `DragEvent` sequence does NOT (it bypasses the
    effect negotiation) — so verify drag UIs with the real helper, and use
    hand-dispatched events only to freeze a mid-drag state for a screenshot.
    (records-table RT-1.)

- **§5.139 — a plain HTML table inside a GridStack dashboard tile costs
    super-linear time in the row count; ~50 rows is fine and 500 never
    finishes.** RT-1 saved a Records chart (one row per booking) and dropped it
    on a dashboard. Measured on vietuat, same component, same data:
    **50 rows → 1.8 s**, **500 rows → 133 s**, **1 271 rows → the page never
    became responsive again** (CDP `Runtime.evaluate` timed out for minutes
    while `Page.captureScreenshot` still painted, i.e. the thread was pegged,
    not the renderer). The identical `DataTable` component renders 1 271 rows
    full-width in Explore instantly, so the cost is the TILE, not the table:
    the tile grows with its content, GridStack re-lays out the grid, OWL
    re-renders, the getter re-formats every cell, repeat. Two defences, both
    cheap: (a) memoise the formatting getter on `(envelope, lang)` so a
    re-render is not a re-format; (b) give the widget host a `maxRows` render
    cap (200) with an honest final row stating the overflow — never a silent
    slice. Generalise: any component that can be dropped into a
    resize-observed / auto-layout container needs a bound on its rendered
    node count, and "the query is capped at 5 000" is not that bound. Same
    family as §5.28 (vis-timeline backgrounds); diagnose the same way — a
    main-thread block detector, not the network panel. (records-table RT-1.)

- **§5.140 — `xlsxwriter.add_worksheet()` RAISES on a sheet name containing
    `[ ] : * ? / \`, and a sheet name is usually user input.** Odoo BI names
    the export sheet after the chart, and a chart called `Q1: Revenue [VN]`
    would have 500'd `/bi/export/xlsx` — the crash is in workbook
    construction, so nothing downstream ever runs and the user gets an Odoo
    error page instead of a file. Excel's rules: those six characters are
    forbidden, the name is capped at 31 characters, it may not start or end
    with an apostrophe, and it may not be empty. Sanitise every sheet name
    from user input (`_sheet_name()` in `biz_bi/controllers/main.py`) and pin
    it with a unit test — the same applies to `ir.attachment` filenames built
    from record names, where the offending set is different but the reflex is
    the same. (records-table RT-1.)

- **§5.141 — a `res.users.lang` written from a separate `odoo-bin shell` is not
    honoured by a fresh LOGIN in the running workers, and whether it is
    honoured is a coin toss.** §5.48 (config parameter) and §5.132 (groups) both
    end in "restart the service"; `lang` belongs in the same family, but it
    hides better because a language change *feels* like something a re-login
    must pick up. RT-2 set `lang = vi_VN` on a QA persona from a shell,
    committed, logged the browser out and back in — and got Vietnamese. It did
    the identical thing on a second persona twenty minutes later and got
    **English**, from the same code, with `res_partner.lang = 'vi_VN'` visible
    in psql the whole time. The difference is only which worker served the
    login and whether that worker had already cached that user/partner: the
    first persona had never been read by any worker, the second had been read
    all through the English drive. So the failure is intermittent, which is
    worse than consistent — a vi_VN evidence screenshot can be silently
    English on a re-run of the exact same steps. Rules: restart the service
    between a `lang` write and the drive (never merely re-login), assert the
    language in the page (`document.title`, or a known translated string)
    before you take the screenshot, and prefer flipping the language through
    the UI where a surface offers it. (records-table RT-2.)

- **§5.142 — not every Odoo table has `create_uid`/`write_uid`, and a raw
    `DELETE` against one that does not will roll back the ORM `unlink()`s your
    cleanup script has already printed as done.** RT-2's QA cleanup unlinked the
    widgets, the dashboard and the charts, printed a line for each, then ran
    `DELETE FROM bi_query_cache WHERE create_uid = %s`. `bi.query.cache` sets
    `_log_access = False` (its columns are `cache_key / created_at /
    dataset_id / expires_at / hit_count / id / result_json`), so psycopg2
    raised `UndefinedColumn`, the whole transaction aborted, and **nothing was
    deleted** — while stdout said `widgets unlinked / dashboards unlinked /
    charts unlinked`. A cleanup script's own log is not evidence that it
    cleaned anything; only the fresh-cursor check of §5.34 is, which is
    exactly why that rule exists. Two habits: check
    `information_schema.columns` before writing a raw `DELETE` against a model
    you did not author, and put the raw SQL FIRST (or in its own committed
    step) so an ORM unlink is never the thing a later SQL error undoes.
    (records-table RT-2.)

- **§5.143 — a `bi.query.engine` envelope names its columns `label`, not
    `name`.** `columns_meta` is `{ref, field_id, label, type, role, grain,
    format, selection_labels}` (+ `agg` for a measure, `value_labels` after
    label attachment, `nulled` for a masked one) —
    `bi_query_engine.py:337-373`. `bi.field.name` becomes `label` on the way
    out, so a consumer or a test that reads `column['name']` gets a bare
    `KeyError`, not a wrong value. Assert on `field_id` for identity and
    `label` for display. (records-table RT-2.)

- **§5.144 (CORRECTED by §5.149 — read that one) — Odoo's JS minifier deletes
    whitespace directly after `}`, inside template literals too.** `` `${esc(T("fullLesson"))} · ${mins} ${esc(T("min"))}` ``
    reaches the browser as `Full lesson· 7min`. MEASURED by diffing
    `/web/assets/<hash>/web.assets_web.js` against the `.min.js` beside it: the
    non-minified bundle has the spaces and the minified one does not — so it is
    invisible in development and invisible in code review, and only ever shows
    up as text that looks slightly wrong in production. Never leave a literal
    space after a closing `}`; put it in its own interpolation, `${" "}`. Guard
    it with a test that scans the source, not by remembering
    (`health_learn/tests/test_assets.py::test_01`). (learn Phase 1.)

- **§5.145 — `res.groups.category_id` is gone in Odoo 19; it is
    `privilege_id`.** A `<record model="res.groups">` carrying `category_id`
    fails the whole module install with `ValueError: Invalid field
    'category_id' in 'res.groups'` — and because it happens during data load,
    the traceback names the XML line, not the field, until you read three
    frames up. Use `privilege_id` pointing at a `res.groups.privilege`; this
    repo's is `health_base.res_groups_privilege_healthcare`. Same release also
    renamed `res.users.groups_id` to `group_ids`, which bites in tests that
    create a user. And `<group expand="0">` inside a search view is no longer
    valid arch — one invalid attribute invalidates the entire view.
    (learn Phase 1.)

- **§5.146 — a "translate everything" zipper keyed on FIELD NAME will skip a
    translatable string whose name collides with a structural key.** Merging an
    English and a Vietnamese read of the same records into `{en, vi}` leaves
    pass through keys like `key`, `icon`, `screen` untouched. A flat map of UI
    labels is keyed by CONTENT name, and three of ours — `required`, `correct`,
    `after` — collided with that list, so they shipped as bare English beside
    translated neighbours. Two lessons: zip structural trees and flat prose maps
    with SEPARATE functions, and make the parity test assert that nothing
    arrives as a bare string — a test that walks `{en, vi}` pairs is blind to
    the value that never became one. Also return `''` for an empty
    translatable: `{"en": "", "vi": ""}` is truthy, and every
    `field ? card : ""` in the frontend then draws an empty card.
    (learn Phase 1.)

- **§5.147 — on this UAT box, JS and QWeb template assets invalidate
    INDEPENDENTLY, and the pair you are served can be mismatched.** Observed
    repeatedly while building the Coach: the bundle contained a brand-new
    method while the DOM still rendered the previous template, and later the
    reverse. Every symptom looked like an application bug — a handler that
    "does not fire", state that "does not update" — and cost three wrong
    diagnoses. **Before concluding anything about frontend behaviour on UAT,
    verify what was actually SERVED**: `fetch` the bundle URL from the page and
    grep it for the symbol you just added. If it is missing, the problem is the
    cache, not the code. The reliable flush is
    `delete from ir_attachment where name like '%assets%'` followed by a
    stop/start — `-u <module>` alone is not enough. (learn Phase 2.)

- **§5.148 — a `min()`/`max()` wrapping a `calc()` kills the WHOLE asset
    bundle, and the only symptom is a screen that looks unstyled.** Already in
    this ledger as prose, and it still caught a new module — so it is now a
    test: `health_learn/tests/test_assets.py::test_01b`. Diagnose with the
    bundle SIZE: ~40 KB and starting with `/* ## CSS error message ##*/` means
    a compile failure, and the `css_error_message` content names the offending
    expression. Declare the expression as a CSS custom property; Sass passes
    those through verbatim. (learn Phase 2.)

- **§5.149 — the minifier mis-parses the WHOLE REMAINDER of a template literal
    after an interpolation, not just the space after `}`.** §5.144 got the
    symptom right and the cause wrong, and the incomplete fix produced a second
    bug that took two more rounds to see. What actually happens: once rjsmin
    passes a `${...}`, it treats the following literal text as CODE until it
    re-syncs — so it strips whitespace anywhere JS would allow it. A space after
    `}` goes; so does the space after a full stop, because `people. The` reads
    as property access. `"13 visits across 4 people. The one"` shipped as
    `"…people.The one"` while an identical sentence with no interpolation in it
    was untouched.

    Two consequences:
    * `${" "}` is NOT a general fix. It repairs the space it replaces and
      leaves every later `. ` in the same string broken.
    * **Build prose with concatenation, not interpolation.**
      `N(a) + " visits across " + N(b) + " people. The one…"` is ordinary JS and
      the minifier parses it correctly. Keep template literals for HTML
      structure, where the only text between interpolations is markup.

    Diagnose by fetching the served bundle FROM THE PAGE and reading the actual
    bytes — `fetch(src).then(t => t.slice(i - 90, i + 120))`. Three rounds were
    spent on hypotheses that a single look at the output would have killed.
    (learn Phase 4.)

- **§5.150 — a parent CMS sidebar leaf claims its children's actions, so any
    "which screen am I on" resolver must try the leaf's OWN action first.**
    `cms.sidebar.item.match_action_xmlids` on a parent lists the actions of its
    child leaves, so the sidebar can keep the parent highlighted while a child
    is open. That is correct for the sidebar and wrong for anything that needs
    to know which screen is actually on display: opening **Cash In Transit**
    resolved to **AR Management**, because the parent matched first and both
    were "exact" matches.

    The fix is a pass 0 above the existing exact/broad passes: the leaf whose
    `action_tag`/`action_xmlid` IS this action wins over any leaf that merely
    lists it in `match_*`. Two-pass exact-then-model (§5.147's sibling) is not
    enough on its own — inside "exact" there is still a hierarchy.
    Guard: `health_learn/tests/test_coach.py::test_16`. (learn Phase 4C.)

- **§5.151 — a default that is correct for the section you built first is
    invisible until you build the second one.** Two instances in one phase,
    both shipped green and both wrong:

    * The mission runner resolved a step with no `nav` (a decision, a
      consequence card) to a hard-coded `"carecommand"`. Every CRM mission
      starts there, so it looked right for a year of CRM work; the FINANCE
      refund decision was then asked over the CRM triage wall. Fix: hold the
      last screen the mission navigated to, and give each line its own home.
    * The practice shell titled its screen from a menu that only listed CRM
      leaves, so all nine OPS replica screens rendered a **blank heading**. No
      test failed, because a missing title is empty rather than wrong.

    The pattern: `x || SOME_LITERAL_FROM_THE_FIRST_SECTION`. When a module is
    going to be extended section by section, grep for that shape before
    starting section two, and assert the invariant across sections rather than
    within one (`test_mission.py::test_14` checks that no mission navigates
    outside its own section). Neither of these was caught by tests; both were
    caught by opening the thing and looking at it. (learn Phase 4C.)

- **§5.152 — `assertRaises` as a context manager can discard database writes
    made inside it.** A guard wrote an audit row and then raised; the row was
    present when queried inside the `except` block and GONE from raw SQL
    immediately after the `with self.assertRaises(...)` block closed. No error,
    no rollback in our code, and the identical sequence in `odoo-bin shell`
    wrote the row every time.

    Cause: `unittest`'s `_AssertRaisesContext.__exit__` calls
    `traceback.clear_frames()` to break reference cycles, and clearing those
    frames takes the pending work with it.

    **Rule: when you assert on the SIDE EFFECTS of a call that raises, catch it
    manually.**

        raised = None
        try:
            thing.that_raises()
        except TheError as caught:
            raised = caught
        self.assertIsNotNone(raised)
        # now assert on rows

    Cost four rounds of wrong diagnosis (deferred create, separate cursor,
    exception-in-flight) because every hypothesis was plausible and the shell
    reproduction kept passing. What settled it: querying raw SQL INSIDE the
    except block and again after. (ai_egress.)

- **§5.153 — a field-label match must cover every naming word in the question,
    not merely appear in it.** Schema-driven "what is this field for" answers
    match `ir.model.fields.field_description` against the question. Substring
    matching alone produced confident wrong answers: "what is the activity date
    field used for" matched `calendar_display_name`, whose label is just
    **"Activity"**, and "what does external submission id mean" matched
    `external_event_id`. Each read as authoritative.

    The rule that fixed it: `label in question AND all(word in label for word
    in naming_words)`. A label accounting for one of the two things the user
    named is a miss, and a miss sends them to a person. Also: scope candidate
    fields to the models the SCREEN claims, or "status" matches something on a
    model they have never opened.

    General form — **for a lookup that answers in the product's own voice,
    partial-match fallbacks are a liability, not a courtesy.**
    (learn field lookup.)

- **§5.154 — `sudo()` does NOT change `env.uid` in Odoo 19, so "this audit row
    will say uid 1" is a claim to MEASURE, not one to infer from the code
    shape.** The AH-3 report deferred a defect — *"`bi.ai._log`'s audit
    attribution is uid 1, because `_log` calls
    `self.env['bi.audit.log'].sudo().log(...)` and `log()` reads `self.env.uid`
    from the sudo'd recordset"* — and the BG-1 handover carried it forward as
    item §1.4. It is not true. `BaseModel.sudo()` is documented in the source
    as *"superuser mode does not change the current user, and simply bypasses
    access rights checks"* (`odoo/orm/models.py:5946`): it returns
    `self.with_env(self.env(su=True))`, and `uid` is untouched, so
    `self.env.uid` under `.sudo()` is still the human. Measured on vietuat
    before touching anything: `bi_audit_log` held 29 `ai_request` rows at uid 2
    (a real person) and 7 at uid 1 — and the uid-1 rows are the TEST suite,
    which runs as SUPERUSER. The uid-1 population in an audit table is
    therefore evidence about your test runs, not about your sudo. Two lessons,
    both cheap: (a) settle an attribution question with
    `SELECT user_id, count(*) … GROUP BY 1` on the target database before
    writing it into a handover — a table of who-appears-how-often names the
    real cause in one query; (b) the pre-Odoo-13 mental model where `sudo()`
    swapped the user still travels by word of mouth, and it produces
    confident, wrong findings about audit trails, `default=lambda self:
    self.env.user` fields and record-rule behaviour alike. BG-1 still hardened
    the path (the uid is captured before any sudo scope and passed explicitly
    to both `bi.ai.log` and `bi.audit.log.log(user_id=…)`) because an explicit
    argument survives a future refactor that a re-read of `env.uid` does not —
    but it fixed no live defect, and the report says so. (BG-1.)

- **§5.155 — a stored field maintained by `write()` and an onchange is NOT
    maintained by `create()`, and a queue that selects on it then goes
    silently quiet.** `bi.dashboard.next_send` was computed in
    `_onchange_schedule` and in a `write()` override, and nowhere else. A
    dashboard CREATED with `schedule_enabled=True` therefore kept
    `next_send = False`, and `_process_snapshot_queue` selects on
    `('next_send', '!=', False)` — so its scheduled email snapshot never went
    out, for ever, with no error anywhere. The form view HID it: the onchange
    fires in the client and `create` arrives with the field already filled, so
    only a programmatic create (an import, the AI report composer, a test)
    could see it. This is ledger §5.2 with a price tag, and the tell is
    structural: **any field that a `write()` override maintains is a field
    `create()` must maintain too** — grep your models for
    `def write` overrides that compute a stored value and check each one has a
    `create()` sibling. The test that caught it,
    `TestSnapshot.test_snapshot_xlsx_builds`, had been red on EVERY database
    since it was written and was filed for months as live-data fragility
    (§5.156). (BG-1.)

- **§5.156 — a known-failing set inherits its diagnosis, and the inheritance
    is where the real bugs hide.** Six `biz_bi` failures were characterised in
    the AH-3 report as "the §5.50/§5.95 family — live data on vietuat",
    re-confirmed by name in the RT-1 report, and handed to BG-1 as "FIXTURE
    fragility, not product bugs (they fail closed)". Reproducing them and
    reading each traceback: three were indeed the live-data family (a
    `res.partner` rule hiding the fixture rows, a translated `res_country.name`
    keyed rule, 77 latitude-bearing partners polluting an unscoped aggregate);
    one was a plain **arithmetic error in a test constant** — an expected
    `60.75` that added back a row the pipeline's own filter step removes, red
    on every database that has ever existed; and one was a **real product
    defect** (§5.155) that would never have surfaced on any database either.
    A seventh, `test_relative_filter`, was not in the list at all because it
    only fails between 22:00 and 24:00 UTC (§5.107) and every previous run
    happened in the morning. Rules: (a) re-derive a failure from its OWN
    traceback before accepting an inherited label — "the six" is a set of
    names, not a diagnosis; (b) `git log` on the test constant is cheaper than
    a theory; (c) a suite whose failures are known and tolerated will absorb
    new ones invisibly, which is the argument for spending a phase getting to
    `0 failed, 0 error(s)` rather than maintaining a list. (BG-1.)

- **§5.157 — relative date windows resolve in the CALLER's timezone against
    columns stored in UTC, and the flaky test is only the visible edge of
    it.** §5.107 records the test-side symptom (`fields.Date.today()` vs
    `context_today()`); this is the engine-side one. `bi.query.engine`'s
    `relative_bounds` builds `today`/`this_month` from
    `fields.Date.context_today(self)` — the acting user's tz — and compares
    them against a naive-UTC `datetime` column with no conversion. Three
    consequences worth carrying: (a) a Vietnamese user asking for "today" gets
    the UTC day, i.e. a window shifted seven hours from the one they mean;
    (b) any test using a relative filter is a time-of-day flake, and on the
    LAST DAY OF A MONTH a `this_month` filter flips a month early for the
    Europe/Brussels superuser that runs tests here — pin `tz='UTC'` on the
    fixture's environment so the window means what `create_date` means
    (`biz_bi/tests/common.py`); (c) the same UTC-vs-reader mismatch reaches
    the user through every EXPORT, because a spreadsheet has no timezone
    concept at all: BG-1 converts datetime cells to `env.user.tz` at the
    xlsx-writing layer, which is the only honest cell. Left open and stated
    rather than hidden: the on-screen table still parses the naive ISO string
    with `new Date(value)`, i.e. as browser-local, so for an instant after
    17:00 UTC the screen shows one date and the (now correct) export shows the
    next. The screen is the wrong one. Whenever you fix half of a
    timezone story, say which half. (BG-1.)

- **§5.158 — a `res.users.tz` set from a shell did not survive the persona's
    first browser login; the surviving value was the BROWSER's zone.**
    Measured in BG-1: a QA user was created with `tz = Asia/Ho_Chi_Minh`,
    confirmed in psql from a separate process, then driven through
    `/web/login`; after the session the stored `tz` read `Australia/Sydney`,
    which is the zone of the machine running the browser, and the Excel export
    correspondingly shifted by +10 rather than +7. The mechanism was not
    pinned down (no `write` of `tz` is obvious in the Odoo 19 web controllers,
    and BG-1 did not spend the phase finding it) — which is exactly why this
    is recorded as an observation with its measurement rather than as an
    explanation. It is the §5.141 shape one step further: for `lang` the
    danger is a stale worker cache, for `tz` the stored value itself moves.
    Remedy that worked: set the timezone *through the session* (the ordinary
    `res.users.write({'tz': …})` the Preferences dialog makes, from the
    authenticated page), then ASSERT the value immediately before the
    measurement you care about. General rule for any evidence pack that
    depends on a user preference: read the preference back inside the session
    that will exercise it, never from the shell that set it. (BG-1.)
