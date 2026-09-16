# Research: axicli safe stop cleanup (3.9.6)

Sources: `axicli --help` (local), [AxiDraw CLI API](https://axidraw.com/doc/cli_api/).

## Commands

| Step | Command | Notes |
|------|---------|--------|
| Pen up | `axicli -m manual -M raise_pen` | Idempotent if already up |
| Return to enable origin | `axicli -m manual -M walk_home` | Not hardware absolute 0,0 |
| Disable motors | `axicli -m manual -M disable_xy` | De-energize XY steppers |

## walk_home semantics

Official docs: moves the carriage to **the position where the motors were first enabled** for the
current session. In typical use (carriage at home corner before enable/plot), this matches the home
corner; if motors were enabled elsewhere, `walk_home` returns there instead.

Docs explicitly recommend `walk_home` after pausing a plot that will not be resumed. Requires EBB
firmware **2.6.2+**.

After an interrupted plot (Ctrl+C / SIGINT), firmware retains motion state; `walk_home` is the
documented way to return to the enable-origin before further manual handling.

## raise_pen after interrupt

`raise_pen` only lifts when pen is down or indeterminate; safe to call after stop. Plot mode may
leave pen down mid-segment after SIGINT; raising before XY transit is required.

## disable_xy safety

Disabling motors while the carriage is mid-transit could leave it between positions with no holding
torque. PlotPilot **skips `disable_xy` if `walk_home` fails** so we do not de-energize during an
unknown XY position after a failed home move.

## raise_pen failure

If `raise_pen` fails (disconnect, timeout), PlotPilot **does not run `walk_home` or `disable_xy`**
because XY motion with pen potentially down is higher risk; errors are surfaced clearly.

## Plot stop (unchanged)

PlotPilot Stop → SIGINT to plot child, 8s wait, terminate, kill (see slice 005 research).
