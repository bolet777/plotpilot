# Testing PlotPilot

PlotPilot uses [pytest](https://docs.pytest.org/) via `uv`.

## Commands

**Fast development** (no slow integration, no hardware):

```bash
uv run pytest -m "not slow" -q
```

**Normal automated suite** (includes slow integration, still no hardware):

```bash
uv run pytest -q
```

**Slow integration only**:

```bash
uv run pytest -m slow -q
```

**Physical AxiDraw** (explicit opt-in — may touch the machine; passive probe only in repo today):

```bash
uv run pytest -m hardware -v
```

Hardware tests are excluded by default (`addopts` in `pyproject.toml` and collection skips). They skip cleanly when `axicli` or a plotter is unavailable.

## Safety

- Default `uv run pytest` uses `FakePlotterBackend` or mocked subprocess runners — not your AxiDraw.
- Tests run headless (`QT_QPA_PLATFORM=offscreen` in `tests/conftest.py`).
- Opening SVG in tests uses an injected `svg_file_chooser` — no modal `QFileDialog`.

## Fixtures

Shared SVG files live under `tests/fixtures/` (e.g. `simple.svg`, `five_inkscape_layers.svg`, `malformed.xml`).
