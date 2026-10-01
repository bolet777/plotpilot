# Research: axicli 3.9.6 plot controls

**Date**: 2026-09-30  
**CLI**: `AxiDraw Command Line Interface 3.9.6` (`axicli --version`)  
**Install**: pipx venv `axicli` (`axidrawinternal` 3.9.x, config header dated 2023-05-11)

## Sources

- `axicli --help` and `axicli/axidraw_cli.py` (public flags)
- `axidrawinternal/axidraw_conf.py` (defaults when a flag is omitted)
- `axidrawinternal/axidraw.py` `get_doc_props()` / `update_options()` (ranges, `-N`)
- `axidrawinternal/motion.py` and `axidraw_conf.py` (`const_speed` factors)
- `axidrawinternal/path_objects.py` `rotate()` and `preview.py` (rotation direction)
- https://axidraw.com/doc/cli_api/

PlotPilot does not pass `-f`. Omitted flags therefore use `axidraw_conf.py`, or a user copy of that file if they invoke axicli that way outside PlotPilot. PlotPilot never reads that file.

## Flags

| Flag | Meaning | Help / CLI range | Runtime clamp | Omitted default (`axidraw_conf.py`) | Model-dependent |
|------|---------|------------------|---------------|--------------------------------------|-----------------|
| `-G` / `--reordering` | Path joining and reorder | 0–4; **3 deprecated** | stored as int | `reordering = 0` (least: join adjoining paths only) | No |
| `-N` / `--no_rotate` | Force auto-rotate off | store_const `'True'` | forces `auto_rotate = False` | `no_rotate` unset → `auto_rotate = True` | No. Direction is not a CLI flag |
| `-u` / `--pen_pos_up` | Raised pen servo | 0–100 | 0–100 | `pen_pos_up = 60` | No (servo units, not mm) |
| `-d` / `--pen_pos_down` | Lowered pen servo | 0–100 | 0–100 | `pen_pos_down = 30` | No |
| `-C` / `--const_speed` | Constant pen-down velocity | store_const `'True'` | multiplies pen-down speed | `const_speed = False` | No. Factor depends on resolution, not model |
| `-s` / `--speed_pendown` | Pen-down speed | 1–100 | 1–110 | `25` | No |
| `-S` / `--speed_penup` | Pen-up speed | 1–100 | 1–200 | `75` | No |
| `-a` / `--accel` | Acceleration | 1–100 | 1–110 | `75` | No |
| `-L` / `--model` | Travel limits | 1–7 | model table | `model = 1` | **Yes** — selects X/Y travel |
| `-v -T` | Preview, no motion, report time | flags | n/a | preview off, report off | Estimate uses the same model/speed flags |

`-G` values that PlotPilot may send:

| Value | axicli help | PlotPilot label |
|-------|-------------|-----------------|
| omit | config decides (stock `0`) | Driver default |
| `4` | None; strictly preserve file order | None / strict file order |
| `1` | Basic; reorder paths for speed | Basic reorder |
| `2` | Full; also allow path reversal | Full reorder + reverse |

`0` (least) is valid in axicli but is the stock config value, so it is covered by “Driver default” when the config is untouched. `3` is deprecated and rejected. Strict mode (`4`) also disables axicli’s short-gap path joining (`min_gap`).

`-C` cannot be forced off. The short flag only sets the option true. Off means omit the flag. Stock default is false. In constant-speed mode the driver multiplies pen-down speed by `const_speed_factor_hr = 0.4` (default high resolution) or `0.25` (low resolution). Pen-up moves still accelerate. This does not change clip bounds.

Pen heights are servo positions. The driver uses `abs(pen_pos_up - pen_pos_down)` for lift time. It does not require up > down and does not interpret the numbers as millimeters.

## `-v -T` report

Preview does not move hardware. Stable labels (same as slice 012):

```text
Estimated print time: N.NNN Seconds
Length of path to draw: N.NNN m
Pen-up travel distance: N.NNN m
```

PlotPilot parses those three fields. The estimate must be run on the **prepared clipped SVG**, with the same argv tail as the plot (including `-N` and `-G`).

## Auto-rotate (B12)

`get_doc_props()`:

1. If `-N` was passed, `no_rotate` is the string `'True'` and `auto_rotate` is forced false.
2. Otherwise `auto_rotate` comes from config (default true).
3. If auto-rotate is on **and SVG height > width** (root `width`/`height` in inches), `rotate_page` is set.
4. Paths are rotated 90°. Direction is `auto_rotate_ccw` in the config file only (default true, counterclockwise). There is **no CLI flag** for direction, and the public CLI has **no flag that forces auto-rotate on**. `--auto_rotate` exists on the internal parser, not on `axicli --help`.

PlotPilot sends a prepared SVG whose page size is the plot viewport:

- Explicit model: machine travel, usually wider than tall, so axicli would not rotate even without `-N`.
- Default (CLI) plus A4/A3 fallback: portrait page (`210×297` or `297×420`). Without `-N`, axicli rotates that page and the Qt preview does not.

Enabling auto-rotate from PlotPilot cannot be mirrored in the preview, because the direction is not on the command line and “on” cannot override a config file that sets `auto_rotate = False`.

**Decision:** always pass `-N` on plot and on `-v -T`. Do not offer an Enabled control. Preview, bounds preflight, and the physical plot all assume the prepared SVG orientation. Bounds default `auto_rotate=False`. A portrait page that would fit only after a 90° turn is reported as out of bounds, with a note that PlotPilot keeps preview orientation.

## Safety interactions

| Control | Effect on clipping / bounds |
|---------|-----------------------------|
| `-G` | Execution order and optional reversal (`2`) only. Geometry clip is unchanged. |
| `-N` | Stops axicli from rotating the page before its own clip. Matches PlotPilot’s clip. |
| `-u` / `-d` | Servo only. No XY travel change. |
| `-C` | Timing only. |
| `-s` / `-S` / `-a` | Timing only. |
| `-L` | Machine rectangle. Wrong model still changes axicli’s internal limits. PlotPilot clip uses the selected model. |
| `walk_home` | XY move to the enable-origin. Does not lower the pen. Not the safe-stop sequence. |
| `disable_xy` | De-energize steppers. No motion, no pen-down. |

Manual Home and Motors Off are refused while a plot, safe stop, or another manual command is active. They do not call `raise_pen` first; that sequence stays in safe stop only.

## Project format

Version stays **1**. New optional keys: `pen_pos_up`, `pen_pos_down`, `const_speed`. Missing keys mean driver default (omit flag) and constant speed off.

`path_reordering: null` or a missing key inside an existing `plot_settings` object still means **driver default** (omit `-G`), which is what older files saved. New `PlotSettings()` and a missing QSettings key use **strict file order** (`-G4`) so a fresh app no longer depends on `axidraw_conf.py` for path order.
