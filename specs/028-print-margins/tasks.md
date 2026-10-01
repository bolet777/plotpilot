# Tasks: Editable Print Margins

**Input**: Design documents from `/specs/028-print-margins/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Requested in the feature specification. Targeted cases live in `tests/test_print_margins.py`.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested as an increment.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

**Purpose**: Confirm the slice directory and leave existing tooling alone.

- [x] T001 Confirm `specs/028-print-margins/` plan, data model, and contract match branch `028-print-margins`

---

## Phase 2: Foundational

**Purpose**: Domain types every story uses.

- [x] T002 Add `PrintMargins`, `PrintableArea`, and validation in `src/plotpilot/models/print_margins.py`

**Checkpoint**: Model tests can run before UI or persistence.

---

## Phase 3: User Story 1 - Plot only inside a safe printable area (Priority: P1)

**Goal**: Preview, estimate, and plot clip to an offset printable rectangle in machine coordinates.

**Independent Test**: A full-width line on a 300 mm work area with 10 mm margins prepares as x = 10..290, and every emitted point stays inside the printable rectangle.

### Tests for User Story 1

- [x] T003 [P] [US1] Add model, printable-area, clipping, and validator tests in `tests/test_print_margins.py`

### Implementation for User Story 1

- [x] T004 [US1] Accept an arbitrary clip rectangle in `src/plotpilot/geometry/plot_viewport.py` and validate emitted points against it
- [x] T005 [US1] Thread `PrintMargins` through `src/plotpilot/services/layer_geometry.py`, `src/plotpilot/services/positioned_plot_service.py`, `src/plotpilot/services/preview_prepared_service.py`, and `src/plotpilot/services/preview_compute_service.py`
- [x] T006 [US1] Pass margins into estimate and plot in `src/plotpilot/services/plotter_service.py` and `src/plotpilot/services/multi_layer_plot_service.py` without changing axicli flags

**Checkpoint**: Geometry and plot preparation honor margins with the default 10 / 10 on the product path. Low-level calls that omit a clip rectangle stay full-bleed.

---

## Phase 4: User Story 2 - See and edit the margin (Priority: P2)

**Goal**: Compact margin fields and two preview boundaries, with cache reuse.

**Independent Test**: Changing a margin updates the printable readout and the inner boundary, and does not flatten the SVG again.

### Tests for User Story 2

- [x] T007 [P] [US2] Add preview-boundary and cache-reuse tests in `tests/test_print_margins.py`

### Implementation for User Story 2

- [x] T008 [US2] Add margin spin boxes and the printable line in `src/plotpilot/ui/artwork_transform_controls.py`
- [x] T009 [US2] Draw the inner printable boundary in `src/plotpilot/ui/preview_widget.py` using a palette color
- [x] T010 [US2] Wire edits, limits, and cached preview refresh in `src/plotpilot/ui/main_window.py`

**Checkpoint**: The main window shows both rectangles and stays responsive when margins change.

---

## Phase 5: User Story 3 - Remember margins per session (Priority: P3)

**Goal**: QSettings defaults, project-owned margins, legacy 10 / 10, and dirty state.

**Independent Test**: A project round-trips its margins, a file without `print` opens at 10 / 10, and a project session does not write global defaults.

### Tests for User Story 3

- [x] T011 [P] [US3] Add QSettings, project, legacy, and dirty-state tests in `tests/test_print_margins.py`

### Implementation for User Story 3

- [x] T012 [US3] Persist margins in `src/plotpilot/services/settings_service.py` without writing them during a project session
- [x] T013 [US3] Add optional `print` fields to `src/plotpilot/models/project_session.py` and `src/plotpilot/services/project_file_service.py`
- [x] T014 [US3] Restore margin controls on project open and mark edits dirty in `src/plotpilot/ui/main_window.py`

**Checkpoint**: Old projects open. New projects keep their own margins.

---

## Phase 6: Polish

**Purpose**: Suite and lint gates from the quickstart.

- [x] T015 Run `tests/test_print_margins.py`, `./scripts/test_fast.sh`, `uv run pytest -m "not hardware"`, and ruff check/format

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup → Foundational → US1 → US2 → US3 → Polish
- US2 paints the rectangle US1 clips to
- US3 stores the same `PrintMargins` value US2 edits

### User Story Dependencies

- **User Story 1 (P1)**: After the model. No UI required for the clip tests.
- **User Story 2 (P2)**: After US1 so the preview shows the same geometry the plotter receives.
- **User Story 3 (P3)**: After the model. UI restore depends on US2 controls.

### Parallel Opportunities

- T003 can be drafted beside T002
- T007 and T011 touch the same test file, so they stay sequential with the other test tasks

### Parallel Example: User Story 1

```bash
# After PrintMargins exists, geometry and the service wiring are sequential
# because they share the clip signature.
Task: "Arbitrary clip rectangle in src/plotpilot/geometry/plot_viewport.py"
Task: "Thread PrintMargins through preview and plot services"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Add `PrintMargins` and `PrintableArea`
2. Clip and validate against the offset rectangle
3. Confirm a 0..300 line prepares as 10..290

### Incremental Delivery

1. US1 makes estimate and plot safe
2. US2 makes the inset visible and editable
3. US3 makes it stick for projects and defaults

## Notes

- Do not change curve flattening, axicli flags, transform math, or work-area dimensions
- Product default is 10 / 10; omitted low-level clip bounds remain the full viewport
