# Research: viewport positioning and geometric clipping (axicli 3.9.6)

**Environment**: macOS, `AxiDraw Command Line Interface 3.9.6` (pipx `axicli`).

**Primary sources**:

- `axidrawinternal/boundsclip.py`, `axidrawinternal/clipping.py`, `axidrawinternal/axidraw.py`
- `plotink/plot_utils.py` (`clip_segment` — Cohen–Sutherland)
- `axidrawinternal/axidraw_conf.py` (`clip_to_page`, `bounds_tolerance`, `curve_tolerance`)
- PlotPilot `bounds_service.py`, `preview_work_area.py`, slice 013 research

## 1. What does PlotPilot currently validate?

| Layer | What | When |
|-------|------|------|
| SVG load | Well-formed SVG, layer extraction | Open file |
| Plot dimensions | Root `width`/`height` in physical units | Before plot temp SVG |
| Page bounds | Root page mm vs selected `PlotterModelInfo` (auto-rotate aware) | UI status + block on `OUT_OF_BOUNDS` |
| Default model | `UNKNOWN_MODEL` — warn, do not block | UI |
| Layer isolation | Stdlib copy of layer subtree | Preview + plot temp |
| Preview overlay | Red dashed machine rect (model or A3/A4 fallback) | UI only |

PlotPilot does **not** today transform artwork, clip path geometry, or validate motion coordinates before axicli.

## 2. What does axicli currently clip?

After SVG digest (flatten curves to polylines per `curve_tolerance`):

**Normal plot mode** (`options.hiding` false): `boundsclip.clip_at_bounds()` clips each subpath against:

- **Physical bounds** `[[0,0],[x_max,y_max]]` from selected model (`-L` / config)
- Optionally **document bounds** when `clip_to_page = True` (default): effective max X/Y is `min(machine, page size)`

**Hidden-line mode** (`-H`): `ClipPathsProcess` uses **pyclipper** for fill/stroke occlusion and rectangular bounds intersection — not used by PlotPilot.

Clipping is on **flattened vertex lists** in inch space internally, not on raw SVG `<clipPath>`.

## 3. Paths crossing machine/page boundaries?

`clip_at_bounds` walks consecutive vertices. When a segment crosses the rectangle:

- Uses `plot_utils.clip_segment` (Cohen–Sutherland) to trim to `[x_min,y_min]–[x_max,y_max]`
- **Splits** subpaths: exit at boundary ends one subpath; re-entry starts a new subpath
- Does **not** draw across excluded regions

Same semantics required in PlotPilot layer C.

## 4. Mathematical clip vs motion constraint?

**Mathematical segment clipping** on the digested polyline. Motion planner then follows clipped vertices. It is not merely “stop at limit without trimming the segment” — the segment is truncated at the intersection.

## 5. Element types (axicli digest)

`digest_svg.DigestSVG` converts drawable SVG into `DocDigest` paths:

- **line, polyline, polygon, rect, circle, ellipse** → path segments
- **path** → M/L/H/V/C/S/Q/T/A/Z (unsupported commands warned/skipped per driver)
- **Transforms** on groups/elements applied during digest (before bounds clip)
- **viewBox** + root width/height scale user units to physical inches

Curves are **flattened** to polylines using `curve_tolerance` (default **0.002 in ≈ 0.05 mm**) before bounds clipping.

**Fills**: digest retains fill flags; default plot mode clips **stroked** motion via boundsclip. Filled-only regions may not produce pen-down motion unless stroked. PlotPilot targets **stroke trajectories** (pen plotter); filled shapes without stroke are out of scope for clipping output unless they already plot as boundaries today.

## 6. Can axicli command travel beyond configured bounds?

After successful clipping, motion should stay within clip bounds (plus `bounds_tolerance` for warnings). Warnings (`plot_warnings` / `bounds` key) fire when requested motion exceeds physical limits by ≥ `bounds_tolerance` **and** clipping occurred on the **positive** X/Y machine limits (not page-limited, not at 0).

PlotPilot must not rely on this alone — driver bugs or bypassing digest would be unsafe.

