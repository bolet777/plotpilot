# Quickstart: macOS PlotPilot.app

## Prerequisites

- macOS
- [uv](https://docs.astral.sh/uv/) and project synced (`uv sync --group dev`)

## Commands

From the repository root:

| Command | What it does |
|---|---|
| `./build.sh` | Rebuild `dist/PlotPilot.app` |
| `./open.sh` | Open that app. Builds it only when it is missing |
| `./open.sh --rebuild` | Rebuild, then open |
| `./install.sh` | Copy the built app into `/Applications` |
| `./publish.sh` | Build, add `axicli`, notarize, make a disk image, and upload a GitHub Release |

Pin to the Dock from the running app (Options → Keep in Dock). The Dock tooltip should read **PlotPilot**.

## Development without rebuilding

For day-to-day coding, `uv run plotpilot` still works but may show **Python 3.12** in the Dock. Use `./open.sh` when testing macOS branding.

## Icons

After changing `assets/icons/icon.png`:

```bash
./scripts/regenerate_icons.sh
./build.sh
```
