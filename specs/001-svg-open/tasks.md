# Tasks: 001-svg-open

## Phase 1 — Core (no UI)

- [x] T001 Create `SvgDocument` model in `src/plotpilot/models/svg_document.py`
- [x] T002 Implement `parse_svg_text` in `src/plotpilot/svg/parse.py` with error types
- [x] T003 Implement `load_svg_from_path` in `src/plotpilot/services/svg_loader.py`
- [x] T004 Add fixtures under `tests/fixtures/`
- [x] T005 Add `tests/test_svg_parse.py` and `tests/test_svg_loader.py`

## Phase 2 — UI

- [x] T006 Wire **File → Open SVG…** and **Cmd+O** in `main_window.py`
- [x] T007 Display loaded file name; preserve state on cancel/failure; error dialogs

## Phase 3 — Verify

- [x] T008 Run pytest and ruff; fix any issues
