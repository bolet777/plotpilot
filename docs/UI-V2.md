# PlotPilot UI V2

V2 is a presentation/layout refactor of the PySide6 interface. Services,
models, SVG parsing, geometry, plotting sequences, settings persistence and
transform/margin calculations are unchanged; `MainWindow` keeps every slot and
reconnects the existing widgets to a new shell.

## Layout

```text
┌ Top bar ───────────────────────────────────────────────────────────────────┐
│ PlotPilot · SVG to AxiDraw     Open  Preview  Layers  Plot     [device chip] Settings │
├ Layers ──────┬ Preview workspace ──────────────────────┬ Properties ────────┤
│ ☐ ■ Name     │ rulers · paper · margins · printable    │ Transform          │
│   299 paths  │ area · artwork · zoom/pan overlays      │ Plot Settings      │
│              │                                          │ Device             │
├ Action bar ────────────────────────────────────────────────────────────────┤
│ file · activity · plotter message · firmware · estimate                    │
│ [progress]  [pen-change banner + Continue]                                 │
│ Plotter | Pen Control | Motors | Actions                                   │
└────────────────────────────────────────────────────────────────────────────┘
```

The three columns live in a `QSplitter`; the layers column can be hidden
(**View → Layers Sidebar**, `Ctrl+Shift+L`, or the **Layers** nav button). The
properties column scrolls vertically (and horizontally only when the window is
narrower than its content). Bottom-bar groups wrap onto a second row on narrow
windows instead of clipping. Minimum window size is 760 × 520 (clamped to the
screen); the preferred launch size is 1240 × 800.

## Top bar navigation

The nav buttons are shortcuts into existing areas, not new features:

| Button | Action |
|--------|--------|
| Open | `File → Open SVG…` (`⌘O`) |
| Preview | Fit the preview to the window and show the Transform tab |
| Layers | Show/hide the layers sidebar (checkable) |
| Plot | Show the Plot Settings tab and focus **Plot Selected Layer** |
| Device chip | Show the Device tab (model name, connection state) |
| Settings | Show the Plot Settings tab |

## Functional regression checklist (V1 → V2)

Every user-facing capability of V1 and where it lives in V2.

### File / project

| V1 feature | V2 location | Status |
|------------|-------------|--------|
| Open SVG (`File → Open SVG…`, `⌘O`) | Same menu/shortcut; also top bar **Open**, Layers header **Open…**, empty-state **Open SVG…** | Kept |
| Open Project (`Ctrl+Shift+O`) | `File` menu, unchanged | Kept |
| Save Project / Save Project As | `File` menu, unchanged | Kept |
| Window title shows file / project name | Unchanged | Kept |
| Empty state ("No SVG loaded", open button, shortcut hint) | Preview workspace empty page | Kept |
| Persistent **Open SVG…** button above the layer list | Layers header **Open…** (visible once a document is loaded) | Relocated |

### Layers

| V1 feature | V2 location | Status |
|------------|-------------|--------|
| Layer list with colour swatch and name | Left sidebar; delegate draws check, swatch, name, path count, hidden flag | Kept |
| Select a layer to preview it | Same list; selection highlighted with accent bar | Kept |
| Checkboxes to include layers in multi-layer plot | Custom checkbox in each row (same `Qt.CheckStateRole`) | Kept |
| Hidden layers marked | "· hidden" on the secondary line and tooltip | Kept |
| Fallback work-area combos (size / orientation) when the SVG has no page size | Transform tab → Margins card, "Work area" row | Relocated |
| Layer count | Header badge next to "Layers" | New (display only) |

### Preview

| V1 feature | V2 location | Status |
|------------|-------------|--------|
| Prepared layer preview in machine space | Centre workspace | Kept |
| Paper / work area, user margins, printable area outline | Paper surface, margin zone, dashed accent printable outline with corner marks | Kept |
| Faint source-SVG context | Kept (clipped to work area) | Kept |
| Drag artwork with the mouse to move it (mm) | Left-drag, unchanged semantics | Kept |
| Work-area label and plot warnings under the paper | Info chip at the top-left of the canvas | Relocated |
| Bounds / fit status text | Transform tab → Margins card (`Document … / fits` lines) | Relocated |
| mm rulers, zoom in/out/fit, pan (hand tool, middle-drag, `⌘`+wheel), cursor mm readout | Overlays on the canvas + `View` menu (`Ctrl+0`, `⌘+`, `⌘-`) | New, view-only |

### Transform

