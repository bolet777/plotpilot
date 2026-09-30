# Tasks: 018-fix-core-geometry

- [x] Precondition: PR #18 merged, branch `018-fix-core-geometry`, baseline green
- [x] Investigate and document B1 `pen_xy` root cause
- [x] Fix independent segment clipping + safe polyline continuity
- [x] B1 golden tests pass; remove xfails
- [x] B1 edge-case unit tests (`tests/test_geometry_clipping.py`)
- [x] Fix B2 via `Arc.length()` flattening estimate
- [x] B2 golden pass; arc matrix (`tests/test_geometry_arcs.py`)
- [x] B13 degenerate polyline cleanup at flush
- [x] B13 unit tests
- [x] Full regression + ruff
- [x] Spec kit docs + PR