## 7. Role of `clip_to_page`

When `True` (default), max clip X/Y is `min(machine_travel, svg_width, svg_height)` (after auto-rotate swap of doc dimensions). Prevents plotting outside the SVG page box even if the machine is larger.

PlotPilot output SVG will use **width/height = machine viewport** with geometry already clipped to `[0,W]×[0,H]`, so page and machine bounds align.

## 8. Bounds before or after transforms?

**After** SVG parse transforms and digest flattening. Order in `axidraw.py`: digest → optional rotate digest → bounds clip → optimizations.

PlotPilot order: isolate layer → resolve mm coordinates → **ArtworkTransform** → flatten → clip → validate → temp SVG.

## 9. Safety margin / tolerance

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `bounds_tolerance` | 0.003 in (~0.076 mm) | Warning threshold for overflow |
| Nominal bounds padding | ~1e-9 in | Avoid float edge false clips |
| `curve_tolerance` | 0.002 in (0.05 mm) | Curve flattening |

PlotPilot final validator: use **0.01 mm** coordinate tolerance (stricter display, looser than curve flatten).

## 10. Can PlotPilot inspect final geometry before execution?

Yes — by design in this slice: parse generated temp SVG (or retain internal polyline list) and assert all vertices in `[0, W]×[0, H]`. Tests export fixtures via helper `prepare_positioned_plot_svg(...)` return value.

Preview `-v -T` does **not** replace geometric validation (see slice 013).

---

## Default (CLI) safety policy (slice decision)

| Use | Policy |
|-----|--------|
| Preview red rectangle | ISO A3/A4 **fallback** when `model is None` (existing combo) |
| **Physical plot clip rectangle** | Explicit `PlotterModelInfo` **or** user-selected fallback size (same combo) — **never** silently assume A4 equals hardware |
| Blocking | If `model is None`, plot allowed only with fallback-selected mm rect; UI shows “user-defined work area — not verified hardware” |
| Page-level `OUT_OF_BOUNDS` on **source** SVG | Informational only once viewport clipping is active; **pre-plot block** uses empty intersection + final geometry validator |

---

## SVG geometry strategy (PlotPilot layer C)

**Inventory**: path, line, polyline, polygon, rect, circle, ellipse; nested transforms; viewBox scaling.

**Library**: [`svgelements`](https://github.com/meerk40t/svgelements) **MIT**

- Parses SVG paths and primitives, resolves transforms, converts shapes to paths
- Deterministic, pure Python, macOS/packaging friendly
- No GPL code, no Inkscape

**Segment clipping**: PlotPilot-owned **Liang–Barsky** on mm segments (user spec preference; axicli uses Cohen–Sutherland — both acceptable for axis-aligned rects).

**Curve flattening**: Before segment clip, flatten via svgelements sampling at **`curve_flatness_mm = 0.05`** (match axicli `curve_tolerance`).

**Not safely supported** (documented limitations):

- `text`, `image`, `use`/external refs, filters, masks (except what svgelements skips)
- Hatch/raster fills
- Rotation/skew in `ArtworkTransform` (out of scope)

---

## Output coordinate system

Generated plot SVG:

```xml
<svg xmlns="http://www.w3.org/2000/svg"
     width="{W}mm" height="{H}mm"
     viewBox="0 0 {W} {H}">
```

1 user unit = 1 mm in viewBox; matches PlotPilot `plot_dimensions` and axicli physical width/height parsing (verified same as slice 001/013).

No nested transforms in output; only `path`/`polyline` stroke geometry.

---

## Defense in depth (target)

1. `ArtworkTransform.validate()` (scale > 0, finite bounds)
2. Geometric clip to machine rectangle
3. Independent vertex bounds validator on generated SVG
4. axicli `boundsclip` + model limits (unchanged)

---

## References

- https://axidraw.com/doc/cli_api/
- Evil Mad `AxiDraw` 3.9.6 `axidrawinternal/boundsclip.py`
- PlotPilot `specs/013-plotter-model-and-bounds/research.md`
