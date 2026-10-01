# Spec: axicli plot controls

Explicit axicli 3.9.6 behavior for path order, pen heights, constant speed, orientation, manual home / motors off, and a pre-plot estimate. Geometry and vpype are unchanged.

## Decisions

- **Path order** is one of: driver default (omit `-G`), strict (`-G4`, product default), basic (`-G1`), full with reversal (`-G2`).
- **Orientation** is always preserved. Plot and preview argv include `-N`. There is no Enabled option: axicli cannot force rotation on, and the direction is config-only. See `research.md`.
- **Pen up / pen down position** are optional 0–100 servo overrides (`-u`, `-d`). Omitted means driver default. Not millimeters.
- **Constant pen-down speed** (`-C`) is off by default (omit the flag). Stock axicli default is also off.
- **Home** is `walk_home` only. **Motors Off** is `disable_xy` only. Neither lowers the pen. Safe stop is unchanged.
- **Estimate** is a button, not a continuous recompute. It runs `axicli -v -T` on each layer’s prepared clipped SVG.

## Project compatibility

Format version remains 1.

| Key | Missing or null in an old file |
|-----|--------------------------------|
| `path_reordering` | Driver default (omit `-G`) |
| `pen_pos_up`, `pen_pos_down` | Omit `-u` / `-d` |
| `const_speed` | Off |

A QSettings store with no path-order key loads strict file order (`-G4`).

## Safety

Clipping, the final bounds validator, safe stop, multi-layer pen-up, and hardware-poll suspension while busy are unchanged. Home, Motors Off, and Estimate return a visible error when a plot or another manual command is already running. They are disabled in the plotter row while a plot is active.

## Out of scope

Geometry engine, vpype, layer architecture, fills, device profiles, plot queues, and a settings-screen redesign.
