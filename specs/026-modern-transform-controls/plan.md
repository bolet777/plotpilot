# Implementation plan

## UI

- Add `ArtworkTransformControls` widget (`QSlider`, `QDoubleSpinBox`, `QPushButton`) with POSITION / SCALE sections and plot-area footer.
- Replace the horizontal spinbox row in `MainWindow` with the new widget.
- Remove redundant artwork X/Y/Scale status line; keep plot-area line and preview diagnostic lines.

## Mapping

- Qt-free helpers in `transform_slider_mapping.py`: 0.1 mm steps for position; 0.1 % steps for scale between `DEFAULT_SCALE_MIN/MAX`.

## Wiring

- Widget emits full `ArtworkTransform` on user edits; `MainWindow._set_artwork_transform` remains authoritative.
- `_refresh_artwork_transform_panel` sets slider ranges from `resolve_preview_work_area`.
- Preview `artwork_transform_changed` continues to call `_sync_artwork_controls_from_preview` only.

## Tests

- `tests/test_artwork_transform_controls.py`: axis/slider sync, presets, resets, ranges, drag sync, lightweight slider callback.
