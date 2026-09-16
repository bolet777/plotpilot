# Tests

PlotPilot uses **pytest** for automated tests.

## Conventions

- **Unit tests** live next to the behavior they protect: pure logic in `svg/`,
  `plotter/` (without hardware), `services/`, and `models/` should be testable
  without Qt or a plotter.
- **UI tests** stay minimal until they add clear value; default CI should not
  require a display or attached hardware.

## Commands

From the repository root (with the dev environment synced):

```bash
uv sync --group dev
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
```
