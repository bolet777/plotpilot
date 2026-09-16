# Data Model: 001-svg-open

## SvgDocument

| Field | Type | Description |
|-------|------|-------------|
| `path` | `pathlib.Path` | Absolute path to the file on disk |
| `name` | `str` | File name component for display (e.g. `art.svg`) |
| `raw_text` | `str` | Full file contents as decoded text |
| `root` | `xml.etree.ElementTree.Element` | Parsed document root (validated SVG element) |

**Lifecycle**: Created only on successful load. Application holds at most one instance;
successful open replaces the previous instance. Failed open does not mutate the held instance.

## SvgLoadError (service layer)

Structured failure from `load_svg_from_path` with:

| Attribute | Purpose |
|-----------|---------|
| `user_message` | Short text suitable for a dialog |
| `kind` | `missing`, `unreadable`, `encoding`, `xml`, `not_svg` (for tests/logging) |

No separate persistence or ID field in this slice.
