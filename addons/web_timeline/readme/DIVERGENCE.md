# health19 fork divergences from upstream OCA `web_timeline`

This fork carries a few intentional changes on top of OCA `web_timeline` (19.0).
Keep them in mind when rebasing from upstream.

## 1. `_onAdd` merges the search/action context into the dialog context

`timeline_controller.esm.js` — the create dialog is opened with
`makeContext([this.env.searchModel.context, context])` instead of
`makeContext([context], this.env.searchModel.context)`. Upstream passed the
search/action context only as the *evaluation* context, so an action's
`default_*` values (e.g. `default_fso_id`) never reached the `FormViewDialog`.
Item-specific defaults (`default_planned_*`, `default_<group>`) are listed last
so they still win on conflict. This matches how core calendar/gantt create
dialogs behave, and it let us delete a "template assignment" DB-row hack in
`health_fieldservice` that reimplemented `default_*` via a global side channel.

## 2. `dynamic_range="1"` — opt-in windowed fetch

A new timeline arch attribute. When set:

- `timeline_arch_parser.esm.js` parses `dynamic_range` (default **false**).
- `timeline_model.esm.js` — `load()` appends a visible-range clause
  `['&', (date_start < window_end + margin), (date_stop||date_start > window_start - margin)]`
  built from a window set via `setVisibleWindow()`. Margin = one window width, so
  small pans don't refetch. **No window set ⇒ no clause ⇒ byte-identical to
  upstream.**
- `timeline_renderer.esm.js` — binds `rangechanged` → `props.onRangeChanged`
  **only** when the flag is on (optional prop).
- `timeline_controller.esm.js` — `_onRangeChanged` debounces (300 ms) and
  refetches only when the visible window leaves the fetched span.

Default OFF: every timeline view that does not set the attribute behaves exactly
as upstream. Used by `health_fieldservice`'s Staff Schedule (via an inherit in
`health_schedule_canvas`).
