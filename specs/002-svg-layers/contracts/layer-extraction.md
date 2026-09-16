# Contract: Layer extraction

## `extract_layers(document: SvgDocument) -> list[SvgLayer]`

**Preconditions**: `document.root` is a valid SVG element from `parse_svg_text`.

**Postconditions**:

- Non-empty list always (at least one synthetic layer when no Inkscape layers).
- If any Inkscape layer groups exist, every returned layer is such a group; ordinary `<g>` are excluded.
- If no Inkscape layers, exactly one synthetic layer bound to `document.root`.
- `order` values are `0 .. n-1` matching list order.
- Names follow label → id → `Layer {k}` fallback among unnamed Inkscape layers.
- Nested non-layer groups inside a layer do not produce extra top-level layers.

**Errors**: Does not raise for valid documents; malformed trees are not re-validated here.
