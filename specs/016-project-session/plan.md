# Implementation Plan: Project session

**Branch**: `016-project-session` | **Spec**: [spec.md](./spec.md)

## Summary

Add `ProjectSession` + `ProjectFileService`, extend `SettingsService` for project-scoped state, wire File menu and transactional load in `MainWindow`.

## Files

| Path | Role |
|------|------|
| `models/project_session.py` | Serializable project state |
| `services/project_file_service.py` | JSON v1, paths, errors |
| `services/settings_service.py` | Project session mode, apply without QSettings |
| `ui/main_window.py` | Menu, save/open, dirty, title |
| `tests/test_project_file_service.py` | Format, paths, round trip |
| `tests/test_main_window_project.py` | Open/save UX with injectors |

## V1 JSON schema

```json
{
  "format": "plotpilot-project",
  "version": 1,
  "svg": { "path": "design.svg" },
  "layers": { "checked_ids": ["orange"] },
  "artwork_transform": { "x_mm": 0.0, "y_mm": 0.0, "scale": 1.0 },
  "plot_settings": {
    "pen_down_speed": null,
    "pen_up_speed": null,
    "acceleration": null,
    "model": null,
    "path_reordering": null
  },
  "preview": { "fallback_work_area": "A4" }
}
```
