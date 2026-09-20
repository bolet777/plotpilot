# Research: AxiDraw model travel and bounds (axicli 3.9.6)

**Environment**: macOS, `AxiDraw Command Line Interface 3.9.6`, pipx install at `axidrawinternal/`.

**Primary sources**:

- Bundled `axidraw_conf.py` (travel limits in inches, comments give mm equivalents)
- `axidrawinternal/axidraw.py` — `update_options()` maps model code → bounds; `get_doc_props()` auto-rotate
- `axidrawinternal/clipping.py` — `calculate_bounds()` combines machine travel with document size when `clip_to_page`
- `plot_warnings.py` — bounds warning text when path clipping detects overflow
- `axicli --help` — model codes 1–7 labels

## Model codes and physical travel limits

AxiDraw stores limits as **X then Y travel in inches**, origin at **(0, 0)** with positive X/Y only (`bounds = [[0,0], [x_max, y_max]]` in inches, with tiny epsilon padding).

These are the **usable plotting travel areas** configured in the official driver (not separate “recommended margin” values).

| Code | axicli label | X (in) | Y (in) | X (mm) | Y (mm) | Source constant |
|------|--------------|--------|--------|--------|--------|-----------------|
| 1 | V2/V3/SE/A4 | 11.81 | 8.58 | 300.0 | 218.0 | `x_travel_default`, `y_travel_default` |
| 2 | V3/A3 or SE/A3 | 16.93 | 11.69 | 430.0 | 297.0 | `x_travel_V3A3`, `y_travel_V3A3` |
| 3 | V3 XLX | 23.42 | 8.58 | 595.0 | 218.0 | `x_travel_V3XLX`, `y_travel_V3XLX` |
| 4 | MiniKit | 6.30 | 4.00 | 160.0 | 101.6 | `x_travel_MiniKit`, `y_travel_MiniKit` |
| 5 | SE/A1 | 34.02 | 23.39 | 864.0 | 594.0 | `x_travel_SEA1`, `y_travel_SEA1` |
| 6 | SE/A2 | 23.39 | 17.01 | 594.0 | 432.0 | `x_travel_SEA2`, `y_travel_SEA2` |
| 7 | V3/B6 | 7.48 | 5.51 | 190.0 | 140.0 | `x_travel_V3B6`, `y_travel_V3B6` |

PlotPilot stores limits as mm computed as `inches × 25.4` from the exact inch constants above (not rounded marketing mm alone), so values match the driver.

Model **1** is also the CLI default when `-L` is omitted (`model = 1` in config). PlotPilot **Default (CLI)** means `model = None` and must **not** assume code 1 for preflight.

## Orientation and auto-rotate

- Default `auto_rotate = True` in `axidraw_conf.py` (overridable with axicli `-N` / `--no_rotate`).
- When `auto_rotate` is on and **SVG height > width** (in inches after parsing root `width`/`height`), `rotate_page = True`.
- After rotation, document extents on the bed are **(height × width)** instead of **(width × height)** — see `clipping.calculate_bounds()` and `doc_bounds` in `axidraw.py`.
- PlotPilot does **not** pass `-N`; preflight assumes the same default auto-rotate as axicli for page-fit checks.
- PlotPilot does **not** rotate or rescale artwork.

## How axicli checks bounds

1. **Machine rectangle** from selected model (table above).
2. **Document size** from root SVG `width`/`height` (physical units); viewBox affects path scaling but page size comes from width/height attributes.
3. With default `clip_to_page = True`, effective clip region is the **intersection** of machine travel and document bounds (after rotate).
4. **Path geometry** is digested and clipped via `boundsclip.clip_at_bounds()` against machine bounds and document bounds. If clipping removes out-of-range motion, warning key `bounds` is added → user message: movement limited by physical reach / wrong model.
5. **`bounds_tolerance`** (0.003 in) suppresses warnings for tiny overflow.

Preflight in PlotPilot is **page-level only** (root width/height vs model, with auto-rotate semantics). Path-level overflow (geometry outside page box, transforms, negative coords outside viewBox) is **not** replicated without a full SVG engine; axicli remains authoritative at plot time.

## Preview dry-run (`axicli file.svg -v -T`)

- Computes time/distance; does **not** reliably print bounds warnings to stdout for oversized **page** alone (tested: 500 mm page with tiny path — no bounds message).
- Bounds warnings appear when **path motion** exceeds limits after clipping, not merely when width/height attributes exceed travel.

Optional secondary validation via preview is **not** used for UI refresh (too heavy / inconclusive for page size).

## width / height / viewBox

- Physical plotting size for bounds uses **`width` and `height` on the root `<svg>`**, converted to inches internally.
- Paths can extend outside the nominal page; axicli may clip or warn based on actual motion, not attribute size alone.

## Negative coordinates and transforms

- Supported in full driver via digest transforms; page-fit check on attributes alone cannot detect transformed overflow.

## PlotPilot policy (this slice)

| Model setting | Preflight |
|---------------|-----------|
| Explicit 1–7 | Compare page mm vs model mm (auto-rotate aware) |
| Default (CLI) | `UNKNOWN_MODEL` — allow plot, show unverified warning |
| Invalid SVG dimensions | `INVALID_DIMENSIONS` — block (existing validate path) |
| Page exceeds model | `OUT_OF_BOUNDS` — block before axicli |

## References

- https://axidraw.com/doc/cli_api/ (`--model`, preview, `--no_rotate`)
- Evil Mad `axidraw_conf.py` 3.9.x travel constants
- GitHub `evil-mad/AxiDraw` — `axidraw.py` bounds setup
