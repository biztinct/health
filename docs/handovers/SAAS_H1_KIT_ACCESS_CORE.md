# SAAS H1 — `biz_kit` + `biz_access`: the generic UI kit and the Access home core, in health19

Read FIRST: `docs/handovers/SAAS_PORT_PROGRAM.md` (owner decisions, verified plumbing, rails
R1–R13, design bar, ledger H1–H5). Then, for the thing you are porting:
`docs/handovers/from_payobook/ACCESS_CLOSEOUT.md` §1–§4 and `ACCESS_PROGRAM.md` (rulings 1–5,
ledger A3, B3, B4, C4, C5, D2, D8, F4, F5, F12 bind this phase). You do NOT need FLEET for H1.

**Source material (READ-ONLY — rail R10, never write there):**
`/Users/adity/Documents/GitHub/gitlocal/biz_access/` (11,769 lines: models 3,327, JS 1,784,
SCSS 2,269, XML 1,517, tests 2,142, hooks 323), `…/pb_import_kit/static/src/` (tokens 86, kit
primitives 182, modal 119, icons 203), `…/pb_hub/static/src/js/hub_nav.js` (150).

Design bar (verbatim, binding): **"Extreme WOW, intuitive, out-of-this-world experience, best in
class."** Hero moment, zero dead-ends, plain language, motion with purpose, keyboard + bulk
ergonomics, measured against Linear / Stripe / Vercel. H1's hero is the Access home itself
arriving in this product looking NATIVE — the health palette, not indigo — with the role builder's
live mini-menu lighting up as abilities are ticked, on a database that has never had it.

White-label rule (binding, R12): the word "Odoo" never appears in a user-visible string (field
`string=`/`help=`, labels, toasts, mail bodies, PDF titles, `_t()` copy). Technical identifiers
(`from odoo import`, xmlids, `odoo-bin`) untouched. Plain English in the screen's vocabulary.

---

## 0. What H1 is, in one paragraph

Payobook's Access home (`biz_access`) works and is loved, but it is welded to Payobook's UI kit
(`pb_import_kit`, `pb_hub`, `pb_settings`) and to Payobook's left menu (`pb.sidebar.item`). H1
re-creates it in this repo as two product-neutral modules with clean generic names: **`biz_kit`**
(design tokens, kit primitives, the Lucide `ic()` registry, the back chip, two soft-registry keys)
and **`biz_access`** (roles as bundles of plain-English abilities, the Roles / People / Screens /
Hand-overs lenses, the role builder, "See it as…", hand-overs with auto-revert and an audit trail
with no delete button). The one architectural change is the **rail provider seam**: `biz_access`
no longer inherits any menu model; it asks a registered provider what the left menu is and who
sees what, and ships with NO provider (an honest, empty Screens lens — exactly the ACCESS P6 T2
proof). H2 writes the `cms.sidebar` provider. H1 installs on a scratch clone of the live
database, runs the full ported suite there, and is Chrome-validated there. **Nothing is installed
on `vietuat`.**

## 1. Scope

1. New module `addons/biz_kit` — depends `['web']`.
2. New module `addons/biz_access` — depends `['base', 'mail', 'biz_kit']` (NOT `hr`: the one
   `hr.employee` read is already guarded by `'hr.employee' in self.env`, facade :1139).
3. The rail provider seam (§3.3) replacing the `pb.sidebar.item` inherit; the facade's every
   rail touchpoint rewired to it; the ONE visibility rule shipped as a pure function.
4. The 4 test files ported to the new names, the rail tests rewritten against a fake provider,
   plus the new tests in §5. Target: every ported test green on the scratch clone.
5. A 20-line brand bridge in `health_theme` so the kit paints in the Việt Úc palette (§3.4).
6. Scratch clone `vietuat_h1` of the live DB, install, tests, a served instance through an SSH
   tunnel, Chrome validation, screenshots, clone dropped.
7. Three commits (biz_kit / biz_access / theme bridge + docs), explicit staging, **no push**.
8. Append to the H-ledger in `SAAS_PORT_PROGRAM.md`; write the report (§7).

## 2. Binding NON-goals

- **Nothing installed, upgraded or written on `vietuat`.** No `vietuat-deploy` run. No service
  stop/start. (Copying the new module folders into `/odoo/odoo-server/addons/` is allowed — an
  uninstalled module is inert — and the theme bridge file is allowed because it defines unused
  custom properties only; say both in the report.)
