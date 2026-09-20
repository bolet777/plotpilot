# Research: axicli 3.9.6 plot progress and preview

**CLI version verified**: `AxiDraw Command Line Interface 3.9.6`

## 1. Live plot progress during hardware plotting

`-b` / `--progress` enables a **terminal progress bar** with percentage and mm-travel
fraction. Official docs state it is only available in modes that plot to hardware
(`plot`, `layers`, `res_plot`), **not** in preview mode.

PlotPilot runs `axicli` with `stdout`/`stderr` piped (`subprocess.Popen` +
`communicate()`). The progress bar is a **TTY/cursor** UI; it does not emit a stable,
machine-parseable progress stream on stdout when captured. No documented JSON or
callback API exists without importing GPL AxiDraw Python internals.

**Conclusion**: Strategy A (true live progress via subprocess output) is **not viable**
with the current backend architecture.

## 2. Incremental stdout/stderr while plotting

Default plotting is **silent** (no progress). With `-b`, feedback is the progress bar
on the controlling terminal, not line-oriented progress events suitable for parsing.

## 3. Preview mode (`-v`) and time report (`-T`)

Command:

```bash
axicli file.svg -v -T
```

Example output (stable across runs on `tests/fixtures/valid_basic.svg`):

```text
Estimated print time: 2.052 Seconds
Length of path to draw: 0.053 m
Pen-up travel distance: 0.053 m
Total movement distance: 0.106 m
This estimate took 0.001 Seconds
```

With overrides (`-s 50 -S 75 -a 80 -L 1 -G 1`) the estimated print time **changes**
(1.624 s vs 2.052 s on the same fixture), so preview **respects** speed, acceleration,
model, and `-G` reordering flags passed on the command line.

Preview runs **without hardware** (exit 0, sub-second for small SVGs).

## 4. `-b` with preview

`axicli file.svg -v -b -T` produces the same estimate lines; `-b` does not add a
progress bar in preview mode (documented: progress bar only when plotting to device).

## 5. Metrics available from preview

| Field | Example | Parse reliably |
|-------|---------|----------------|
| Estimated print time | `Estimated print time: 2.052 Seconds` | Yes (regex) |
| Pen-down path length | `Length of path to draw: 0.053 m` | Yes |
| Pen-up travel | `Pen-up travel distance: 0.053 m` | Yes |
| Total movement | `Total movement distance: 0.106 m` | Yes |
| Preview compute time | `This estimate took 0.001 Seconds` | Yes (not used for UX) |

## 6. argv alignment with hardware plot

Hardware plot argv (PlotPilot): `[cli, svg, -m, plot, -c, 1, …settings…]`.

Preview estimate argv: `[cli, svg, -v, -T, …same settings flags…]` — no `-m plot`;
`-v` selects simulation.

## 7. Chosen strategy

**Strategy B — estimated progress**

1. Before / in parallel with plotting, run preview with the **same** settings overrides
   as the plot (including `-G1` when optimization enabled).
2. Parse `Estimated print time` as `estimated_total_seconds`.
3. During plot: `fraction = elapsed / estimated_total`, clamp to **0.99** while running.
4. Label UI **“estimated”**; set **100%** only when the backend reports success.
5. If preview fails: show elapsed + “Estimate unavailable”; plotting continues.

## 8. Limitations

- Estimate ≠ actual time (USB, acceleration, pen delays, load).
- No per-layer true position without TTY progress bar or GPL imports.
- Very short estimates (&lt;1 s) make percentage noisy; elapsed time remains primary.
