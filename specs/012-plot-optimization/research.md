# Research: AxiDraw path reordering (axicli 3.9.6)

**Date**: 2026-09-20  
**CLI version**: `AxiDraw Command Line Interface 3.9.6` (`axicli --version`)

## Source

Primary source: `axicli --help` on the development machine with AxiDraw Software 3.9.6 installed.

Secondary: preview runs on `tests/fixtures/simple.svg` with `-v -T` (no hardware).

Official reference: https://axidraw.com/doc/cli_api/

## `-G` / `--reordering`

```
-G VALUE, --reordering VALUE
    SVG reordering option (0-4; 3 deprecated).
    0: Least; Only connect adjoining paths.
    1: Basic; Also reorder paths for speed.
    2: Full; Also allow path reversal.
    4: None; Strictly preserve file order.
```

| Value | Label (help) | Path reorder | Path reversal |
|-------|----------------|--------------|---------------|
| 0 | Least | Connect adjoining paths only | No |
| 1 | Basic | Reorder paths for speed | No |
| 2 | Full | Reorder paths for speed | Yes |
| 3 | (deprecated) | — | — |
| 4 | None | Strictly preserve file order | No |

When `-G` is **omitted**, axicli uses the reordering level from the AxiDraw configuration file (`axidraw_conf.py` / user config), not a hard-coded CLI default visible in `--help`.

## Plot mode interaction

- Reordering applies to normal plotting: `-m plot` (default mode).
- Deprecated standalone mode `-m reorder` exists in the mode list; PlotPilot does **not** use it. Use `-G` on plot invocations instead.

## Preview / dry-run (`-v`, `-T`)

Command shape (from slice 005):

```text
axicli file.svg -v -T
```

With reordering override:

```text
axicli file.svg -v -T -G1
```

Observed stdout (structured, stable line labels):

```text
Estimated print time: N.NNN Seconds
Length of path to draw: N.NNN m
Pen-up travel distance: N.NNN m
Total movement distance: N.NNN m
This estimate took N.NNN Seconds
```

Preview simulates plotting only (`-v`); no hardware motion. `-G` affects pen-up travel and estimated time in preview (verified: `-G1` vs `-G4` on `simple.svg` produced different pen-up distance and time).

PlotPilot does **not** implement an Estimate/Compare UI in this slice; metrics are documented for a possible follow-up.

## Copies (`-c`)

Reordering affects path execution order for each plot job. PlotPilot uses `-c 1` per invocation; optimization is applied per invocation, not across copies (N/A for current `-c 1` usage).

## Source file modification

- Default plot/preview: reads input SVG; does **not** write back unless `-o FILE` / `--output_file` is supplied.
- PlotPilot never passes `-o` for normal plots. Temporary layer SVG content on disk is unchanged; only runtime execution order may differ.

## Per-layer / document scope

Each `axicli` run processes one SVG file (PlotPilot: one isolated layer temp file per invocation). Reordering is scoped to paths within that file for that run. Multi-layer jobs remain separate axicli calls; no cross-layer combined optimization.

## Fills, groups, transforms

Not detailed in `--help`. Reordering is an SVG path execution optimization inside AxiDraw’s plot pipeline; PlotPilot does not rewrite SVG structure. Direction-sensitive artwork may be affected when value `2` (path reversal) is used.

## PlotPilot defaults (product decision)

- **UI default**: optimization **off** — omit `-G` so behavior matches pre-slice plots (axicli config default).
- **When enabled** (checkbox): pass `-G1` (Basic reorder for speed, no reversal).
- Optional future: combo for `-G2` (Full + reversal); not required for MVP checkbox.

## Limitations

- Does not merge paths, simplify geometry, or edit the source SVG.
- Value `3` is deprecated; do not expose.
- `-G4` strictly preserves file order (useful only if overriding a config that enables reordering); PlotPilot omits `-G` when off instead of forcing `-G4`.
- vpype and custom TSP are out of scope.
