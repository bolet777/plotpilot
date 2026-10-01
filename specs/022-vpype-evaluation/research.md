# vpype research (Task #6)

Evaluation date: 2026-09-30. Environment: macOS, Python 3.12, `uv`, PlotPilot branch `022-vpype-evaluation`.

## Version and license

| Item | Value |
|------|--------|
| Package | `vpype` **1.15.0** (PyPI; latest docs mention 1.16.0) |
| License | **MIT** (compatible with PlotPilot MIT) |
| CLI entry | `vpype` via `vpype_cli` + Click |
| Python API | `import vpype` — `read_svg`, `read_multilayer_svg`, `Document`, `LineCollection`, geometry filters |

Authoritative sources: [vpype documentation](https://vpype.readthedocs.io/en/latest/), installed package `vpype/io.py`, `vpype_cli/read.py`.

## `vpype read` and plugins

**No extra plugins are required for SVG import.** `read` is built into core `vpype` / `vpype_cli`.

Optional PyPI extras (`vpype[all]`) add viewer (PySide6, moderngl), matplotlib, Pillow — not needed for read/crop/optimize.

Separate ecosystem packages (e.g. **vpype-gcode**, **vpype-occ**) are for HPGL/G-code export or OCC geometry — **not** used by `read`.

## Dependencies and packaging impact

Core `vpype` install (evaluation) pulled:

- **svgelements** (already a PlotPilot runtime dependency)
- **numpy**, **scipy**, **shapely**, **multiprocess**, **svgwrite**, **click**, **asteval**, **cachetools**, **pyphen**, **pnoise**, **tomli**

Approximate disk (site-packages): scipy ~73 MB, numpy ~26 MB, shapely ~6 MB, vpype ~1 MB.

PlotPilot today: PySide6 + svgelements only (no numpy/scipy). Adding vpype to the **app runtime** would significantly increase PyInstaller bundle size and hidden-import surface (numpy/scipy/shapely/multiprocess).

Spike dependency: `vpype>=1.15,<2` in **`[dependency-groups] dev`** only (not production `dependencies`).

## macOS / PyInstaller

- vpype is pure Python plus **numpy/scipy/shapely** wheels on macOS (no separate brew libs in this install).
- **multiprocess** is used when `read --parallel` + `--simplify`; default read path is single-process.
- Bundling would require PyInstaller hooks for numpy/scipy (PlotPilot macOS build today does not ship them).
- **Python API vs subprocess CLI:** API is preferable for integration (typed `Document`, no temp files). CLI equivalent: `vpype read … scale … crop … write -` for experiments.

## SVG import capabilities (`read`)

From CLI/API docs and `vpype/io.py`:

| Capability | vpype behavior |
|------------|----------------|
| Elements | `path`, `line`, `rect`, `ellipse`, `circle`, `polyline`, `polygon` |
| Discarded | **text**, **images**, filters, most non-path markup |
| Curves | Linearized; default quantization **0.1 mm** (`--quantization`) |
| Transforms | Applied via **svgelements** when extracting paths |
| viewBox / width/height | Page size from `width`/`height`; if missing/`%`, uses viewBox or **1000×1000 px** default; `--display-size` override |
| preserveAspectRatio | Delegated to **svgelements** parse (same library as PlotPilot) |
| read crop | Optional crop to SVG page box (`--no-crop` to disable) — **not** machine viewport |
| Layers | Top-level `<g>` → layers (Inkscape label/id digits); `--single-layer`, `--attr stroke`, etc. |
| Stroke/fill policy | **No stroke-only filter** — shapes become paths even fill-only / `stroke="none"` |
| Dashes | Stored as layer metadata (`svg_stroke-dasharray`); **geometry is continuous** |
| clipPath / markers | Not modeled as SVG clip; markers not expanded |

## Export

`write` emits multi-layer SVG polylines; units default CSS px with mm/in support on CLI.

## Relation to PlotPilot pipeline

PlotPilot authoritative path (post PR #21/#22):

```text
isolated layer → canonical page geometry → ArtworkTransform → flatten → Liang–Barsky clip → validate → PreparedPlotSvg
```

vpype overlaps only the **flatten** step (also svgelements-based). It does **not** replace:

- PlotPilot layer isolation / Inkscape groups
- `SvgPageGeometry` + physical mm from `parse_physical_size`
- Preview=Output diagnostics for unsupported content
- Post-clip **machine bounds validator** (`PlotViewportError`)

## Spike location

`experiments/vpype/adapter.py` — not wired to `MainWindow` or plotter services.
