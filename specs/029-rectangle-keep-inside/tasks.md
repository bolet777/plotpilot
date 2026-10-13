# Tasks: Rectangle Keep-Inside Clip

**Input**: Design documents from `/specs/029-rectangle-keep-inside/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Requested. Geometry, margin overlap, regression, and preview/plot parity live in `tests/test_rectangle_keep_inside.py`. Existing clip tests must stay green.

**Organization**: Tasks are grouped by user story. This file is Slice 1 only (no preview drawing UI).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

**Purpose**: Confirm the slice directory and leave dependencies alone.

- [x] T001 Confirm `specs/029-rectangle-keep-inside/` matches branch `029-rectangle-keep-inside` and `pyproject.toml` gains no dependencies

---

## Phase 2: Foundational

**Purpose**: The rectangle value every story clips against.

- [x] T002 Add `ClipRectangle` and `ClipRectangleError` in `src/plotpilot/models/clip_shape.py`

**Checkpoint**: Invalid rectangles can be rejected before any clip.

---

## Phase 3: User Story 1 - Keep pen strokes inside a rectangle (Priority: P1)

**Goal**: An optional axis-aligned rectangle keeps strokes inside its overlap with the printable area. Crossing strokes are cut. Exit and re-entry splits the run. Margins still win.

**Independent Test**: A line across a rectangle is trimmed to the overlap, a path that leaves and re-enters becomes two runs with no bridge, and a rectangle in the margin cannot emit points there.

### Tests for User Story 1

- [x] T003 [P] [US1] Add rectangle validation, overlap clipping, split, miss, and margin tests in `tests/test_rectangle_keep_inside.py`

### Implementation for User Story 1

- [x] T004 [US1] Intersect `keep_inside` with the printable `ClipRect` and Liang–Barsky clip once in `src/plotpilot/geometry/plot_viewport.py`
- [x] T005 [US1] Thread optional `keep_inside` through `src/plotpilot/services/layer_geometry.py`, `src/plotpilot/services/positioned_plot_service.py`, `src/plotpilot/services/preview_prepared_service.py`, and `src/plotpilot/services/preview_compute_service.py`

**Checkpoint**: Supplying a rectangle cuts geometry. Omitting it still compiles and defaults to today's clip.

---

## Phase 4: User Story 2 - Leave today's plots unchanged (Priority: P1)

**Goal**: No rectangle reproduces the current printable-area clip. Source SVG text and flattened document polylines stay unchanged.

**Independent Test**: Existing clipping tests pass. A prepare call with no rectangle matches a prepare call from before this argument. Flattened polylines compare equal before and after the clip.

### Tests for User Story 2

- [x] T006 [P] [US2] Add omitted-rectangle and source-immutability tests in `tests/test_rectangle_keep_inside.py`

### Implementation for User Story 2

- [x] T007 [US2] Default `keep_inside` to `None` on every new parameter so `src/plotpilot/services/plotter_service.py` and existing callers stay on the printable-area clip

**Checkpoint**: `tests/test_geometry_clipping.py` and `tests/test_print_margins.py` pass without edits.

---

## Phase 5: User Story 3 - Preview and plot describe the same cut (Priority: P2)

**Goal**: Preview preparation and plot preparation emit the same polylines for the same rectangle, including the empty-plot outcome.

**Independent Test**: `build_prepared_layer_preview` and `prepare_layer_plot_svg` agree with a rectangle and without one.

### Tests for User Story 3

- [x] T008 [P] [US3] Add preview/plot polyline parity tests in `tests/test_rectangle_keep_inside.py`

### Implementation for User Story 3

- [x] T009 [US3] Pass the same `keep_inside` into both prepare entries so `src/plotpilot/services/preview_prepared_service.py` and `src/plotpilot/services/positioned_plot_service.py` share one overlap

**Checkpoint**: Parity holds for a hit, a margin overlap, and a total miss.

---

## Phase 6: Polish

**Purpose**: Record decisions and run the quickstart checks.

- [x] T010 Document Slice 1 decisions in `specs/029-rectangle-keep-inside/implementation-notes.md`
- [x] T011 Add the slice to the spec index in `docs/ARCHITECTURE.md` and the coverage row in `tests/README.md`
- [x] T012 Run pytest and ruff as listed in `specs/029-rectangle-keep-inside/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. Blocks story work.
- **User Story 1 (Phase 3)**: Depends on Foundational. MVP.
- **User Story 2 (Phase 4)**: Depends on the default argument from Phase 3. Independently testable via omitted `keep_inside`.
- **User Story 3 (Phase 5)**: Depends on both prepare entries accepting `keep_inside`.
- **Polish (Phase 6)**: Depends on the stories above.

### User Story Dependencies

- **User Story 1 (P1)**: Starts after `ClipRectangle` exists. No UI.
- **User Story 2 (P1)**: The omitted-argument path of the same functions. No separate algorithm.
- **User Story 3 (P2)**: Requires User Story 1's argument on both preview and plot preparation.

### Parallel Opportunities

- T003 can be written before T004 and T005.
- T006 and T008 can be written in the same test module after the signatures exist.

### Parallel Example: User Story 1

```bash
# Tests first (must fail before the clip exists):
Task: "Add rectangle validation, overlap clipping, split, miss, and margin tests in tests/test_rectangle_keep_inside.py"

# Then the clip and the service argument:
Task: "Intersect keep_inside with the printable ClipRect in src/plotpilot/geometry/plot_viewport.py"
Task: "Thread optional keep_inside through the prepare services"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 and Phase 2.
2. Phase 3 tests, then the intersection clip.
3. Stop and run the rectangle tests plus `tests/test_geometry_clipping.py`.

### Incremental Delivery

1. Rectangle cut (US1).
2. Prove the default path is unchanged (US2).
3. Prove preview and plot match (US3).
4. Notes, index, full pytest and ruff.

Slice 2 (drawing the rectangle) is not in this task list.

---

## Notes

- Tests are required for this slice.
- Do not add packages to `pyproject.toml`.
- Do not change `PlotterService` call sites; the new argument defaults to absent.
- Mark each task `[x]` when it is done.
