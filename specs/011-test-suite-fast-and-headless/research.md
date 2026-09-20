# Research: 011 test suite fast and headless

## Before (baseline audit)

| Metric | Value |
|--------|--------|
| Test count | 179 collected (`pytest --collect-only`) |
| Full suite duration | ~5+ minutes (prior runs; full `--durations=30` run interrupted to avoid blocking dev) |

### Root causes (code review)

1. **`MainWindow()` without `FakePlotterBackend`** — `test_main_window_{preview,layers,open_svg}.py` constructed windows with real `AxiDrawCliBackend` and `start_automatic_monitoring()`, risking subprocess/hardware probes and 5s polling timers.
2. **Per-test Qt teardown** — `tests/conftest.py` drained `QThreadPool` for up to **5s after every test** (~179× overhead).
3. **Production auto-detect intervals** — `AUTO_DETECT_INTERVAL_MS = 5000` used in integration tests unless manually patched.
4. **`QFileDialog`** — `_open_svg()` always opened a modal picker when the open action ran with production code path (buttons wired to the same action could show a dialog if chooser not injected).
5. **`time.sleep` in fakes** — slow presence overlap tests in `test_plotter_auto_detect.py`.

### QFileDialog triggers (before fix)

Any test calling `MainWindow._open_svg()` or triggering `_open_svg_action` without mocking file selection. Open-button tests only asserted action wiring, not `_open_svg()` body — risk on future changes. Preview/layer tests used real backend side effects, not dialogs directly.

### Hardware touchpoints in tests (before)

- Default `MainWindow()` → `AxiDrawCliBackend()` + monitoring.
- `AxiDrawCliBackend` in backend tests uses injected `_runner` or mocked `Popen` (safe).
- No `@pytest.mark.hardware` gate.

## After (architecture)

- Default pytest excludes `hardware` (`addopts` + skip hook unless `--hardware`).
- `@pytest.mark.slow` on auto-detect integration tests; fast dev uses `-m "not slow"`.
- Global test intervals: 25ms / 15ms via conftest autouse monkeypatch; optional constructor injection on `PlotterService` / `MainWindow`.
- `choose_svg_file()` + injectable `svg_file_chooser` on `MainWindow`.
- Shared `main_window` / `fake_plotter_backend` fixtures; `QT_QPA_PLATFORM=offscreen`.
- Thread pool drain capped at 1s with 25ms waits.

## After (measured)

| Suite | Count | Duration |
|-------|-------|----------|
| `pytest -m "not slow"` | 168 passed, 1 skipped (hardware), 13 deselected (slow) | **~71s** |
| `pytest -q` (default, no hardware) | 181 passed, 1 deselected (hardware) | **~72s** |
| Hardware only | 1 test (`tests/hardware/test_axidraw_presence.py`) | opt-in |

Down from ~5+ minutes (pre-change full suite) primarily by fixing Qt waits that slept full 5–8s timeouts after missed signals, using `FakePlotterBackend` in UI tests, 25ms detect intervals in tests, and lighter per-test teardown.
