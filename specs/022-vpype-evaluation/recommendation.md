# Recommendation (Task #6)

## Decision

**KEEP CURRENT ENGINE**

## Evidence

1. **Correctness:** With PlotPilot’s `SvgPageGeometry` mm mapping and Liang–Barsky clip, vpype read matches **all 18 golden preparations** (bbox + polyline count) — see `comparison.md`. That parity shows vpype adds little beyond shared **svgelements** flattening already used in `plot_viewport.py`.

2. **Semantic gaps:** vpype imports **fill-only** and **`stroke="none"`** geometry PlotPilot correctly rejects (B8/Q1 policy). Text/images discarded without PlotPilot-style diagnostics. Dashes not honored in geometry.

3. **Architecture:** Layer isolation, canonical page geometry, preview diagnostics, and **post-clip validator** remain PlotPilot-specific. vpype does not replace those; “vpype core” would still require a thick adapter layer.

4. **Clipping safety:** Machine-bound guarantee comes from PlotPilot validator + Liang–Barsky. vpype `crop` is usable but unvalidated and crops SVG page on read by default — easy to misuse.

5. **Performance:** vpype read is **~15–20% faster** on 1k–10k synthetic paths but both are dominated by flatten cost; current engine is already sub-ms on typical golden files.

6. **Packaging:** vpype pulls **numpy + scipy + shapely + multiprocess** (~100 MB+ site-packages). PlotPilot macOS bundle avoids this weight today. PyInstaller cost is high for uncertain gain.

7. **Optimization:** vpype `linesort` / `linemerge` could complement axicli `-G1` later, but that is a **separate** preprocessing experiment — not a geometry-engine migration.

## Options considered

| Option | Benefits | Risks | Effort |
|--------|----------|-------|--------|
| **A. Keep current** | Golden-backed, lightweight deps, explicit stroke policy, safety validator | Maintain custom clip/flatten code | None |
| **B. Hybrid** | Could reuse vpype flatten or optimizers | Two stacks (svgelements twice), packaging bloat, semantic drift on fill/stroke | Medium–high |
| **C. vpype core** | Rich optimizer CLI ecosystem | Loses layer/page/diagnostic integration; scipy in app; fill/stroke regressions | High |

## Optional future seam (not implemented)

If optimization integration is revisited:

```python
class PlotGeometryEngine(Protocol):
    def prepare(self, svg_text: str, *, viewport_mm, transform) -> PreparedPlotSvg: ...
```

Implementations: `CurrentGeometryEngine` (today), `VpypeGeometryEngine` (experimental). **Not added** in this slice — no production refactor warranted.

## Follow-ups (out of scope Task #6)

- Subprocess experiment: `vpype read … linemerge linesort write` vs axicli `-G1` on real plots (hardware-free SVG diff).
- Re-evaluate if vpype 1.16+ changes SVG unit handling or stroke filtering.
