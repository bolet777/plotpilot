# Research: 016-project-session

## Current architecture

| Concern | Location | Notes |
|---------|----------|-------|
| Document | `MainWindow._document: SvgDocument` | `path`, `name`, `raw_text`, `root` |
| SVG load | `load_svg_from_path`, `_open_svg` → `set_document` | Resets `ArtworkTransform` in `_apply_document` |
| Layers | `layers_for_document` → `SvgLayer` | Stable `layer_id` (Inkscape id, root group id, or synthetic) |
| Checked layers | `QListWidget` check state + `UserRole` = `layer_id` | `_checked_layers()` maps rows to `SvgLayer` |
| Transform | `LayerPreviewWidget._artwork_transform` | Synced via spins / drag |
| Plot settings | `SettingsService` + `PlotSettingsWidget` | Persisted to QSettings on every `replace()` |
| Fallback work area | `SettingsService.preview_fallback_work_area` | QSettings key `preview/fallback_work_area` |
| Menu | File → Open SVG only | Cmd+O |

## Layer identity

Use `SvgLayer.layer_id` (see `tests/test_svg_layers.py`). Multi-layer jobs already key by `layer_id`.

## Design decisions

1. **ProjectSession** dataclass — explicit persistence model, not Qt types.
2. **ProjectFileService** — JSON encode/decode, validation, relative paths.
3. **SettingsService** — `apply_project_state()` and `set_project_session_active()` so project loads do not overwrite QSettings; widget changes while a project file is open skip QSettings persist.
4. **Shared load path** — `_load_svg_document(path)` used by Open SVG and Open Project (after validation).

## macOS packaging (future)

- Extension: `.plotpilot`
- UTI suggestion: `com.plotpilot.project` (exported type)
- Role: Editor
- `CFBundleDocumentTypes` with `LSHandlerRank` Owner
- Open-file: pass path to app launch / `application:openFiles:`
