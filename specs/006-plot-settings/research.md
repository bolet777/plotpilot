# Research: axicli plot settings (3.9.6)

**Environment**: macOS, `axicli` 3.9.6 (pipx). Verified via `axicli --help`, `axicli --version`, official CLI API docs, and bundled `axidraw_conf.py`.

## Per-plot flags (target settings)

| Setting | Short | Long | Range (help) | Range (runtime) | Default when omitted |
|---------|-------|------|--------------|-----------------|----------------------|
| Pen-down speed | `-s` | `--speed_pendown` | 1–100 | constrained 1–110 in driver | `speed_pendown = 25` in `axidraw_conf.py` |
| Pen-up speed | `-S` | `--speed_penup` | 1–100 | constrained 1–110 | `speed_penup = 75` |
| Acceleration | `-a` | `--accel` | 1–100 | constrained 1–110 | `accel = 75` |
| Model | `-L` | `--model` | 1–7 | 1–7 | `model = 1` |

Omitting a flag leaves that parameter to the CLI session defaults (from `axidraw_conf.py` or a custom `-f` config file). PlotPilot must **not** pass flags for unset overrides so user config files and official defaults remain authoritative.

## Model codes (axicli 3.9.6 `--help`)

| Code | Official label |
|------|----------------|
| 1 | AxiDraw V2, V3, or SE/A4 |
| 2 | AxiDraw V3/A3 or SE/A3 |
| 3 | AxiDraw V3 XLX |
| 4 | AxiDraw MiniKit |
| 5 | AxiDraw SE/A1 |
| 6 | AxiDraw SE/A2 |
| 7 | AxiDraw V3/B6 |

There is no CLI flag for “auto-detect model”; default `1` applies when `-L` is omitted. PlotPilot offers **Default (CLI)** as `model = None` (no `-L`).

## Safety / suitability

- **Pen-down / pen-up speed**: Safe, per-plot, affects motion timing only. Wrong values slow plots or reduce corner precision; no firmware risk.
- **Acceleration**: Safe, per-plot; same class as speeds.
- **Model**: Safe but **must match hardware** for travel limits; wrong model can clip paths or allow out-of-bounds motion assumptions. Exposing official codes 1–7 with clear labels is appropriate; default should remain CLI default until user overrides.

## Copies (`-c`)

Default `1`; continuous plotting (`0`) and multi-copy workflows are out of scope for this slice. PlotPilot continues to pass `-c 1` only (unchanged from slice 005).

## Command shape

Base plot (slice 005):

```bash
axicli path/to/layer.svg -m plot -c 1
```

With overrides (examples):

```bash
axicli file.svg -m plot -c 1 -s 30 -S 80 -a 60 -L 2
```

## PlotPilot validation policy

- UI and model layer use **1–100** for speeds and acceleration (matches argparse help text).
- Model must be `None` or integer 1–7.
- Invalid combinations rejected before subprocess.

## References

- https://axidraw.com/doc/cli_api/ (sections `speed_pendown`, `speed_penup`, `accel`, `model`)
- Bundled defaults: `axidrawinternal/axidraw_conf.py` in axicli 3.9.6 install
