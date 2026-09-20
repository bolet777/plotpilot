# Tests

PlotPilot uses **pytest** for automated tests. Default runs do **not** require a
display, attached AxiDraw, or `axicli` on `PATH`.

## Conventions

- **Unit tests** target pure logic in `svg/`, `models/`, `services/`, and
  `plotter/` (via `FakePlotterBackend` or mocked CLI).
- **Main window tests** inject fake plotter backends and drive Qt widgets where
  needed; they validate wiring, not visual pixels.
- **Hardware / axicli** — not part of CI; optional manual checks on a machine
  with AxiDraw software installed.

## Coverage map (by area)

| Module / behavior | Test files (examples) |
|-------------------|------------------------|
| SVG parse / load | `test_svg_parse.py`, `test_svg_loader.py` |
| Layers / preview SVG | `test_svg_layers.py`, `test_svg_preview.py` |
| Plot SVG prep / dimensions | `test_plot_service.py`, `test_plot_dimensions.py` |
| Plot settings | `test_plot_settings.py`, `test_settings_service.py` |
| Plotter backend / argv | `test_plotter_backend.py`, `test_plotter_backend_plot_argv.py` |
| PlotterService | `test_plotter_service.py`, `test_plotter_service_plot.py`, `test_plotter_auto_detect.py`, `test_safe_stop.py` |
| Multi-layer | `test_multi_layer_plot_service.py` |
| Main window | `test_main_window_*.py` |
| Packaging smoke | `test_macos_app_packaging.py` |
| Import / smoke | `test_smoke.py` |

Fixtures live in `tests/fixtures/` (sample SVGs for layers, preview, errors).

## Commands

From the repository root:

```bash
uv sync --group dev
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
```

Run a subset:

```bash
uv run pytest tests/test_svg_layers.py -q
```
