<p align="center">
  <img src="assets/icons/icon.png" alt="PlotPilot icon: a pen plotter drawing a colored P" width="96">
</p>

<h1 align="center">PlotPilot</h1>

<p align="center">
  Open-source macOS app for plotting SVG drawings on an
  <a href="https://axidraw.com/">AxiDraw</a>.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e" alt="MIT license"></a>
  <a href="https://github.com/bolet777/plotpilot/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/bolet777/plotpilot/tests.yml?branch=main&label=tests" alt="Tests status"></a>
  <img src="https://img.shields.io/badge/platform-macOS-111111" alt="macOS">
  <img src="https://img.shields.io/badge/python-3.12-3776AB" alt="Python 3.12">
  <img src="https://img.shields.io/badge/UI-PySide6-41CD52" alt="PySide6">
  <img src="https://img.shields.io/badge/plotter-AxiDraw-f97316" alt="AxiDraw">
</p>

<p align="center">
  <img src="docs/PlotPilot.png" alt="PlotPilot on macOS: layers sidebar, page preview with millimetre rulers, plot settings, and a live plot of the Wedge layer at 81 percent" width="920">
</p>

<p align="center">
  <em>Place the drawing, watch the page, and plot layer by layer — with progress, pen changes, and a safe stop.</em>
</p>

PlotPilot is a desktop controller for pen plotters. It opens an SVG, lists its layers, shows each layer on the machine’s page, and sends that same geometry to the AxiDraw through [`axicli`](https://axidraw.com/doc/cli_api/). The preview is the prepared plot: position, scale, rotation, margins, and clipping are applied before anything is drawn on screen or on paper.

A downloadable Mac app is a disk image of `PlotPilot.app`, built on your machine with `./publish.sh`. It is signed and notarized. The recipient opens the image and drags PlotPilot to Applications. `axicli` is inside the app, so they do not install Python or the AxiDraw command-line tools.

## What you can do

<table>
<tr>
<td width="50%" valign="top">

### Layers that match the file

Inkscape layers, with root groups used when a file has no layer markup. Each row shows a colour, a name, and a path count. Select a layer to preview it. Check the layers that belong in a multi-pen job.

</td>
<td width="50%" valign="top">

### A page you can trust

Millimetre rulers, the physical work area, and a dashed printable outline. Drag the drawing to place it, or set X, Y, and scale in the Transform tab. Zoom and pan are view-only and do not move the plot.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Margins and orientation

Horizontal and vertical safe margins (0.1 mm) inset the printable area. Strokes that cross a margin are clipped. Keep the page as drawn, auto-rotate it to fit, or turn it 90° either way. The preview updates with the choice.

</td>
<td width="50%" valign="top">

### Plot settings that stick

Pen-down speed, pen-up speed, acceleration, servo heights, constant pen-down speed, machine model, and path order. Values are remembered between launches. A `.plotpilot` project file stores the setup for one drawing.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### One layer, or a pen-change sequence

**Plot Selected Layer** sends the current layer. **Plot Checked Layers** walks the checked layers and pauses so you can change pens, then **Continue**. **Estimate** reports duration before the motors move.

</td>
<td width="50%" valign="top">

### A machine you can stop

Live progress (percent, elapsed, remaining), pen up and pen down, home, and motors off. **Stop** cancels the plot, raises the pen, walks home, and disables the XY motors.

</td>
</tr>
</table>

Supported models: AxiDraw V2 / V3 / SE/A4, V3/A3 or SE/A3, V3 XLX, MiniKit, SE/A1, SE/A2, and V3/B6. The travel limits of the selected model define the page.

## A plotting session

1. Connect the plotter. A release zip already includes `axicli`. From a source checkout, install [AxiDraw software](https://axidraw.com/doc/) so `axicli` is on your `PATH`.
2. Launch PlotPilot and open an SVG (**File → Open SVG…**, **⌘O**).
3. Pick a layer. Fit the preview, then place, scale, and rotate the drawing inside the printable area.
4. Set margins and speeds. Run **Estimate** if you want a duration before plotting.
5. **Plot Selected Layer**, or check several layers and **Plot Checked Layers**. Swap pens when the app pauses, then press **Continue**.
6. Save a **project** (**⌘S**) to reopen the same SVG, checks, placement, margins, and plot settings.

The full walkthrough, shortcuts, and control reference are in the [user guide](docs/guide.md).

## Requirements

- macOS
- [Python 3.12](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/)
- [AxiDraw software](https://axidraw.com/doc/) (`axicli` on `PATH`) when you run from source and want to plot

The interface and plot preparation run without hardware. A connected AxiDraw is needed only when you plot. A disk image from `./publish.sh` already contains `axicli`.

## Run PlotPilot

```bash
git clone https://github.com/bolet777/plotpilot.git
cd plotpilot
uv sync --group dev
./open.sh
```

| Command | What it does |
|---|---|
| `./build.sh` | Rebuild `dist/PlotPilot.app` |
| `./open.sh` | Open that app. Builds it only when it is missing. `./open.sh --rebuild` forces a build |
| `./install.sh` | Copy the built app into `/Applications` |
| `./publish.sh` | Build, add `axicli`, notarize, make a disk image, and upload a GitHub Release |

`./open.sh` uses the PlotPilot name and icon in the Dock. For a faster edit loop, run from source. The Dock may show Python instead of PlotPilot:

```bash
uv run plotpilot
```

## Share a build

Commit the source first, then from the repository root:

```bash
./publish.sh
```

This builds `PlotPilot.app`, downloads the official AxiDraw command-line interface into the app, signs and notarizes the app, then signs and notarizes `dist/PlotPilot-<version>-macos-<arch>.dmg`. That disk image is what gets uploaded to a [GitHub Release](https://github.com/bolet777/plotpilot/releases) tagged `v<version>`. It stays out of git. The script pushes the current commit, then attaches the image. Inside it: PlotPilot and a shortcut to Applications.

Build on the same kind of Mac your recipients use. An Apple Silicon image does not launch on an Intel Mac.

The app stays MIT. `axicli` stays a separate program, with its own license files inside the bundle. It is not added to PlotPilot’s Python dependencies.

## Documentation

| | |
|---|---|
| [User guide](docs/guide.md) | Interface, plotting, projects, shortcuts |
| [Documentation index](docs/README.md) | All docs in this repository |
| [Architecture](docs/ARCHITECTURE.md) | Modules and data flow |
| [Feature specs](specs/README.md) | SpecKit slices behind each capability |

## Development

```bash
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```

Tests use a fake plotter and do not need a display, an AxiDraw, or `axicli`. The same non-hardware suite, plus ruff, runs on GitHub after every push. See [tests/README.md](tests/README.md) and [docs/testing.md](docs/testing.md).

Icons are regenerated from `assets/icons/icon.png` with `./scripts/regenerate_icons.sh`, then `./build.sh`.

## License

**MIT** — see [LICENSE](LICENSE).
