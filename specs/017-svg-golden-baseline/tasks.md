# Tasks: 017-svg-golden-baseline

- [x] Record baseline: `main` @ `5f507b4`, B11 failure, ruff I001 (research.md)
- [x] B11: wait for `PlotPhase.FAILED` and multi-layer `ERROR`
- [x] Ruff I001 / format in `tests/test_square_pipeline_regression.py`
- [x] T7: expect CSS px, not the B3 heuristic
- [x] Golden harness (`tests/golden_oracle.py`) — M/L parse only
- [x] Passing goldens: identity square, CarreA4 rotate, translate, relative subpaths
- [x] Passing locks: B9 meet, B6 document, B5 document, B7 parent, B3 large-line file, B10 10×10 coincidence
- [x] XFAIL: B1 (two cases), B2, B3 (rect + invariant), B5 isolated, B6 isolated, B7 child, B10 marker 200
- [x] B8 / Q1 fixture with `policy: pending` and no plot assertion
- [x] `tests/fixtures/golden/README.md`
- [x] D10: README, specs index, architecture (`geometry/`, slices through 016)
- [x] Fast suite, non-hardware suite, ruff check and format
- [ ] Merge — stopped for review
