# Research: SVG Layers

## Inkscape layer markers

Inkscape marks layers as `<g inkscape:groupmode="layer" inkscape:label="…">`. In ElementTree,
namespaced attributes appear as `{http://www.inkscape.org/namespaces/inkscape}groupmode` and
`{…}label`, independent of XML prefix (`inkscape`, `svg`, etc.).

## Layer discovery order

`Element.iter()` yields elements in document order (depth-first). Filtering to Inkscape layer
groups preserves visual/document order among layers.

## Non-layer SVGs

Ordinary `<g>` elements lack `groupmode="layer"` and must not become layers. A single synthetic
layer referencing the `<svg>` root avoids listing nested groups.

## Representative color

Search layer subtree depth-first for the first drawable shape (`path`, `rect`, …). Read `stroke`
then `fill` from attributes, then from semicolon-separated inline `style`. Ignore `none` and
`transparent`. No `<style>` blocks or CSS classes in this slice.

## Element reference in models

Store the `xml.etree.ElementTree.Element` on `SvgLayer` for future preview/plot slices; tests
compare identity or tag/id without serializing.
