# Implementation Plan: Plot path optimization

**Branch**: `012-plot-optimization` | **Spec**: [spec.md](./spec.md)

## Summary

Extend `PlotSettings` with optional `path_reordering: int | None`. When `1`, `build_axicli_plot_argv` appends `-G1`. Persist via `SettingsService`. Add checkbox to `PlotSettingsWidget`. Existing plot/multi-layer snapshot paths pick up the new field automatically.

## Structure

| Area | Change |
|------|--------|
| `models/plot_settings.py` | Field, validation (allowed: None, 1), argv `-G` |
| `services/settings_service.py` | QSettings key load/save/reset |
| `ui/plot_settings_widget.py` | Checkbox + tooltip, disable while plotting |
| Tests | `test_plot_settings.py`, `test_settings_service.py`, widget/snapshot tests |

## argv examples

```text
# Default (optimization off)
axicli layer.svg -m plot -c 1

# Optimization on
axicli layer.svg -m plot -c 1 -G1
```

## Dry-run estimate

Not implemented; preview metrics documented in research.md only.
