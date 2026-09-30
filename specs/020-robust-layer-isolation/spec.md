# 020 — Robust layer isolation

Fix audit items B6, B7, D12, and U11 without changing preview parity, fill-only policy, orientation, or axicli flags.

## Root causes

### B6 — root CSS lost on isolation

`build_layer_preview_svg` copied the SVG root shell and `<defs>` but omitted sibling `<style>` blocks. Isolated layers referencing CSS classes (e.g. `.st0`) lost stroke/fill; plot prep produced no intersecting artwork.

**Fix:** Copy direct root children tagged `style` and `defs` into every isolated document (no CSS pruning in this task).

### B7 — nested Inkscape layer missing ancestor context

Isolation deep-copied only the target layer `<g>`, dropping ancestor groups (transform, stroke, fill, opacity). Nested child layers plotted in local coordinates without parent `translate(40,40)` and `stroke="black"`.

**Fix:** Reconstruct the ancestor chain from the document root to the target layer: shallow-copy each ancestor wrapper (attributes only), deep-copy the target subtree. Siblings under those ancestors are excluded.

### D12 — layers inside `<defs>`

`_extract_inkscape_layers` used `root.iter()` without excluding Inkscape layer groups under `<defs>`.

**Fix:** Build a `parent_map` once; skip any layer whose ancestry includes a `<defs>` element.

### U11 — hidden layers indistinguishable

Layers with `display:none` or hidden visibility were listed like visible layers.

**Fix:** `SvgLayer.hidden` from the layer element’s presentation attributes; UI shows `list_label` with an `(hidden)` suffix. Hidden layers are not auto-enabled for plot.

## Nested layer listing policy

**Decision (this task):** Continue listing every Inkscape layer outside `<defs>`, including nested sub-layers.

Rationale: Golden B7 and product workflow require plotting a nested layer in isolation with ancestor context. Restricting the list to SVG-root–level layers only would remove the “Child” row and break that workflow without changing golden expectations.

**Follow-up (not in scope):** Top-level-only listing with explicit “plot includes nested content” UX would avoid duplicate geometry when users plot both Parent and Child.

## Hidden layer behavior

- Detection on the layer group element: `display="none"`, `visibility="hidden"|"collapse"`, or the same in inline `style`.
- `SvgLayer.name` stays the Inkscape/root-group label; `SvgLayer.list_label` adds `(hidden)` for UI.
- No automatic plotting of hidden layers; empty geometry from hidden content remains safe.

## Invariants (isolated layer)

- Root `width`/`height`/`viewBox` unchanged
- Root `<defs>` and `<style>` preserved
- Ancestor transforms and presentation attributes preserved via shallow wrappers
- Unrelated siblings excluded
- Source document not mutated

## Validation

- Golden B6 and B7 pass (xfail removed)
- `./scripts/test_fast.sh`, non-hardware pytest, ruff
