# Feature Specification: Open SVG File

**Feature Branch**: `001-svg-open`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: "Allow the user to open a local SVG file from the PlotPilot UI and load it into application state."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open a valid SVG (Priority: P1)

A user chooses **File → Open SVG…** (or **Cmd+O** on macOS), picks an SVG file from the
system file picker, and sees the application acknowledge that file as the current document.

**Why this priority**: Without loading an SVG, no later preview, layer, or plot workflows
can exist.

**Independent Test**: Open a minimal valid SVG; the main window shows the selected file name
and the application holds document state for that path and content.

**Acceptance Scenarios**:

1. **Given** no document is loaded, **When** the user opens a valid SVG via the menu or
   **Cmd+O**, **Then** the file loads and the main window displays the file name clearly.
2. **Given** a document is already loaded, **When** the user opens another valid SVG,
   **Then** application state reflects the newly selected file (single active document).

---

### User Story 2 - Cancel open (Priority: P1)

A user starts **Open SVG…** but cancels the file picker.

**Why this priority**: Cancel must be safe and predictable.

**Independent Test**: Cancel with and without an existing document; state is unchanged.

**Acceptance Scenarios**:

1. **Given** no document loaded, **When** the user cancels the picker, **Then** nothing
   changes in the UI or application state.
2. **Given** a valid document is loaded, **When** the user cancels the picker, **Then** the
   previously loaded document and displayed file name remain unchanged.

---

### User Story 3 - Recover from invalid files (Priority: P1)

A user selects a file that cannot be loaded as an SVG document.

**Why this priority**: Real-world files are often wrong, corrupt, or mislabeled.

**Independent Test**: Attempt to open fixture files representing each failure mode; user sees
a clear dialog and prior state is preserved when applicable.

**Acceptance Scenarios**:

1. **Given** a missing or unreadable path, **When** open is attempted, **Then** a friendly
   error dialog explains the problem and the app does not crash.
2. **Given** malformed XML, **When** open is attempted, **Then** a friendly error dialog
   explains the file is not valid XML/SVG and any previously loaded document remains.
3. **Given** well-formed XML whose root is not an SVG element, **When** open is attempted,
   **Then** a friendly error dialog explains the file is not SVG and any previously loaded
   document remains.

---

### Edge Cases

- Empty file or whitespace-only file → treat as load/parse failure with a clear message.
- SVG root with namespace (e.g. `http://www.w3.org/2000/svg`) → must be accepted as SVG.
- File picker filter shows SVG files; user may still pick a non-SVG file if the OS allows it
  → validate after selection.
- Very large files are not optimized in this slice; only read and parse enough to validate
  root element (full file read is acceptable for typical plotter SVG sizes).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST provide **File → Open SVG…** with keyboard shortcut
  **Cmd+O** on macOS.
- **FR-002**: **Open SVG…** MUST open a native file picker filtered to `.svg` files.
- **FR-003**: Cancelling the picker MUST leave UI and document state unchanged.
- **FR-004**: On successful open, the application MUST store at minimum: absolute file path,
  file name, and the SVG content in a form suitable for later processing (raw text and/or
  parsed structure).
- **FR-005**: On successful open, the main window MUST visibly show the loaded file name.
- **FR-006**: Loading MUST verify the file is readable, parseable as XML, and has an SVG
  root element (including common SVG namespace on the root tag).
- **FR-007**: On any load failure, the application MUST show a user-friendly error dialog,
  MUST NOT crash, and MUST NOT replace a previously valid document with failed state.
- **FR-008**: Document loading and validation logic MUST be testable without running the
  graphical UI.
- **FR-009**: This slice MUST NOT add layer detection, rendering/preview, plotter
  communication, plotting, editing, drag-and-drop, recent files, persistence, or
  multi-document windows.

### Key Entities *(include if feature involves data)*

- **SVG document**: The single in-memory document representing the user’s current file—path,
  display name, and loaded SVG content/metadata needed for future slices.
- **Open result**: Success with a new document, or failure with a reason suitable for display.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can open a valid local SVG and see the correct file name in the main
  window within one interaction (menu or **Cmd+O** → choose file).
- **SC-002**: 100% of cancel actions during open leave prior document and UI unchanged.
- **SC-003**: For malformed XML, non-SVG XML, and missing/unreadable files, users always
  receive an explanatory dialog and the application remains running.
- **SC-004**: Automated tests cover valid SVG, malformed XML, non-SVG root, missing file,
  state preservation after failure, and path/name extraction without launching the UI.

## Assumptions

- One active SVG document in memory; opening a new file replaces the previous one on success
  only.
- Validation is structural (XML + SVG root), not full SVG schema or rendering correctness.
- macOS is the primary target; **Cmd+O** is the required shortcut on macOS for this slice.
- Encoding: UTF-8 is expected; other encodings may fail with a clear message if detected.

## Out of Scope

- SVG layer detection (**002-svg-layers** and later).
- Preview, plotter, optimization, persistence, and multi-document UI.
