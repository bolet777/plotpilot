# Testing PlotPilot

PlotPilot uses [pytest](https://docs.pytest.org/) via `uv`.

## Developer loops

**While coding** (single file or test):

```bash
uv run pytest tests/test_whatever.py -q
```

**Pre-commit / normal fast loop** (no slow integration, no hardware):

```bash
./scripts/test_fast.sh
# equivalent:
uv run pytest -m "not slow and not hardware" -q
```

**Full software validation** (includes slow integration, still no hardware):

```bash
uv run pytest -m "not hardware" -q
```

**Slow integration only** (auto-detect polling, longer async chains):

```bash
uv run pytest -m slow -q
```

**Physical AxiDraw** (explicit opt-in):

```bash
uv run pytest -m hardware -v
```

Hardware tests are excluded by default (`addopts` in `pyproject.toml` and collection skips).

## Expected suite timing (local dev machine, order of magnitude)

| Suite | Target |
|-------|--------|
| Pure models / SVG (no Qt workers) | &lt; 1 s |
| Fast suite (`not slow`, `not hardware`) | &lt; 30 s (goal &lt; 15 s) |
| Full non-hardware | &lt; 60 s when feasible |

Regressions: if the fast suite suddenly takes minutes, check for accidental `QMessageBox` modals in tests, missed Qt signal waits, or real `axicli`/hardware use.

## Safety

- Default `uv run pytest` uses `FakePlotterBackend` or mocked subprocess runners — not your AxiDraw.
- Tests run headless (`QT_QPA_PLATFORM=offscreen` in `tests/conftest.py`).
- Opening SVG in tests uses an injected `svg_file_chooser` — no modal `QFileDialog`.
- Patch `QMessageBox.warning` when testing UI paths that surface errors; offscreen modals block forever.

## Qt async tests

Prefer `tests/qt_helpers.py` (`wait_until`, `wait_for_plot_success`, …) over ad-hoc `QEventLoop` + 5 s timers. Connect or poll **before** assuming a signal was missed — do not burn multi-second timeouts on every plot test.

## Fixtures

Shared SVG files live under `tests/fixtures/` (e.g. `simple.svg`, `five_inkscape_layers.svg`, `malformed.xml`).
