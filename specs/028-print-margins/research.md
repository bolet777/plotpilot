# Research: Editable Print Margins

## Decision: One horizontal value and one vertical value

**Decision**: `PrintMargins.horizontal_mm` applies to both left and right. `vertical_mm` applies to both top and bottom. Do not store four sides.

**Rationale**: The request is a symmetric safe inset. Four independent margins would change the project schema and the UI for no current need.

**Alternatives considered**: Four spin boxes; a single uniform margin. Rejected because the request distinguishes horizontal from vertical and forbids four sides in this slice.

## Decision: Printable origin is offset, machine origin is not

**Decision**: Clip to `(horizontal, vertical, work_width - horizontal, work_height - vertical)`. Emit SVG in the full machine viewBox.

**Rationale**: Translating artwork or shrinking the viewport to `(0, 0, printable_width, printable_height)` would move physical coordinates. The pen must still treat x=10 mm as 10 mm from machine home.

**Alternatives considered**: Crop by rewriting the SVG viewBox to the printable size; pad by shifting `ArtworkTransform`. Both change either machine coordinates or transform semantics.

## Decision: Low-level clip defaults stay full-bleed; product path applies margins

**Decision**: `prepare_positioned_plot_svg` and `clip_document_polylines` default the clip rectangle to the full viewport when no rectangle is passed. `prepare_layer_plot_svg`, preview, estimate, and plot pass `PrintMargins` (default 10 / 10).

**Rationale**: Golden geometry tests call the low-level function without margins and must keep full-bleed expectations. The application always goes through the service that knows the user's margins.

**Alternatives considered**: Change the low-level default to 10 mm. That would silently rewrite every golden fixture.

## Decision: Reject impossible project margins; recover bad QSettings

**Decision**: Project files with invalid margins raise `ProjectFileError`. Invalid `QSettings` values are dropped and replaced with 10 / 10. The spin box maximum tracks the current work area.

**Rationale**: Project open already rejects invalid settings with a dialog. `SettingsService` already clears corrupt plot settings instead of crashing. The editor can prevent impossible values while the user is changing paper size.

**Alternatives considered**: Clamp bad project values silently. The request prefers an explicit validation error for project data.

## Decision: Reuse the preview cache

**Decision**: Margin changes are viewport parameters, like X/Y/scale. They schedule `compute_interactive_preview` with the cached `PreparedLayerGeometry`.

**Rationale**: Slice 025 already separated flatten from clip. Re-flattening on every margin tick would block the UI and violate the performance requirement.

**Alternatives considered**: Invalidate the geometry cache on margin edits. Unnecessary: flatten output does not depend on the clip rectangle.
