# Research: 001-svg-open

## XML parser choice

**Decision**: Use `xml.etree.ElementTree` from the standard library.

**Rationale**: Slice only requires well-formed XML and an SVG root tag. No path geometry,
namespaces beyond root detection, or DTD validation. Keeps dependencies zero and tests fast.

**Alternatives considered**: `lxml` (heavier dependency); `defusedxml` (security for untrusted
XML — defer until needed; local user-selected files only in this slice).

## SVG root detection

**Decision**: Accept root element if local tag name is `svg` (strip XML namespace URI prefix
`{http://www.w3.org/2000/svg}`).

**Rationale**: Matches common SVG files with and without default namespace on root.

## Document representation

**Decision**: Store `raw_text: str`, `root: xml.etree.ElementTree.Element`, plus `path` and
`name` on `SvgDocument`.

**Rationale**: Raw text supports future re-parse; Element supports 002 layer walks without
re-reading disk immediately.

## Encoding

**Decision**: Read bytes from disk; decode as UTF-8. On `UnicodeDecodeError`, fail with a
user-visible encoding message.

**Rationale**: SVG spec default is UTF-8; plotter artwork is overwhelmingly UTF-8.

## UI integration

**Decision**: `MainWindow` holds `SvgDocument | None`; `QFileDialog.getOpenFileName` with
`*.svg` filter; `QMessageBox` for errors.

**Rationale**: Minimal Qt surface; no separate presenter class until complexity warrants it.
