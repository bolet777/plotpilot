# Quickstart: Editable Print Margins

## Automated

From the repository root:

```bash
uv run pytest tests/test_print_margins.py -q
./scripts/test_fast.sh
uv run pytest -m "not hardware" -q
uv run ruff check src tests
uv run ruff format --check src tests
```

No hardware test is required.

## What the tests cover

- Default 10 / 10, zero margins, negative rejection, impossible margins
- 300 × 217.9 → x 10, y 10, 280 × 197.9
- A4 portrait, A4 landscape, explicit AxiDraw model
- Line 0..300 becomes 10..290, vertical equivalent, exit/re-enter, curves, 200% scale, translation
- No emitted point inside the margin
- Inner preview boundary and prepared strokes stopping on it
- `QSettings` round trip, project round trip, legacy file defaults 10 / 10
- Margin edit marks the project dirty; reopen restores the spin boxes
- Project margins do not overwrite global defaults
- Margin edits reuse cached flattened geometry

## Manual

Launch the app (`./lance.sh` or the dev entry point) and load a drawing:

1. Confirm margins start at 10.0 / 10.0 and the printable line matches the current work area minus 20 mm on each axis.
2. Set 0 / 0. The inner boundary meets the work-area boundary and artwork can reach the machine edge.
3. Switch A4 portrait, A4 landscape, and an explicit AxiDraw model. The printable line follows the new size. The work-area dimensions themselves do not change except for the paper or model you selected.
4. Set scale to 200% and drag artwork into each margin. Faint source may cross the margin. Black prepared strokes stop on the inner boundary.
5. Type in the numeric fields. They stay responsive (no long freeze).
6. Save a project, change global margins on a plain SVG, reopen the project, and confirm the project margins return.
