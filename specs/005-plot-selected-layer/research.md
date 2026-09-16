# Research: axicli plotting (3.9.6)

## Plot command

Basic syntax (default mode is `plot`):

```bash
axicli path/to/file.svg -m plot -c 1
```

Verified locally:

```bash
axicli tests/fixtures/valid_basic.svg -v -T
```

`-v` / `--preview`: offline simulation (no hardware). `-T` / `--report_time`: prints time/distance
estimates. Exit code 0 on successful preview.

Hardware plot (no `-v`):

```bash
axicli /path/to/layer.svg -m plot -c 1
```

Useful options (defaults from `axidraw_conf.py` if omitted):

| Flag | Purpose |
|------|---------|
| `-s` | Pen-down speed (1–100) |
| `-S` | Pen-up speed (1–100) |
| `-a` | Acceleration (1–100) |
| `-L` | Model code (1–7) |
| `-c` | Copies (default 1) |
| `-b` | CLI progress bar (adds pre-plot preview cost) |
| `-G` | Path reordering (0–4) |

Slice 005 uses **CLI defaults** only (`-m plot -c 1`).

## Layers mode (not used)

`axicli -m layers -l N file.svg` plots Inkscape-numbered layers inside a **single multi-layer file**.
PlotPilot instead writes an **isolated single-layer SVG** and plots that file with `-m plot`, so only
the selected layer geometry is sent.

## Pause / stop / exit

Official docs: an active plot can be **paused** with **Control+C** or the physical pause button; pause
finishes the current segment. PlotPilot **Stop** sends **SIGINT** to the `axicli` child (Ctrl+C
equivalent), waits up to 8s, then `terminate()`, then `kill()` if needed.

Each `axicli` invocation is an independent session; settings are not persisted between runs.

## Physical SVG dimensions

AxiDraw converts SVG page size to millimeters for motion (see preview output in meters). PlotPilot
requires **`width` and `height` on the root `<svg>`** before plotting.

Supported units in validation (converted to mm): `mm`, `cm`, `in`, `pt`, `pc`, `px`, and **unitless**
numbers (treated as CSS px at 96 dpi, matching common SVG/plotter tooling).

**Rejected**: missing width/height, relative units (`%`, `em`, …), unparseable values.

Preview dry-run for tests: `axicli file.svg -v -T` (no `-m` change needed; preview flag disables hardware).

## Bounds / warnings

CLI stdout/stderr may include travel estimates and model/bounds messages. PlotPilot captures combined
output and surfaces the first meaningful line on failure without rescaling artwork.

## Licensing

Unchanged from slice 004: subprocess to user-installed `axicli`; no bundled GPL libraries.