- No `health_access` overlay, no `cms.sidebar` provider, no ability catalogue for the clinic, no
  touch of `access_roles`, `health_user_admin`, `health_cms_sidebar` — all H2.
- No `biz_tenancy` / `biz_tenants`, no features service, no "feature off" page, no settings hub
  `resolve_gates` — H4. (`hub_features.js`, `hub_feature_off.js`, `hub_shell.js` are NOT ported now.)
- No rail item, no menu entry for the Access home in the product — H2. H1 reaches it by URL.
- No new features beyond the port. Do not "improve" behaviour the tests pin (B3, D2, D8 rulings).
- Do not reference any `pb_*` module or `pb.*` model anywhere in `addons/` (R11's test enforces it).

## 3. Architecture

### 3.1 Naming — the rename table (apply EXACTLY; grep to zero afterwards)

| Payobook | health19 |
|---|---|
| modules `pb_import_kit` + `pb_hub` (nav only) | `biz_kit` |
| `$pbim-*`, `--pbim-*`, mixin `pbim-root-vars` | `$bzk-*`, `--bzk-*`, `bzk-root-vars` |
| `.pbim` root class and every `.pbim-*` primitive (btn, badge, chip, card, empty, busy, spin, stat*, pill, modal, modal-scrim, modal__*, wrap, page, note, panel*, table*, hero*, h1/h2/sub/eyebrow, seg*, rail*, mini, fchip) | `.bzk`, `.bzk-*` (BEM parts keep `__`; `bzk-modal-scrim` keeps its ONE hyphen — F57) |
| `@pb_import_kit/js/import_icons` → `IC`, `ic()` | `@biz_kit/js/kit_icons` → `IC`, `ic()` |
| `@pb_hub/js/hub_nav` → `openHub`, `hubBack`, `HubBackChip`, `HUB_LENS_KEY = "pb_lens"` | `@biz_kit/js/kit_nav` → same names, `HUB_LENS_KEY = "biz_lens"` |
| `@pb_settings/js/settings_hub` `SETTINGS_CATEGORIES = "pb_settings_category"`; registry `"pb_hub_palette"` | `@biz_kit/js/kit_registries` → `SETTINGS_CATEGORIES = "biz_kit_settings_category"`, `PALETTE = "biz_kit_palette"`, `HOME_ACTION = "biz_kit_home"` |
| model `pb.role.profile` | `biz.access.role` (table `biz_access_role`) |
| model `pb.role.ability` | `biz.access.ability` |
| model `pb.access.delegation` | `biz.access.delegation` |
| facade `pb.access` (AbstractModel) | `biz.access` |
| `biz.access.export` | unchanged |
| m2m rel tables `pb_*_rel` | `biz_access_*_rel` (name every one explicitly in the field definition) |
| `_inherit = 'pb.sidebar.item'` + `pb_sidebar_item_role_rel` + the two view inherits (`access_views.xml:369–390`) | **deleted** → the provider seam (§3.3) |
| client action tag `pb_access_board`, xmlid `action_pb_access_board`, OWL class `PbAccessBoard`, template `biz_access.PbAccessBoard` | tag `biz_access_home`, xmlid `action_biz_access_home`, class `BizAccessHome`, template `biz_access.Home` |
| `PbMiniRail` / `biz_access.PbMiniRail` | `BizMiniRail` / `biz_access.MiniRail` |
| xmlids `action_pb_role_profile`, `action_pb_access_delegation`, view ids `view_pb_*` | `action_biz_access_role`, `action_biz_access_delegation`, `view_biz_access_*` |
| CSS prefix `.pbva-*` (607 occurrences) | `.bza-*` |
| context key `pb_lens` | `biz_lens` |
| files `pb_access_facade.py`, `pb_role_profile.py`, `pb_role_ability.py`, `pb_access_delegation.py`, `pb_sidebar_item_ext.py` | `access_facade.py`, `access_role.py`, `access_ability.py`, `access_delegation.py`, `access_rail.py` (new) |
| group `biz_access.group_access_manager`, privilege, record rules, ACL rows, cron, 2 mail templates | same xmlids; model references updated (`model_biz_access_role` …) |
| `hooks.py` `LEGACY_MODULE`, `pre_init_hook`, the 28-xmlid re-homing lists, `ir_model_relation` moves | **deleted** (no legacy here). Keep `register_areas`, `register_manager_groups`, `register_catalogue`, `ensure_catalogue`, `reseed_catalogue`, `post_init_hook` |

Do the rename with `sed`/`perl` over the copied tree, then prove it: `grep -rn "pbim\|pbva\|pb_import_kit\|pb_hub\|pb_settings\|pb_sidebar\|pb\.sidebar\|pb\.role\|pb\.access\|pb_access\|pb_lens\|PbAccess\|PbMini" addons/biz_kit addons/biz_access` must return nothing. Watch the SCSS root blocks (F35): `access.scss` is several top-level blocks; renaming must not merge them.

### 3.2 `biz_kit` — files

```
biz_kit/__manifest__.py            name "UI Kit (shared)", depends ['web'], assets below
biz_kit/static/src/scss/kit_tokens.scss     from import_tokens.scss — see the brand indirection below
biz_kit/static/src/scss/kit.scss            from import_kit.scss (all primitives) — verbatim, renamed
biz_kit/static/src/scss/kit_modal.scss      from modal.scss — verbatim, renamed
biz_kit/static/src/js/kit_icons.js          from import_icons.js — IC (102 Lucide glyphs) + ic(name, size)
biz_kit/static/src/js/kit_nav.js            from hub_nav.js — openHub/hubBack/HubBackChip/HUB_LENS_KEY
biz_kit/static/src/js/kit_registries.js     NEW — the three registry keys + `registerHome(actionTagOrXmlid)`
biz_kit/static/src/xml/kit_nav.xml          HubBackChip's template (check where hub_nav's template lives: hub_shell.xml? If so extract only the chip's `t-name`)
biz_kit/tests/__init__.py, test_static.py   source-text tests (§5 T1–T3)
```

Assets: `web._assets_primary_variables` gets nothing; `web.assets_backend` gets tokens → kit →
modal → icons → nav → registries → xml. Tokens must load BEFORE `biz_access/static/src/scss/access.scss`,
which module dependency order guarantees.

**Brand indirection (the one design change in the kit).** In `kit_tokens.scss` every colour custom
property reads a brand override first, with the SCSS default as fallback:

```scss
$bzk-primary: #5A4BB0 !default;   // the generic default stays Payobook's indigo; products override
@mixin bzk-root-vars {
    --bzk-primary:        var(--bzk-brand-primary, #{$bzk-primary});
    --bzk-primary-hover:  var(--bzk-brand-primary-hover, #{$bzk-primary-hover});
    --bzk-primary-strong: var(--bzk-brand-primary-strong, #{$bzk-primary-strong});
    --bzk-primary-light:  var(--bzk-brand-primary-light, #{$bzk-primary-light});
    --bzk-primary-dark:   var(--bzk-brand-primary-dark, #{$bzk-primary-dark});
    --bzk-ink:            var(--bzk-brand-ink, #{$bzk-ink});
    --bzk-soft:           var(--bzk-brand-soft, #{$bzk-soft});
    --bzk-soft2:          var(--bzk-brand-soft2, #{$bzk-soft2});
    --bzk-sky:            var(--bzk-brand-soft2, #{$bzk-sky});
    --bzk-ring:           var(--bzk-brand-ring, #{$bzk-ring});
    // neutrals, semantics and shape: unchanged, no override hook
}
```

Everything in `kit.scss`/`kit_modal.scss`/`access.scss` that used the SCSS variable for a BRAND
colour must use the custom property (`var(--bzk-primary)`), or the override never reaches it.
Neutrals and semantics may stay SCSS. Grep `\$bzk-(primary|ink|soft|sky|ring)` in rules after the
port: any remaining direct use of a brand SCSS variable in a property is a defect.

`kit_nav.js` → `hubBack(props)`: today it returns a chip pointing at the Payobook Settings hub.
Here: resolve the target from `registry.category(HOME_ACTION)` (the product registers ONE entry:
`{xmlid}` or `{tag}` — H2 registers the Admin dashboard); when the registry is empty the chip
performs `history.back()` and is labelled "Back". Never a dead chip (design bar: zero dead-ends).

`kit_registries.js`: exports the three keys and a `registerHome()` helper; nothing consumes the
settings/palette registries in H1 — they exist so `access_palette.js` can register into them
unchanged and so H2's overlay can read them.

### 3.3 The rail provider seam (`biz_access/models/access_rail.py`) — the design of the phase

**Why a provider and not an inherit.** Payobook's `biz_access` teaches `pb.sidebar.item` a
`role_ids` column and overrides its `_state_for` (ACCESS ledger C1/D1). This product's left menu
is `cms.sidebar.item` with a different shape (H0 §"The rail", ledger H4): gates are rows of a
third-party model, sub-items inherit through `effective_role_ids`, there is no permission lane
and no locked teaser. A generic module cannot inherit a model it does not know. So the module
defines WHAT IT NEEDS from a left menu and lets each product supply it — the same soft-registration
pattern the module already uses for areas, manager groups and the catalogue (ledger F4).

```python
# access_common.py — module-level, read at call time (F4)
_RAIL_PROVIDER = [None]
def register_rail(provider):   # provider: an object implementing RailProvider, or None to clear
def rail_provider():           # -> provider or None

class RailProvider:            # documented protocol (plain class, not a model)
    key = 'none'
    def available(self, env) -> bool
    def sections(self, env, include_inactive=False) -> list[dict]
        # {id, name, sequence, active}
    def entries(self, env, include_inactive=False) -> list[dict]
        # {id, section_id, parent_id|None, name, icon, sequence, active,
        #  group_ids: [int], restricted: bool, restriction_reason: str,
        #  role_ids: [int]  (biz.access.role ids WRITTEN on it, archived included)}
    def visibility_for(self, env, user) -> {'items': {id: 'on'|'locked'|'hidden'}, 'sections': {id: 'on'|'locked'|'hidden'}}
    def set_roles(self, env, entry_id, role_ids) -> None
    def set_active(self, env, entry_id, active) -> None
    def set_restricted(self, env, entry_id, restricted, reason) -> None
    def reorder(self, env, section_id, entry_ids) -> None
    def reload_event(self) -> str | None   # bus event the product's menu listens to, e.g. "CMS_SIDEBAR:RELOAD"
```

`biz.access.rail` is an AbstractModel that wraps the provider with the "no rail" answers when
none is registered (`available()` False; `sections()`/`entries()` empty; `visibility_for` empty
dicts; every write raises `UserError(_("This system has no left menu the Access home can edit."))`).
The facade calls ONLY `self.env['biz.access.rail']`, never a provider directly. Rewire every
touchpoint listed here (line numbers are the Payobook file's): `_rail` :571, `_rail_skeleton_items`
:584, `_any_gated` :595, `_gate_roles`/`_gate_roles_raw` :610–632 (now read `entry['role_ids']`
and browse `biz.access.role` with `active_test=False`), `_unlocks` :645, `_opens_for` :662,
`_everyone_items` :690, passport mini-rail :1230–1260, `_rail_all` :1420, `_screen_roles` :1435,
`screens_board` :1585, `screen_detail` :1654, `_screen` :1682, `_who_sees` :1690,
`set_screen_roles` :1737, `set_screen_active` / `set_screen_restricted` (find them), `reorder_screens`
:1837. The facade's dicts (`{'id','label','icon','locked','subs'}` etc.) keep their SHAPES — the
browser is unchanged apart from the rename.

**The ONE rule, as a pure function** (`access_common.py`), tested on its own (R6):

```python
def rail_state(entry, is_admin, held_group_ids, role_groups):
    """(visible, locked). role_groups: {role_id: set(group_ids)} for ACTIVE roles only.
    Mirrors pb_sidebar_item_ext._state_for exactly:
      no groups and no roles written -> (True, False)          # open to everybody
      is_admin                        -> (True, False)
      groups & held                   -> (True, False)          # permission lane, ANY
      any role in entry.role_ids whose groups are non-empty and ⊆ held -> (True, False)  # role lane, ALL
      entry.restricted                -> (True, True)           # locked teaser
      else                            -> (False, False)
    An archived role opens nothing (it is absent from role_groups); an entry gated ONLY on archived
    roles is therefore hidden to everybody but an admin (D2)."""
```

Providers MAY use it (H2's cms provider will, for the bundle lane); the fake provider in the tests
MUST use it, so the tests exercise the rule the product will run.

**Icons across the seam.** Payobook entries carry Lucide keys; this product's rail carries
FontAwesome classes (`fa fa-users`). `entries()` returns whatever the product stores. The mini
rail (`mini_rail.js/.xml`) renders: if the icon string starts with `fa ` → `<i t-att-class="icon"/>`;
else `ic(icon)` with `ic('circle')` as the fallback for unknown keys. Same in the Screens lens rows.

**Reload after a gate change.** After `set_roles`/`set_active`/`set_restricted`/`reorder`, the
facade returns `{'ok', 'message', 'reload_event'}` and the browser triggers
`env.bus.trigger(reload_event)` when it is a string (D7 pattern; H2's provider names
`CMS_SIDEBAR:RELOAD` and teaches `cms_sidebar.js` to listen).

### 3.4 The theme bridge (`health_theme`)

New file `health_theme/static/src/scss/bzk_brand.scss`, appended to `web.assets_backend` right
after `vu_tokens.scss`:

```scss
// Tints the shared UI kit (biz_kit, --bzk-*) in this product's palette. Layer-3, derived from the
// Theme Engine's semantic tokens so a published theme re-tints the kit too. Inert without biz_kit.
:root {
    --bzk-brand-primary:        var(--vu-brand-primary, #1565C0);
    --bzk-brand-primary-hover:  #1356A9;
    --bzk-brand-primary-strong: var(--vu-brand-primary, #1565C0);
    --bzk-brand-primary-light:  #83C5FA;
    --bzk-brand-primary-dark:   #0D356B;
    --bzk-brand-ink:            #212121;
    --bzk-brand-soft:           #E4F4FD;
    --bzk-brand-soft2:          #D2EAFB;
    --bzk-brand-ring:           rgba(21, 101, 192, .18);
}
```

Values are the `$vu-deep-blue-*` family from `primary_variables.scss` (:36–41) and
`$vu-text-primary` — never invent a hex; `#D2EAFB` is the one exception and must be justified in
the report or replaced by an existing token. Flat colours only (owner rule: no gradients). Do NOT
bump `health_theme`'s version or `-u` it anywhere: the file is inert until biz_kit is on a
database.

### 3.5 Copy that changes (R11/R12 sweep)

`biz_access` already passed a product-name audit (ACCESS closeout §5), so the copy is neutral.
Re-run it here with a stronger net: a source-text test over `biz_kit` and `biz_access` (models,
xml, js, scss, data) failing on `Payobook`, `payobook`, `pb_`, `pbim`, `pbva`, `Viet Uc`,
`health_`, `Odoo` in anything a user can read (F43's `'odoo' not in text.lower()` pattern for
`_t()`/`string=`/`help=`/mail bodies; technical identifiers exempt by an explicit allow-list —
`from odoo`, `odoo.`, `odoo-bin`, `@odoo/owl`, `/odoo/`). The 2 mail templates and the cron name
are user-visible.

### 3.6 Security

Port `biz_access_security.xml` and `ir.model.access.csv` 1:1 with the new model names. Rail B
(the catalogue tripwire) becomes: no ability may reach `base.group_system` or
`base.group_erp_manager` through `all_implied_ids` — the constraint on `biz.access.ability` and
`biz.access.role` plus the harness test that walks a REGISTERED catalogue (empty here; the test
still runs and passes vacuously, and asserts the constraint fires on a deliberately bad ability).
`FORBIDDEN_GROUP_XMLIDS` stays `('base.group_system', 'base.group_erp_manager')`.

---

## 4. Scratch clone, install, serve, validate — the exact commands

All on `VietUcUAT`. `P="sudo -u postgres psql"`. Odoo runs as user `odoo` with `HOME=/odoo` (F59).

```bash
# 0. copy the new modules + the theme file to the shared addons tree (inert for vietuat)
#    from the Mac, repo root:
ssh VietUcUAT 'rm -rf /tmp/biz_kit /tmp/biz_access /tmp/health_theme'
scp -qr addons/biz_kit addons/biz_access VietUcUAT:/tmp/
scp -q addons/health_theme/static/src/scss/bzk_brand.scss VietUcUAT:/tmp/
scp -q addons/health_theme/__manifest__.py VietUcUAT:/tmp/health_theme_manifest.py
ssh VietUcUAT 'sudo cp -r /tmp/biz_kit /tmp/biz_access /odoo/odoo-server/addons/ \
  && sudo cp /tmp/bzk_brand.scss /odoo/odoo-server/addons/health_theme/static/src/scss/ \
  && sudo cp /tmp/health_theme_manifest.py /odoo/odoo-server/addons/health_theme/__manifest__.py \
  && sudo chown -R odoo:odoo /odoo/odoo-server/addons/biz_kit /odoo/odoo-server/addons/biz_access /odoo/odoo-server/addons/health_theme'

# 1. clone the live DB (G8: -Fc -Z1 + pg_restore -j2; NOT createdb -T). No filestore copy needed.
sudo -u postgres pg_dump -Fc -Z1 vietuat -f /tmp/vietuat_h1.dump
sudo -u postgres createdb -O odoo vietuat_h1
sudo -u postgres pg_restore -j 2 -d vietuat_h1 /tmp/vietuat_h1.dump
sudo -u postgres psql -d vietuat_h1 -c "UPDATE ir_config_parameter SET value='http://localhost:8169' WHERE key='web.base.url'; INSERT INTO ir_config_parameter(key,value) SELECT 'web.base.url.freeze','True' WHERE NOT EXISTS (SELECT 1 FROM ir_config_parameter WHERE key='web.base.url.freeze');"
# a login you know on the clone (ash's password is not known): make one
echo "u=env['res.users'].create({'name':'H1 Validator','login':'h1@local','password':'H1-validate-2026','group_ids':[(4, env.ref('base.group_system').id)]}); env.cr.commit(); print(u.id)" | \
  sudo -u odoo HOME=/odoo python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d vietuat_h1 --db-filter='^vietuat_h1$' --no-http --max-cron-threads=0 --logfile=/tmp/h1/shell.log

# 2. install (the live service keeps running; ports differ; workers=0)
sudo mkdir -p /tmp/h1 && sudo chown odoo:odoo /tmp/h1
sudo -u odoo HOME=/odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d vietuat_h1 \
  --db-filter='^vietuat_h1$' -i biz_kit,biz_access --workers=0 --max-cron-threads=0 \
  --http-port=8169 --gevent-port=8168 --stop-after-init --logfile=/tmp/h1/install.log; echo EXIT:$?
sudo grep -aE "ERROR|CRITICAL|Some modules are not loaded" /tmp/h1/install.log | head

# 3. tests (scope names EVERY module this phase edits — F49: biz_kit, biz_access, health_theme)
sudo -u odoo HOME=/odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d vietuat_h1 \
  --db-filter='^vietuat_h1$' -u biz_kit,biz_access,health_theme --test-enable \
  --test-tags /biz_kit,/biz_access,/health_theme --workers=0 --max-cron-threads=0 \
  --http-port=8169 --gevent-port=8168 --stop-after-init --logfile=/tmp/h1/tests.log; echo EXIT:$?
sudo grep -a "odoo.tests.result\|odoo.tests.runner" /tmp/h1/tests.log | tail -5
# EXIT:1 with FAIL:0 means "read the ERROR lines", never "passed" (reference memory)

# 4. serve it for Chrome (detached; stop it afterwards BY PID)
sudo -u odoo HOME=/odoo systemd-run --unit=h1-serve --collect \
  python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d vietuat_h1 --db-filter='^vietuat_h1$' \
  --workers=0 --max-cron-threads=0 --http-port=8169 --gevent-port=8168 --logfile=/tmp/h1/serve.log
# on the Mac:  ssh -N -L 8169:127.0.0.1:8169 VietUcUAT &   then open http://localhost:8169/bizapp
#   login h1@local / H1-validate-2026 ; the home: http://localhost:8169/bizapp/action-biz_access.action_biz_access_home
# afterwards:  sudo systemctl stop h1-serve

# 5. drop the clone at the end (A8/F7): terminate backends first
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='vietuat_h1'"
sudo -u postgres dropdb vietuat_h1; rm -f /tmp/vietuat_h1.dump
```

Memory rail: `free -m` before step 2 and before step 4; if `available` < 500 MB, stop and report
rather than starting a second server beside the live one. Check `ps aux | grep '[o]doo-bin'`
before every odoo-bin run (another session's process = wait, not improvise).

Chrome: use the chrome-devtools MCP tools against `http://localhost:8169` through the tunnel. If
the MCP tools are unavailable, say so in the report and stop at the server-side proof — do not
claim visual validation you did not do.

---

## 5. Numbered test cases (run + report each)

Ported suites (rename + fake provider):
1. `test_access_generic.py` (23) — the source-text neutrality test now also asserts none of
   `pb_`, `pbim`, `pbva`, `Payobook`, `health_`, `Viet Uc` in user-facing copy or imports (R11);
   the file list it inspects is the NEW file list.
2. `test_access_p2.py` (29), 3. `test_access_p3.py` (26), 4. `test_access_p4.py` (36) — every test
   that created `pb.sidebar.section/item` rows now registers a **fake in-memory provider** in
   `setUp` (a Python class holding sections/entries as dicts, `visibility_for` built on
   `rail_state`, writes mutating the dicts) and clears it in `tearDown`/`addCleanup`. Same
   assertions, same counts. The D2 archived-role test and the D8 mutual-cover tests must survive.

New:
5. `rail_state` unit test: the six branches of the rule + the archived-only-role case + the
   "role with no groups is held by nobody" case (H-ledger will cite it).
6. No provider registered: `screens_board()` returns `any_gated False`, empty sections, the
   headline "There is no left menu on this system yet."; `set_screen_roles` raises the plain
   refusal; `passport()` returns an empty mini-rail with zero counts; the home renders (T9).
7. Rail B harness: registered catalogue empty → vacuous pass; a throwaway ability wrapping a
   group that implies `base.group_system` raises `ValidationError`; the same through
   `biz.access.role.group_ids`.
8. Kit static tests: (a) no `pbim`/`pb_` left in biz_kit; (b) every `--bzk-` brand token in
   `bzk-root-vars` reads a `--bzk-brand-*` override; (c) no Python-style adjacent string literals
   inside `_t(...)` in any JS (F49/W74 gate — copy pb_hub's `test_static.py` idea); (d) `ic()`
   returns markup for every key in `IC` and the `circle` fallback for an unknown key (a
   Python-side check that the JS file parses is enough; do not spin a browser for it).
9. Chrome, on the clone through the tunnel — screenshots into `docs/handovers/saas_h1_shots/`:
   (a) the home opens on the Roles lens with the empty state "No roles have been written down
   yet" in the HEALTH palette (deep blue, not indigo — inspect `getComputedStyle(root).getPropertyValue('--bzk-primary')` = `#1565C0`);
   (b) New role → builder: create "H1 test role" with one throwaway ability you create via the
   plain form view (wrap `base.group_user`), watch the mini-menu (empty, honest) and the
   comparison line; (c) People lens: your own passport, zero-entry menu, the role you just
   granted yourself with "held"; (d) Screens lens: the empty state sentence; (e) Hand-overs:
   create one to a second clone user, see it in the list, end it; (f) the audit rows exist and
   have no delete button; (g) the back chip labelled "Back" goes back. Delete nothing — the clone
   is dropped.
10. Health check of the live service before and after the phase: `curl -s -o /dev/null -w
    '%{http_code}' https://care.biztinct.com/web/login` = 200 both times; `ps aux | grep
    '[o]doo-bin' | wc -l` unchanged; no `vietuat_h1` in `/var/log/odoo/odoo-server.log` cron
    lines (ledger H2's claim, verified once).

---

## 6. Commits (explicit staging, never `git add .`, no push)

1. `feat(biz_kit): shared UI kit — tokens with brand override hooks, primitives, Lucide ic(), back chip, registry keys`
2. `feat(biz_access): Access home core — roles as ability bundles, four lenses, builder, hand-overs; rail provider seam`
3. `feat(health_theme): tint the shared kit in the Việt Úc palette` + `docs(saas): H1 handover, program ledger H6+, screenshots`

Stage by path. The working tree already has unrelated modified files (a `Migration/*.xlsx`,
`health_care_command_channels/*`) — **leave them unstaged and untouched.**

---

## 7. Report back (in this order; the summary in plain English, the rest engineering)

1. **Summary for the owner** (5 lines, screen words): what exists now, where it was seen working,
   what is NOT yet on the live system.
2. Per numbered test: pass/fail + one-line evidence (counts, the sentence seen, the computed
   token value).
3. The test-run line(s) `odoo.tests.result` from `/tmp/h1/tests.log` verbatim, and the install
   log's ERROR grep (empty or explained).
4. The rename proof: the grep command and its empty output; the SCSS root-block list of
   `access.scss` before/after (F35).
5. The provider protocol as implemented (final method list + return shapes) — H2 codes against it.
6. Anything in the Payobook source that did NOT port cleanly and what you did instead (e.g. a
   `HubBackChip` template location, a `.pbim-*` class the kit never defined).
7. Memory readings (`free -m`) at steps 2 and 4; the live-service check (test 10).
8. The H-ledger entries you appended (numbered from H6).
9. The three commit hashes. Confirmation the clone is dropped and `h1-serve` is stopped.
10. Anything you had to decide that this handover did not cover.
