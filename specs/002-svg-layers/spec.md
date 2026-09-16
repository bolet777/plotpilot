# Feature Specification: SVG Layer Detection and List

**Feature Branch**: `002-svg-layers`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: "When an SVG document is loaded, detect its meaningful layers and display them in the PlotPilot UI."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See Inkscape layers after open (Priority: P1)

A user opens an SVG that was structured with Inkscape layers. The main window shows a **Layers**
section listing each layer by name, in the same order as in the document, with a small color
indicator when a representative color can be inferred from layer content.

**Why this priority**: Layer awareness is the foundation for preview and plotting per layer.

**Independent Test**: Open a fixture SVG with five Inkscape layers; the UI lists five rows with
correct names and order; unit tests on layer extraction pass without starting the GUI.

**Acceptance Scenarios**:

1. **Given** no document loaded, **When** the user opens an SVG with Inkscape layers, **Then**
   the Layers section lists those layers in document order with readable names.
2. **Given** a document with layers is loaded, **When** the user selects a layer row, **Then**
   that row is visibly selected (no plot or visibility action yet).

---

### User Story 2 - SVGs without Inkscape layers (Priority: P1)

A user opens an SVG that uses ordinary groups or flat shapes only (no Inkscape layer groups).

**Why this priority**: Most non-Inkscape SVGs must not explode into dozens of meaningless “layers”.

**Independent Test**: Open SVGs with nested `<g>` only or with no groups; exactly one synthetic
layer appears (e.g. document title or file name).

**Acceptance Scenarios**:

1. **Given** an SVG with nested groups but no Inkscape layer markers, **When** it is loaded,
   **Then** the layer list shows a single synthetic layer representing the whole document.
2. **Given** an SVG with no groups at all, **When** it is loaded, **Then** the layer list
   shows a single synthetic layer.

---

### User Story 3 - Replace layers on new open; preserve on failure (Priority: P1)

A user switches documents or attempts to open an invalid file.

**Why this priority**: Layer state must stay consistent with the active document and resilient
to errors.

**Independent Test**: Integration tests for loader + layer refresh; UI tests or manual check for
failed open leaving prior list unchanged.

**Acceptance Scenarios**:

1. **Given** document A with layers displayed, **When** the user opens valid document B,
   **Then** the layer list is replaced by B’s layers only.
2. **Given** document A with layers displayed, **When** open fails (missing, malformed, not SVG),
   **Then** document A and its layer list remain unchanged.

---

### Edge Cases

- Nested groups **inside** a real Inkscape layer must not appear as separate top-level layers.
- Layer name resolution: prefer Inkscape label, then element `id`, then generated names
  (`Layer 1`, `Layer 2`, …) for unnamed Inkscape layers.
- Colors: ignore `none` and obvious transparent values; if nothing found, show neutral/unknown
  swatch state.
- Namespace prefixes on attributes may vary; detection must use namespace URIs, not prefix strings.
- Multiple Inkscape layers at different depths: only elements matching the layer definition
  are listed; order follows document order among those elements.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: After a successful SVG load, the system MUST derive a ordered list of layers from
  the current document.
- **FR-002**: A layer MUST be identified when its element is a group (`<g>`) with Inkscape
  `groupmode="layer"` (Inkscape namespace URI `http://www.inkscape.org/namespaces/inkscape`).
- **FR-003**: If one or more Inkscape layers exist, the system MUST return only those layers
  (not every `<g>` in the file).
- **FR-004**: If no Inkscape layers exist, the system MUST expose exactly one synthetic layer
  representing the entire document, named from the document display name or a generic label such
  as `Document`.
- **FR-005**: Layer display names MUST prefer Inkscape label, then element `id`, then a
  generated fallback name preserving document order among unnamed layers.
- **FR-006**: Each layer MUST expose: stable identifier, display name, document order index,
  reference to the underlying XML group (or root for synthetic layer), optional representative
  color, and drawable child count when practical.
- **FR-007**: Representative color MUST use the first meaningful drawable descendant: prefer
  visible stroke, else visible fill, from direct attributes or inline `style` only (no full CSS
  cascade in this slice).
- **FR-008**: The main window MUST include a **Layers** section listing one row per layer with
  name and color swatch when available; rows MUST be selectable.
- **FR-009**: The system MUST NOT implement preview rendering, plotting, AxiDraw I/O, path
  optimization, editing, layer visibility toggling in the SVG, drag-and-drop, multi-document
  support, or generative features in this slice.
- **FR-010**: Layer extraction MUST be testable without the UI or Qt.

### Key Entities

- **SvgLayer**: A logical layer the user sees in the list (Inkscape layer or synthetic document
  layer); attributes include id, name, order, element reference, optional color, drawable count.
- **SvgDocument** (existing): Loaded file with parsed XML root; input to layer extraction.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Opening a standard five-layer Inkscape test SVG shows five layers in correct order
  with expected names in the UI.
- **SC-002**: Opening an SVG with only nested non-layer groups shows exactly one synthetic layer.
- **SC-003**: Failed open attempts leave the previous document and layer list unchanged in 100%
  of covered error cases (missing, unreadable, non-UTF-8, malformed XML, non-SVG root).
- **SC-004**: Automated tests cover at least: five-layer file, order, name fallbacks, color
  sources, no-color case, no-Inkscape-groups, no groups, nested groups inside a layer, document
  replacement, and failed-load preservation.

## Assumptions

- Users primarily work with Inkscape-exported SVGs for multi-layer art; other tools may omit
  Inkscape layer metadata.
- “Drawable” elements for counting and color search include common SVG shapes and paths
  (`path`, `line`, `rect`, `circle`, `ellipse`, `polyline`, `polygon`, `text`) and exclude
  `<defs>`, `<metadata>`, and pure container groups without treating containers as drawable.
- Synthetic layer references the SVG root element for stability.
- Stable layer identifiers are derived from XML `id` when present, otherwise a deterministic
  synthetic id tied to document order.
