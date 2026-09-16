# Research: AxiDraw CLI / API (3.9.6)

**Environment**: macOS, `axicli` 3.9.6 via pipx; `pyaxidraw` not in PlotPilot `uv` env.

## CLI commands (verified locally)

| Goal | Command | Notes |
|------|---------|--------|
| Version | `axicli --version` | Passive |
| Help | `axicli --help` | Documents `-m manual`, `-M` manual_cmd |
| List named units | `axicli -m manual -M list_names` | Exit 0; passive serial scan; no XY walk |
| Connect / firmware | `axicli -m manual -M fw_version` | Exit 1 + "Failed to connect" when absent |
| Pen up | `axicli -m manual -M raise_pen` | Requires connection |
| Pen down | `axicli -m manual -M lower_pen` | Requires connection |
| Disable motors | `axicli -m manual -M disable_xy` | Optional release after session |

Manual mode does not require an SVG positional argument.

Preview flag (`-v`) blocks manual hardware commands.

## Python API

`pyaxidraw` ships inside the `axicli` pip package (GPL-licensed core libraries). It is **not**
importable from PlotPilot's virtualenv unless users add `axicli` as a dependency.

## Licensing / distribution

- PlotPilot: **MIT**.
- `axicli` distribution: top-level CLI/examples **MIT**; bundled `pyaxidraw`, `axidrawinternal`,
  and `plotink` include **GPL** components (see axicli METADATA "Licensing" section).
- **Decision**: Do **not** vendor or depend on `axicli`/`pyaxidraw` in PlotPilot's wheel. Invoke
  the user-installed `axicli` executable via subprocess. Document external install requirement.
  This keeps PlotPilot MIT-only while allowing integration on machines with official software.

## CLI vs Python API

**Chosen: subprocess → `axicli`** because:

- Avoids GPL library linkage in the MIT package
- Matches how users install AxiDraw on macOS (pip/pipx/app)
- Easy to mock in tests (inject runner)
- Same commands future plotting slice will use (`-m plot`, etc.)
- Works without adding Python deps

Python API would require optional `axicli` pip dependency and GPL-adjacent packaging review.

## Detection strategy

1. If `axicli` not on PATH → `ERROR` with install hint.
2. Run `list_names` (passive) to detect multiple named units.
3. Run `fw_version` to confirm serial connection and capture firmware string in stdout/stderr.

No `walk_*` or plot modes during detection.

## Multiple devices

Official default port behavior (`-P 0`): first unit found. If `list_names` reports more than one
named line, status message notes multiple devices; still use default first unit for pen commands
(device picker deferred).
