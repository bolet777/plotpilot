# Implementation notes — 019 canonical SVG geometry

## Coordinate path

1. `parse_page_geometry(svg_text)` → root Element via `parse_svg_text`, physical mm via `parse_physical_size`, `viewBox` / `preserveAspectRatio` from root attributes only.
2. `prepare_positioned_plot_svg` builds `_SvgToMm.from_page(page, svgelements_root)`.
3. **No viewBox**: segment coords are CSS px → `user_point_to_mm`.
4. **With viewBox**: segment coords from `segments(transformed=True)` are viewport pixels → `viewport_pixel_to_mm` → viewBox user units → mm.

## Removed

- `_VIEWBOX_RE`, root width/height regex in `plot_viewport.py`
- `_coordinates_are_viewport_pixels`, `_max_transformed_coordinate`, `_read_viewbox_user`, `_numeric_length`

## Tests

- `tests/test_page_geometry.py` — units, nested marker ignored, isolation parity.
- Golden xfails cleared in `tests/test_golden_svg.py` for B3/B5/B10.
- Clipping tests that intend mm user space now declare `viewBox="0 0 100 100"` explicitly.
