# Tasks: Interactive Clip Rectangle

**Input**: Design documents from `/specs/030-clip-rectangle-tool/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: `tests/test_clip_rectangle_tool.py`

**Organization**: Slice 2 only. Ellipse and remove-inside stay out.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Branch `030-clip-rectangle-tool` from `main` (Slice 1 is in `ae37b99`)

## Phase 2: Foundational

- [x] T002 Add `drag_rectangle` and `translate_rectangle` in `src/plotpilot/models/clip_shape.py`

## Phase 3: User Story 1 - Draw and edit (P1)

- [x] T003 [US1] Clip tool, gestures, and amber overlay in `src/plotpilot/ui/preview_widget.py`
- [x] T004 [US1] Toolbar button and mutual exclusion in `src/plotpilot/ui/preview_workspace.py`
- [x] T005 [US1] Pass the rectangle through preview refresh in `src/plotpilot/ui/main_window.py` without clearing the flatten cache

## Phase 4: User Story 2 - Plot, estimate, multi-layer (P1)

- [x] T006 [US2] `keep_inside` on `PlotterService.start_plot_layer` and `request_pre_plot_estimate`
- [x] T007 [US2] `keep_inside` on `MultiLayerPlotJob` and `MultiLayerPlotService`

## Phase 5: User Story 3 - Project file (P2)

- [x] T008 [US3] Optional `clipping` object on version 1 in `ProjectSession` and `project_file_service.py`
- [x] T009 [US3] Restore and clear the rectangle from the main window

## Phase 6: Polish

- [x] T010 Document the tool in `docs/guide.md`, `docs/UI-V2.md`, `docs/ARCHITECTURE.md`, and the README indexes
- [x] T011 Full pytest, ruff check, and ruff format check
