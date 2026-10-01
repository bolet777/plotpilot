# Golden suite comparison (vpype spike vs current engine)

Method: for each golden preparation, run **current** `_prepare` and **vpype spike** with:

```text
vpype.read_svg (q = 0.05 mm) → PlotPilot SvgPageGeometry mm map → ArtworkTransform → clip
```

Default clip for parity tests: **Liang–Barsky** (same as production). Separate test uses **vpype `LineCollection.crop`** on B1 exit/re-enter.

Classifications: `SAME` | `VPYPE BETTER` | `CURRENT BETTER` | `SEMANTIC DIFFERENCE` | `UNSUPPORTED`

Tolerance: fixture `tolerance_mm` (default 0.02 mm). Golden expectations unchanged.

## Summary table (hybrid mm map + Liang–Barsky)

| Case | Preparation | Verdict |
|------|-------------|---------|
| square/identity_inside | document | **SAME** |
| viewbox/carre_a4_rotate | document | **SAME** |
| transforms/translate_rect | document | **SAME** |
| paths/relative_multisubpath | document | **SAME** |
| viewbox/b9_preserve_aspect_meet | document | **SAME** |
| styles/b6_root_style_document | document | **SAME** |
| square/b3_viewboxless_rect_plus_line | document | **SAME** |
| groups/b10_marker_viewbox_10 | document | **SAME** |
| groups/b10_marker_viewbox_200 | document | **SAME** |
| clipping/b1_square_exit_reenter | document | **SAME** |
| clipping/b1_scaled_square_exit_reenter | document | **SAME** |
| paths/b2_near_complete_arc | document | **SAME** |
| square/b3_viewboxless_rect | document | **SAME** |
| layers/b5_px_inkscape_layer | document | **SAME** |
| layers/b5_px_inkscape_layer | isolated | **SAME** |
| layers/b7_nested_transformed_layer | parent | **SAME** |
| layers/b7_nested_transformed_layer | child | **SAME** |
| styles/b6_layer1_isolated | isolated | **SAME** |

Automated: `tests/test_vpype_evaluation.py` (parametrized golden list).

**Note:** SAME here means bbox + polyline **count** match current output at fixture tolerance. Point-by-point identity is not asserted (flattening order may differ); topology class is stable on these fixtures.

## Hard cases (audit ids)

| Id | Case | Hybrid (LB clip) | vpype rect clip | Notes |
|----|------|------------------|-----------------|-------|
| A | B1 exit/re-enter | SAME | SAME, no spurious diagonal | Both clippers split correctly on spike |
| B | B2 near-complete arc | SAME | (not golden-asserted) | Arc steps: vpype `length/quantization` vs PlotPilot `Arc.length()` cap |
| C | B3 viewBox-less CSS px | SAME | — | mm map uses PlotPilot page geometry after vpype read |
| D | B5 isolated px layer | SAME (doc + isolated) | — | Layer isolation still PlotPilot-only before read |
| E | B6 CSS class / root style | SAME | — | vpype does not implement PlotPilot style isolation; isolated SVG input used |
| F | B7 nested transformed layer | SAME | — | Transforms from svgelements in both paths |
| G | B9 preserveAspectRatio | SAME | — | |
| H | B10 nested marker viewBox | SAME | — | Markers not expanded by vpype; fixture uses stroked path only |
| I | clipped curves | covered by B1/B2 | — | |
| J | multiple subpaths | SAME (`relative_multisubpath`) | — | |
| K | large SVG (synthetic) | perf only | — | see benchmarks.md |

## Pure vpype semantics (no PlotPilot mm map)

If coordinates are naively converted (px→mm with fixed 96 dpi only):

- viewBox-scaled documents **diverge** from golden (expected — vpype page px ≠ PlotPilot physical mm policy).

Therefore vpype **cannot** replace `SvgPageGeometry` without replicating PlotPilot rules.

## Unsupported / semantic content (not golden-asserted)

| Content | Current PlotPilot | vpype read |
|---------|-------------------|------------|
| fill-only rect (B8) | No stroke → empty → error | **Imports closed rect** → **SEMANTIC DIFFERENCE** |
| text | Ignored / diagnostic | **Discarded** (0 paths) |
| image | Ignored | **Discarded** |
| stroke:none rect | Ignored | **Still imports** → **SEMANTIC DIFFERENCE** |
| CSS classes | Style isolation in layer export | Attributes partially in metadata; no class engine |
| markers | Not plotted as separate geometry | Not expanded |
| clipPath | Not SVG clip (machine clip only) | Not applied |
| dashed stroke | Continuous stroke in output | Continuous line; dash in metadata only |

## Clipping safety (machine rectangle)

| Clipper | Guarantees all points in [0,W]×[0,H]? | Exit/re-enter | Curves |
|---------|----------------------------------------|---------------|--------|
| PlotPilot Liang–Barsky + validator | **Yes** (raises if violation) | Correct (B1 golden) | Flatten then clip |
| vpype `crop` (axis half-planes) | **Mostly**; no final validator in vpype | B1 OK in spike | Pre-flattened polylines |
| vpype `read` default crop | Clips to **SVG page**, not machine | N/A | N/A |

Recommendation: do not rely on vpype alone for safety-critical machine bounds; PlotPilot validator remains necessary.
