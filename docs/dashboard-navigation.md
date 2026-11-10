# Dashboard navigation and browser favorites (#84)

URLs retain compatible category, exact object, period and view-specific filters.
The dashboard removes fields without an effect in the destination view and
shows a reset notice. An absent or incompatible object is reset explicitly in
rendered navigation; the underlying analytical `view()` still rejects invalid
identities. Inventory sorting, search and paging remain local to that view;
object search can carry into the detail view. Active filters each have a remove
link, alongside a complete reset.

Period-aware views offer all dates, 30/90/365 days and custom bounds. Presets
resolve to visible calendar dates, anchored at the selected end or the current
analysis date, with no future anchor. Date inputs automatically select custom
mode when edited. A historical end still selects recorded quantities, never
current holdings. Current-only views do not display a misleading start-date
control. Comparison presets constrain the available recorded snapshots.

Favorites use `localStorage['ckin2.views.v1']` in the user's browser. Save, open,
rename and delete are explicit actions. No account, server preference store,
network synchronization or portfolio-file change is involved. Names render as
text. Only bounded relative same-origin dashboard URLs with known fields and
values are accepted. Duplicate IDs, unknown pages/fields, malformed dates,
external URLs and obsolete records are ignored with an explanation. An obsolete
item selection is reset visibly by the server. A denied or full store disables
saving without breaking portfolio consultation. At most 100 views are stored.

Optional Playwright/Chromium acceptance tests exercise saving, renaming, opening,
deleting, invalid/obsolete favorites, denied storage, browser back navigation,
periods, category preservation, snapshot selection and keyboard focus. Desktop
and 390px mobile checks forbid external requests and verify no document overflow
or fixture changes. CI without those optional browser packages skips that layer;
URL-state and functional data tests still run with the declared Python dependencies.