| V1 feature | V2 location | Status |
|------------|-------------|--------|
| Position X / Y sliders + mm spin boxes + Reset X / Reset Y | Transform tab → Position card (slider ranges still follow scale and printable area) | Kept |
| Scale slider + % spin box + 50/100/150/200 presets | Transform tab → Scale card | Kept |
| Double-click slider to reset | Kept | Kept |
| Margins H / V spin boxes (0.1 mm) | Transform tab → Margins card; mirrored sliders added; optional link toggle | Kept (+ convenience) |
| Plot area and printable area dimensions | Margins card info block + small diagram | Kept |
| "Orientation: preserved (no auto-rotate)" label (was in Plot Settings) | Transform tab → Orientation card: Preserved / Auto-rotate to fit / Rotate 90° CCW / Rotate 90° CW. The rotation is applied by PlotPilot (`ArtworkTransform.orientation`) before clipping, so preview = plot; axicli still always receives `-N`. Auto rotates 90° CCW only when the page and the printable area disagree on portrait/landscape. Saved in the project file (`artwork_transform.orientation`). | Implemented |
| Reset All (transform) | Transform tab bottom | Kept |

### Plot settings

| V1 feature | V2 location | Status |
|------------|-------------|--------|
| Pen-down speed, pen-up speed, acceleration sliders with value labels | Plot Settings tab → Speed card | Kept |
| Pen-up / pen-down position sliders | Plot Settings tab → Pen height card | Kept |
| Model combo, path-order combo | Plot Settings tab → Machine card | Kept |
| Constant pen-down speed checkbox | Speed card | Kept |
| Reset to defaults | Plot Settings tab bottom | Kept |
| Controls disabled while plotting | Unchanged (`set_plotting_active`) | Kept |
| Settings persistence (`QSettings`) | Unchanged | Kept |

### Plotter / device

| V1 feature | V2 location | Status |
|------------|-------------|--------|
| Plotter name + connection status | Top bar device chip, action bar Plotter group, Device tab | Kept (shown in 3 places) |
| Connect / Refresh | Action bar **Connect/Reconnect**, Actions **Refresh**, Device tab **Refresh** | Kept |
| Pen ↑ / Pen ↓ | Action bar Pen Control (**Pen Up / Pen Down**) + Device tab | Kept |
| Home, Motors Off | Action bar Motors group + Device tab | Kept |
| Plotter message / firmware line | Action bar status strip + Device tab | Kept |
| Button enablement rules (disconnected, plotting, stopping) | Unchanged in `_update_plot_controls`; Device tab mirrors the bar | Kept |

### Plotting

| V1 feature | V2 location | Status |
|------------|-------------|--------|
| Plot Selected Layer, Plot Checked Layers, Stop, Estimate | Action bar Actions group | Kept |
| Estimate result text | Action bar status strip | Kept |
| Progress headline, bar, timing, next-layer line | Action bar progress row (visible while plotting) | Kept |
| Pen-change prompt + Continue | Action bar banner (visible while waiting) | Kept |
| Activity / state messages | Action bar status strip | Kept |

### Window

| V1 feature | V2 location | Status |
|------------|-------------|--------|
| Resizable window, minimum size clamped to screen | Kept; new minimum 760 × 520, preferred 1240 × 800 | Kept |
| Whole content scrolls when the window is small | Properties panel scrolls; action bar wraps; layers list scrolls | Changed mechanism |

## Theme

`src/plotpilot/ui/theme.py` holds the palette (`COLORS`) and the stylesheet
(`build_stylesheet()`); `apply_theme(app)` sets the Fusion style, a dark
palette and the stylesheet. Widgets opt in through `objectName` (`#topBar`,
`#layersPanel`, `#propertiesPanel`, `#actionBar`, `#previewWorkspace`) and the
dynamic `role` property (`accent`, `danger`, `quiet`, `nav`, `preset`, `tool`
for buttons; `card`, `banner`, `info`, `separator` for frames; `heading`,
`caption`, `muted`, `value`, `status-*` for labels).

## Manual smoke checklist

- Launch; window opens at ≤ 1240 × 800 and never larger than the screen.
- Open an SVG; layers appear with counts and swatches; preview fits.
- Select layers; preview updates; checkboxes toggle for multi-layer jobs.
- Scale slider/presets, X/Y sliders, margins; preview and labels update.
- Reset X / Reset Y / Reset All / Reset to defaults.
- Change plot settings; values persist across restart.
- Disconnected: pen/home/motors/plot buttons disabled, Connect enabled.
- Connected (fake or real): buttons enabled; Plot Selected Layer / Checked / Stop states follow plotting.
- Resize to 760 × 520: properties panel scrolls, bottom bar wraps, nothing clipped.
- Hide/show the layers sidebar; preview takes the space.
- Zoom/pan the preview; `Fit` restores; artwork X/Y/scale unchanged.
