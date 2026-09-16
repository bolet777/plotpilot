# Feature Specification: SVG Layer Preview

**Feature Branch**: `003-layer-preview`

**Created**: 2026-09-16

**Status**: Draft

**Input**: Display a visual preview of the currently selected SVG layer; update on layer selection.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preview selected layer (Priority: P1)

After opening a layered SVG, the user sees the first layer selected and its artwork in a preview
pane. Selecting another layer updates the preview immediately.

**Acceptance Scenarios**:

1. **Given** a successful open of a multi-layer SVG, **When** the window appears, **Then** the
   first layer is selected and its content is shown in preview.
2. **Given** a loaded document, **When** the user selects another layer, **Then** the preview
   shows only that layer’s content.

---

### User Story 2 - Whole-document preview (Priority: P1)

SVGs without Inkscape layers show one synthetic layer; preview shows the full document.

---

### User Story 3 - Safe failures (Priority: P1)

Invalid preview data or Qt render failure must not crash; document and layer list remain usable.

**Acceptance Scenarios**:

1. **Given** a loaded document, **When** preview generation or rendering fails, **Then** a neutral
   preview state is shown and the app continues to work.

---

### Edge Cases

- Preserve viewBox and width/height on generated preview SVGs.
- Include `<defs>` needed for gradients/patterns referenced by layer content.
- Do not mutate the loaded `SvgDocument` tree.
- Failed file open leaves prior document, layers, and preview unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Two-area layout: layer list left, preview right, filename visible.
- **FR-002**: Auto-select first layer after successful load; preview follows selection.
- **FR-003**: Build isolated preview SVG per layer without modifying source XML.
- **FR-004**: Synthetic layer previews full document; Inkscape layer previews layer subtree only.
- **FR-005**: Respect SVG coordinate system (viewBox, dimensions).
- **FR-006**: No plotting, AxiDraw, zoom/pan, editing, or export in this slice.

### Key Entities

- **Preview SVG**: Ephemeral serialized SVG string/bytes for Qt rendering.

## Success Criteria *(mandatory)*

- **SC-001**: Layer selection drives preview content in manual and automated checks.
- **SC-002**: Source document tree unchanged after preview generation (tests).
- **SC-003**: pytest and ruff pass; app launches without error.

## Assumptions

- Qt `QSvgRenderer` renders generated preview SVGs; no full CSS engine in PlotPilot.
- Including the source document’s `<defs>` block in layer previews is acceptable for reference resolution.
