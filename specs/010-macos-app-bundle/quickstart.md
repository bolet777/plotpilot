# Quickstart: macOS PlotPilot.app

## Prerequisites

- macOS
- [uv](https://docs.astral.sh/uv/) and project synced (`uv sync --group dev`)

## Build and launch (recommended)

From the repository root:

```bash
./lance.sh
```

This runs PyInstaller and opens `dist/PlotPilot.app`. To relaunch without rebuilding:

```bash
./lance.sh --no-build
```

## Build only

```bash
./scripts/build_macos_app.sh
```

Output: `dist/PlotPilot.app` — then `open dist/PlotPilot.app`

Pin to the Dock from the running app (Options → Keep in Dock). The Dock tooltip should read **PlotPilot**.

## Development without rebuilding

For day-to-day coding, `uv run plotpilot` still works but may show **Python 3.12** in the Dock. Use the built `.app` when testing macOS branding.

## Icons

After changing `assets/icons/icon.png`:

```bash
./scripts/regenerate_icons.sh
./scripts/build_macos_app.sh
```
