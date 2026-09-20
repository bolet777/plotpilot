# Plan

1. Audit suite (counts, slow patterns, QFileDialog, hardware paths).
2. Pytest markers `slow`, `hardware`; default exclude hardware.
3. Headless Qt + faster teardown in `conftest.py`.
4. Inject SVG file chooser; fake plotter in UI tests.
5. Short auto-detect intervals in tests; mark slow integration tests.
6. Document in `docs/testing.md`; measure before/after.
